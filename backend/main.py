"""Campus Customs backend API (FastAPI).

Run from the backend/ directory:
    uvicorn main:app --reload --port 8000
or from the project root:
    uvicorn backend.main:app --reload --port 8000

All shop data goes through the campus-customs MCP server (data/campus_customs_new.db).
The only non-MCP data this file reads is the agent audit trail (output/audit_trail.json).
Interactive docs: http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# `uvicorn main:app` from backend/ imports this file as a top-level module, so make
# the project root importable and use absolute `backend.` imports.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend import audit  # noqa: E402
from backend.config import MODEL_NAME  # noqa: E402
from backend.models import (  # noqa: E402
    AgentEvent, ApprovalDecisionRequest, ApprovalResult, CashResponse, ErrorResponse, EventsResponse,
    RejectionRequest, ResetRequest, ResetResponse, RunTicketResponse, TicketDetail, TicketListResponse,
    TicketSummary,
)
from backend.orchestrator import new_run_id, run_ticket  # noqa: E402
from backend.runtime import AgentRuntime  # noqa: E402

runtime = AgentRuntime()
run_lock = asyncio.Lock()        # one agent workflow at a time: tickets share one cash account
approval_lock = asyncio.Lock()   # approvals are decided one at a time
active_run: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(
    title="Campus Customs Operations API",
    description="Tickets, agent runs, agent activity, human payment approval, cash and reset for the Campus Customs dashboard.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    # Any local dev-server port (Vite moves off 5173 when it is busy); never a remote origin.
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


# ------------------------------------------------------------------ helpers

def _tool_message(error: Exception) -> str:
    message = getattr(error, "message", None) or str(error)
    return re.sub(r"^Error executing tool \w+: ", "", message)


async def mcp(tool: str, args: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool and turn its failures into HTTP errors."""
    try:
        return await runtime.mcp(tool, args)
    except Exception as error:
        tool_failure = type(error).__name__ in {"ToolFailed", "ToolError", "ModelRetry"} or "Error executing tool" in str(error)
        if not tool_failure:
            raise HTTPException(503, f"MCP server unavailable: {type(error).__name__}: {error}") from error
        message = _tool_message(error)
        lower = message.lower()
        if "not found" in lower:
            raise HTTPException(404, message) from error
        if "must" in lower or "unknown" in lower or "no inventory" in lower:
            raise HTTPException(422, message) from error
        raise HTTPException(409, message) from error


def _summary(ticket: dict) -> dict:
    return {**ticket, "state": "resolved" if ticket["status"] == "resolved" else "open"}


async def _ticket_detail(ticket_id: int) -> TicketDetail:
    ticket = await mcp("get_ticket", {"ticket_id": ticket_id})
    drafts = (await mcp("list_message_drafts", {"ticket_id": ticket_id}))["drafts"]
    pending = sum(1 for a in ticket["approval_requests"] if a["status"] == "pending")
    return TicketDetail(**{**_summary(ticket), "message_drafts": drafts, "pending_approvals": pending, "drafts": len(drafts)})


def _event_message(r: dict) -> str:
    out, inp, action = r.get("outputs"), r.get("inputs"), r["action"]
    target = r.get("delegation_target")
    if action == "delegation":
        task = inp.get("task") if isinstance(inp, dict) else ""
        if r["status"] == "started":
            return f"Asked {target}: {task}"
        if r["status"] in {"completed", "cached"} and isinstance(out, dict):
            prefix = "(cached) " if r["status"] == "cached" else ""
            return f"{prefix}{target} replied: {out.get('summary', '')}"
        return f"Delegation to {target} {r['status']}: {r.get('error') or ''}".strip()
    if action == "mcp_tool_call":
        return f"Called {r['tool']}" + (f" - {r['error']}" if r.get("error") else "")
    if action == "ticket_decision" and isinstance(out, dict):
        return f"Decision ({out.get('final_status')}): {out.get('decision')}"
    if action == "triage_decision" and isinstance(out, dict):
        order = ", ".join(f"{p['ticket_id']} ({p['priority']})" for p in out.get("order", []))
        return f"Triage: {order}. {out.get('cash_note', '')}"
    if action.startswith("approval_") and isinstance(inp, dict):
        rid = inp.get("approval_request_id")
        verb = action.removeprefix("approval_")
        if r["status"] == "ok":
            return f"{r['agent']} {verb}d request #{rid}"
        return f"{r['agent']} tried to {verb} request #{rid}: {r['status']} - {r.get('error') or ''}".strip()
    if action == "ticket_started":
        return f"Started ticket {r.get('ticket_id')}"
    return action.replace("_", " ").capitalize() + (f" - {r['error']}" if r.get("error") else "")


# ------------------------------------------------------------------- routes

@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "Campus Customs Operations API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health", tags=["system"])
async def health() -> dict:
    """Confirms the MCP server answers and reports the business date and model."""
    date = await mcp("get_business_date")
    return {"status": "ok", "mcp": "connected", "business_date": date["business_date"], "model": MODEL_NAME,
            "agent_run_in_progress": active_run.get("ticket_id")}


# A. Tickets ---------------------------------------------------------------

@app.get("/api/tickets", response_model=TicketListResponse, tags=["tickets"], responses=ERRORS)
async def list_tickets() -> TicketListResponse:
    """All tickets (101-103) with status, open/resolved state, pending approvals and draft counts."""
    data = await mcp("list_tickets")
    return TicketListResponse(business_date=data["business_date"], tickets=[TicketSummary(**_summary(t)) for t in data["tickets"]])


@app.get("/api/tickets/{ticket_id}", response_model=TicketDetail, tags=["tickets"], responses=ERRORS)
async def get_ticket(ticket_id: int) -> TicketDetail:
    """One ticket with its approval requests, purchase orders and full draft text."""
    return await _ticket_detail(ticket_id)


# B. Run agents on a ticket ------------------------------------------------

@app.post("/api/tickets/{ticket_id}/run", response_model=RunTicketResponse, tags=["agents"],
          responses={**ERRORS, 502: {"model": ErrorResponse}})
async def run_agents(ticket_id: int) -> RunTicketResponse:
    """Start the multi-agent workflow for one ticket. The Boss coordinates and delegates; the call
    returns when the Boss has decided (typically 30-90 s). Never resets the database."""
    ticket = await mcp("get_ticket", {"ticket_id": ticket_id})
    if ticket["status"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved. Reset the simulation to run it again.")
    if run_lock.locked():
        raise HTTPException(409, f"Agents are already working on ticket {active_run.get('ticket_id')}. Try again when it finishes.")
    async with run_lock:
        run_id = new_run_id()
        active_run.update(ticket_id=ticket_id, run_id=run_id)
        try:
            outcome = await runtime.call(lambda team: run_ticket(team, ticket_id, run_id))
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(502, f"Agent run {run_id} failed: {type(error).__name__}: {error}. "
                                     "See /api/events for the steps that completed.") from error
        finally:
            active_run.clear()
    detail = await _ticket_detail(ticket_id)
    pending = (await mcp("list_approval_requests", {"status": "pending", "ticket_id": ticket_id}))["approval_requests"]
    return RunTicketResponse(run_id=run_id, ticket_id=ticket_id, decision=outcome["decision"], usage=outcome["usage"],
                             delegations=outcome["delegations"], ticket=detail, pending_approvals=pending)


# C. Agent activity --------------------------------------------------------

@app.get("/api/events", response_model=EventsResponse, tags=["agents"])
async def events(
    after_id: int = Query(0, ge=0, description="Only events with id greater than this (for polling)"),
    limit: int = Query(100, ge=1, le=1000),
    ticket_id: int | None = None,
    run_id: str | None = None,
    agent: str | None = None,
    include_payloads: bool = Query(False, description="Include raw tool/delegation inputs and outputs"),
    since_reset: bool = Query(False, description="Only events after the most recent database reset"),
) -> EventsResponse:
    """Agent events from the append-only audit trail: who acted, what they said or decided, MCP tools
    used, delegations and status. Oldest first. Without after_id: the latest `limit` events. With
    after_id: up to `limit` events after it; poll again with the last returned id."""
    records = audit.read_all()
    floor = after_id
    if since_reset:
        last_reset = max((i for i, r in enumerate(records, start=1) if r.get("action") == "reset_working_database"), default=0)
        floor = max(floor, last_reset)
    selected = []
    for index, r in enumerate(records, start=1):
        if index <= floor:
            continue
        if ticket_id is not None and r.get("ticket_id") != ticket_id:
            continue
        if run_id and r.get("run_id") != run_id:
            continue
        if agent and r.get("agent") != agent:
            continue
        selected.append(AgentEvent(
            id=index, timestamp=r["timestamp"], run_id=r.get("run_id"), ticket_id=r.get("ticket_id"), agent=r["agent"],
            action=r["action"], tool=r.get("tool"), delegation_target=r.get("delegation_target"), status=r.get("status", "ok"),
            message=_event_message(r), error=r.get("error"), usage=r.get("usage"),
            inputs=r.get("inputs") if include_payloads else None, outputs=r.get("outputs") if include_payloads else None,
        ))
    # Polling (after_id set) pages forward from after_id so nothing is skipped;
    # otherwise return the most recent `limit` events.
    page = selected[:limit] if after_id else selected[-limit:]  # since_reset alone still returns the latest
    return EventsResponse(events=page, latest_id=len(records), total=len(records))


@app.get("/api/drafts", tags=["agents"], responses=ERRORS)
async def drafts(ticket_id: int | None = None) -> dict:
    """Saved message drafts with full text, for human review. Drafts are never sent."""
    return await mcp("list_message_drafts", {"ticket_id": ticket_id} if ticket_id is not None else {})


# D. Approvals -------------------------------------------------------------

@app.get("/api/approvals", tags=["approvals"], responses=ERRORS)
async def approvals(status: str | None = Query(None, pattern="^(pending|executed|rejected)$"), ticket_id: int | None = None) -> dict:
    """Payment, purchase-order and discount requests prepared by the agents."""
    args: dict[str, Any] = {}
    if status:
        args["status"] = status
    if ticket_id is not None:
        args["ticket_id"] = ticket_id
    return await mcp("list_approval_requests", args)


async def _pending_request(request_id: int) -> dict:
    requests = (await mcp("list_approval_requests"))["approval_requests"]
    request = next((r for r in requests if r["id"] == request_id), None)
    if not request:
        raise HTTPException(404, f"Approval request {request_id} not found")
    if request["status"] != "pending":
        raise HTTPException(409, f"Approval request {request_id} is already {request['status']}; it cannot be decided again")
    return request


@app.post("/api/approvals/{request_id}/approve", response_model=ApprovalResult, tags=["approvals"], responses=ERRORS)
async def approve(request_id: int, body: ApprovalDecisionRequest) -> ApprovalResult:
    """A human approves a pending request; this is the only way money moves. The MCP tool re-checks
    that the request is pending (no duplicates), that the vendor has no unpaid invoices (for POs), and
    that the balance stays at or above zero, then updates cash, payments, invoices, leases and POs."""
    async with approval_lock:
        request = await _pending_request(request_id)
        if request["kind"] != "discount":
            cash = await mcp("get_cash_position", {"account": request["account"]})
            audit_cash = {"balance_before": cash["balance"], "amount": request["amount"]}
        else:
            audit_cash = {}
        log = dict(run_id="human", agent=f"human:{body.approved_by}", ticket_id=request["ticket_id"],
                   action="approval_approve", tool="execute_approved_payment",
                   inputs={"approval_request_id": request_id, "approved_by": body.approved_by, **audit_cash})
        try:
            result = await mcp("execute_approved_payment", {"approval_request_id": request_id, "approved_by": body.approved_by})
        except HTTPException as error:
            audit.record(**log, status="refused", error=str(error.detail))
            raise
        if result.get("status") == "rejected":
            audit.record(**log, outputs=result, status="rejected", error=result.get("error"))
            raise HTTPException(409, f"Request {request_id} rejected: {result.get('error')}. No money moved.")
        audit.record(**log, outputs=result)
    return ApprovalResult(
        approval_request_id=request_id, status="executed", kind=request["kind"], amount=request["amount"],
        payment_id=result.get("payment_id"), new_balance=result.get("new_balance"),
        message=(f"Paid {request['amount']:.2f}; checking balance is now {result['new_balance']:.2f}"
                 if result.get("payment_id") else f"{request['kind'].capitalize()} approved; no cash moved"),
    )


@app.post("/api/approvals/{request_id}/reject", response_model=ApprovalResult, tags=["approvals"], responses=ERRORS)
async def reject(request_id: int, body: RejectionRequest) -> ApprovalResult:
    """A human rejects a pending request. A rejected purchase order is cancelled. No money moves."""
    async with approval_lock:
        request = await _pending_request(request_id)
        log = dict(run_id="human", agent=f"human:{body.decided_by}", ticket_id=request["ticket_id"], action="approval_reject",
                   tool="reject_approval_request", inputs={"approval_request_id": request_id, "note": body.note})
        try:
            result = await mcp("reject_approval_request",
                               {"approval_request_id": request_id, "decided_by": body.decided_by, "note": body.note})
        except HTTPException as error:
            audit.record(**log, status="refused", error=str(error.detail))
            raise
        audit.record(**log, outputs=result)
    return ApprovalResult(approval_request_id=request_id, status="rejected", kind=request["kind"], amount=request["amount"],
                          message=f"Request {request_id} rejected by {body.decided_by}")


# E. Cash ------------------------------------------------------------------

@app.get("/api/cash", response_model=CashResponse, tags=["cash"], responses=ERRORS)
async def cash(account: str = "checking") -> CashResponse:
    """Current balance from cash_accounts (reflects executed payments), plus money committed to
    pending requests and upcoming obligations."""
    data = await mcp("get_cash_position", {"account": account})
    return CashResponse(**data)


# F. Reset -----------------------------------------------------------------

@app.post("/api/reset", response_model=ResetResponse, tags=["system"], responses={**ERRORS, 400: {"model": ErrorResponse}})
async def reset(body: ResetRequest) -> ResetResponse:
    """Restore data/campus_customs_new.db from data/campus_customs.db. Requires {"confirm": true};
    refused while agents are running. The original database is only read."""
    if not body.confirm:
        raise HTTPException(400, 'Reset needs {"confirm": true}')
    if run_lock.locked():
        raise HTTPException(409, "Agents are running; reset after they finish")
    async with approval_lock:
        result = await mcp("reset_working_database")
    audit.record(run_id="human", agent="human", action="reset_working_database", tool="reset_working_database", outputs=result)
    return ResetResponse(**result, message="Working database restored to the original starting values.")

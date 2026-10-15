"""Run the Campus Customs ticket workflow.

    python -m backend.orchestrator --reset            # clean start: reset DB, triage, resolve all open tickets
    python -m backend.orchestrator --tickets 102      # one ticket on the current working DB
    python -m backend.orchestrator                    # all open tickets on the current working DB

Reset only happens when asked for (--reset here, POST /api/reset in the API).
Flow: Boss triages open tickets -> Boss handles each ticket in priority order,
delegating to specialists -> structured TicketDecision per ticket.
Payments are only queued; a human executes them (backend/approvals.py or the API).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import uuid4

from pydantic_ai.exceptions import UsageLimitExceeded

from . import audit
from .agents import AgentTeam
from .config import MODEL_NAME, TICKET_USAGE_LIMITS, TRIAGE_USAGE_LIMITS
from .models import AgentDeps, TicketDecision, TicketPriority, TicketState, TriagePlan


def new_run_id() -> str:
    return uuid4().hex[:12]


def ticket_brief(ticket: dict) -> str:
    """One line of ticket facts every agent on the ticket receives, so none has to re-fetch it."""
    if isinstance(ticket, str):
        ticket = json.loads(ticket)
    parts = [f"Ticket {ticket['id']} ({ticket['type']}) from requester \"{ticket['requester']}\": {ticket['subject']}."]
    if ticket.get("sku"):
        name = f"{ticket['product_name']} " if ticket.get("product_name") else ""
        parts.append(f"Item: {name}({ticket['sku']}) size {ticket['size']}, qty {ticket['qty']}.")
    if ticket.get("lease_id"):
        parts.append(f"Lease ID {ticket['lease_id']}.")
    if ticket.get("invoice_id"):
        parts.append(f"Linked invoice ID {ticket['invoice_id']}.")
    parts.append(f"Notes: {ticket.get('notes') or 'none'}")
    return " ".join(parts)


def usage_dict(result) -> dict:
    u = result.usage
    return {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}


async def triage(team: AgentTeam, run_id: str) -> TriagePlan:
    deps = AgentDeps(run_id, None, "boss", ("boss",), TicketState())
    result = await team.agents["boss"].run(
        "Triage mode: order all open tickets by priority and note the cash constraint. Do not delegate.",
        deps=deps, output_type=TriagePlan, usage_limits=TRIAGE_USAGE_LIMITS,
    )
    audit.record(run_id=run_id, agent="boss", action="triage_decision", outputs=result.output.model_dump(), inputs=usage_dict(result))
    return result.output


async def run_ticket(team: AgentTeam, ticket_id: int, run_id: str,
                     priority: TicketPriority | None = None, cash_note: str | None = None) -> dict:
    """Boss handles one ticket end to end. Raises on failure (after auditing it)."""
    ticket = await team.mcp.direct_call_tool("get_ticket", {"ticket_id": ticket_id})
    brief = ticket_brief(ticket)
    deps = AgentDeps(run_id, ticket_id, "boss", ("boss",), TicketState(brief=brief))
    prompt = f"Ticket mode: handle this ticket.\n{brief}"
    if priority:
        prompt += (f"\nYour triage said: priority {priority.priority}; {priority.reason} "
                   f"Suggested specialists: {', '.join(priority.lead_agents)}.")
    if cash_note:
        prompt += f"\nCash note: {cash_note}"
    audit.record(run_id=run_id, agent="boss", ticket_id=ticket_id, action="ticket_started", inputs=prompt)
    try:
        result = await team.agents["boss"].run(prompt, deps=deps, output_type=TicketDecision, usage_limits=TICKET_USAGE_LIMITS)
    except UsageLimitExceeded as error:
        audit.record(run_id=run_id, agent="boss", ticket_id=ticket_id, action="ticket_decision", status="usage_limit", error=str(error))
        raise
    except Exception as error:
        audit.record(run_id=run_id, agent="boss", ticket_id=ticket_id, action="ticket_decision",
                     status="error", error=f"{type(error).__name__}: {error}")
        raise
    decision: TicketDecision = result.output
    audit.record(run_id=run_id, agent="boss", ticket_id=ticket_id, action="ticket_decision",
                 outputs=decision.model_dump(), inputs=usage_dict(result))
    return {"decision": decision, "usage": usage_dict(result), "delegations": deps.state.delegations}


async def run_workflow(team: AgentTeam, ticket_ids: list[int] | None = None, reset: bool = False) -> dict:
    run_id = new_run_id()
    audit.record(run_id=run_id, agent="orchestrator", action="run_started",
                 inputs={"tickets": ticket_ids or "all open", "reset": reset, "model": MODEL_NAME})
    summary: dict = {"run_id": run_id, "triage": None, "decisions": [], "errors": []}

    if reset:
        result = await team.mcp.direct_call_tool("reset_working_database", {})
        audit.record(run_id=run_id, agent="orchestrator", action="reset_working_database", tool="reset_working_database", outputs=result)

    plan = await triage(team, run_id)
    summary["triage"] = plan.model_dump()
    order = [p for p in plan.order if ticket_ids is None or p.ticket_id in ticket_ids]
    missed = [t for t in (ticket_ids or []) if t not in {p.ticket_id for p in order}]
    if missed:
        summary["errors"].append(f"Not in triage (not open?): {missed}")

    for item in order:
        try:
            outcome = await run_ticket(team, item.ticket_id, run_id, item, plan.cash_note)
        except Exception as error:
            summary["errors"].append(f"Ticket {item.ticket_id}: {type(error).__name__}: {error}")
            continue
        summary["decisions"].append({**outcome["decision"].model_dump(), "usage": outcome["usage"],
                                     "delegations": outcome["delegations"]})

    approvals = await team.mcp.direct_call_tool("list_approval_requests", {"status": "pending"})
    summary["pending_approvals"] = approvals.get("approval_requests", approvals) if isinstance(approvals, dict) else approvals
    audit.record(run_id=run_id, agent="orchestrator", action="run_finished",
                 outputs={"decisions": len(summary["decisions"]), "errors": summary["errors"]},
                 status="ok" if not summary["errors"] else "partial")
    return summary


async def _main(ticket_ids: list[int] | None, reset: bool) -> dict:
    async with AgentTeam() as team:
        return await run_workflow(team, ticket_ids, reset)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickets", type=int, nargs="*", help="ticket IDs (default: all open)")
    parser.add_argument("--reset", action="store_true", help="restore the working database from the original first")
    args = parser.parse_args()
    summary = asyncio.run(_main(args.tickets or None, args.reset))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()

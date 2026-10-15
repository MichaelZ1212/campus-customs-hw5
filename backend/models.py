"""Structured data shared by the agents and the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")


class AgentReport(BaseModel):
    """What every specialist returns to whoever asked it for help."""

    agent: AgentName
    ticket_id: int | None
    status: Literal["completed", "needs_human_approval", "blocked", "failed"]
    summary: str = Field(description="Two or three sentences with the answer, using exact figures from tools.")
    findings: list[str] = Field(default_factory=list, description="Key facts from MCP tools, each with its number or date.")
    approval_request_ids: list[int] = Field(default_factory=list, description="Approval requests this agent created.")
    purchase_order_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list, description="Message drafts this agent saved.")
    recommendation: str | None = Field(default=None, description="What the requester or Boss should do next.")


class TicketPriority(BaseModel):
    ticket_id: int
    priority: Literal["high", "medium", "low"]
    reason: str
    lead_agents: list[AgentName] = Field(description="Specialists the Boss expects to involve.")


class TriagePlan(BaseModel):
    """Boss's ordering of all open tickets before any work starts."""

    business_date: str
    order: list[TicketPriority] = Field(description="Open tickets, highest priority first.")
    cash_note: str = Field(description="One sentence on how cash constrains the tickets.")


class TicketDecision(BaseModel):
    """Boss's final decision for one ticket."""

    ticket_id: int
    final_status: Literal["awaiting_approval", "resolved", "blocked"]
    decision: str = Field(description="The decision and why, in two to four sentences.")
    approval_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    agents_consulted: list[AgentName] = Field(default_factory=list)
    next_steps_for_human: list[str] = Field(default_factory=list)


@dataclass
class TicketState:
    """Shared by every agent run for one ticket: delegation bookkeeping and a result cache."""

    delegations: int = 0
    cache: dict[tuple[str, str], AgentReport] = field(default_factory=dict)
    brief: str = ""  # one-line ticket summary (from the get_ticket MCP tool) passed with every delegation


@dataclass
class AgentDeps:
    """Per-agent-run context. `chain` is who asked whom, e.g. ('boss', 'accounting')."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    chain: tuple[AgentName, ...]
    state: TicketState


# --------------------------------------------------------------- API models
# Request and response shapes for backend/main.py (the React dashboard's API).

class TicketSummary(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str = Field(description="open | in_progress | awaiting_approval | resolved | blocked")
    state: Literal["open", "resolved"] = Field(description="'resolved' only when status is resolved; everything else is still open")
    pending_approvals: int = 0
    drafts: int = 0
    notes: str | None = None


class TicketListResponse(BaseModel):
    business_date: str
    tickets: list[TicketSummary]


class TicketDetail(TicketSummary):
    product_name: str | None = Field(default=None, description="Catalogue name of the ticket's SKU, if any")
    approval_requests: list[dict] = Field(default_factory=list)
    purchase_orders: list[dict] = Field(default_factory=list)
    message_drafts: list[dict] = Field(default_factory=list)


class RunTicketResponse(BaseModel):
    run_id: str
    ticket_id: int
    decision: TicketDecision
    usage: dict
    delegations: int
    ticket: TicketDetail
    pending_approvals: list[dict]


class AgentEvent(BaseModel):
    id: int = Field(description="1-based position in the audit trail; use as after_id when polling")
    timestamp: str
    run_id: str | None
    ticket_id: int | None
    agent: str
    action: str
    tool: str | None
    delegation_target: str | None
    status: str
    message: str = Field(description="Human-readable summary of what the agent did, said or decided")
    error: str | None = None
    usage: dict | None = Field(default=None, description="Tokens/requests used by a delegated agent (incl. its own delegations)")
    inputs: object | None = None
    outputs: object | None = None


class EventsResponse(BaseModel):
    events: list[AgentEvent]
    latest_id: int
    total: int


class ApprovalDecisionRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=80, description="Name of the human approving")


class RejectionRequest(BaseModel):
    decided_by: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=500)


class ApprovalResult(BaseModel):
    approval_request_id: int
    status: Literal["executed", "rejected"]
    kind: str | None = None
    amount: float | None = None
    payment_id: int | None = None
    new_balance: float | None = None
    message: str


class CashResponse(BaseModel):
    account: str
    balance: float
    business_date: str
    committed_to_pending: float
    available_after_pending: float
    pending_requests: list[dict]
    unpaid_invoices: list[dict]
    rent_due_within_30_days: list[dict]


class ResetRequest(BaseModel):
    confirm: bool = Field(description="Must be true. Reset never happens implicitly.")


class ResetResponse(BaseModel):
    reset: bool
    business_date: str
    checking_balance: float
    open_tickets: int
    message: str


class ErrorResponse(BaseModel):
    detail: str

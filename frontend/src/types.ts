// Shapes returned by the FastAPI backend (backend/main.py, backend/models.py).

export type TicketStatus = 'open' | 'in_progress' | 'awaiting_approval' | 'resolved' | 'blocked'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  state: 'open' | 'resolved'
  pending_approvals: number
  drafts: number
  notes: string | null
}

export interface TicketListResponse {
  business_date: string
  tickets: Ticket[]
}

export interface MessageDraft {
  id: number
  ticket_id: number
  audience: string
  recipient: string
  subject: string
  body: string
  author: string
  status: string
  created_at: string
}

export interface TicketDetail extends Ticket {
  approval_requests: ApprovalRequest[]
  purchase_orders: Record<string, unknown>[]
  message_drafts: MessageDraft[]
}

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface TicketDecision {
  ticket_id: number
  final_status: 'awaiting_approval' | 'resolved' | 'blocked'
  decision: string
  approval_request_ids: number[]
  draft_ids: number[]
  agents_consulted: AgentName[]
  next_steps_for_human: string[]
}

export interface AgentReport {
  agent: AgentName
  ticket_id: number | null
  status: 'completed' | 'needs_human_approval' | 'blocked' | 'failed'
  summary: string
  findings: string[]
  approval_request_ids: number[]
  purchase_order_ids: number[]
  draft_ids: number[]
  recommendation: string | null
}

export interface RunTicketResponse {
  run_id: string
  ticket_id: number
  decision: TicketDecision
  usage: { requests: number; tool_calls: number; input_tokens: number; output_tokens: number }
  delegations: number
  ticket: TicketDetail
  pending_approvals: ApprovalRequest[]
}

export interface AgentEvent {
  id: number
  timestamp: string
  run_id: string | null
  ticket_id: number | null
  agent: string
  action: string
  tool: string | null
  delegation_target: string | null
  status: string
  message: string
  error: string | null
  usage?: Usage | null
  inputs?: unknown
  outputs?: unknown
}

export interface Usage { requests: number; tool_calls: number; input_tokens: number; output_tokens: number }

export interface EventsResponse {
  events: AgentEvent[]
  latest_id: number
  total: number
}

export interface ApprovalRequest {
  id: number
  ticket_id: number | null
  kind: 'invoice' | 'rent' | 'purchase_order' | 'discount'
  ref_id: number
  amount: number
  account: string
  reason: string
  requested_by: string
  status: 'pending' | 'executed' | 'rejected'
  decided_by: string | null
  decision_note: string | null
  payment_id: number | null
  created_at: string
  decided_at: string | null
  payee: string | null
  description: string
}

export interface ApprovalResult {
  approval_request_id: number
  status: 'executed' | 'rejected'
  kind: string | null
  amount: number | null
  payment_id: number | null
  new_balance: number | null
  message: string
}

export interface CashResponse {
  account: string
  balance: number
  business_date: string
  committed_to_pending: number
  available_after_pending: number
  pending_requests: { id: number; ticket_id: number; kind: string; ref_id: number; amount: number }[]
  unpaid_invoices: { id: number; vendor: string; amount: number; due_date: string; days_overdue: number }[]
  rent_due_within_30_days: { lease_id: number; landlord: string; amount: number; due: string; days_until_due: number }[]
}

export interface Health {
  status: string
  mcp: string
  business_date: string
  model: string
  agent_run_in_progress: number | null
}

// Thin typed client for the FastAPI backend. No business logic lives here:
// every number shown in the dashboard comes from these responses.
import type {
  ApprovalRequest, ApprovalResult, CashResponse, EventsResponse, Health, RunTicketResponse,
  TicketDetail, TicketListResponse,
} from './types'

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function detailText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg) : String(d))).join('; ')
  return JSON.stringify(detail)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ? detailText(body.detail) : `${response.status} ${response.statusText}`)
  }
  return body as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  tickets: () => request<TicketListResponse>('/api/tickets'),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  runTicket: (id: number) => request<RunTicketResponse>(`/api/tickets/${id}/run`, { method: 'POST' }),
  events: (params: { after_id?: number; limit?: number; ticket_id?: number; run_id?: string; include_payloads?: boolean; since_reset?: boolean }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)))
    return request<EventsResponse>(`/api/events?${q}`)
  },
  approvals: () => request<{ approval_requests: ApprovalRequest[] }>('/api/approvals'),
  approve: (id: number, approvedBy: string) =>
    request<ApprovalResult>(`/api/approvals/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) }),
  reject: (id: number, decidedBy: string, note: string) =>
    request<ApprovalResult>(`/api/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ decided_by: decidedBy, note }) }),
  cash: () => request<CashResponse>('/api/cash'),
  reset: () => request<{ reset: boolean; checking_balance: number; message: string }>('/api/reset', {
    method: 'POST', body: JSON.stringify({ confirm: true }),
  }),
}

export const money = (n: number | null | undefined) =>
  n == null ? '-' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

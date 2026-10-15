import { useState } from 'react'
import { money } from '../api'
import { identity } from '../agents'
import { Avatar } from './Avatar'
import type { ApprovalRequest } from '../types'

const KIND_LABEL: Record<ApprovalRequest['kind'], string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent payment',
  purchase_order: 'Purchase order',
  discount: 'Price discount',
}

function approvalState(a: ApprovalRequest): { label: string; tone: string } {
  if (a.status === 'pending') return { label: 'Pending approval', tone: 'wait' }
  if (a.status === 'rejected') return { label: a.decided_by === 'system' ? 'Rejected by system' : 'Rejected', tone: 'bad' }
  if (a.kind === 'discount') return { label: 'Approved', tone: 'info' }
  return { label: 'Paid · completed', tone: 'done' }
}

interface Props {
  approvals: ApprovalRequest[] | null
  error: string | null
  busyId: number | null
  operator: string
  selectedTicket: number | null
  onApprove: (a: ApprovalRequest) => void
  onReject: (a: ApprovalRequest, note: string) => void
}

function Card({ a, busy, disabled, onApprove, onReject }: {
  a: ApprovalRequest; busy: boolean; disabled: boolean
  onApprove: () => void; onReject: (note: string) => void
}) {
  const [rejecting, setRejecting] = useState(false)
  const [note, setNote] = useState('')
  const state = approvalState(a)
  const moves = a.kind !== 'discount'
  return (
    <li className={`approval approval--${state.tone}`}>
      <div className="approval__top">
        <span className="approval__kind">{KIND_LABEL[a.kind]}</span>
        <span className={`pill pill--${state.tone}`}>{state.label}</span>
      </div>
      <div className="approval__amount">
        {money(a.amount)}
        <span>{moves ? 'from checking' : 'discount value · no cash moves'}</span>
      </div>
      <div className="approval__payee">{a.payee ?? 'Unknown payee'}</div>
      <div className="approval__desc">{a.description}</div>
      <div className="approval__meta">
        <span className="chip">Ticket #{a.ticket_id}</span>
        <span className="approval__by"><Avatar name={a.requested_by} size={18} /> {identity(a.requested_by).label}</span>
        <span className="muted">Request #{a.id}</span>
      </div>
      {a.status !== 'pending' && (
        <div className="approval__decided">
          {a.decided_by && <>Decided by <b>{a.decided_by}</b>{a.payment_id ? ` · payment #${a.payment_id}` : ''}</>}
          {a.decision_note && <div className="muted">{a.decision_note}</div>}
        </div>
      )}
      {a.status === 'pending' && (rejecting ? (
        <div className="approval__reject">
          <input autoFocus placeholder="Reason (optional)" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
          <button className="btn btn--danger btn--sm" disabled={busy || disabled} onClick={() => onReject(note)}>Confirm reject</button>
          <button className="btn btn--ghost btn--sm" onClick={() => setRejecting(false)}>Back</button>
        </div>
      ) : (
        <div className="approval__actions">
          <button className="btn btn--approve" disabled={busy || disabled} onClick={onApprove}>
            {busy ? <><span className="spinner" /> Processing...</> : moves ? `Approve & pay ${money(a.amount)}` : 'Approve discount'}
          </button>
          <button className="btn btn--ghost btn--sm" disabled={busy || disabled} onClick={() => setRejecting(true)}>Reject</button>
        </div>
      ))}
    </li>
  )
}

export function ApprovalQueue({ approvals, error, busyId, operator, selectedTicket, onApprove, onReject }: Props) {
  const [showAll, setShowAll] = useState(false)
  const pending = approvals?.filter((a) => a.status === 'pending') ?? []
  const decided = (approvals?.filter((a) => a.status !== 'pending') ?? []).slice().reverse()
  const visibleDecided = showAll ? decided : decided.filter((a) => a.ticket_id === selectedTicket).slice(0, 4)
  const noOperator = !operator.trim()

  return (
    <section className={`panel panel--approvals${pending.length ? ' panel--attention' : ''}`}>
      <div className="panel__head">
        <h2>Approvals</h2>
        {pending.length > 0 && <span className="badge-count">{pending.length} waiting</span>}
      </div>
      <p className="panel__hint">Agents only prepare requests. Nothing is paid until you approve it here.</p>
      {noOperator && pending.length > 0 && <div className="banner banner--warn">Enter your name as Operator (top right) to approve.</div>}
      {error && <div className="banner banner--error">{error}</div>}
      {approvals && pending.length === 0 && <div className="empty empty--small">No requests waiting for approval.</div>}
      <ul className="approval-list">
        {pending.map((a) => (
          <Card key={a.id} a={a} busy={busyId === a.id} disabled={busyId !== null || noOperator}
                onApprove={() => onApprove(a)} onReject={(n) => onReject(a, n)} />
        ))}
      </ul>
      {decided.length > 0 && (
        <>
          <div className="subhead">
            <span>History {showAll ? '(all tickets)' : selectedTicket ? `(ticket #${selectedTicket})` : ''}</span>
            <button className="link" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show selected ticket' : `Show all ${decided.length}`}</button>
          </div>
          <ul className="approval-list approval-list--history">
            {visibleDecided.map((a) => <Card key={a.id} a={a} busy={false} disabled onApprove={() => {}} onReject={() => {}} />)}
          </ul>
        </>
      )}
    </section>
  )
}

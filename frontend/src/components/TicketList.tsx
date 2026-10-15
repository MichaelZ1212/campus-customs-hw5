import type { Ticket } from '../types'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

function statusMeta(status: string, running: boolean): { label: string; tone: string } {
  if (running) return { label: 'Running', tone: 'run' }
  switch (status) {
    case 'open': return { label: 'Open', tone: 'open' }
    case 'in_progress': return { label: 'In progress', tone: 'run' }
    case 'awaiting_approval': return { label: 'Awaiting approval', tone: 'wait' }
    case 'resolved': return { label: 'Resolved', tone: 'done' }
    case 'blocked': return { label: 'Blocked', tone: 'bad' }
    default: return { label: status, tone: 'open' }
  }
}

function details(t: Ticket): string[] {
  const out: string[] = []
  if (t.sku) out.push(`${t.sku} · size ${t.size} · qty ${t.qty}`)
  if (t.lease_id) out.push(`Lease #${t.lease_id}`)
  if (t.invoice_id) out.push(`Linked invoice #${t.invoice_id}`)
  return out
}

interface Props {
  tickets: Ticket[] | null
  error: string | null
  selectedId: number | null
  runningTicket: number | null
  offline: boolean
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

export function TicketList({ tickets, error, selectedId, runningTicket, offline, onSelect, onRun }: Props) {
  return (
    <section className="panel panel--tickets">
      <div className="panel__head">
        <h2>Tickets</h2>
        {tickets && <span className="panel__count">{tickets.filter((t) => t.state === 'open').length} open</span>}
      </div>
      {error && !tickets && <div className="empty empty--error">{error}</div>}
      {!tickets && !error && <div className="skeleton-list"><div /><div /><div /></div>}
      <div className="ticket-list">
        {tickets?.map((t) => {
          const running = runningTicket === t.id
          const meta = statusMeta(t.status, running)
          const firstLine = (t.notes ?? '').split('\n')[0]
          return (
            <article
              key={t.id}
              className={`ticket ticket--${meta.tone}${selectedId === t.id ? ' ticket--selected' : ''}`}
              onClick={() => onSelect(t.id)}
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect(t.id)}
              aria-current={selectedId === t.id}
            >
              <div className="ticket__top">
                <span className="ticket__id">#{t.id}</span>
                <span className={`pill pill--${meta.tone}`}>
                  {meta.tone === 'done' ? '✓ ' : ''}{meta.label}
                </span>
              </div>
              <div className="ticket__subject">{t.subject}</div>
              <div className="ticket__meta">{TYPE_LABEL[t.type] ?? t.type} · {t.requester}</div>
              {firstLine && <div className="ticket__note">"{firstLine}"</div>}
              <div className="ticket__details">
                {details(t).map((d) => <span key={d} className="chip">{d}</span>)}
              </div>
              <div className="ticket__foot">
                <span className="ticket__counts">
                  {t.pending_approvals > 0 && <span className="dot-count dot-count--wait">{t.pending_approvals} pending approval{t.pending_approvals > 1 ? 's' : ''}</span>}
                  {t.drafts > 0 && <span className="dot-count">{t.drafts} draft{t.drafts > 1 ? 's' : ''}</span>}
                </span>
                {t.state === 'resolved' ? (
                  <span className="ticket__done">Closed</span>
                ) : (
                  <button
                    className="btn btn--primary btn--sm"
                    disabled={runningTicket !== null || offline}
                    onClick={(e) => { e.stopPropagation(); onRun(t.id) }}
                    title={offline ? 'Backend offline' : runningTicket !== null && !running ? `Agents are busy with #${runningTicket}` : undefined}
                  >
                    {running ? <><span className="spinner" /> Running</> : t.status === 'open' ? 'Run agents' : 'Re-run'}
                  </button>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

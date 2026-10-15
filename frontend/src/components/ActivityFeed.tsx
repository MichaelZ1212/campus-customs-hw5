import { useEffect, useRef } from 'react'
import { AGENTS, AGENT_ORDER, identity, isAgent } from '../agents'
import { Avatar } from './Avatar'
import type { AgentEvent, AgentName, Ticket } from '../types'

function time(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function taskOf(e: AgentEvent): string {
  const inp = e.inputs as { task?: string } | undefined
  return inp?.task ?? e.message.replace(/^Asked \w+: /, '')
}

function EventRow({ e }: { e: AgentEvent }) {
  const who = identity(e.agent)
  const failed = ['error', 'refused', 'tool_error', 'usage_limit', 'rejected'].includes(e.status)

  if (e.action === 'mcp_tool_call') {
    return (
      <li className={`ev ev--tool${failed ? ' ev--fail' : ''}`} style={{ '--c': who.color } as React.CSSProperties}>
        <span className="ev__rail" />
        <span className="ev__tool">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.7 6.3a4 4 0 00-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 005.4-5.4l-2.5 2.5-2.4-.6-.6-2.4 2.5-2.5z" /></svg>
          <b style={{ color: who.color }}>{who.label}</b> called <code>{e.tool}</code>
          {failed && <span className="ev__err"> - {e.error}</span>}
        </span>
        <time>{time(e.timestamp)}</time>
      </li>
    )
  }

  if (e.action === 'delegation' && isAgent(e.delegation_target)) {
    const to = AGENTS[e.delegation_target]
    if (e.status === 'started') {
      return (
        <li className="ev ev--handoff" style={{ '--c': who.color, '--c2': to.color } as React.CSSProperties}>
          <div className="ev__handoff">
            <Avatar name={e.agent} size={22} /><b style={{ color: who.color }}>{who.label}</b>
            <span className="ev__arrow">→</span>
            <Avatar name={e.delegation_target} size={22} /><b style={{ color: to.color }}>{to.label}</b>
            <time>{time(e.timestamp)}</time>
          </div>
          <p className="ev__task">{taskOf(e)}</p>
        </li>
      )
    }
    if (e.status === 'completed' || e.status === 'cached') {
      const report = e.outputs as { summary?: string; findings?: string[] } | undefined
      return (
        <li className="ev ev--reply" style={{ '--c': to.color } as React.CSSProperties}>
          <Avatar name={e.delegation_target} />
          <div className="ev__body">
            <div className="ev__head"><b style={{ color: to.color }}>{to.label}</b><span>reported back to {who.label}{e.status === 'cached' ? ' (cached)' : ''}</span><time>{time(e.timestamp)}</time></div>
            <p>{report?.summary ?? e.message}</p>
            {!!report?.findings?.length && (
              <ul className="ev__findings">{report.findings.slice(0, 4).map((f, i) => <li key={i}>{f}</li>)}</ul>
            )}
          </div>
        </li>
      )
    }
  }

  if (e.action === 'ticket_decision') {
    const d = e.outputs as { final_status?: string; decision?: string; next_steps_for_human?: string[] } | undefined
    return (
      <li className={`ev ev--decision${failed ? ' ev--fail' : ''}`}>
        <Avatar name="boss" />
        <div className="ev__body">
          <div className="ev__head"><b style={{ color: 'var(--agent-boss)' }}>Boss</b><span>{failed ? 'run failed' : `final decision · ${d?.final_status?.replace('_', ' ')}`}</span><time>{time(e.timestamp)}</time></div>
          <p>{failed ? e.error : d?.decision ?? e.message}</p>
          {!!d?.next_steps_for_human?.length && (
            <ul className="ev__findings">{d.next_steps_for_human.map((s, i) => <li key={i}>{s}</li>)}</ul>
          )}
        </div>
      </li>
    )
  }

  return (
    <li className={`ev ev--note${failed ? ' ev--fail' : ''}`} style={{ '--c': who.color } as React.CSSProperties}>
      <Avatar name={e.agent} size={22} />
      <span>{e.message}</span>
      <time>{time(e.timestamp)}</time>
    </li>
  )
}

interface Props {
  ticket: Ticket | null
  events: AgentEvent[]
  loading: boolean
  running: boolean
  active: AgentName[]
  error: string | null
}

export function ActivityFeed({ ticket, events, loading, running, active, error }: Props) {
  const listRef = useRef<HTMLOListElement>(null)
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length])

  const current = active[active.length - 1]
  const toolCalls = events.filter((e) => e.action === 'mcp_tool_call').length
  const handoffs = events.filter((e) => e.action === 'delegation' && e.status === 'started').length

  return (
    <section className="panel panel--feed">
      <div className="panel__head">
        <h2>Agent activity {ticket && <span className="muted">· ticket #{ticket.id}</span>}</h2>
        <div className="feed__stats">
          {running && <span className="live"><span className="live__dot" />LIVE</span>}
          <span>{handoffs} handoffs</span><span>{toolCalls} tool calls</span>
        </div>
      </div>

      <div className="roster">
        {AGENT_ORDER.map((a) => {
          const working = running && active.includes(a)
          const isCurrent = running && current === a
          const involved = events.some((e) => e.agent === a || e.delegation_target === a)
          return (
            <div key={a} className={`roster__agent${isCurrent ? ' roster__agent--current' : working ? ' roster__agent--waiting' : ''}${involved ? '' : ' roster__agent--idle'}`}
                 style={{ '--c': AGENTS[a].color } as React.CSSProperties}>
              <Avatar name={a} size={30} pulse={isCurrent} />
              <div>
                <div className="roster__name">{AGENTS[a].label}</div>
                <div className="roster__state">{isCurrent ? 'Working...' : working ? 'Waiting on teammate' : involved ? 'Contributed' : 'Idle'}</div>
              </div>
            </div>
          )
        })}
      </div>

      {error && <div className="banner banner--error">{error}</div>}
      {!ticket && <div className="empty">Select a ticket to see its agent activity.</div>}
      {ticket && loading && events.length === 0 && <div className="empty"><span className="spinner" /> Loading activity...</div>}
      {ticket && !loading && events.length === 0 && (
        <div className="empty">
          <div className="empty__title">No agent activity yet</div>
          {ticket.state === 'resolved' ? 'This ticket is resolved.' : 'Press Run agents on the ticket to start the team.'}
        </div>
      )}
      {events.length > 0 && (
        <ol className="feed" ref={listRef}>
          {events.map((e) => <EventRow key={e.id} e={e} />)}
          {running && (
            <li className="ev ev--typing">
              <Avatar name={current ?? 'boss'} size={22} pulse />
              <span>{AGENTS[current ?? 'boss'].label} is working</span><span className="typing"><i /><i /><i /></span>
            </li>
          )}
        </ol>
      )}
    </section>
  )
}

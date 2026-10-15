import { useState } from 'react'
import { AGENTS } from '../agents'
import { Avatar } from './Avatar'
import type { Contribution } from '../runAnalysis'
import type { MessageDraft, Ticket } from '../types'

interface Props {
  ticket: Ticket | null
  contributions: Contribution[]
  drafts: MessageDraft[]
  running: boolean
}

export function Contributions({ ticket, contributions, drafts, running }: Props) {
  const [openDraft, setOpenDraft] = useState<number | null>(null)
  const boss = contributions.find((c) => c.agent === 'boss')
  const decision = boss?.decision

  return (
    <section className="panel panel--summary">
      <div className="panel__head"><h2>Ticket summary {ticket && <span className="muted">· #{ticket.id}</span>}</h2></div>
      {!ticket && <div className="empty empty--small">Select a ticket.</div>}
      {ticket && contributions.length === 0 && (
        <div className="empty empty--small">{running ? 'Summary appears when the team finishes.' : 'No agent run recorded for this ticket yet.'}</div>
      )}

      {decision && (
        <div className={`decision decision--${decision.final_status}`}>
          <div className="decision__label">
            Boss decision · left it {decision.final_status.replace('_', ' ')}
            {ticket?.state === 'resolved' && decision.final_status !== 'resolved' && <span className="decision__now"> · now resolved after your approvals</span>}
          </div>
          <p>{decision.decision}</p>
        </div>
      )}

      <ul className="contrib-list">
        {contributions.map((c) => {
          const id = AGENTS[c.agent]
          const summary = c.agent === 'boss' ? null : c.report?.summary
          return (
            <li key={c.agent} className="contrib" style={{ '--c': id.color } as React.CSSProperties}>
              <div className="contrib__head">
                <Avatar name={c.agent} size={26} />
                <div>
                  <b style={{ color: id.color }}>{id.label}</b>
                  <div className="contrib__role">{id.role}</div>
                </div>
              </div>
              {c.agent === 'boss' && (
                <p className="contrib__text">Coordinated the ticket{c.delegatedTo.length ? `, delegating to ${c.delegatedTo.map((a) => AGENTS[a].label).join(', ')}` : ''}, and set the final status.</p>
              )}
              {summary && <p className="contrib__text">{summary}</p>}
              {c.agent !== 'boss' && (c.askedBy.length > 0 || c.delegatedTo.length > 0) && (
                <div className="contrib__flow">
                  {c.askedBy.length > 0 && <>Asked by {c.askedBy.map((a) => AGENTS[a].label).join(', ')}</>}
                  {c.delegatedTo.length > 0 && <> · asked {c.delegatedTo.map((a) => AGENTS[a].label).join(', ')} for help</>}
                </div>
              )}
              {!!c.report?.findings?.length && (
                <ul className="contrib__findings">{c.report.findings.slice(0, 3).map((f, i) => <li key={i}>{f}</li>)}</ul>
              )}
              {c.report?.recommendation && <div className="contrib__rec"><span>Recommends</span> {c.report.recommendation}</div>}
              {(!!c.report?.approval_request_ids?.length || !!c.report?.draft_ids?.length) && (
                <div className="contrib__ids">
                  {c.report!.approval_request_ids.map((i) => <span key={`a${i}`} className="chip chip--wait">Request #{i}</span>)}
                  {c.report!.draft_ids.map((i) => <span key={`d${i}`} className="chip">Draft #{i}</span>)}
                </div>
              )}
              {c.tools.length > 0 && (
                <div className="contrib__tools">{c.tools.map((t) => <code key={t}>{t}</code>)}</div>
              )}
              {c.usage && (
                <div className="contrib__usage" title={c.agent === 'boss' ? 'All agents on this ticket' : 'This agent plus any teammates it asked'}>
                  {c.agent === 'boss' ? 'Ticket total' : 'Used'}: {c.usage.input_tokens.toLocaleString()} in / {c.usage.output_tokens.toLocaleString()} out tokens · {c.usage.requests} model requests
                </div>
              )}
            </li>
          )
        })}
      </ul>

      {drafts.length > 0 && (
        <>
          <div className="subhead"><span>Message drafts · never sent</span></div>
          <ul className="draft-list">
            {drafts.map((d) => (
              <li key={d.id} className="draft">
                <button className="draft__head" onClick={() => setOpenDraft(openDraft === d.id ? null : d.id)}>
                  <Avatar name={d.author} size={20} />
                  <span><b>To {d.recipient}</b> · {d.subject}</span>
                  {d.status === 'needs_review' && <span className="chip chip--wait" title="An approval was decided after this draft was written, so it may be out of date">Needs review</span>}
                  <span className="draft__chev">{openDraft === d.id ? '−' : '+'}</span>
                </button>
                {openDraft === d.id && <pre className="draft__body">{d.body}</pre>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

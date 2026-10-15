// Derives presentation state from audit events returned by GET /api/events.
// Nothing here invents data: it only groups and reads what the backend recorded.
import { isAgent } from './agents'
import type { AgentEvent, AgentName, AgentReport, TicketDecision, Usage } from './types'

/** Events from the most recent agent run on this ticket onward (incl. later human approvals). */
export function latestRunEvents(events: AgentEvent[]): AgentEvent[] {
  let start = -1
  events.forEach((e, i) => { if (e.action === 'ticket_started') start = i })
  return start === -1 ? [] : events.slice(start)
}

/** Who is working right now: follows delegation start/finish like a call stack. */
export function activeAgents(runEvents: AgentEvent[]): AgentName[] {
  const stack: AgentName[] = []
  for (const e of runEvents) {
    if (e.action === 'ticket_started') stack.splice(0, stack.length, 'boss')
    else if (e.action === 'delegation' && isAgent(e.delegation_target)) {
      if (e.status === 'started') stack.push(e.delegation_target)
      else if (stack[stack.length - 1] === e.delegation_target) stack.pop()
    } else if (e.action === 'ticket_decision') stack.splice(0, stack.length)
  }
  return stack
}

export interface Contribution {
  agent: AgentName
  tools: string[]
  askedBy: AgentName[]
  delegatedTo: AgentName[]
  report: AgentReport | null
  decision: TicketDecision | null
  toolErrors: string[]
  /** Tokens/requests for this agent's delegated work (incl. agents it asked); for the Boss, the whole ticket. */
  usage: Usage | null
}

export function contributions(runEvents: AgentEvent[]): Contribution[] {
  const map = new Map<AgentName, Contribution>()
  const get = (a: AgentName) => {
    if (!map.has(a)) map.set(a, { agent: a, tools: [], askedBy: [], delegatedTo: [], report: null, decision: null, toolErrors: [], usage: null })
    return map.get(a)!
  }
  for (const e of runEvents) {
    if (e.action === 'mcp_tool_call' && isAgent(e.agent) && e.tool) {
      const c = get(e.agent)
      if (!c.tools.includes(e.tool)) c.tools.push(e.tool)
      if (e.status !== 'ok' && e.error) c.toolErrors.push(`${e.tool}: ${e.error}`)
    }
    if (e.action === 'delegation' && isAgent(e.agent) && isAgent(e.delegation_target)) {
      const from = get(e.agent), to = get(e.delegation_target)
      if (e.status === 'started') {
        if (!from.delegatedTo.includes(to.agent)) from.delegatedTo.push(to.agent)
        if (!to.askedBy.includes(from.agent)) to.askedBy.push(from.agent)
      }
      if ((e.status === 'completed' || e.status === 'cached') && e.outputs && typeof e.outputs === 'object') {
        to.report = e.outputs as AgentReport
        if (e.usage) to.usage = e.usage
      }
    }
    if (e.action === 'ticket_decision' && e.outputs && typeof e.outputs === 'object') {
      get('boss').decision = e.outputs as TicketDecision
      if (e.inputs && typeof e.inputs === 'object' && 'input_tokens' in e.inputs) get('boss').usage = e.inputs as Usage
    }
  }
  const order: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']
  return order.filter((a) => map.has(a)).map((a) => map.get(a)!)
}

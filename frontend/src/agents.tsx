// Visual identity for each actor in the activity feed: colour, icon, role.
import type { AgentName } from './types'

export interface AgentIdentity {
  key: string
  label: string
  role: string
  color: string
  icon: React.ReactNode
}

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

const icons = {
  boss: (
    <svg viewBox="0 0 24 24" {...stroke}><path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z" /></svg>
  ),
  inventory: (
    <svg viewBox="0 0 24 24" {...stroke}><path d="M21 8l-9-5-9 5v8l9 5 9-5V8z" /><path d="M3 8l9 5 9-5M12 13v8" /></svg>
  ),
  accounting: (
    <svg viewBox="0 0 24 24" {...stroke}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 7h8M8 11h2m4 0h2M8 15h2m4 0h2M8 18h2m4 0h2" /></svg>
  ),
  facilities: (
    <svg viewBox="0 0 24 24" {...stroke}><path d="M3 21h18M5 21V9l7-5 7 5v12" /><path d="M10 21v-6h4v6" /></svg>
  ),
  customer_service: (
    <svg viewBox="0 0 24 24" {...stroke}><path d="M21 12a8 8 0 01-11.6 7.1L4 20l1-4.4A8 8 0 1121 12z" /><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" /></svg>
  ),
  human: (
    <svg viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /></svg>
  ),
  system: (
    <svg viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="12" r="3" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9L7 7m10 10l2.1 2.1M4.9 19.1L7 17m10-10l2.1-2.1" /></svg>
  ),
}

export const AGENTS: Record<AgentName, AgentIdentity> = {
  boss: { key: 'boss', label: 'Boss', role: 'Triage, delegation and final decision', color: 'var(--agent-boss)', icon: icons.boss },
  inventory: { key: 'inventory', label: 'Inventory', role: 'Stock, suppliers and lead times', color: 'var(--agent-inventory)', icon: icons.inventory },
  accounting: { key: 'accounting', label: 'Accounting', role: 'Cash, invoices, margins and payment requests', color: 'var(--agent-accounting)', icon: icons.accounting },
  facilities: { key: 'facilities', label: 'Facilities', role: 'Lease and premises obligations', color: 'var(--agent-facilities)', icon: icons.facilities },
  customer_service: { key: 'customer_service', label: 'Customer Service', role: 'Customer-facing reply drafts', color: 'var(--agent-cs)', icon: icons.customer_service },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export function isAgent(name: string | null | undefined): name is AgentName {
  return !!name && name in AGENTS
}

export function identity(name: string): AgentIdentity {
  if (isAgent(name)) return AGENTS[name]
  if (name.startsWith('human')) {
    const who = name.split(':')[1] ?? 'Operator'
    return { key: 'human', label: who, role: 'Human operator', color: 'var(--human)', icon: icons.human }
  }
  return { key: 'system', label: name === 'orchestrator' ? 'Orchestrator' : 'System', role: 'Workflow control', color: 'var(--muted)', icon: icons.system }
}

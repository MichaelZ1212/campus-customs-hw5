import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, api, money } from './api'
import { ActivityFeed } from './components/ActivityFeed'
import { ApprovalQueue } from './components/ApprovalQueue'
import { Contributions } from './components/Contributions'
import { Header } from './components/Header'
import { TicketList } from './components/TicketList'
import { activeAgents, contributions, latestRunEvents } from './runAnalysis'
import type { AgentEvent, ApprovalRequest, CashResponse, Health, MessageDraft, Ticket } from './types'

interface Toast { id: number; tone: 'ok' | 'err' | 'info'; title: string; body?: string }

const errText = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : String(e))
const RUN_POLL_MS = 1200
const IDLE_POLL_MS = 8000

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [ticketsError, setTicketsError] = useState<string | null>(null)
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null)
  const [approvalsError, setApprovalsError] = useState<string | null>(null)
  const [cash, setCash] = useState<CashResponse | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsError, setEventsError] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<MessageDraft[]>([])
  const [runningTicket, setRunningTicket] = useState<number | null>(null)
  const [busyApproval, setBusyApproval] = useState<number | null>(null)
  const [resetting, setResetting] = useState(false)
  const [operator, setOperator] = useState(() => localStorage.getItem('cc-operator') ?? '')
  const [toasts, setToasts] = useState<Toast[]>([])
  const cursor = useRef(0)
  const eventsTicket = useRef<number | null>(null)

  const toast = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Date.now() + Math.random()
    setToasts((all) => [...all, { ...t, id }])
    setTimeout(() => setToasts((all) => all.filter((x) => x.id !== id)), t.tone === 'err' ? 9000 : 5500)
  }, [])

  useEffect(() => { localStorage.setItem('cc-operator', operator) }, [operator])

  // Refs mirror state that async callbacks need without re-creating them.
  const selectedRef = useRef<number | null>(null)
  const localRunRef = useRef<number | null>(null)
  const remoteRunRef = useRef<number | null>(null)

  // ---------------------------------------------------------------- loaders
  const loadDrafts = useCallback(async (id: number) => {
    try { setDrafts((await api.ticket(id)).message_drafts) } catch { setDrafts([]) }
  }, [])

  /** Full reload of a ticket's events (on select). */
  const loadEvents = useCallback(async (id: number) => {
    eventsTicket.current = id
    setEventsLoading(true)
    try {
      // Only activity since the last reset: older runs belong to a previous simulation.
      const res = await api.events({ ticket_id: id, limit: 1000, include_payloads: true, since_reset: true })
      if (eventsTicket.current !== id) return
      setEvents(res.events)
      cursor.current = res.latest_id
      setEventsError(null)
    } catch (e) {
      setEventsError(errText(e))
    } finally {
      setEventsLoading(false)
    }
  }, [])

  /** Incremental poll: only events after the cursor. */
  const pollEvents = useCallback(async (id: number) => {
    try {
      const res = await api.events({ ticket_id: id, after_id: cursor.current, limit: 200, include_payloads: true })
      if (eventsTicket.current !== id) return
      if (res.events.length) setEvents((prev) => [...prev, ...res.events.filter((e) => !prev.some((p) => p.id === e.id))])
      cursor.current = res.events.length === 200 ? res.events[res.events.length - 1].id : res.latest_id
      setEventsError(null)
    } catch (e) {
      setEventsError(errText(e))
    }
  }, [])

  /** Select a ticket and load its activity and drafts (an event handler, not an effect). */
  const selectTicket = useCallback((id: number) => {
    selectedRef.current = id
    setSelectedId(id)
    setEvents([]); setDrafts([])
    loadEvents(id); loadDrafts(id)
  }, [loadEvents, loadDrafts])

  const loadBoard = useCallback(async () => {
    const [t, a, c] = await Promise.allSettled([api.tickets(), api.approvals(), api.cash()])
    if (t.status === 'fulfilled') {
      const list = t.value.tickets
      setTickets(list); setTicketsError(null)
      // First load: select the first open ticket (or the first ticket).
      if (selectedRef.current == null && list.length) selectTicket((list.find((x) => x.state === 'open') ?? list[0]).id)
    } else setTicketsError(errText(t.reason))
    if (a.status === 'fulfilled') { setApprovals(a.value.approval_requests); setApprovalsError(null) } else setApprovalsError(errText(a.reason))
    if (c.status === 'fulfilled') setCash(c.value)
  }, [selectTicket])

  const loadHealth = useCallback(async () => {
    try {
      const h = await api.health()
      setHealth(h); setHealthError(null)
      // A run started elsewhere (another tab, the CLI) just finished: refresh what it changed.
      const remote = h.agent_run_in_progress ?? null
      if (remoteRunRef.current != null && remote == null && localRunRef.current == null) {
        loadBoard()
        const sel = selectedRef.current
        if (sel != null) { pollEvents(sel); loadDrafts(sel) }
      }
      remoteRunRef.current = remote
    } catch (e) {
      setHealthError(errText(e))
    }
  }, [loadBoard, pollEvents, loadDrafts])

  // ------------------------------------------------------------- lifecycle
  useEffect(() => {
    const first = setTimeout(() => { loadHealth(); loadBoard() }, 0)
    const h = setInterval(loadHealth, 5000)
    const b = setInterval(loadBoard, IDLE_POLL_MS)
    return () => { clearTimeout(first); clearInterval(h); clearInterval(b) }
  }, [loadHealth, loadBoard])

  // A run started elsewhere (another tab, the CLI) still shows as running.
  const remoteRun = health?.agent_run_in_progress ?? null
  const running = runningTicket ?? remoteRun

  useEffect(() => {
    if (running == null || running !== selectedId) return
    const timer = setInterval(() => pollEvents(running), RUN_POLL_MS)
    return () => clearInterval(timer)
  }, [running, selectedId, pollEvents])

  // --------------------------------------------------------------- actions
  const runTicket = useCallback(async (id: number) => {
    if (running != null) return
    if (selectedRef.current !== id) selectTicket(id)
    localRunRef.current = id
    setRunningTicket(id)
    toast({ tone: 'info', title: `Agents started on ticket #${id}`, body: 'The Boss is reading the ticket. This usually takes 30-90 seconds.' })
    try {
      const res = await api.runTicket(id)
      const pending = res.pending_approvals.length
      toast({
        tone: 'ok',
        title: `Ticket #${id}: ${res.decision.final_status.replace('_', ' ')}`,
        body: pending ? `${pending} request${pending > 1 ? 's' : ''} need your approval.` : res.decision.decision,
      })
    } catch (e) {
      toast({ tone: 'err', title: `Agent run on #${id} failed`, body: errText(e) })
    } finally {
      localRunRef.current = null
      setRunningTicket(null)
      await pollEvents(id)
      await Promise.all([loadBoard(), loadDrafts(id), loadHealth()])
    }
  }, [running, selectTicket, pollEvents, loadBoard, loadDrafts, loadHealth, toast])

  const approve = useCallback(async (a: ApprovalRequest) => {
    setBusyApproval(a.id)
    try {
      const res = await api.approve(a.id, operator.trim())
      toast({ tone: 'ok', title: `Request #${a.id} approved`, body: res.message })
    } catch (e) {
      const insufficient = errText(e).toLowerCase().includes('insufficient')
      toast({ tone: 'err', title: insufficient ? 'Not enough cash' : `Request #${a.id} not executed`, body: errText(e) })
    } finally {
      setBusyApproval(null)
      await loadBoard()
      if (selectedId != null) { await pollEvents(selectedId); loadDrafts(selectedId) }
    }
  }, [operator, toast, loadBoard, selectedId, pollEvents, loadDrafts])

  const reject = useCallback(async (a: ApprovalRequest, note: string) => {
    setBusyApproval(a.id)
    try {
      await api.reject(a.id, operator.trim(), note)
      toast({ tone: 'info', title: `Request #${a.id} rejected`, body: 'No money moved.' })
    } catch (e) {
      toast({ tone: 'err', title: `Couldn't reject #${a.id}`, body: errText(e) })
    } finally {
      setBusyApproval(null)
      await loadBoard()
      if (selectedId != null) pollEvents(selectedId)
    }
  }, [operator, toast, loadBoard, selectedId, pollEvents])

  const reset = useCallback(async () => {
    setResetting(true)
    try {
      const res = await api.reset()
      toast({ tone: 'info', title: 'Simulation reset', body: `${res.message} Balance ${money(res.checking_balance)}.` })
      setDrafts([])
      if (selectedId != null) await loadEvents(selectedId)
    } catch (e) {
      toast({ tone: 'err', title: 'Reset failed', body: errText(e) })
    } finally {
      setResetting(false)
      loadBoard()
    }
  }, [toast, selectedId, loadEvents, loadBoard])

  // ---------------------------------------------------------------- derived
  const selected = tickets?.find((t) => t.id === selectedId) ?? null
  const runEvents = useMemo(() => latestRunEvents(events), [events])
  const active = useMemo(() => activeAgents(runEvents), [runEvents])
  const contribs = useMemo(() => contributions(runEvents), [runEvents])
  const selectedRunning = running != null && running === selectedId

  return (
    <div className="app">
      <Header health={health} healthError={healthError} cash={cash} operator={operator} onOperatorChange={setOperator}
              onReset={reset} resetting={resetting} runningTicket={running} />
      {healthError && (
        <div className="banner banner--error banner--global">
          {healthError} Start it with <code>uvicorn main:app --reload --port 8000</code> in <code>backend/</code>. Retrying every 5 seconds.
        </div>
      )}
      <main className="grid">
        <TicketList tickets={tickets} error={ticketsError} selectedId={selectedId} runningTicket={running}
                    offline={!!healthError} onSelect={selectTicket} onRun={runTicket} />
        <ActivityFeed ticket={selected} events={runEvents} loading={eventsLoading} running={selectedRunning}
                      active={active} error={eventsError} />
        <aside className="side">
          <ApprovalQueue approvals={approvals} error={approvalsError} busyId={busyApproval} operator={operator}
                         selectedTicket={selectedId} onApprove={approve} onReject={reject} />
          <Contributions ticket={selected} contributions={selectedRunning ? [] : contribs} drafts={drafts} running={selectedRunning} />
        </aside>
      </main>
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone}`}>
            <b>{t.title}</b>{t.body && <span>{t.body}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

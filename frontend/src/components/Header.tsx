import { useEffect, useRef, useState } from 'react'
import { money } from '../api'
import type { CashResponse, Health } from '../types'

function useAnimatedNumber(value: number | null, duration = 900) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    if (value == null) return
    const start = from.current ?? value
    if (start === value) { setShown(value); return }
    const t0 = performance.now()
    let frame = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setShown(start + (value - start) * eased)
      if (p < 1) frame = requestAnimationFrame(tick)
      else from.current = value
    }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); from.current = value }
  }, [value, duration])
  return shown
}

interface Props {
  health: Health | null
  healthError: string | null
  cash: CashResponse | null
  operator: string
  onOperatorChange: (name: string) => void
  onReset: () => void
  resetting: boolean
  runningTicket: number | null
}

export function Header({ health, healthError, cash, operator, onOperatorChange, onReset, resetting, runningTicket }: Props) {
  const balance = useAnimatedNumber(cash?.balance ?? null)
  const [flash, setFlash] = useState<'down' | 'up' | null>(null)
  const last = useRef<number | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)

  useEffect(() => {
    if (cash == null) return
    if (last.current != null && cash.balance !== last.current) {
      setFlash(cash.balance < last.current ? 'down' : 'up')
      const t = setTimeout(() => setFlash(null), 1600)
      last.current = cash.balance
      return () => clearTimeout(t)
    }
    last.current = cash.balance
  }, [cash])

  const online = !!health && !healthError
  return (
    <header className="header">
      <div className="brand">
        <div className="brand__mark" aria-hidden>CC</div>
        <div>
          <div className="brand__name">Campus Customs</div>
          <div className="brand__sub">Operations Command Center</div>
        </div>
      </div>

      <div className="header__status">
        <span className={`status-dot ${online ? (runningTicket ? 'status-dot--busy' : 'status-dot--ok') : 'status-dot--down'}`} />
        <div>
          <div className="header__status-main">
            {online ? (runningTicket ? `Agents working on #${runningTicket}` : 'All systems online') : 'Backend offline'}
          </div>
          <div className="header__status-sub">
            {online
              ? <>MCP {health!.mcp} · {health!.model} · Business date {health!.business_date}</>
              : healthError ?? 'Connecting...'}
          </div>
        </div>
      </div>

      <div className="header__right">
        <label className="operator">
          <span>Operator</span>
          <input value={operator} onChange={(e) => onOperatorChange(e.target.value)} maxLength={80} placeholder="Your name" />
        </label>
        {confirmReset ? (
          <div className="reset-confirm">
            <span>Reset all data?</span>
            <button className="btn btn--danger btn--sm" disabled={resetting} onClick={() => { setConfirmReset(false); onReset() }}>Reset</button>
            <button className="btn btn--ghost btn--sm" onClick={() => setConfirmReset(false)}>Cancel</button>
          </div>
        ) : (
          <button className="btn btn--ghost btn--sm" disabled={resetting || !!runningTicket || !online}
                  title="Restore the working database to its starting values" onClick={() => setConfirmReset(true)}>
            {resetting ? 'Resetting...' : 'Reset simulation'}
          </button>
        )}
        <div className={`cash${flash ? ` cash--${flash}` : ''}`}>
          <div className="cash__label">Checking balance</div>
          <div className="cash__value">{cash ? money(balance) : '-'}</div>
          <div className="cash__sub">
            {cash ? <>{money(cash.committed_to_pending)} pending · {money(cash.available_after_pending)} free</> : 'loading'}
          </div>
        </div>
      </div>
    </header>
  )
}

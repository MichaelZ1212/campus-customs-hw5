# Campus Customs Operations Dashboard: Design Decisions

The dashboard (`frontend/`, React 19 + Vite 8 + TypeScript) is the human operator's console for the multi-agent system. It reads and changes everything through the FastAPI backend at `http://localhost:8000`. The only things it works out for itself are display details, such as which agent is speaking. Every balance, status and request comes from an API response.

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

---

## 1. Layout and navigation

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CC Campus Customs │ ● All systems online   │ Operator [____]  Reset  $3,400  │  header (sticky)
├───────────────┬────────────────────────────────────────┬─────────────────────┤
│ TICKETS       │ AGENT ACTIVITY · ticket #101     ● LIVE│ APPROVALS  2 waiting│
│ ┌───────────┐ │ [Boss][Inventory][Accounting][Fac][CS] │ ┌─────────────────┐ │
│ │#101  Open │ │ Boss → Inventory  "check size S…"      │ │ $840 Vendor inv.│ │
│ │Bulldog tee│ │   🔧 Inventory called check_stock…     │ │ [Approve & pay] │ │
│ │[Run agents]│ │ Inventory → Accounting …              │ └─────────────────┘ │
│ └───────────┘ │ Accounting reported back: …            │ TICKET SUMMARY      │
│ #102 …        │ Boss · final decision                  │ Boss decision, per- │
│ #103 …        │                                        │ agent cards, drafts │
└───────────────┴────────────────────────────────────────┴─────────────────────┘
```

| Area | Content | Why it helps |
|---|---|---|
| **Header** (sticky) | Brand; system status (MCP connection, model, business date, active run); operator name; Reset; checking balance | The two things an operator glances at constantly, "is the system healthy?" and "how much cash is left?", are always visible, even while scrolling the feed |
| **Left: Tickets** | One card per ticket with status, requester, the request quote, SKU/size/qty or lease, pending-approval and draft counts, and the Run button | The work queue reads top to bottom. Each card has everything needed to decide whether to start it, without opening anything |
| **Center: Agent activity** | Agent roster strip, then a chronological feed of handoffs, tool calls, replies and the Boss's decision | The widest column goes to the part that changes most and needs reading. A run is a conversation, so it's shown as one |
| **Right: Approvals + Ticket summary** | Pending requests with Approve/Reject on top; below, the Boss decision, per-agent contribution cards and message drafts | Approvals sit at the top of the action column because they're the only thing that waits on the human. The summary underneath explains *why* each request exists |

There's no page navigation. Selecting a ticket card is the only navigation, and the feed and summary follow the selection. One screen with one selection matches how an operator works a queue.

**Responsive:** three columns from 1280px up. Below that, the approval and summary panels move to a full-width row under tickets and the feed. Below 860px everything stacks into one column, the header wraps, and the agent roster becomes a 2-column grid. I checked at 375px wide: no horizontal scroll.

---

## 2. The five agents

Each agent has a fixed **colour, line icon and label**, used everywhere it appears: the roster, avatars on every feed entry, handoff arrows, contribution cards and the requester on approval cards.

| Agent | Colour | Icon | Why this pairing |
|---|---|---|---|
| Boss | Violet `#a78bfa` | Crown | Violet is used for nothing else in the UI, so the Boss's decisions stand apart. The crown signals authority |
| Inventory | Teal `#2dd4bf` | Box | Stock means physical goods |
| Accounting | Rose `#f472b6` | Ledger | Deliberately not green or amber, which are reserved for status (paid / pending), so a money agent is never confused with a money state |
| Facilities | Orange `#fb923c` | Building | Premises |
| Customer Service | Sky `#60a5fa` | Speech bubble | Messages |

The five hues are spread around the colour wheel (violet 270°, sky 215°, teal 170°, orange 25°, rose 330°), so they stay distinguishable on the dark background. Each pairs with a different icon shape, so colour is never the only cue, which helps colour-blind users. The human operator uses neutral white and a person icon; system steps use grey.

**Roster strip:** at the top of the feed, each agent shows *Idle*, *Working…* (border in its colour, pulsing avatar), *Waiting on teammate* (it delegated and is waiting) or *Contributed*. This is worked out by following delegation start and finish events like a call stack, so the operator can see who holds the task right now.

---

## 3. Ticket status

| Backend status | Pill | Card accent bar | Notes |
|---|---|---|---|
| `open` | Grey **Open** | Grey | "Run agents" button |
| *(run in progress)* | Indigo **Running**, glowing | Indigo, pulsing | Every Run button disabled; header reads "Agents working on #N" |
| `awaiting_approval` | Amber **Awaiting approval** | Amber | "N pending approvals" counter in amber; button becomes "Re-run" |
| `resolved` | Green **✓ Resolved** | Green | Card dimmed to 72%, subject struck through in green, button replaced by "Closed" |
| `blocked` | Red **Blocked** | Red | |

**Running** is the only state the frontend tracks itself, because the backend only knows a ticket's status before and after a run. It's taken from the in-flight `POST /run` request, and from `/api/health → agent_run_in_progress` for runs started in another tab or from the command line.

**Why the ticket doesn't turn Resolved the moment the agents finish:** the backend leaves a ticket at `awaiting_approval` while any payment request is still pending. A ticket isn't really done until the money decision is made. The dashboard shows the backend's status as-is, so the ticket turns **Resolved** right after the operator approves or rejects its last request. If a run ever ends with nothing to approve, the backend returns `resolved` and the pill updates straight away.

**Resolved vs open:** resolved cards lose saturation, get a green check and strikethrough, and lose their action button. The eye skips them, and the remaining open work stands out.

---

## 4. Approvals and cash

**Approval cards** (right column, top) show, from top to bottom:
- **kind** (Vendor invoice / Rent payment / Purchase order / Price discount);
- **amount** in large type, labelled *from checking* or *discount value · no cash moves*;
- **payee** (Bulldog Print Co, Elm City Properties, Yale AI Club). This comes from the backend's `payee` field, which the MCP tool fills in from the invoice, lease or PO record;
- a **description** such as "PO #1: 1 x Classic Bulldog Tee size S (ETA 2026-09-05)";
- the **ticket** and the **requesting agent's** avatar.

The button names the action and the amount, **"Approve & pay $840.00"**, so there's no doubt what a click does. Reject needs a second click and takes an optional reason.

| Request state | Shown as |
|---|---|
| `pending` | Amber card glow + **Pending approval** pill. The panel border turns amber and an amber "N waiting" counter appears |
| `executed` (payment) | Green **Paid · completed**, with approver name and payment # |
| `executed` (discount) | Blue **Approved** (no money moved, so it isn't shown as paid) |
| `rejected` | Red **Rejected**, or **Rejected by system** with the reason (e.g. insufficient funds) |

Pending approvals are highlighted with one amber accent rather than a modal or banner. That's noticeable without interrupting someone who is reading the feed. History shows the selected ticket by default, with "Show all".

**Guard rails in the UI:**
- Approve is disabled until an operator name is entered (the backend records `approved_by`).
- All approve buttons are disabled while one request is processing, so there are no double submissions.
- Backend refusals appear as red toasts with the backend's own wording, for example "Vendor still has unpaid invoice(s) [501]…" or **"Not enough cash · Request 1 rejected: Insufficient funds…"**.

**Cash balance:** a large tabular figure in the header, from `GET /api/cash`. It refreshes right after every approval and every 8 seconds. The frontend never computes it. When the value changes, the number animates from the old to the new value over 0.9 s and the card briefly glows red (decrease) or green (increase), so the effect of an approval is visible. The line underneath shows "$X pending · $Y free" from the backend's `committed_to_pending` and `available_after_pending`, so the operator can see how much cash is already spoken for before approving more.

---

## 5. Visual language

| Choice | Detail | Why |
|---|---|---|
| **Dark navy theme** | Background `#0b1220`, panels `#121c2e`, borders `#22304a`, Yale-blue accent `#2f6fdf` | Command-center tools are used for long sessions. A dark, low-glare base lets the coloured agent and status accents carry meaning. The Yale blue ties it to the campus brand |
| **Status palette separate from agent palette** | Green = done/paid, amber = waiting on you, red = failed/rejected, indigo = running, grey = open | Each colour means one thing. Amber always means "needs your action" |
| **Typography** | System UI stack (Segoe UI Variable / Inter / system-ui), 14px base; uppercase tracked 11–13px labels for panel headings; tabular numerals for money; monospace only for tool names | No web-font download; it works offline and renders crisply on Windows. Tabular figures keep amounts aligned as they animate. Monospace marks tool names as machine actions |
| **Spacing** | 16px gutters between panels, 10–14px inside cards, 12px radius on panels and 10px on cards | Enough air to scan three columns at once, dense enough that a full run fits in the feed |
| **Hierarchy in the feed** | Tool calls are one-line, low-contrast rows on a coloured rail; handoffs are dashed cards with a two-colour gradient; agent replies are solid cards with a coloured left edge; the Boss's final decision is a violet-tinted card | The eye goes to decisions and handoffs first; the many tool calls stay available without dominating |

---

## 6. Interaction and motion

- **Live feed:** while a run is in progress, the dashboard polls `/api/events` every 1.2 s, fetching only events after the last one it has. New entries slide in, the feed auto-scrolls, a red **LIVE** badge pulses, and a "Inventory is working ●●●" typing indicator shows who holds the task.
- **Feedback on everything:** a toast when a run starts, finishes or fails; when an approval succeeds or is refused; and on reset. Buttons show a spinner and "Processing…" / "Running" while their request is in flight.
- **Subtle motion only:** 0.3 s slide-ins, a pulsing dot for live and running states, the cash count animation. `prefers-reduced-motion` turns all animation off.
- **Keyboard:** ticket cards are focusable and open with Enter; focus rings use the Yale blue.

---

## 7. Loading, empty and error states

| Situation | What the operator sees |
|---|---|
| Backend down / unreachable | Red header dot, **"Backend offline"**, and a banner with the exact `uvicorn` command. Last-known data stays on screen, Run and Reset are disabled, and health is retried every 5 s. It reconnects by itself (tested by stopping the server) |
| First load | Shimmering skeleton ticket cards |
| Ticket run in progress | Running pill, LIVE badge, typing indicator; every Run button disabled; reset refused |
| Failed agent run | Red toast with the backend's 502 detail; the feed keeps the steps that completed, and a failed decision is outlined in red |
| No activity | "No agent activity yet. Press Run agents…" (or "This ticket is resolved.") |
| Unknown ticket / API error | The panel shows the backend's message (e.g. "Ticket 999 not found") instead of failing silently |
| Approval refused (PO before invoice, duplicate) | Red toast with the backend's reason; the card stays pending |
| Insufficient cash | **"Not enough cash"** toast; the request moves to history as **Rejected by system** with the reason; the balance doesn't change |
| No operator name | Amber banner "Enter your name as Operator…", and approve buttons disabled |

---

## 8. Features beyond the brief

- **Agent contribution cards** after each run, one per agent that actually took part (worked out from the run's events). Each shows:
  - the agent's role;
  - who asked it, and whom it asked;
  - its summary, top findings and recommendation;
  - the approval requests and drafts it created;
  - the MCP tools it used.
- **Message drafts inline.** Expand any draft to read the exact text Customer Service or Facilities wrote, labelled "never sent". Drafts written before an approval decision carry an amber **Needs review** badge, so the operator knows to check them before sending.
- **Per-agent cost.** Each contribution card shows the tokens and model requests that agent used (including teammates it asked); the Boss card shows the ticket total. That makes it visible where a ticket's cost went.
- **History only since the last reset.** The audit trail keeps every run forever, but the dashboard asks for `since_reset=true`, so a fresh simulation isn't mixed up with old runs.
- **Remote-run awareness.** A run started in another tab or from the command line still shows as Running, and the dashboard refreshes when it ends.
- **Operator name remembered** in `localStorage` and stamped on every approval in the database and audit trail.

---

## 9. Backend changes made for the dashboard

- `list_approval_requests` (MCP) now adds `payee` and `description` to each request, from the referenced invoice, lease, PO or ticket. The dashboard can then show who gets paid without its own database logic.
- `GET /api/events` gained `since_reset`.
- CORS accepts any `localhost`/`127.0.0.1` port, because Vite moves off 5173 when that port is busy. Other origins are still refused (tested: `https://evil.example` → 400).

---

## 10. Test log (live, real backend, real gpt-6-luna runs)

| Check | Result |
|---|---|
| App loads; 3 tickets; header shows MCP connected, model, business date; cash $3,400 | ✅ |
| Reset from the UI (two-step confirm) → all Open, $3,400, no approvals | ✅ |
| Run #102 from the UI → Facilities → Accounting delegation; rent request appears with payee Elm City Properties | ✅ |
| Run #101 sampled every 400 ms: pill **Running**, all Run buttons disabled, LIVE badge, typing indicator, roster showed Accounting then Customer Service as current, 12 events streamed in before completion | ✅ |
| After #101: summary shows Boss, Inventory, Accounting, Customer Service (Facilities correctly absent); 3 pending approvals with payees | ✅ |
| Approve PO before invoice → red toast with the backend reason; no cash change; all approve buttons disabled while processing | ✅ |
| Approve invoice → $3,400 → $2,560 with the decrease animation | ✅ |
| Run #103 and approve PO, rent, discount through the UI → $152.00; all tickets **✓ Resolved**, dimmed, "Closed" | ✅ |
| Insufficient cash (fixture: rent queued, balance set to $1,000) → "Not enough cash" toast, balance unchanged | ✅ |
| Backend stopped → offline banner, Reset disabled; restarted → reconnected by itself | ✅ (Run buttons now also disabled offline; fixed after this test) |
| 375 px mobile → single column, no horizontal overflow | ✅ (header wrap fixed after the first check) |
| `npm run build` (tsc + vite) | ✅ |

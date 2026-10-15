# Campus Customs Dashboard (frontend)

React 19 + Vite + TypeScript operator console for the Campus Customs multi-agent system. It talks only to the FastAPI backend (`http://localhost:8000` by default; override with `VITE_API_URL` in `frontend/.env.local`).

```bash
npm install
npm run dev       # http://localhost:5173 (backend must be running)
npm run build     # type-check + production build
npm run lint
```

| File | Role |
|---|---|
| `src/App.tsx` | State, polling (health 5 s, board 8 s, events 1.2 s while a run is live), run/approve/reject/reset actions, toasts |
| `src/api.ts` | Typed client for `/api/*` |
| `src/types.ts` | Response types matching `backend/models.py` |
| `src/agents.tsx` | Colour, icon and role for each agent |
| `src/runAnalysis.ts` | Works out the active agent and per-agent contributions from audit events |
| `src/components/` | `Header`, `TicketList`, `ActivityFeed`, `ApprovalQueue`, `Contributions`, `Avatar` |
| `src/index.css` | Command-center theme |

Design decisions are documented in `../output/design.md`.

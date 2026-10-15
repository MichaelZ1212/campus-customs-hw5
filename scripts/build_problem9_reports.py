"""Problem 9: build the "Actual" and "Cash" sections of output/desk_tickets.html and
output/resolved_tickets.json from the real run.

Everything is read from the running backend API (events since the last reset,
tickets, approvals, drafts, cash). The working DB is opened read-only only to
cross-check the payments table and the ending balance. Nothing is invented.

Usage (backend running on :8000):  python scripts/build_problem9_reports.py
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "http://localhost:8000"
DESK = ROOT / "output" / "desk_tickets.html"
RESOLVED = ROOT / "output" / "resolved_tickets.json"
DB = ROOT / "data" / "campus_customs_new.db"
LABEL = {"boss": "Boss", "inventory": "Inventory", "accounting": "Accounting", "facilities": "Facilities",
         "customer_service": "Customer Service"}
AGENTS = set(LABEL)


def get(path: str):
    with urllib.request.urlopen(API + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def esc(s) -> str:
    return html.escape(str(s))


def money(x: float) -> str:
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


# ------------------------------------------------------------------ gather
all_events = get("/api/events?since_reset=true&limit=1000&include_payloads=true")["events"]
reset_events = [e for e in get("/api/events?limit=1000&include_payloads=true")["events"] if e["action"] == "reset_working_database"]
last_reset = reset_events[-1]
start_balance = last_reset["outputs"]["checking_balance"]
tickets = {t["id"]: t for t in get("/api/tickets")["tickets"]}
approvals = get("/api/approvals")["approval_requests"]
drafts = get("/api/drafts")["drafts"]
cash = get("/api/cash")

db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
db.row_factory = sqlite3.Row
db_payments = [dict(r) for r in db.execute("SELECT * FROM payments ORDER BY id")]
db_balance = db.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]


def ticket_runs(tid: int) -> list[list[dict]]:
    """Split a ticket's events into agent runs (ticket_started .. ticket_decision)."""
    runs, cur = [], None
    for e in all_events:
        if e["ticket_id"] != tid:
            continue
        if e["action"] == "ticket_started":
            cur = [e]
            runs.append(cur)
        elif cur is not None and e["run_id"] == cur[0]["run_id"]:
            cur.append(e)
    return runs


def analyse(tid: int) -> dict:
    runs = ticket_runs(tid)
    if not runs:
        return {"ticket_id": tid, "error": "no agent run found since the last reset"}
    run = runs[-1]
    run_id = run[0]["run_id"]
    delegations = [e for e in run if e["action"] == "delegation" and e["status"] == "started"]
    first = next((e["delegation_target"] for e in delegations if e["agent"] == "boss"), None)
    participants = []
    for e in run:
        for a in (e["agent"], e.get("delegation_target")):
            if a in AGENTS and a not in participants:
                participants.append(a)
    tools_by_agent: dict[str, list[str]] = {}
    tool_seq = []
    for e in run:
        if e["action"] == "mcp_tool_call" and e["agent"] in AGENTS:
            tools_by_agent.setdefault(e["agent"], []).append(e["tool"])
            tool_seq.append({"agent": e["agent"], "tool": e["tool"], "status": e["status"], "error": e["error"]})
    reports = {}
    for e in run:
        if e["action"] == "delegation" and e["status"] in ("completed", "cached") and isinstance(e.get("outputs"), dict):
            reports[e["delegation_target"]] = e["outputs"]
    decision_ev = next((e for e in run if e["action"] == "ticket_decision"), None)
    decision = decision_ev["outputs"] if decision_ev and isinstance(decision_ev.get("outputs"), dict) else None
    t_approvals = [a for a in approvals if a["ticket_id"] == tid]
    t_drafts = [d for d in drafts if d["ticket_id"] == tid]
    human = [e for e in all_events if e["ticket_id"] == tid and e["action"].startswith("approval_")]

    contributions = []
    for a in participants:
        tools = Counter(tools_by_agent.get(a, []))
        entry = {"agent": LABEL[a], "tools": [f"{t} x{n}" if n > 1 else t for t, n in tools.items()]}
        if a == "boss":
            asked = [LABEL[d["delegation_target"]] for d in delegations if d["agent"] == "boss"]
            entry["contribution"] = (f"Read the ticket, delegated to {', '.join(asked)}, set the final status "
                                     f"({decision['final_status'] if decision else 'n/a'}) and wrote the decision.")
        elif a in reports:
            r = reports[a]
            entry["contribution"] = r.get("summary")
            entry["findings"] = r.get("findings", [])
            if r.get("recommendation"):
                entry["recommendation"] = r["recommendation"]
            ids = {k: r.get(k) for k in ("approval_request_ids", "purchase_order_ids", "draft_ids") if r.get(k)}
            if ids:
                entry["created"] = ids
        contributions.append(entry)

    decided = "; ".join(
        f"#{a['id']} {a['kind'].replace('_', ' ')} to {a['payee']} ${a['amount']:,.2f} {a['status']}"
        + (f" (payment #{a['payment_id']})" if a["payment_id"] else " (no cash moved)" if a["status"] == "executed" else "")
        for a in t_approvals)
    resolution = (f"{decision['decision'] if decision else ''} Human approvals afterwards: {decided or 'none needed'}. "
                  f"Final ticket status: {tickets[tid]['status']}.").strip()
    return {
        "ticket_id": tid,
        "type": tickets[tid]["type"],
        "requester": tickets[tid]["requester"],
        "subject": tickets[tid]["subject"],
        "final_status": tickets[tid]["status"],
        "resolution": resolution,
        "run_id": run_id,
        "runs_since_reset": len(runs),
        "first_agent_contacted_by_boss": LABEL.get(first, first),
        "agents_involved": [LABEL[a] for a in participants],
        "delegations": [{"from": LABEL[d["agent"]], "to": LABEL[d["delegation_target"]],
                         "task": (d.get("inputs") or {}).get("task")} for d in delegations],
        "mcp_tool_calls": [{"agent": LABEL[t["agent"]], **{k: v for k, v in t.items() if k != "agent" and v is not None}} for t in tool_seq],
        "boss_decision": decision,
        "agent_contributions": contributions,
        "human_approvals": [{
            "approval_request_id": a["id"], "kind": a["kind"], "payee": a["payee"], "description": a["description"],
            "amount": a["amount"], "requested_by": a["requested_by"], "status": a["status"], "decided_by": a["decided_by"],
            "payment_id": a["payment_id"], "decided_at": a["decided_at"],
            "cash_moved": a["amount"] if a["payment_id"] else 0.0,
        } for a in t_approvals],
        "approval_events": [{"event_id": e["id"], "agent": e["agent"], "message": e["message"], "status": e["status"]} for e in human],
        "drafts": [{"draft_id": d["id"], "author": d["author"], "audience": d["audience"], "recipient": d["recipient"],
                    "subject": d["subject"], "body": d["body"], "status": d["status"]} for d in t_drafts],
        "audit_event_ids": [run[0]["id"], run[-1]["id"]],
    }


results = {tid: analyse(tid) for tid in (101, 102, 103)}

# ----------------------------------------------------------- reconciliation
executed = [a for a in approvals if a["status"] == "executed"]
paid = [a for a in executed if a["payment_id"]]
total_paid = round(sum(a["amount"] for a in paid), 2)
calc_end = round(start_balance - total_paid, 2)
pay_ids_api = sorted(a["payment_id"] for a in paid)
pay_ids_db = sorted(p["id"] for p in db_payments)
db_total = round(sum(p["amount"] for p in db_payments), 2)
checks = {
    "calculated_equals_api_balance": calc_end == round(cash["balance"], 2),
    "calculated_equals_cash_accounts_table": calc_end == round(db_balance, 2),
    "payments_table_matches_approvals": pay_ids_api == pay_ids_db and db_total == total_paid,
    "every_payment_has_named_human_approver": all(p["approved_by"] and p["approved_by"] != "system" for p in db_payments),
    "no_pending_requests": not any(a["status"] == "pending" for a in approvals),
}
if not all(checks.values()):
    print("RECONCILIATION FAILED:", checks)
    sys.exit(1)

by_ticket_cash = {}
running = start_balance
for tid in (102, 101, 103):  # execution order
    rows = []
    for a in sorted((a for a in approvals if a["ticket_id"] == tid), key=lambda a: a["decided_at"] or ""):
        moved = a["amount"] if a["payment_id"] else 0.0
        running = round(running - moved, 2)
        rows.append({**a, "moved": moved, "balance_after": running})
    by_ticket_cash[tid] = rows

reconciliation = {
    "starting_balance": start_balance,
    "starting_balance_source": f"cash_accounts.checking after reset (audit event #{last_reset['id']})",
    "payments": [{"payment_id": a["payment_id"], "ticket_id": a["ticket_id"], "kind": a["kind"], "payee": a["payee"],
                  "amount": a["amount"], "approved_by": a["decided_by"]} for a in sorted(paid, key=lambda a: a["payment_id"])],
    "total_approved_payments": total_paid,
    "calculated_ending_balance": calc_end,
    "database_ending_balance": db_balance,
    "formula": f"{start_balance:.2f} - {total_paid:.2f} = {calc_end:.2f}",
    "checks": checks,
}

RESOLVED.write_text(json.dumps({
    "generated_from": "live backend API (events since last reset, tickets, approvals, drafts, cash) + read-only DB cross-check",
    "business_date": cash["business_date"],
    "execution_order": [102, 101, 103],
    "approvals_note": "Approve clicks were made in the React dashboard by Claude Code at the user's instruction; "
                      "the operator name 'Michael Zheng (via Claude Code)' is stored as approved_by.",
    "tickets": [results[t] for t in (101, 102, 103)],
    "cash_reconciliation": reconciliation,
}, indent=2, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------ HTML: Actual
def actual_html(r: dict, expected_first: str, deviations: list[str]) -> str:
    seq = "".join(f"<li><span class='agent'>{esc(d['from'])} → {esc(d['to'])}</span> {esc(d['task'] or '')}</li>" for d in r["delegations"])
    tool_rows = "".join(
        f"<tr><td>{esc(c['agent'])}</td><td>{', '.join(f'<code>{esc(t)}</code>' for t in c['tools']) or '-'}</td>"
        f"<td>{esc(c.get('contribution') or '')}</td></tr>" for c in r["agent_contributions"])
    appr = "".join(
        f"<li>Request #{a['approval_request_id']} · {esc(a['kind'])} · {esc(a['payee'])} · <strong>{money(a['amount'])}</strong> → "
        f"<strong>{esc(a['status'])}</strong> by {esc(a['decided_by'])}"
        f"{f' (payment #{a["payment_id"]})' if a['payment_id'] else ' (no cash moved)'}</li>"
        for a in r["human_approvals"]) or "<li>None</li>"
    drafts_html = "".join(f"<li><strong>Draft #{d['draft_id']}</strong> by {esc(LABEL.get(d['author'], d['author']))} to {esc(d['recipient'])}: "
                          f"“{esc(d['subject'])}”<blockquote>{esc(d['body'])}</blockquote></li>" for d in r["drafts"])
    match = "matches" if r["first_agent_contacted_by_boss"] == expected_first else "differs from"
    dev = "".join(f"<li>{esc(x)}</li>" for x in deviations)
    dec = r["boss_decision"] or {}
    return f"""<div class="actual actual--filled" data-ticket="{r['ticket_id']}">
    <p class="runmeta">Real run <code>{esc(r['run_id'])}</code> · gpt-6-luna via Portkey · started from the React dashboard · audit events #{r['audit_event_ids'][0]}–#{r['audit_event_ids'][1]}</p>
    <h4>First contact</h4>
    <p><span class="agent">Boss → {esc(r['first_agent_contacted_by_boss'])}</span> ({match} the expected first agent, {esc(expected_first)}).</p>
    <h4>Agents that participated</h4>
    <p>{' · '.join(f'<span class="agent">{esc(a)}</span>' for a in r['agents_involved'])}</p>
    <h4>Delegation sequence</h4>
    <ol class="flow">{seq}</ol>
    <h4>MCP tools and contributions</h4>
    <table><thead><tr><th>Agent</th><th>MCP tools called</th><th>What it reported</th></tr></thead><tbody>{tool_rows}</tbody></table>
    <h4>Decision and human approvals</h4>
    <p><strong>Boss ({esc(dec.get('final_status', ''))} at end of run):</strong> {esc(dec.get('decision', ''))}</p>
    <ul>{appr}</ul>
    <h4>Drafts saved (never sent)</h4>
    <ul class="drafts">{drafts_html}</ul>
    <h4>Final outcome</h4>
    <p><strong>Ticket status: {esc(r['final_status'])}.</strong></p>
    <h4>Expected vs actual</h4>
    <ul>{dev}</ul>
  </div>"""


EXPECTED_FIRST = {101: "Inventory", 102: "Facilities", 103: "Accounting"}


def deviations(r: dict) -> list[str]:
    out = []
    tid = r["ticket_id"]
    expected_agents = {101: {"Boss", "Inventory", "Accounting", "Customer Service"},
                       102: {"Boss", "Facilities", "Accounting"},
                       103: {"Boss", "Accounting", "Inventory", "Customer Service"}}[tid]
    got = set(r["agents_involved"])
    out.append("Same agents as expected." if got == expected_agents else
               f"Agents differ from expected: extra {sorted(got - expected_agents) or 'none'}, missing {sorted(expected_agents - got) or 'none'}.")
    peer = [d for d in r["delegations"] if d["from"] != "Boss"]
    if peer:
        out.append("Peer delegation happened as predicted: " + "; ".join(f"{d['from']} → {d['to']}" for d in peer) + ".")
    tools = [c["tool"] for c in r["mcp_tool_calls"]]
    if tid == 101:
        out.append("Invoice-before-PO ordering held: request_payment came before create_purchase_order."
                   if "request_payment" in tools and "create_purchase_order" in tools and tools.index("request_payment") < tools.index("create_purchase_order")
                   else "Invoice/PO ordering differed from the plan.")
    if tid == 102:
        extra = [t for t in tools if t == "get_business_date"]
        if extra:
            out.append("Facilities also called get_business_date, which was redundant because get_lease_payment_status already returns the business date. It cost tokens but didn't affect the outcome.")
    if tid == 103:
        out.append("No purchase order was created, as expected: the shop couldn't fund the $264 restock."
                   if "create_purchase_order" not in tools else "A purchase order was attempted, which the plan did not expect.")
        body = " ".join(d["body"] for d in r["drafts"])
        if "September 5" in body or "2026-09-05" in body:
            out.append("Deviation: the Yale AI Club draft mentions an estimated September 5 arrival 'if a restock is approved', "
                       "but no restock was queued. The plan expected no date for the remaining 12. A human should edit that line before sending.")
    out.append("Expected ending: awaiting human approval, then resolved after the operator decided every request. Actual: "
               f"{r['final_status']} once all {len(r['human_approvals'])} request(s) were decided.")
    return out


page = DESK.read_text(encoding="utf-8")
for tid in (101, 102, 103):
    pattern = re.compile(rf'<div class="actual(?: actual--filled)?" data-ticket="{tid}">.*?</div>(?=\s*</section>)', re.S)
    replacement = actual_html(results[tid], EXPECTED_FIRST[tid], deviations(results[tid]))
    page, n = pattern.subn(lambda _m: replacement, page)
    if n != 1:
        print(f"could not find the Actual block for {tid}")
        sys.exit(1)

# ------------------------------------------------------------- HTML: Cash
rows = []
for tid in (102, 101, 103):
    tr = by_ticket_cash[tid]
    if not tr:
        rows.append(f"<tr><td>#{tid}</td><td colspan='4'>No payment or purchase</td><td>$0.00</td><td>-</td></tr>")
    for a in tr:
        rows.append(
            f"<tr><td>#{tid}</td><td>{esc(a['kind'].replace('_', ' '))}: {esc(a['payee'])}<br><span class='muted'>{esc(a['description'])}</span></td>"
            f"<td>{esc(a['reason'])}</td><td>{'Yes, ' + esc(a['decided_by']) if a['decided_by'] else 'No'}"
            f"{f' · payment #{a["payment_id"]}' if a['payment_id'] else ''}</td>"
            f"<td>{money(a['amount']) if a['payment_id'] else '$0.00 (discount, no cash)'}</td>"
            f"<td>{money(-a['moved']) if a['moved'] else '$0.00'}</td><td>{money(a['balance_after'])}</td></tr>")
per_ticket = "".join(
    f"<tr><td>#{tid}</td><td>{money(-sum(a['moved'] for a in by_ticket_cash[tid]))}</td></tr>" for tid in (101, 102, 103))
cash_html = f"""<section role="tabpanel" id="panel-cash" aria-labelledby="tab-cash">
  <h2>Cash reconciliation</h2>
  <p class="sub">Checking account, business date {esc(cash['business_date'])}. Outflows only: no revenue or incoming cash was assumed. Built from the live API and checked against the <code>payments</code> and <code>cash_accounts</code> tables.</p>

  <div class="card"><dl class="facts">
    <div><dt>Starting balance</dt><dd>{money(start_balance)}<br><span class="muted">cash_accounts.checking right after reset (audit #{last_reset['id']})</span></dd></div>
    <div><dt>Total approved payments</dt><dd>{money(total_paid)}<br><span class="muted">{len(paid)} payments, all human-approved</span></dd></div>
    <div><dt>Calculated ending</dt><dd>{money(calc_end)}<br><span class="muted">{esc(reconciliation['formula'])}</span></dd></div>
    <div><dt>Database ending</dt><dd>{money(db_balance)}<br><span class="muted">cash_accounts.checking now</span></dd></div>
  </dl></div>
  <p class="ok">✓ Calculated and database ending balances match exactly ({money(calc_end)} = {money(db_balance)}). The payments table holds {len(db_payments)} rows totalling {money(db_total)}, the same as the executed approval requests. Every payment has a named human approver, and no request is left pending.</p>

  <h3>Cash changes in execution order</h3>
  <table>
    <thead><tr><th>Ticket</th><th>Payment / purchase</th><th>Reason (from the requesting agent)</th><th>Human approval</th><th>Amount</th><th>Change</th><th>Balance after</th></tr></thead>
    <tbody>
      <tr><td colspan="6"><strong>Starting balance</strong></td><td><strong>{money(start_balance)}</strong></td></tr>
      {''.join(rows)}
      <tr><td colspan="5"><strong>Ending balance</strong></td><td><strong>{money(-total_paid)}</strong></td><td><strong>{money(calc_end)}</strong></td></tr>
    </tbody>
  </table>

  <h3>Net cash change by ticket</h3>
  <table><thead><tr><th>Ticket</th><th>Change to checking</th></tr></thead><tbody>{per_ticket}</tbody></table>
  <p class="muted">Ticket 103's only approval was a 15% discount on 8 hoodies (discount value $69.60), a price decision with no cash outflow, so its cash change is $0.00. The $264 restock for the other 12 hoodies was never created: after rent, invoice 501 and the tee order, only $152 remained.</p>

  <h3>Reconciliation</h3>
  <p><code>Ending cash = Starting cash − Total approved payments = {esc(reconciliation['formula'])}</code></p>
</section>"""
page, n = re.subn(r'<section role="tabpanel" id="panel-cash".*?</section>', lambda _m: cash_html, page, flags=re.S)
if n != 1:
    print("could not find the Cash panel")
    sys.exit(1)

if ".actual--filled" not in page:
    page = page.replace("</style>", """  .actual--filled { border-style: solid; border-color: #9fc3ef; background: #f7fbff; padding: 6px 20px 14px; }
  .actual--filled h4:first-of-type { margin-top: 10px; }
  .runmeta { font-size: 13px; color: var(--muted); margin: 10px 0 0; }
  blockquote { margin: 6px 0 4px; padding: 8px 12px; background: #fff; border-left: 3px solid var(--line); white-space: pre-wrap; font-size: 13px; color: var(--muted); }
  ul.drafts { list-style: none; padding-left: 0; }
  .ok { background: #e8f6ee; color: #1d6b40; border-radius: 6px; padding: 10px 14px; font-size: 14px; }
  .muted { color: var(--muted); font-size: 13px; }
</style>""", 1)
DESK.write_text(page, encoding="utf-8")
print(json.dumps({"start": start_balance, "paid": total_paid, "end_calc": calc_end, "end_db": db_balance, "checks": checks,
                  "first_agents": {t: results[t]["first_agent_contacted_by_boss"] for t in results},
                  "statuses": {t: results[t]["final_status"] for t in results}}, indent=1))

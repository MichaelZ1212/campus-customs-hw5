"""Problem 9: build output/resolved_board.html from the three real dashboard
screenshots in output/screenshots/ and the verified output/resolved_tickets.json.
Images are embedded (base64) so the HTML is a single file that opens anywhere.

Usage:  python scripts/build_resolved_board.py
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
data = json.loads((OUT / "resolved_tickets.json").read_text(encoding="utf-8"))
rec = data["cash_reconciliation"]
esc = html.escape


def money(x: float) -> str:
    return f"${x:,.2f}"


sections = []
for t in data["tickets"]:
    tid = t["ticket_id"]
    img = OUT / "screenshots" / f"ticket_{tid}_resolved.jpg"
    b64 = base64.b64encode(img.read_bytes()).decode("ascii")
    paid = [a for a in t["human_approvals"] if a["payment_id"]]
    approvals = "".join(
        f"<li>#{a['approval_request_id']} {esc(a['kind'].replace('_', ' '))} · {esc(a['payee'])} · {money(a['amount'])} · "
        f"{'paid (payment #' + str(a['payment_id']) + ')' if a['payment_id'] else 'approved, no cash moved'}</li>"
        for a in t["human_approvals"])
    sections.append(f"""
  <section class="ticket" id="ticket-{tid}">
    <header>
      <h2>Ticket {tid}: {esc(t['subject'])}</h2>
      <span class="pill">✓ {esc(t['final_status'].capitalize())}</span>
    </header>
    <p class="meta">{esc(t['type'].replace('_', ' '))} · requester {esc(t['requester'])} · run <code>{esc(t['run_id'])}</code></p>
    <figure>
      <img src="data:image/jpeg;base64,{b64}" alt="Campus Customs dashboard with ticket {tid} selected after resolution">
      <figcaption>Ticket {tid}, actual React dashboard capture (<code>http://localhost:5174</code> → API <code>:8000</code>) after the run and approvals. Source file: <code>output/screenshots/{img.name}</code></figcaption>
    </figure>
    <div class="facts">
      <div><h3>Agents</h3><p>{' → '.join(esc(a) for a in t['agents_involved'])}</p>
        <p class="small">Boss contacted <strong>{esc(t['first_agent_contacted_by_boss'])}</strong> first · {len(t['delegations'])} delegations · {len(t['mcp_tool_calls'])} MCP tool calls</p></div>
      <div><h3>Human approvals</h3><ul>{approvals or '<li>None</li>'}</ul></div>
      <div><h3>Cash effect</h3><p class="big">{'-' + money(sum(a['amount'] for a in paid)) if paid else '$0.00'}</p></div>
    </div>
  </section>""")

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Customs: Resolved Board</title>
<style>
  body {{ margin: 0; font: 15px/1.55 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1f2933; background: #f3f5f8; }}
  .top {{ background: #00356b; color: #fff; padding: 22px 32px; }}
  .top h1 {{ margin: 0; font-size: 22px; }}
  .top p {{ margin: 4px 0 0; color: #c9d6e8; font-size: 13px; }}
  nav {{ display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }}
  nav a {{ color: #fff; text-decoration: none; background: rgba(255,255,255,.1); padding: 5px 12px; border-radius: 6px; font-size: 13px; }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px 60px; }}
  .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .summary div {{ background: #fff; border: 1px solid #d9dee5; border-radius: 8px; padding: 12px 16px; }}
  .summary dt {{ font-size: 12px; color: #5f6b7a; text-transform: uppercase; letter-spacing: .04em; }}
  .summary dd {{ margin: 2px 0 0; font-size: 20px; font-weight: 700; }}
  .ticket {{ background: #fff; border: 1px solid #d9dee5; border-radius: 10px; padding: 20px 24px; margin-bottom: 28px; }}
  .ticket header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
  .ticket h2 {{ margin: 0; color: #00356b; font-size: 19px; }}
  .pill {{ background: #e8f6ee; color: #1d6b40; border: 1px solid #9ed6b5; border-radius: 999px; padding: 2px 12px; font-weight: 600; font-size: 13px; }}
  .meta {{ color: #5f6b7a; font-size: 13px; margin: 4px 0 12px; }}
  figure {{ margin: 0; }}
  img {{ width: 100%; border-radius: 8px; border: 1px solid #c8d0db; display: block; }}
  figcaption {{ font-size: 12px; color: #5f6b7a; margin-top: 6px; }}
  .facts {{ display: grid; grid-template-columns: 2fr 2fr 1fr; gap: 18px; margin-top: 14px; }}
  .facts h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #5f6b7a; margin: 0 0 4px; }}
  .facts p, .facts ul {{ margin: 0; font-size: 14px; }}
  .facts ul {{ padding-left: 18px; }}
  .small {{ font-size: 12px !important; color: #5f6b7a; margin-top: 4px !important; }}
  .big {{ font-size: 22px !important; font-weight: 700; }}
  code {{ font-size: 12px; background: #eef2f7; padding: 1px 5px; border-radius: 4px; }}
  @media (max-width: 800px) {{ .summary, .facts {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<div class="top">
  <h1>Campus Customs: Resolved Board</h1>
  <p>Final state after the full run on business date {esc(data['business_date'])}. Screenshots are real captures of the React dashboard; figures come from <code>output/resolved_tickets.json</code>.</p>
  <nav><a href="#ticket-101">Ticket 101</a><a href="#ticket-102">Ticket 102</a><a href="#ticket-103">Ticket 103</a></nav>
</div>
<main>
  <dl class="summary">
    <div><dt>Tickets resolved</dt><dd>{sum(t['final_status'] == 'resolved' for t in data['tickets'])} / {len(data['tickets'])}</dd></div>
    <div><dt>Starting balance</dt><dd>{money(rec['starting_balance'])}</dd></div>
    <div><dt>Approved payments</dt><dd>{money(rec['total_approved_payments'])}</dd></div>
    <div><dt>Ending balance</dt><dd>{money(rec['database_ending_balance'])}</dd></div>
  </dl>
  {''.join(sections)}
  <p class="meta">Run order 102 → 101 → 103 (the Boss's priority). Approve clicks were made in the dashboard by Claude Code at the user's instruction; they're recorded as <code>approved_by = "Michael Zheng (via Claude Code)"</code>.</p>
</main>
</body>
</html>
"""
(OUT / "resolved_board.html").write_text(page, encoding="utf-8")
print("wrote", OUT / "resolved_board.html", f"({len(page) // 1024} KB)")

# Campus Customs MCP Server

## Purpose

This server is the only data layer for the Campus Customs multi-agent system. It exposes the shop's operational database as [MCP](https://modelcontextprotocol.io) tools, so the five AI agents get structured, database-backed answers and make changes only through rule-checked tools. It is built with **FastMCP** (`mcp.server.fastmcp`, from the `mcp` 1.x SDK).

## Database

| File | Used by the server? |
|---|---|
| `data/campus_customs_new.db` | **Yes.** The working copy. Every tool reads and writes it. |
| `data/campus_customs.db` | **Read only by `reset_working_database`**, which copies it over the working copy. Never modified. |

The paths are set in `db.py` and can be overridden with `CAMPUS_CUSTOMS_DB` and `CAMPUS_CUSTOMS_ORIGINAL_DB`. `db.py` also creates three workflow tables in the working copy only: `approval_requests`, `purchase_orders` and `message_drafts`.

Every tool takes the business date from `desk.date_today`, never the system clock. Each tool call runs in one transaction that rolls back on error.

## Tools (19)

### Read tools from Problem 3 (`tools.py`)

| Tool | Returns | Ticket |
|---|---|---|
| `check_stock_and_vendor_status(sku, size, qty_needed=1)` | On-hand stock and shortfall, restock cost, invoices mentioning the SKU, and every vendor's lead time, unpaid invoices and `can_accept_new_orders` | 101 |
| `get_lease_payment_status(lease_id)` | Lease terms, days until due, rent payments recorded, cash before and after rent, other unpaid invoices | 102 |
| `evaluate_bulk_discount(sku, size, qty, discount_pct)` | Stock and shortfall, other sizes, restock cost, break-even discount, margins at the requested discount | 103 |

### Agent workflow tools from Problem 5 (`workflow_tools.py`)

| Tool | Does |
|---|---|
| `get_business_date()` | `desk.date_today` |
| `list_open_tickets()` | All unresolved tickets (Boss triage) |
| `get_ticket(ticket_id)` | One ticket with the SKU's catalogue `product_name`, its approval requests, POs and drafts |
| `list_tickets()` | Every ticket (any status) with pending-approval and draft counts (dashboard API) |
| `list_message_drafts(ticket_id=None)` | Full text of saved drafts (dashboard API) |
| `get_cash_position(account="checking")` | Balance, amount committed to pending requests, available cash, unpaid invoices, rent due within 30 days |
| `get_vendor_status(vendor_id)` | Lead time, unpaid invoices (with days overdue and any pending payment request), whether it can take new orders |
| `list_approval_requests(status=None, ticket_id=None)` | Queued, executed and rejected requests |
| `request_payment(kind, ref_id, ticket_id, reason, requested_by, account="checking")` | Queues an `invoice` or `rent` payment for human approval. The amount comes from the DB; no duplicates; refused if uncommitted cash can't cover it |
| `create_purchase_order(ticket_id, vendor_id, sku, size, qty, reason, requested_by)` | Drafts a PO at unit cost with delivery from `lead_days` and queues its payment. Refused if the vendor has unpaid invoices not queued for payment, or cash is short |
| `request_discount_approval(ticket_id, sku, qty, discount_pct, reason, requested_by)` | Queues a discount for human sign-off; refused below unit cost |
| `save_message_draft(ticket_id, audience, recipient, subject, body, author)` | Saves a customer, vendor, landlord or internal message as a draft. Never sent. Customer drafts are refused if they mention internal operations (invoices, approvals, purchase orders, vendors, cash…) or a SKU code, or omit the catalogue product name |
| `update_ticket_status(ticket_id, status, note, updated_by)` | Sets status and appends a note; can't mark `resolved` while approvals are pending |

None of these moves money.

### HUMAN-ONLY tools (`human_tools.py`)

These are in no agent's allowlist. A person calls them through the API (`POST /api/approvals/{id}/approve|reject`, `POST /api/reset`) or `python -m backend.approvals`; reset never runs implicitly.

| Tool | Does |
|---|---|
| `execute_approved_payment(approval_request_id, approved_by)` | The only code path that moves money. It re-checks that the request is still pending, the invoice is unpaid, and the PO vendor has no unpaid invoices, and that the balance stays ≥ 0 (otherwise the request is auto-rejected). It then updates `cash_accounts`, `payments`, `invoices`, `leases`, `purchase_orders` and the ticket |
| `reject_approval_request(approval_request_id, decided_by, note="")` | Rejects a pending request; a rejected PO is cancelled |

Any decision (approve, reject or system rejection) marks that ticket's existing drafts `needs_review`, because they were written before the decision.
| `reset_working_database()` | Restores the working copy from the original |

Errors such as unknown records, bad input or a business-rule refusal come back as MCP tool errors with a readable message.

## Layout

```
mcp_server/
├── db.py              # working-DB path, workflow tables, reset, connection helper, business date
├── tools.py           # Problem 3 read tools
├── workflow_tools.py  # Problem 5 agent tools
├── human_tools.py     # human-only payment execution, rejection, reset
└── server.py          # FastMCP instance; registers each module's TOOLS list
```

To add a tool, write a typed function with a docstring in the right module and add it to that module's `TOOLS`.

## Running and testing

```bash
python -m mcp_server.server
```

The server runs over stdio from the project root. `.mcp.json` registers it for Claude Code, and the backend launches it itself (`backend/config.py`). `python scripts/test_mcp_rules.py` runs 22 business-rule checks over a real stdio connection. It resets the working DB before and after.

## Place in the architecture

```
human ──▶ backend/approvals.py ──(HUMAN-ONLY tools)──┐
                                                     ▼
backend/orchestrator.py ──▶ Boss ⇄ Inventory ⇄ Accounting ⇄ Facilities ⇄ Customer Service
                              (each agent sees only its allowlisted tools)
                                                     │ MCP over stdio
                                                     ▼
                                     MCP server (this) ──SQL──▶ data/campus_customs_new.db
```

The backend has no database code of its own. All shop data flows through this server.

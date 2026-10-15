# Campus Customs Harness

Technical overview of the Campus Customs multi-agent operations system: a FastMCP server over SQLite, five PydanticAI agents on `gpt-6-luna` (via Portkey), a FastAPI backend and a React dashboard. A human approves every payment.

```
React dashboard (frontend/, Vite :5173)
        │  HTTP/JSON
        ▼
FastAPI backend (backend/main.py, :8000) ── audit trail (output/audit_trail.json, append-only)
        │  one long-lived MCP connection (backend/runtime.py)
        ▼
Agents: Boss ⇄ Inventory ⇄ Accounting ⇄ Facilities ⇄ Customer Service   (PydanticAI, gpt-6-luna)
        │  MCP tool calls (per-agent allowlists; HUMAN-ONLY tools excluded)
        ▼
MCP server (mcp_server/, FastMCP, stdio) ──SQL──▶ data/campus_customs_new.db   (original data/campus_customs.db never modified)
```

**Run it** (needs `PORTKEY_API_KEY` set):

```bash
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.

| Topic | Section |
|---|---|
| Database tables and their purposes | 1 (original tables), 1.5 (workflow tables) |
| Open tickets and what they need | 2, 3 |
| MCP tools and the tables they access | 4 (original three), 6 (all 19) |
| The five agents and their responsibilities | 5 |
| Agent delegation, collaboration, token safeguards | 7 |
| Human approval, payment safety, cash balance protection | 8 |
| Audit logging | 9 |
| FastAPI endpoints | 10 |
| React dashboard | 11 |
| Final full run: results and cash reconciliation | 12 |

---

## 1. Database

### 1.1 Files

| File | Role |
|---|---|
| `data/campus_customs.db` | **Original.** Extracted from `data.zip` (byte-identical, MD5 `46effb90…`; SQLite `integrity_check` = ok). Never written to. Used to reset the system. |
| `data/campus_customs_new.db` | **Working copy.** Starts as an exact copy of the original (same MD5). All ticket processing and every future database update happens here. |

To reset, overwrite the working copy with the original:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

### 1.2 Overview

The database is a one-day snapshot of a small campus retail shop on business date **2026-08-31**. It has 9 tables in four groups:

| Group | Tables | Main agent |
|---|---|---|
| Control | `desk`, `tickets` | Boss |
| Products | `inventory`, `pricing`, `vendors` | Inventory (vendors shared with Accounting) |
| Money | `cash_accounts`, `invoices`, `payments` | Accounting |
| Facilities | `leases` | Facilities |

There are no customer or user tables, no sales history and no incoming cash. The data exists to give the agents operational decisions to make under a tight cash limit.

### 1.3 Relationships

```
desk ── date_today ──▶ business date for every due/overdue calculation

tickets ── lease_id ───▶ leases                          (FK)
   │   └── invoice_id ─▶ invoices ── vendor_id ─▶ vendors   (FK, FK)
   └── sku + size ─ ─ ─▶ inventory (sku, size)           (by value, no FK)
                            └── sku ─ ─ ─▶ pricing        (by value, no FK)

payments ── kind + ref_id ─ ─▶ invoices or leases        (by value, no FK)
payments ── account ─ ─ ─ ─ ─▶ cash_accounts.name        (by value, no FK)
vendors ─ ─ specialty ─ ─ ─ ─▶ products                  (inferred from text)
```

Solid arrows are real foreign keys. Dashed links are matched by value, so the application has to validate them.

### 1.4 Tables

#### `desk`

| Column | Type | Notes |
|---|---|---|
| `date_today` | TEXT NOT NULL | `2026-08-31` |
| `notes` | TEXT | NULL |

**Contains:** one row holding the shop's official current date.
**Why it matters:** agents must judge "overdue" and "due in N days" against this date rather than the computer clock, so every agent reads it first.

#### `tickets`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | 101–103 |
| `type` | TEXT NOT NULL | `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT NOT NULL | Free-text name; no contact details |
| `subject` | TEXT NOT NULL | One-line summary |
| `sku` | TEXT | Product, matched to `inventory` by value |
| `size` | TEXT | Product size |
| `qty` | INTEGER | Units requested |
| `lease_id` | INTEGER FK → `leases.id` | Facility tickets |
| `invoice_id` | INTEGER FK → `invoices.id` | Ticket depends on a vendor invoice |
| `status` | TEXT NOT NULL | All `open` |
| `notes` | TEXT | Original request text |
| `created_at` | TEXT NOT NULL | ISO timestamp with `-04:00` offset |

**Contains:** the incoming business requests the system has to resolve.
**Why it matters:** this is the Boss agent's work queue, and `type` plus the linked IDs tell it which specialist agents to involve.

#### `inventory`

| Column | Type | Notes |
|---|---|---|
| `sku` | TEXT NOT NULL | PK part 1 |
| `name` | TEXT NOT NULL | Product name |
| `size` | TEXT NOT NULL | PK part 2 (S/M/L/XL or OS = one size) |
| `qty` | INTEGER NOT NULL | Units on hand |
| `location` | TEXT NOT NULL | Aisle |

| SKU | Name | Qty by size | Location |
|---|---|---|---|
| CC-HOOD-NAVY | Basic Hoodie Big Yale | S 4 · **M 8** · L 14 · XL 6 | Aisle A |
| CC-TEE-WHITE | Classic Bulldog Tee | **S 0** · M 5 · L 3 · XL 2 | Aisle B |
| CC-HAT-BLUE | Yale Cap | OS 40 | Aisle C |
| CC-MUG-CREST | Crest Mug | **OS 0** | Aisle D |

**Contains:** units on hand for each product and size.
**Why it matters:** the Inventory agent uses it to confirm availability and size up shortages before anyone promises a customer delivery or orders stock.

#### `pricing`

| Column | Type | Notes |
|---|---|---|
| `sku` | TEXT PK | One row per SKU (not per size) |
| `unit_cost` | REAL NOT NULL | What the shop pays the vendor |
| `list_price` | REAL NOT NULL | Normal selling price |

| SKU | Cost | List | Margin |
|---|---|---|---|
| CC-HOOD-NAVY | 22.00 | 58.00 | 36.00 (62%) |
| CC-TEE-WHITE | 8.00 | 28.00 | 20.00 (71%) |
| CC-HAT-BLUE | 6.00 | 22.00 | 16.00 (73%) |
| CC-MUG-CREST | 3.50 | 14.00 | 10.50 (75%) |

**Contains:** cost and selling price for each product.
**Why it matters:** Accounting uses `unit_cost` to price restock orders and the margin to decide whether a discount request is acceptable.

#### `vendors`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | |
| `specialty` | TEXT NOT NULL | Only clue to which products they supply |
| `lead_days` | INTEGER NOT NULL | Days from order to delivery |

| id | Name | Specialty | Lead days |
|---|---|---|---|
| 1 | Bulldog Print Co | apparel reprint | 5 |
| 2 | Elm City Gifts | mugs and small goods | 3 |
| 3 | QuickShip CT | local courier | 1 |

**Contains:** suppliers, what they supply and how long they take.
**Why it matters:** the Inventory agent estimates restock dates as business date + `lead_days`. Combined with `invoices`, this shows whether a vendor is allowed to take a new order.

#### `invoices`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `vendor_id` | INTEGER NOT NULL FK → `vendors.id` | |
| `amount` | REAL NOT NULL | |
| `due_date` | TEXT NOT NULL | |
| `status` | TEXT NOT NULL | Only `open` appears |
| `description` | TEXT | |

| id | Vendor | Amount | Due | Status | Description |
|---|---|---|---|---|---|
| 501 | Bulldog Print Co | 840.00 | 2026-08-28 | open | Rush reprint CC-TEE-WHITE S |

**Contains:** bills the shop owes vendors. Invoice 501 is **3 days overdue**.
**Why it matters:** an unpaid invoice blocks that vendor from new orders, so Accounting must clear it before Inventory can restock from them.

#### `leases`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `space_name` | TEXT NOT NULL | Chapel Street shop |
| `landlord` | TEXT NOT NULL | Elm City Properties |
| `monthly_rent` | REAL NOT NULL | 2400.00 |
| `next_due` | TEXT NOT NULL | 2026-09-02 (2 days away) |
| `notes` | TEXT | NULL |

**Contains:** the shop's rental agreement and when the next rent is due.
**Why it matters:** the Facilities agent uses it to verify a landlord's rent notice and hands the amount to Accounting for a payment request.

#### `cash_accounts`

| Column | Type | Notes |
|---|---|---|
| `name` | TEXT PK | `checking` |
| `balance` | REAL NOT NULL | 3400.00 |
| `date` | TEXT NOT NULL | 2026-08-31 |

**Contains:** the shop's only bank account and its balance.
**Why it matters:** Accounting checks it before every payment so no transaction can push the balance below zero. No revenue comes in, so this is all the money there is.

#### `payments`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `kind` | TEXT NOT NULL | What was paid, e.g. invoice or rent |
| `ref_id` | INTEGER | ID in the table `kind` refers to (no FK) |
| `amount` | REAL NOT NULL | |
| `account` | TEXT NOT NULL | Which cash account paid |
| `paid_at` | TEXT NOT NULL | Business date of payment |
| `approved_by` | TEXT NOT NULL | Human who approved it |

**Contains:** the ledger of executed payments. It's **empty**, so nothing has been paid.
**Why it matters:** it's the record of every approved outflow. Because `approved_by` is NOT NULL, the schema itself expects a human approver on every payment.

---

### 1.5 Workflow tables (working copy only)

The original schema has nowhere to keep approvals, orders or drafts. `mcp_server/db.py` creates these in `data/campus_customs_new.db` with `CREATE TABLE IF NOT EXISTS`; a reset removes them, and they're recreated empty on the next tool call.

| Table | Columns | Purpose |
|---|---|---|
| `approval_requests` | `id, ticket_id, kind (invoice/rent/purchase_order/discount), ref_id, amount, account, reason, requested_by, status (pending/executed/rejected), decided_by, decision_note, payment_id, created_at, decided_at` | The human approval queue. Agents write `pending` rows; only `execute_approved_payment` / `reject_approval_request` (human-only) change their status |
| `purchase_orders` | `id, ticket_id, vendor_id, sku, size, qty, unit_cost, total, expected_date, status (awaiting_approval/placed/cancelled), created_at` | Restock orders priced at `pricing.unit_cost`, with delivery at business date + `vendors.lead_days` |
| `message_drafts` | `id, ticket_id, audience, recipient, subject, body, author, status (draft / needs_review), created_at` | Customer, landlord and vendor messages for human review; nothing is ever sent. A draft becomes `needs_review` when an approval on its ticket is decided after it was written |

---

## 2. Open tickets

### Ticket 101: Customer order (Tauhid Zaman)

> Needs a Classic Bulldog Tee (`CC-TEE-WHITE`) in size S, qty 1. Linked to invoice 501.

| Related table | What it shows |
|---|---|
| `inventory` | CC-TEE-WHITE / S has **qty 0**, so it can't ship from stock. |
| `invoices` | Linked invoice 501 is an $840 **rush reprint of this exact item** to Bulldog Print Co, 3 days overdue and unpaid. |
| `vendors` | Bulldog Print Co (apparel) has a 5-day lead time and is blocked while 501 is unpaid. |
| `pricing` | Cost $8.00, list $28.00. Restocking one unit costs $8. |
| `cash_accounts` | $3,400 is enough to pay the invoice and the $8 restock. |
| `payments` | No payment for 501 exists yet. |

**Agents need:** stock for S, the invoice status, the vendor's lead time and payment status, the cash balance, and the cost of a restock. The likely path is to pay invoice 501 (with human approval), then reorder one tee. The earliest arrival is 2026-09-05. Customer Service drafts an update for Tauhid.

### Ticket 102: Rent notice (Elm City Properties)

> Email: shop rent due in 2 days. Linked to lease 1.

| Related table | What it shows |
|---|---|
| `leases` | Chapel Street shop, $2,400/month, next due **2026-09-02**. This matches "due in 2 days" from 8/31. |
| `cash_accounts` | $3,400 covers it. |
| `payments` | No rent payment recorded yet. |

**Agents need:** the lease terms, the due date relative to the business date, and the cash balance. Facilities checks the notice against the lease, and Accounting prepares a $2,400 rent payment for human approval. After payment, `next_due` should move to 2026-10-02.

### Ticket 103: Price override (Yale AI Club)

> 20 Basic Hoodies (`CC-HOOD-NAVY`) in size M, asking for a bulk discount.

| Related table | What it shows |
|---|---|
| `inventory` | Size M has **8**, a shortfall of **12**. (S 4, L 14, XL 6 if sizes are flexible.) |
| `pricing` | Cost $22, list $58. At 15% off ($49.30) the margin is still about 55%. The break-even discount is about 62%. |
| `vendors` | Restock would come from Bulldog Print Co (5 days), which is blocked until invoice 501 is paid. |
| `cash_accounts` | Restocking 12 × $22 = **$264**. |

**Agents need:** stock for M, margin at the proposed discount, vendor status and lead time, and the cash left after other obligations. The cash table below shows a full restock **doesn't fit**, so the Boss has to choose among selling 8 now, offering other sizes, or deferring the rest. Customer Service then drafts the reply.

### Cash across all three tickets

| Outflow | Amount | Balance |
|---|---|---|
| Starting checking | | 3,400.00 |
| Invoice 501 (unblocks the vendor; overdue) | 840.00 | 2,560.00 |
| Rent, lease 1 (due 9/2) | 2,400.00 | 160.00 |
| 1 tee S restock (ticket 101) | 8.00 | **152.00** |
| 12 hoodie M restock (ticket 103) | 264.00 | **−112.00 ✗** |

Every item except the hoodie restock fits. Paying all four would overdraw the account, which the cash-protection rule forbids.

---

## 3. Summary: how the agents use the data

| Agent | Reads | Decides or prepares |
|---|---|---|
| **Boss** | `desk`, `tickets` | Classifies each ticket by `type`, routes it to specialists, sets priority (rent and overdue invoice before discretionary restocks) and closes tickets. |
| **Inventory** | `inventory`, `vendors`, `pricing`, `invoices` | Finds shortages by SKU and size, picks a vendor by specialty, checks the vendor has no unpaid invoices, and estimates arrival as `date_today + lead_days`. |
| **Accounting** | `cash_accounts`, `invoices`, `payments`, `pricing` | Checks the cash available after all commitments, evaluates margins and discounts, and prepares invoice, rent and purchase-order payments for **human approval**. Writes to `payments` only after approval. |
| **Facilities** | `leases`, `tickets` | Verifies rent notices against the lease and asks Accounting for payment. |
| **Customer Service** | `tickets`, plus answers from the other agents | Drafts replies to requesters. They have no contact details, so replies stay drafts and nothing is sent. |

**Data quirks to handle:**
- Dates are ISO text. `tickets.created_at` has a timezone offset; the other dates don't.
- Only `tickets → leases`, `tickets → invoices` and `invoices → vendors` are real foreign keys. Other links are by value and need validation.
- Vendors map to products only through the free-text `specialty`.
- `invoices.status` only shows `open`, and `payments` is empty, so the system defines what "paid" and the payment `kind` values look like.
- The schema has nowhere to store approvals, message drafts or agent conversations. Later problems will need extra tables in the working copy only.
- The Crest Mug is also out of stock (OS 0) with no ticket. Elm City Gifts has no unpaid invoices and could restock it if asked.

---

## 4. MCP server

A FastMCP server in `mcp_server/` reads `data/campus_customs_new.db` only. It has three read-only tools, one for each open ticket. Details are in `mcp_server/README.md`.

### 4.1 `check_stock_and_vendor_status(sku, size, qty_needed=1)` → ticket 101

**Purpose:** decide whether a customer order can ship from stock, and if not, whether it can be restocked and when.

**Reads:** `desk`, `inventory`, `pricing`, `vendors`, `invoices`

**How it helps with ticket 101:** Tauhid Zaman wants one Classic Bulldog Tee in size S. Called with `("CC-TEE-WHITE", "S", 1)`, the tool returns:
- `on_hand: 0`, `shortfall: 1` and `restock_cost_for_shortfall: 8.0`.
- Invoice 501 ("Rush reprint CC-TEE-WHITE S", $840, open), found by searching invoice descriptions for the SKU. This is the same invoice the ticket links to.
- Bulldog Print Co, the apparel vendor: 5 lead days, invoice 501 is **3 days overdue**, and `can_accept_new_orders: false`.
- An earliest delivery of 2026-09-05 if ordered today.

That gives the agents the full chain: no stock, the apparel vendor is blocked by an unpaid invoice, so paying 501 is the precondition for restocking the tee.

### 4.2 `get_lease_payment_status(lease_id)` → ticket 102

**Purpose:** verify a rent notice against the lease and check whether the shop can pay it.

**Reads:** `desk`, `leases`, `payments`, `cash_accounts`, `invoices`, `tickets`

**How it helps with ticket 102:** Elm City Properties emailed that rent is "due in 2 days." Called with `lease_id=1`, the tool returns:
- The Chapel Street shop lease: $2,400, `next_due` 2026-09-02, `days_until_due: 2`. This confirms the email against the database.
- `rent_payments_recorded: []`, so the rent hasn't been paid.
- `checking` at $3,400 with `can_cover_rent: true` and `balance_after_rent: 1000.0`.
- Invoice 501 ($840) as another unpaid obligation competing for the same cash.

Facilities can verify the notice, and Accounting can see the rent fits but leaves only $160 after the invoice.

### 4.3 `evaluate_bulk_discount(sku, size, qty, discount_pct)` → ticket 103

**Purpose:** judge a bulk price-override request on both margin and availability.

**Reads:** `desk`, `inventory`, `pricing`, `cash_accounts`

**How it helps with ticket 103:** the Yale AI Club wants 20 Basic Hoodies in size M at a bulk discount. The ticket doesn't name a percentage, so the agent picks one to test. Called with `("CC-HOOD-NAVY", "M", 20, 15)`, the tool returns:
- `on_hand: 8`, `shortfall: 12`, `restock_cost_for_shortfall: 264.0`.
- Other sizes on hand: S 4, L 14, XL 6, in case the club can mix sizes.
- List $58, cost $22, a 62.1% margin at list price, and a **break-even discount of 62.1%**.
- At 15% off: $49.30 per unit, a 55.4% margin, $986 revenue, $546 margin and $174 of discount given.
- The checking balance, so the $264 restock can be compared with the cash left after rent and invoice 501.

Accounting can approve or counter the discount on margin, and Inventory and the Boss can see that only 8 of the 20 can ship now.

---

## 5. Agent team (Problem 5)

Five PydanticAI agents live in `backend/`. All of them use **`gpt-6-luna` through Portkey** (`backend/config.py`), authenticated with the `PORTKEY_API_KEY` environment variable. Calls go through the OpenAI Responses API, because `gpt-6-luna` rejects function tools on `/chat/completions`. Reasoning effort is set to `low` to keep tokens down. No other model appears anywhere in the code.

| Agent | Responsibilities | MCP tools (allowlist) | Prompt |
|---|---|---|---|
| **Boss** | Triages all open tickets, sets priority, delegates, makes the final decision, and is the **only** agent that changes ticket status. Passes Customer Service customer-safe facts only | `list_open_tickets`, `get_ticket`, `get_cash_position`, `list_approval_requests`, `update_ticket_status`, `get_business_date` | `backend/prompts/boss.md` |
| **Inventory** | Stock by SKU and size, shortages, vendor choice by specialty, lead-time delivery dates; checks whether a vendor is blocked by unpaid invoices | `check_stock_and_vendor_status`, `get_vendor_status`, `evaluate_bulk_discount` | `inventory.md` |
| **Accounting** | Cash position, invoices, rent, margins, discounts; **queues** payment requests, purchase orders and discount approvals for a human; reuses facts it is handed instead of re-fetching | `get_cash_position`, `get_vendor_status`, `get_lease_payment_status`, `evaluate_bulk_discount`, `list_approval_requests`, `request_payment`, `create_purchase_order`, `request_discount_approval` | `accounting.md` |
| **Facilities** | Verifies rent notices against the lease, asks Accounting to queue rent, drafts the landlord reply | `get_lease_payment_status`, `save_message_draft` | `facilities.md` |
| **Customer Service** | Customer-facing reply drafts using teammates' facts; catalogue product names, no internal operations or SKU codes, no delivery date without a queued PO, nothing sent | `check_stock_and_vendor_status`, `save_message_draft` | `customer_service.md` |

Every agent also has `ask_agent` (section 7). Only the Boss has `get_ticket` and `get_business_date`. Specialists receive the ticket brief (now including the product's catalogue name) with every request, and each of their main tools returns `business_date`. Each agent's instructions are its role file plus `backend/prompts/shop_policies.md`: the shared data rules, payment priority, vendor rule, discount policy, communication rules and efficiency rules.

**Shop policies we set** (they aren't in the database, so they're written down in `shop_policies.md`):
- Payment priority when cash is short: (1) rent due within 7 days, (2) overdue vendor invoices, especially ones blocking a customer restock, (3) restocks for existing customer orders, smallest first, (4) discretionary or bulk restocks.
- Bulk discount: 10+ units as ordered, at most 15% off list, unit margin at least 50%, queued only for the units the shop can supply now.

### Backend files

| File | Purpose |
|---|---|
| `backend/config.py` | Model (`gpt-6-luna` via Portkey), model settings, delegation and usage limits, and how to launch the MCP server |
| `backend/models.py` | `AgentReport` (every specialist's structured reply), `TriagePlan`, `TicketPriority`, `TicketDecision`, `AgentDeps`, `TicketState` |
| `backend/agents.py` | `AgentTeam`: one MCP connection, five agents, per-agent tool allowlists, `ask_agent` with loop guards, the audit hook on every MCP call |
| `backend/orchestrator.py` | `run_ticket()` (one ticket, used by the API) and `python -m backend.orchestrator [--reset]` (triage, then every open ticket in priority order). Resets only with `--reset` |
| `backend/runtime.py` | Keeps the agent team and its MCP connection on a dedicated thread and event loop for the API's lifetime (Problem 7) |
| `backend/main.py` | FastAPI app (Problem 7, section 10) |
| `backend/approvals.py` | `python -m backend.approvals list / approve / reject`: the human approval desk, the only path that executes payments |
| `backend/audit.py` | Append-only writer for `output/audit_trail.json` |
| `backend/prompts/*.md` | One instruction file per agent plus `shop_policies.md` |

---

## 6. MCP tools (full list)

The server in `mcp_server/` has **19 tools**: the original 3 from Problem 3, 11 added in Problem 5 for the agents, 2 read tools added in Problem 7 for the dashboard API (`list_tickets`, `list_message_drafts`), and 3 human-only tools. All of them read and write `data/campus_customs_new.db` only. Tool failures (missing records, bad input, business-rule refusals) come back as MCP tool errors with a readable reason.

### Original read tools (`mcp_server/tools.py`)

| Tool | Tables | Ticket | Used by |
|---|---|---|---|
| `check_stock_and_vendor_status(sku, size, qty_needed)` | desk, inventory, pricing, vendors, invoices | 101 | Inventory, Customer Service |
| `get_lease_payment_status(lease_id)` | desk, leases, payments, cash_accounts, invoices, tickets | 102 | Facilities, Accounting |
| `evaluate_bulk_discount(sku, size, qty, discount_pct)` | desk, inventory, pricing, cash_accounts | 103 | Inventory, Accounting |

### Added in Problem 5 (`mcp_server/workflow_tools.py`)

| Tool | Reads / **writes** | Why the tickets need it |
|---|---|---|
| `get_business_date()` | desk | Every due, overdue and delivery calculation uses `desk.date_today` |
| `list_open_tickets()` | desk, tickets | Boss triage of 101–103 |
| `get_ticket(ticket_id)` | tickets, inventory, approval_requests, purchase_orders, message_drafts | Start of every ticket; shows what is already queued and the SKU's catalogue `product_name` (used in the ticket brief) |
| `list_tickets()` *(Problem 7, API only)* | desk, tickets, approval_requests, message_drafts | Every ticket, including resolved ones, with pending-approval and draft counts for the dashboard |
| `list_message_drafts(ticket_id)` *(Problem 7, API only)* | tickets, message_drafts | Full draft text for human review |
| `get_cash_position(account)` | desk, cash_accounts, approval_requests, invoices, vendors, leases | Rent ($2,400), invoice 501 ($840) and restocks compete for $3,400, so agents need committed vs available cash |
| `get_vendor_status(vendor_id)` | desk, vendors, invoices, approval_requests | Bulldog Print Co is blocked by invoice 501 (101 and 103) |
| `list_approval_requests(status, ticket_id)` | approval_requests | Avoid duplicate requests; Boss's final summary |
| `request_payment(kind, ref_id, ticket_id, reason, requested_by)` | invoices / leases, approval_requests, cash_accounts → **approval_requests** | Queue invoice 501 (101) and rent for lease 1 (102). The amount comes from the DB; no duplicates; refused if uncommitted cash can't cover it |
| `create_purchase_order(ticket_id, vendor_id, sku, size, qty, reason, requested_by)` | vendors, inventory, pricing, invoices, approval_requests → **purchase_orders, approval_requests** | Restock 1 tee S (101). Priced at `unit_cost`, delivery date from `lead_days`; refused while the vendor has unqueued unpaid invoices or cash is short (blocks the $264 hoodie restock in 103) |
| `request_discount_approval(ticket_id, sku, qty, discount_pct, reason, requested_by)` | pricing → **approval_requests** | 103's bulk discount; refused below unit cost |
| `save_message_draft(ticket_id, audience, recipient, subject, body, author)` | tickets, inventory → **message_drafts** | Replies to Tauhid Zaman, Elm City Properties and Yale AI Club. Never sent. **Customer** drafts are refused if they contain internal terms (invoice, approval, purchase order, vendor, cash…) or a SKU code, or omit the catalogue product name |
| `update_ticket_status(ticket_id, status, note, updated_by)` | tickets, approval_requests → **tickets** | Boss closes each ticket; `resolved` is refused while approvals are pending |

### Human-only (`mcp_server/human_tools.py`), in no agent's allowlist

| Tool | Writes | Rules checked at execution |
|---|---|---|
| `execute_approved_payment(approval_request_id, approved_by)` | **cash_accounts, payments, invoices, leases, purchase_orders, approval_requests, tickets** | Request still pending (no double payment); named human approver; invoice not already paid; PO vendor has no unpaid invoices; balance stays ≥ 0, otherwise auto-rejected. Rent rolls `next_due` forward a month; a PO becomes `placed`; the ticket resolves when its last request is decided |
| `reject_approval_request(approval_request_id, decided_by, note)` | approval_requests, purchase_orders, tickets | Pending only; a rejected PO is cancelled |
| `reset_working_database()` | replaces the working DB | Copies `data/campus_customs.db` over the working copy. Runs only when explicitly requested: `POST /api/reset` with `{"confirm": true}` or `orchestrator --reset` |

**Workflow tables.** The original schema has nowhere to store approvals, POs or drafts. `mcp_server/db.py` creates `approval_requests`, `purchase_orders` and `message_drafts` in the **working copy only** (`CREATE TABLE IF NOT EXISTS`); the original is never modified.

---

## 7. How agents collaborate

```
orchestrator ──reset──▶ MCP
     │
     ├─▶ Boss (triage mode) ── list_open_tickets, get_cash_position ──▶ TriagePlan (102 → 101 → 103)
     │
     └─▶ for each ticket, in priority order:
           get_ticket (MCP) → one-line ticket brief
           Boss (ticket mode) ── ask_agent ──▶ Facilities / Inventory / Accounting / Customer Service
                                                    │ ask_agent (peer to peer)
                                                    └──▶ any other agent, e.g. Inventory ──▶ Accounting
           Boss ── update_ticket_status ──▶ TicketDecision
```

- **Any agent can ask any other** with `ask_agent(agent, task, context)`. The callee gets the ticket brief, the caller's task and the facts the caller already has. It returns a structured `AgentReport` (status, summary, findings, approval request IDs, PO IDs, draft IDs, recommendation).
- **Loop and cost guards** (`backend/agents.py`, `backend/config.py`):
  - no self-delegation;
  - no delegating to an agent already in the chain (prevents A → B → A);
  - maximum chain depth of 3;
  - at most 8 delegations per ticket;
  - an identical repeat request to the same agent is answered from a per-ticket cache;
  - every agent on a ticket shares one usage counter, capped at 40 model requests, 45 tool calls and 120k tokens per ticket (triage: 6 / 6 / 20k).
- **Token efficiency:** the ticket is fetched once and passed as a brief instead of every agent re-reading it. Delegations carry already-known facts in `context`, tool results are compact JSON, and the prompts tell agents to call each tool once and ask each specialist once.

### Verified run (`output/agent_run_summary.json`)

The full run reset the DB, triaged the tickets as 102 (high) → 101 (medium) → 103 (low), and produced:

| Ticket | Delegations | Outcome | Queued for human | Draft |
|---|---|---|---|---|
| 102 rent | Boss → Facilities → **Accounting** (peer delegation) | Lease confirms $2,400 due 2026-09-02 | #1 rent $2,400 | #1 to Elm City Properties |
| 101 tee S | Boss → Inventory → **Accounting** (peer delegation), Boss → Customer Service | 0 in stock; vendor blocked by invoice 501 | #2 invoice 501 $840, #3 PO 1 tee $8 (executes only after #2) | #2 to Tauhid Zaman, delivery ~2026-09-05 |
| 103 hoodies | Boss → Accounting → **Inventory** (peer delegation), Boss → Inventory, Boss → Customer Service | 8 of 20 in stock; $264 restock exceeds the $160 left after rent and the invoice, and the vendor is blocked | #4 15% discount on the 8 in stock | #3 to Yale AI Club |

Total for the three tickets: about 109k input and 5k output tokens. Cash stayed at $3,400 with zero payments until a human acted. Approving everything via `backend.approvals`, tested on a backup copy and then reverted, left a $152 balance. The PO was refused until the invoice was paid, and a second approval of the same request was refused.

---

## 8. Safety

| Rule | Where it is enforced |
|---|---|
| **Human approval for every payment** | Agents can only *queue* (`request_payment`, `create_purchase_order`). `execute_approved_payment` is in no agent's allowlist, the audit hook refuses it even if a filter were misconfigured, and it requires a named human `approved_by`. It is reached only via `python -m backend.approvals` |
| **No negative balance** | Queuing is refused if cash minus already-pending requests can't cover it; execution re-checks the live balance and auto-rejects if the payment would go below 0 |
| **Vendor invoices before new orders** | `create_purchase_order` refuses while a vendor has unpaid invoices not queued for payment; `execute_approved_payment` refuses a PO while any vendor invoice is unpaid |
| **No repeated payment** | Duplicate pending requests aren't created; only `pending` requests execute, so a second approve is refused; an already-paid invoice is auto-rejected |
| **Business date and lead times** | Every tool computes from `desk.date_today` and `vendors.lead_days` |
| **No assumed revenue** | Cash tools model outflows only; the prompts forbid assuming income |
| **No external communication** | No email or vendor integration exists. `save_message_draft` stores status `draft`, and the prompts forbid claiming anything was sent |
| **No unauthorized DB changes** | Agents reach data only through MCP (the backend has no SQLite code). Each agent sees only its allowlisted tools; only the Boss can change ticket status; `resolved` is refused while approvals are pending |
| **Data integrity** | Every tool runs in a transaction that rolls back on error; the original DB is never written (verified by checksum against `data.zip`) |
| **Token limits** | Shared per-ticket usage caps plus delegation depth, count and cache limits (section 7) |

---

## 9. Audit trail

`output/audit_trail.json` is a JSON array, written by `backend/audit.py`. Each write reads the existing records, appends, and atomically replaces the file, so earlier runs are kept. An unreadable file is moved aside, never deleted.

Completed delegations also carry `usage` (requests, tool calls, input/output tokens used by that agent and anyone it asked), so cost can be split per agent. Each record has: `timestamp`, `run_id`, `ticket_id`, `agent`, `action` (`run_started`, `reset_working_database`, `triage_decision`, `ticket_started`, `mcp_tool_call`, `delegation`, `ticket_decision`, `approval_approve`/`approval_reject`, `run_finished`), `tool`, `delegation_target`, `inputs`, `outputs` (long payloads truncated at 4,000 characters), `status` (`ok`, `started`, `completed`, `cached`, `refused`, `tool_error`, `usage_limit`, `error`), and `error`.

The file now holds 366 records covering every run since Problem 5: development runs, API tests, dashboard tests and the final Problem 9 run (records #318–#366). Nothing has been overwritten; the first record is still the Problem 5 `run_started` from 2026-10-15 00:10 UTC. The API exposes the records at `GET /api/events`, with `since_reset=true` limiting them to the current simulation.

---

## 10. Backend API (Problem 7)

`backend/main.py` is a FastAPI app for the React dashboard. Start it from `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

Run that from a normal terminal, using the project's `.venv` Python with `PORTKEY_API_KEY` set. The app is at `http://localhost:8000`, with interactive docs at `/docs`.

**How it connects:**
- On startup the app opens **one** MCP connection, and the five agents share it (`backend/runtime.py`).
- Every shop read and write is an MCP tool call to `data/campus_customs_new.db`. The backend has no database code; the only file it reads directly is the audit trail.
- On Windows, `uvicorn --reload` runs on an event loop that can't start subprocesses, and the MCP server is a subprocess. So the MCP connection and agent runs live on their own thread and event loop, and routes hand work to it.
- CORS allows any `http://localhost:<port>` / `http://127.0.0.1:<port>` origin for GET and POST. Vite moves off 5173 when that port is busy; remote origins are refused.

### Routes

| Method | Path | Purpose | Input | Output |
|---|---|---|---|---|
| GET | `/api/health` | MCP connectivity, business date, model, any run in progress | none | `{status, mcp, business_date, model, agent_run_in_progress}` |
| **A** GET | `/api/tickets` | All tickets with status and open/resolved state | none | `{business_date, tickets: [{id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, state: "open"\|"resolved", pending_approvals, drafts, notes}]}` |
| GET | `/api/tickets/{ticket_id}` | One ticket in detail | path `ticket_id` (int) | ticket fields + `approval_requests`, `purchase_orders`, `message_drafts` (full text) |
| **B** POST | `/api/tickets/{ticket_id}/run` | Run the agent team on one ticket: the Boss reads it, delegates, decides and sets status. Blocks until done (about 30–90 s). Never resets the DB | path `ticket_id` | `{run_id, ticket_id, decision: TicketDecision, usage, delegations, ticket: <detail>, pending_approvals}` |
| **C** GET | `/api/events` | Agent activity from `output/audit_trail.json`: agent, action, MCP tool, delegation target, status, and a readable `message` (what was asked, replied or decided) | query `after_id` (poll forward), `limit` (1–1000, default 100), `ticket_id`, `run_id`, `agent`, `include_payloads`, `since_reset` (only events after the latest DB reset) | `{events: [{id, timestamp, run_id, ticket_id, agent, action, tool, delegation_target, status, message, error, inputs?, outputs?}], latest_id, total}` |
| GET | `/api/drafts` | Draft messages with full text (never sent) | query `ticket_id` (optional) | `{drafts: [...]}` |
| GET | `/api/approvals` | Requests the agents prepared, each with `payee` and `description` | query `status` (`pending`\|`executed`\|`rejected`), `ticket_id` | `{approval_requests: [{id, ticket_id, kind, ref_id, amount, payee, description, status, decided_by, ...}]}` |
| **D** POST | `/api/approvals/{request_id}/approve` | **Human approval: the only way money moves.** Checks the request exists and is pending, notes the balance, then calls `execute_approved_payment`. That tool re-checks pending status under a DB write lock (no duplicate payments), refuses a PO while the vendor has unpaid invoices, and refuses to go negative. It then updates `cash_accounts`, `payments`, `invoices`, `leases`, `purchase_orders` and the ticket. Audited | body `{"approved_by": "<name>"}` | `{approval_request_id, status: "executed", kind, amount, payment_id, new_balance, message}` |
| POST | `/api/approvals/{request_id}/reject` | Human rejects a pending request (a PO is cancelled). Audited | body `{"decided_by": "<name>", "note": "..."}` | `{approval_request_id, status: "rejected", ...}` |
| **E** GET | `/api/cash` | Checking balance from `cash_accounts` (reflects executed payments), plus pending commitments and obligations | query `account` (default `checking`) | `{account, balance, business_date, committed_to_pending, available_after_pending, pending_requests, unpaid_invoices, rent_due_within_30_days}` |
| **F** POST | `/api/reset` | Restore the working DB from `data/campus_customs.db`. Explicit only; refused while agents run. Audited | body `{"confirm": true}` | `{reset, business_date, checking_balance, open_tickets, message}` |

### Errors

Errors come back as JSON in the form `{"detail": ...}`.

| Code | When |
|---|---|
| 400 | Reset without `"confirm": true` |
| 404 | Unknown ticket, approval request or cash account |
| 409 | Ticket already resolved; another agent run in progress; reset during a run; approval request already decided (duplicate); PO before its vendor invoice is paid; payment that would make the balance negative (rejected, no money moved) |
| 422 | Invalid input: non-integer IDs, empty approver name, bad status filter, missing body |
| 502 | Agent run failed. The detail includes the `run_id`; completed steps are in `/api/events` |
| 503 | MCP server unavailable |

### Test results (live, against `data/campus_customs_new.db`)

| Test | Result |
|---|---|
| Server starts with `uvicorn main:app --reload --port 8000` from `backend/`; `/api/health` returns `mcp: connected` | ✅ |
| `--reload` restarts the worker cleanly (old MCP subprocess closed, new one connected) | ✅ in a real terminal. Uvicorn's Windows reloader uses a console Ctrl+C event, so it doesn't restart when started from a shell with no console |
| Reset: missing body 422, `confirm:false` 400, `confirm:true` 200 → balance 3,400, 3 open tickets | ✅ |
| Tickets: list 200; `/999` 404; `/abc` 422 | ✅ |
| Run 102 / 101 / 103 through the API with gpt-6-luna | ✅ All three `awaiting_approval`. 102: rent #1 $2,400. 101: invoice #2 $840 + PO #3 $8. 103: 15% discount #4 on the 8 hoodies in stock, no $264 PO (only $152 uncommitted). One draft each |
| Second run while one is in progress → 409; reset during a run → 409; health shows the active ticket | ✅ |
| Approve PO #3 before invoice → 409; invoice #2 → paid, balance 2,560; #2 again → 409; PO → 2,552; rent → 152; discount → no cash moved | ✅ `payments` has 3 rows, invoice 501 is `paid`, lease `next_due` is 2026-10-02, PO `placed` (ETA 2026-09-05), all tickets `resolved` |
| Re-run a resolved ticket → 409; reject an executed request → 409; approve nonexistent → 404; empty approver → 422 | ✅ |
| **Insufficient cash** (fixture: rent queued, balance lowered to $1,000) → 409 "Insufficient funds", balance stays $1,000, request auto-rejected by `system` | ✅ |
| **Double approval** of one request fired simultaneously → one 200, one 409; exactly one $840 payment | ✅ |
| Events: filter by ticket and agent; polling with `after_id` returns nothing new when caught up | ✅ |
| CORS preflight from `http://localhost:5173` | ✅ |
| Original `data/campus_customs.db` unchanged (MD5 matches `data.zip`); working DB reset to clean state at the end | ✅ |


---

## 11. React dashboard (Problem 8)

`frontend/` uses React 19, Vite 8 and TypeScript. Start it with `npm run dev` (port 5173). It calls the section 10 API at `http://localhost:8000`, set by `VITE_API_URL`. Full design rationale is in `output/design.md`.

| Feature | How it works |
|---|---|
| Header | System status from `/api/health` (MCP, model, business date, active run), operator name (stored as `approved_by`), two-step Reset (`POST /api/reset`), and the checking balance from `/api/cash`, animated on change |
| Ticket list | `/api/tickets`: status pills (Open, Running, Awaiting approval, Resolved, Blocked), business details, pending-approval and draft counts. **Run agents** calls `POST /api/tickets/{id}/run`; it's disabled during any run or while offline. Resolved cards are dimmed, struck through and marked "Closed" |
| Live activity | Polls `/api/events?ticket_id&after_id&include_payloads` every 1.2 s during a run. A roster of the five agents (each with its own colour and icon) shows who is working, worked out from delegation start and finish events. The feed shows handoffs, tool calls, agent replies and the Boss's decision; history only since the last reset |
| Agent contributions | After a run: one card per participating agent with role, who asked it and whom it asked, summary, findings, recommendation, IDs it created and MCP tools used |
| Approvals | `/api/approvals`: pending cards with kind, amount, payee, description, ticket and requesting agent; "Approve & pay $X" (`POST …/approve`) and Reject. History shows Paid, Approved (discount), Rejected or Rejected by system |
| Drafts | Full text of every draft, labelled "never sent" |
| Errors and loading | Offline banner with auto-retry; skeleton loading; toasts for every success and failure using the backend's own wording (e.g. "Not enough cash"); buttons disabled while requests are in flight |

---

## 12. Final full run (Problem 9)

**Procedure.**
1. Reset from the dashboard. Every original table then matched `data/campus_customs.db` row for row, `payments` was empty, all tickets were `open`, and the starting balance was **$3,400.00** (audit #318).
2. Ran each ticket with the dashboard's **Run agents** button, in the Boss's priority order: 102 → 101 → 103.
3. Approved each ticket's requests from the dashboard's approval cards before starting the next ticket.

Approve clicks were made by Claude Code at the user's instruction and are recorded as `approved_by = "Michael Zheng (via Claude Code)"`.

| Ticket | Boss contacted first | Delegations | MCP tool calls | Human approvals | Final status |
|---|---|---|---|---|---|
| 102 | Facilities | Boss → Facilities; Facilities → Accounting | 8 | #1 rent $2,400.00 | resolved |
| 101 | Inventory | Boss → Inventory; Inventory → Accounting; Boss → Customer Service | 7 | #2 invoice $840.00, #3 purchase order $8.00 | resolved |
| 103 | Accounting | Boss → Accounting; Accounting → Inventory; Boss → Customer Service | 7 | #4 discount $69.60 | resolved |

The first agent contacted matched the Problem 6 plan on all three tickets.

**Cash reconciliation** (`Ending = Starting − Approved payments`):

| Payment | Ticket | Kind | Payee | Amount | Approved by |
|---|---|---|---|---|---|
| 1 | 102 | rent | Elm City Properties | $2,400.00 | Michael Zheng (via Claude Code) |
| 2 | 101 | invoice | Bulldog Print Co | $840.00 | Michael Zheng (via Claude Code) |
| 3 | 101 | purchase order | Bulldog Print Co | $8.00 | Michael Zheng (via Claude Code) |

$3,400.00 − $3,248.00 = **$152.00**. That equals `cash_accounts.checking` ($152.00) and the `/api/cash` value. The `payments` table matches the executed approval requests, and every payment has a named human approver. Ticket 103's only approval was a discount ($69.60 value, no cash moved).

**Outputs:**
- `output/desk_tickets.html`: Actual and Cash tabs; Expected sections unchanged, verified byte-identical.
- `output/resolved_tickets.json`: generated by `scripts/build_problem9_reports.py` from the API, with a read-only DB cross-check.
- `output/resolved_board.html`: three real dashboard screenshots (`output/screenshots/`), embedded; built by `scripts/build_resolved_board.py`.
- `output/audit_trail.json`: 49 new records.

**Observed deviation:** the ticket 103 draft to Yale AI Club mentions a possible September 5 arrival "if a restock is approved", but no restock was queued. A human should edit that line before sending.

---

## 13. Fixes after the Problem 10 reflection

The reflection found several defects in the Problem 9 run. These were fixed afterwards. The Problem 9 records (Actual and Cash tabs, `resolved_tickets.json`, the screenshots and the working DB) were deliberately left as they were.

| Defect seen in Problem 9 | Fix | Where |
|---|---|---|
| Customer drafts leaked internal terms ("approvals") and used a shortened product name ("Bulldog tee") | `save_message_draft` refuses customer drafts containing internal terms or SKU codes, or missing the catalogue name, and tells the agent exactly what to change. The ticket brief now includes the catalogue name. The Boss passes customer-safe facts only | `mcp_server/workflow_tools.py`, `backend/orchestrator.py`, `boss.md`, `customer_service.md` |
| Ticket 103's draft promised a September 5 date for a restock that was never queued | Policy: quote a delivery date only for items with a queued purchase order | `shop_policies.md`, `customer_service.md`, `boss.md` |
| Facilities re-fetched the ticket and the business date on 102 | Specialists no longer have `get_ticket` / `get_business_date`; Accounting reuses facts it's handed | `backend/agents.py`, `accounting.md` |
| Drafts went stale after approvals (draft #2 still said the restock was conditional) | Any decision on an approval flags that ticket's drafts as `needs_review`; the dashboard shows a "Needs review" badge | `mcp_server/human_tools.py`, `Contributions.tsx` |
| Token use was only known per ticket | Delegations record `usage`; the events API and the dashboard's contribution cards show it | `backend/agents.py`, `backend/audit.py`, `backend/main.py`, frontend |
| `verify_mcp_smoke.py` failed once later problems changed the working DB | It now checks the Problem 4 snapshot against the original starting data | `scripts/verify_mcp_smoke.py` |
| 10 React lint warnings (setState in effects; components mixed with helpers) | Selection moved to an event handler, run completion detected in the health poll, `Avatar` split out; `npm run lint` is clean | `frontend/src` |

**Verification.**
- `scripts/test_mcp_rules.py`: 27/27 checks pass, including 5 new ones for the draft guard and the `needs_review` flag.
- `verify_mcp_smoke.py`: passes.
- `npm run build` and `npm run lint`: clean.

**Live re-run.** I re-ran all three tickets on a scratch copy of the database with a separate audit file, so the Problem 9 records weren't touched. Same order and approvals as Problem 9:

| Ticket | MCP tool calls, Problem 9 → re-run | Notes |
|---|---|---|
| 102 | 8 → 6 | No redundant calls |
| 101 | 7 → 6 | No redundant calls |
| 103 | 7 → 6 | No redundant calls |

- No draft retries were needed.
- All three drafts used catalogue names, contained no internal terms, gave no unbacked delivery dates, and were flagged `needs_review` after approval.
- The ending balance was again $152.

**Not fixed:**
- **Total tokens stayed about the same** (28.7k / 38.5k / 39.3k vs 27.7k / 37.1k / 32.0k). Most input tokens are the role and policy prompts re-sent to each agent, and the new rules made those slightly longer.
- **Approvals still have no login.** The operator name is free text. Adding authentication is a new feature, not a bug fix.

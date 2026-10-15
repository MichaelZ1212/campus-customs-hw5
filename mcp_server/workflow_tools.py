"""Workflow tools added in Problem 5: ticket context, cash, vendor checks, and
requests that queue work for a human. None of these moves money.

Business rules enforced here, not just in prompts:
  * desk.date_today is the business date.
  * vendor lead times come from vendors.lead_days.
  * a vendor with unpaid invoices cannot get a new purchase order unless every
    unpaid invoice already has a pending payment request (and the PO still
    cannot execute until those invoices are actually paid).
  * a new payment request is refused if it cannot be covered by the balance
    left after all other pending requests (no incoming cash is assumed).
  * messages are saved as drafts only.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from mcp.server.fastmcp.exceptions import ToolError

from .db import business_date, connect, fetch_all, fetch_one

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "resolved", "blocked")
DRAFT_AUDIENCES = ("customer", "vendor", "landlord", "internal")
PAYMENT_KINDS = ("invoice", "rent")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _require_text(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ToolError(f"{field} must not be empty")
    return value.strip()


def _ticket(conn, ticket_id: int) -> dict:
    ticket = fetch_one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if not ticket:
        raise ToolError(f"Ticket {ticket_id} not found")
    return ticket


def _pending_total(conn, account: str) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM approval_requests "
        "WHERE status = 'pending' AND account = ? AND kind != 'discount'",
        (account,),
    ).fetchone()[0]


def _account_balance(conn, account: str) -> float:
    row = fetch_one(conn, "SELECT balance FROM cash_accounts WHERE name = ?", (account,))
    if not row:
        raise ToolError(f"Cash account '{account}' not found")
    return row["balance"]


def _ensure_affordable(conn, account: str, amount: float) -> float:
    """Refuse a request that the cash left after other pending requests can't cover."""
    available = round(_account_balance(conn, account) - _pending_total(conn, account), 2)
    if amount > available:
        raise ToolError(
            f"Cannot queue {amount:.2f}: only {available:.2f} in '{account}' is not already committed to "
            "pending requests. No incoming cash is assumed. Prioritise or reduce the request."
        )
    return round(available - amount, 2)


def _queue(conn, ticket_id, kind, ref_id, amount, account, reason, requested_by) -> int:
    cur = conn.execute(
        "INSERT INTO approval_requests (ticket_id, kind, ref_id, amount, account, reason, requested_by, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ticket_id, kind, ref_id, amount, account, reason, requested_by, _now()),
    )
    return cur.lastrowid


# ------------------------------------------------------------------ reads

def get_business_date() -> dict:
    """Return the official business date (desk.date_today). Use it for every due or overdue calculation."""
    with connect() as conn:
        return {"business_date": business_date(conn)}


def list_open_tickets() -> dict:
    """List every ticket that is not resolved, with the fields needed to triage it."""
    with connect() as conn:
        tickets = fetch_all(
            conn,
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at "
            "FROM tickets WHERE status != 'resolved' ORDER BY id",
        )
        return {"business_date": business_date(conn), "tickets": tickets}


def list_tickets() -> dict:
    """List every ticket (any status) with counts of pending approval requests and saved drafts."""
    with connect() as conn:
        tickets = fetch_all(
            conn,
            "SELECT t.id, t.type, t.requester, t.subject, t.sku, t.size, t.qty, t.lease_id, t.invoice_id, "
            "t.status, t.notes, t.created_at, "
            "(SELECT COUNT(*) FROM approval_requests a WHERE a.ticket_id = t.id AND a.status = 'pending') AS pending_approvals, "
            "(SELECT COUNT(*) FROM message_drafts d WHERE d.ticket_id = t.id) AS drafts "
            "FROM tickets t ORDER BY t.id",
        )
        return {"business_date": business_date(conn), "tickets": tickets}


def list_message_drafts(ticket_id: int | None = None) -> dict:
    """List saved message drafts with their full text, optionally for one ticket. Drafts are never sent."""
    with connect() as conn:
        if ticket_id is not None:
            _ticket(conn, ticket_id)
            drafts = fetch_all(conn, "SELECT * FROM message_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        else:
            drafts = fetch_all(conn, "SELECT * FROM message_drafts ORDER BY id")
        return {"drafts": drafts}


def get_ticket(ticket_id: int) -> dict:
    """Return one ticket (with the product's catalogue name, if it names a SKU) and its approval
    requests, purchase orders and message drafts so far."""
    with connect() as conn:
        ticket = _ticket(conn, ticket_id)
        if ticket.get("sku"):
            item = fetch_one(conn, "SELECT name FROM inventory WHERE sku = ? LIMIT 1", (ticket["sku"],))
            ticket["product_name"] = item["name"] if item else None
        ticket["approval_requests"] = fetch_all(
            conn, "SELECT id, kind, ref_id, amount, status, requested_by FROM approval_requests WHERE ticket_id = ?", (ticket_id,)
        )
        ticket["purchase_orders"] = fetch_all(
            conn, "SELECT id, vendor_id, sku, size, qty, total, expected_date, status FROM purchase_orders WHERE ticket_id = ?", (ticket_id,)
        )
        ticket["message_drafts"] = fetch_all(
            conn, "SELECT id, audience, recipient, subject, author FROM message_drafts WHERE ticket_id = ?", (ticket_id,)
        )
        return ticket


def get_cash_position(account: str = "checking") -> dict:
    """Return the account balance, money already committed to pending approval requests,
    what is still available, and unpaid invoices and rent due within 30 days.
    Outflows only: no incoming revenue is assumed."""
    with connect() as conn:
        today = business_date(conn)
        balance = _account_balance(conn, account)
        pending = fetch_all(
            conn,
            "SELECT id, ticket_id, kind, ref_id, amount FROM approval_requests "
            "WHERE status = 'pending' AND account = ? AND kind != 'discount' ORDER BY id",
            (account,),
        )
        committed = round(sum(p["amount"] for p in pending), 2)
        invoices = fetch_all(
            conn,
            "SELECT i.id, v.name AS vendor, i.amount, i.due_date FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
            "WHERE i.status != 'paid' ORDER BY i.due_date",
        )
        for invoice in invoices:
            invoice["days_overdue"] = max(0, _days_between(invoice["due_date"], today))
        rent = [
            {"lease_id": l["id"], "landlord": l["landlord"], "amount": l["monthly_rent"], "due": l["next_due"],
             "days_until_due": _days_between(today, l["next_due"])}
            for l in fetch_all(conn, "SELECT * FROM leases")
            if _days_between(today, l["next_due"]) <= 30
        ]
        obligations = round(sum(i["amount"] for i in invoices) + sum(r["amount"] for r in rent), 2)
        return {
            "business_date": today,
            "account": account,
            "balance": balance,
            "pending_requests": pending,
            "committed_to_pending": committed,
            "available_after_pending": round(balance - committed, 2),
            "unpaid_invoices": invoices,
            "rent_due_within_30_days": rent,
            "total_obligations_due": obligations,
            "balance_after_all_obligations": round(balance - obligations, 2),
        }


def get_vendor_status(vendor_id: int) -> dict:
    """Return a vendor's specialty, lead time, unpaid invoices and whether it may accept new orders."""
    with connect() as conn:
        today = business_date(conn)
        vendor = fetch_one(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if not vendor:
            raise ToolError(f"Vendor {vendor_id} not found")
        unpaid = fetch_all(
            conn, "SELECT id, amount, due_date, description FROM invoices WHERE vendor_id = ? AND status != 'paid'", (vendor_id,)
        )
        for invoice in unpaid:
            invoice["days_overdue"] = max(0, _days_between(invoice["due_date"], today))
            invoice["pending_payment_request"] = fetch_one(
                conn, "SELECT id FROM approval_requests WHERE kind = 'invoice' AND ref_id = ? AND status = 'pending'", (invoice["id"],)
            )
        vendor.update(
            business_date=today,
            unpaid_invoices=unpaid,
            can_accept_new_orders=not unpaid,
            earliest_delivery_if_ordered_today=(date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat(),
        )
        return vendor


def list_approval_requests(status: str | None = None, ticket_id: int | None = None) -> dict:
    """List approval requests, optionally filtered by status (pending, executed, rejected) and/or ticket."""
    clauses, params = [], []
    if status:
        clauses.append("status = ?"); params.append(status)
    if ticket_id is not None:
        clauses.append("ticket_id = ?"); params.append(ticket_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        requests = fetch_all(conn, f"SELECT * FROM approval_requests {where} ORDER BY id", tuple(params))
        for req in requests:
            req.update(_payee(conn, req))
        return {"approval_requests": requests}


def _payee(conn, req: dict) -> dict:
    """Who the request pays (or benefits) and a one-line description, from the referenced record."""
    kind, ref = req["kind"], req["ref_id"]
    if kind == "invoice":
        row = fetch_one(conn, "SELECT v.name, i.description, i.due_date FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (ref,))
        if row:
            return {"payee": row["name"], "description": f"Invoice #{ref}: {row['description']} (due {row['due_date']})"}
    elif kind == "rent":
        row = fetch_one(conn, "SELECT landlord, space_name, next_due FROM leases WHERE id = ?", (ref,))
        if row:
            return {"payee": row["landlord"], "description": f"Rent for {row['space_name']} (due {row['next_due']})"}
    elif kind == "purchase_order":
        row = fetch_one(
            conn,
            "SELECT v.name, p.qty, p.size, p.expected_date, i.name AS product FROM purchase_orders p "
            "JOIN vendors v ON v.id = p.vendor_id LEFT JOIN inventory i ON i.sku = p.sku AND i.size = p.size WHERE p.id = ?",
            (ref,),
        )
        if row:
            return {"payee": row["name"], "description": f"PO #{ref}: {row['qty']} x {row['product']} size {row['size']} (ETA {row['expected_date']})"}
    elif kind == "discount":
        ticket = fetch_one(conn, "SELECT requester FROM tickets WHERE id = ?", (req["ticket_id"],))
        return {"payee": ticket["requester"] if ticket else None, "description": f"Price override: {req['reason']}"}
    return {"payee": None, "description": req["reason"]}


# ------------------------------------------------------------ agent writes

def request_payment(kind: str, ref_id: int, ticket_id: int, reason: str, requested_by: str, account: str = "checking") -> dict:
    """Queue a payment for HUMAN approval. kind='invoice' (ref_id = invoices.id) or kind='rent'
    (ref_id = leases.id). The amount comes from the database. No money moves."""
    if kind not in PAYMENT_KINDS:
        raise ToolError(f"kind must be one of {PAYMENT_KINDS}; use create_purchase_order for restocks")
    reason, requested_by = _require_text(reason, "reason"), _require_text(requested_by, "requested_by")
    with connect() as conn:
        _ticket(conn, ticket_id)
        if kind == "invoice":
            invoice = fetch_one(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if not invoice:
                raise ToolError(f"Invoice {ref_id} not found")
            if invoice["status"] == "paid":
                raise ToolError(f"Invoice {ref_id} is already paid")
            amount = invoice["amount"]
        else:
            lease = fetch_one(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if not lease:
                raise ToolError(f"Lease {ref_id} not found")
            amount = lease["monthly_rent"]
        existing = fetch_one(
            conn, "SELECT id, amount FROM approval_requests WHERE kind = ? AND ref_id = ? AND status = 'pending'", (kind, ref_id)
        )
        if existing:
            return {"approval_request_id": existing["id"], "status": "pending", "amount": existing["amount"],
                    "note": "A pending request for this already exists; no duplicate created."}
        remaining = _ensure_affordable(conn, account, amount)
        request_id = _queue(conn, ticket_id, kind, ref_id, amount, account, reason, requested_by)
        return {"approval_request_id": request_id, "status": "pending", "kind": kind, "ref_id": ref_id,
                "amount": amount, "available_after_all_pending": remaining,
                "note": "Waiting for human approval. No money has moved."}


def create_purchase_order(ticket_id: int, vendor_id: int, sku: str, size: str, qty: int, reason: str, requested_by: str) -> dict:
    """Draft a restock purchase order priced at pricing.unit_cost, with delivery from vendors.lead_days,
    and queue its payment for HUMAN approval. Refused if the vendor has unpaid invoices that do not
    already have a pending payment request, or if cash after pending requests cannot cover it."""
    if qty <= 0:
        raise ToolError("qty must be a positive integer")
    reason, requested_by = _require_text(reason, "reason"), _require_text(requested_by, "requested_by")
    with connect() as conn:
        _ticket(conn, ticket_id)
        today = business_date(conn)
        vendor = fetch_one(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if not vendor:
            raise ToolError(f"Vendor {vendor_id} not found")
        if not fetch_one(conn, "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)):
            raise ToolError(f"No inventory record for {sku} size {size}")
        pricing = fetch_one(conn, "SELECT unit_cost FROM pricing WHERE sku = ?", (sku,))
        if not pricing:
            raise ToolError(f"No pricing for {sku}")
        unpaid = [r["id"] for r in fetch_all(conn, "SELECT id FROM invoices WHERE vendor_id = ? AND status != 'paid'", (vendor_id,))]
        queued = {r["ref_id"] for r in fetch_all(conn, "SELECT ref_id FROM approval_requests WHERE kind = 'invoice' AND status = 'pending'")}
        not_queued = [i for i in unpaid if i not in queued]
        if not_queued:
            raise ToolError(
                f"{vendor['name']} has unpaid invoice(s) {not_queued} and cannot fulfil new orders. "
                "Request payment of those invoices first."
            )
        total = round(pricing["unit_cost"] * qty, 2)
        remaining = _ensure_affordable(conn, "checking", total)
        expected = (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat()
        po_id = conn.execute(
            "INSERT INTO purchase_orders (ticket_id, vendor_id, sku, size, qty, unit_cost, total, expected_date, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (ticket_id, vendor_id, sku, size, qty, pricing["unit_cost"], total, expected, _now()),
        ).lastrowid
        request_id = _queue(conn, ticket_id, "purchase_order", po_id, total, "checking", reason, requested_by)
        result = {"approval_request_id": request_id, "purchase_order_id": po_id, "status": "pending",
                  "vendor": vendor["name"], "qty": qty, "unit_cost": pricing["unit_cost"], "total": total,
                  "expected_date_if_approved_today": expected, "available_after_all_pending": remaining,
                  "note": "Waiting for human approval. Nothing has been sent to the vendor."}
        if unpaid:
            result["depends_on"] = f"Can only execute after invoice(s) {unpaid} are paid."
        return result


def request_discount_approval(ticket_id: int, sku: str, qty: int, discount_pct: float, reason: str, requested_by: str) -> dict:
    """Queue a price override for HUMAN sign-off. Refused if the discounted price is below unit cost.
    Not a cash outflow."""
    if qty <= 0:
        raise ToolError("qty must be a positive integer")
    if not 0 < discount_pct < 100:
        raise ToolError("discount_pct must be between 0 and 100")
    reason, requested_by = _require_text(reason, "reason"), _require_text(requested_by, "requested_by")
    with connect() as conn:
        _ticket(conn, ticket_id)
        pricing = fetch_one(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
        if not pricing:
            raise ToolError(f"No pricing for {sku}")
        unit_price = round(pricing["list_price"] * (1 - discount_pct / 100), 2)
        if unit_price < pricing["unit_cost"]:
            raise ToolError(f"{discount_pct}% off sells at {unit_price:.2f}, below unit cost {pricing['unit_cost']:.2f}")
        discount_given = round((pricing["list_price"] - unit_price) * qty, 2)
        request_id = _queue(conn, ticket_id, "discount", ticket_id, discount_given, "checking",
                            f"{discount_pct}% off {qty} x {sku}: {reason}", requested_by)
        return {"approval_request_id": request_id, "status": "pending", "discounted_unit_price": unit_price,
                "unit_margin": round(unit_price - pricing["unit_cost"], 2), "discount_given": discount_given,
                "note": "Waiting for human approval."}


# Words that expose internal operations (finances, approvals, suppliers) to a customer.
_INTERNAL_TERMS = re.compile(
    r"\b(invoices?|approvals?|approv(?:e|ed|ing)|payment requests?|purchase orders?|PO|vendors?|suppliers?|"
    r"cash|budget|funding|checking account|margins?)\b",
    re.IGNORECASE,
)
_SKU = re.compile(r"\bCC-[A-Z]+-[A-Z]+\b")


def _check_customer_draft(conn, ticket: dict, text: str) -> None:
    """Customer drafts must not leak internal operations or SKU codes, and must use the catalogue name."""
    problems = []
    leaked = sorted({m.group(0).lower() for m in _INTERNAL_TERMS.finditer(text)})
    if leaked:
        problems.append(f"remove internal terms {leaked} (say e.g. 'we're arranging a restock' or 'we're reviewing a group price')")
    if _SKU.search(text):
        problems.append("refer to the product by name, not its SKU code")
    if ticket.get("sku"):
        row = fetch_one(conn, "SELECT name FROM inventory WHERE sku = ? LIMIT 1", (ticket["sku"],))
        if row and row["name"].lower() not in text.lower():
            problems.append(f"use the catalogue product name '{row['name']}'")
    if problems:
        raise ToolError("Customer draft not saved: " + "; ".join(problems) + ". Revise and save again.")


def save_message_draft(ticket_id: int, audience: str, recipient: str, subject: str, body: str, author: str) -> dict:
    """Save an outbound message as a draft for human review. audience: customer, vendor, landlord or internal.
    Nothing is ever sent. Customer drafts are refused if they mention internal operations (invoices,
    approvals, purchase orders, vendors, cash...) or SKU codes, or omit the product's catalogue name."""
    if audience not in DRAFT_AUDIENCES:
        raise ToolError(f"audience must be one of {DRAFT_AUDIENCES}")
    recipient, subject = _require_text(recipient, "recipient"), _require_text(subject, "subject")
    body, author = _require_text(body, "body"), _require_text(author, "author")
    with connect() as conn:
        ticket = _ticket(conn, ticket_id)
        if audience == "customer":
            _check_customer_draft(conn, ticket, f"{subject}\n{body}")
        draft_id = conn.execute(
            "INSERT INTO message_drafts (ticket_id, audience, recipient, subject, body, author, created_at) VALUES (?,?,?,?,?,?,?)",
            (ticket_id, audience, recipient, subject, body, author, _now()),
        ).lastrowid
        return {"draft_id": draft_id, "status": "draft", "note": "Saved for human review; not sent."}


def update_ticket_status(ticket_id: int, status: str, note: str, updated_by: str) -> dict:
    """Set a ticket's status (open, in_progress, awaiting_approval, resolved, blocked) and append a dated note.
    A ticket with pending approval requests cannot be marked resolved."""
    if status not in TICKET_STATUSES:
        raise ToolError(f"status must be one of {TICKET_STATUSES}")
    note, updated_by = _require_text(note, "note"), _require_text(updated_by, "updated_by")
    with connect() as conn:
        ticket = _ticket(conn, ticket_id)
        pending = conn.execute(
            "SELECT COUNT(*) FROM approval_requests WHERE ticket_id = ? AND status = 'pending'", (ticket_id,)
        ).fetchone()[0]
        if status == "resolved" and pending:
            raise ToolError(f"Ticket {ticket_id} has {pending} pending approval request(s); use awaiting_approval")
        notes = f"{ticket['notes'] or ''}\n[{business_date(conn)} {updated_by}] {note}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
        return {"ticket_id": ticket_id, "previous_status": ticket["status"], "status": status}


TOOLS = [
    get_business_date, list_open_tickets, list_tickets, list_message_drafts, get_ticket, get_cash_position, get_vendor_status, list_approval_requests,
    request_payment, create_purchase_order, request_discount_approval, save_message_draft, update_ticket_status,
]

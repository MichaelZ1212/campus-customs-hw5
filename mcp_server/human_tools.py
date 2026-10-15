"""HUMAN-ONLY tools. They are never placed in any agent's toolset (see
backend/agents.py AGENT_TOOLS); they are called by a person through
backend/approvals.py (and later the dashboard).

execute_approved_payment is the only code path that moves money.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

from mcp.server.fastmcp.exceptions import ToolError

from .db import business_date, connect, fetch_one, reset_working_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _add_month(day: str) -> str:
    d = date.fromisoformat(day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _decide(conn, request_id: int, status: str, who: str, note: str, payment_id: int | None = None) -> None:
    conn.execute(
        "UPDATE approval_requests SET status = ?, decided_by = ?, decision_note = ?, payment_id = ?, decided_at = ? WHERE id = ?",
        (status, who, note, payment_id, _now(), request_id),
    )
    # Drafts were written while this request was pending; after a decision they may describe
    # the situation wrongly (e.g. "restock is conditional" once the PO is placed). Flag them.
    conn.execute(
        "UPDATE message_drafts SET status = 'needs_review' WHERE status = 'draft' "
        "AND ticket_id = (SELECT ticket_id FROM approval_requests WHERE id = ?)",
        (request_id,),
    )


def _note_ticket(conn, ticket_id: int | None, today: str, text: str) -> None:
    if ticket_id is not None:
        conn.execute("UPDATE tickets SET notes = COALESCE(notes, '') || ? WHERE id = ?", (f"\n[{today} human] {text}", ticket_id))


def _close_if_done(conn, ticket_id: int | None, today: str) -> None:
    """A ticket waiting on approvals is resolved once none of its requests is still pending."""
    if ticket_id is None:
        return
    ticket = fetch_one(conn, "SELECT status FROM tickets WHERE id = ?", (ticket_id,))
    pending = conn.execute("SELECT COUNT(*) FROM approval_requests WHERE ticket_id = ? AND status = 'pending'", (ticket_id,)).fetchone()[0]
    if ticket and ticket["status"] == "awaiting_approval" and pending == 0:
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        _note_ticket(conn, ticket_id, today, "All approval requests decided; ticket resolved.")


def execute_approved_payment(approval_request_id: int, approved_by: str) -> dict:
    """HUMAN-ONLY. Execute a pending approval request after a person approves it.
    Re-checks everything at execution time: the request is still pending (no double payment),
    the invoice is still unpaid, the vendor has no unpaid invoices (for purchase orders), and
    the balance stays at or above zero. Then updates cash_accounts, payments, invoices,
    leases and purchase_orders."""
    if not approved_by or not approved_by.strip():
        raise ToolError("approved_by must name the human approver")
    approved_by = approved_by.strip()
    with connect() as conn:
        # Write lock before reading the request, so two simultaneous approvals
        # cannot both see it as pending (no double payment).
        conn.execute("BEGIN IMMEDIATE")
        req = fetch_one(conn, "SELECT * FROM approval_requests WHERE id = ?", (approval_request_id,))
        if not req:
            raise ToolError(f"Approval request {approval_request_id} not found")
        if req["status"] != "pending":
            raise ToolError(f"Approval request {approval_request_id} is already {req['status']}; it cannot run twice")
        today = business_date(conn)

        if req["kind"] == "discount":
            _decide(conn, req["id"], "executed", approved_by, "Discount approved")
            _note_ticket(conn, req["ticket_id"], today, f"Discount approved by {approved_by}: {req['reason']}")
            _close_if_done(conn, req["ticket_id"], today)
            return {"approval_request_id": req["id"], "status": "executed", "kind": "discount", "cash_moved": 0}

        po = None
        if req["kind"] == "purchase_order":
            po = fetch_one(conn, "SELECT * FROM purchase_orders WHERE id = ?", (req["ref_id"],))
            unpaid = [r[0] for r in conn.execute("SELECT id FROM invoices WHERE vendor_id = ? AND status != 'paid'", (po["vendor_id"],))]
            if unpaid:
                # Left pending: it can run once the blocking invoices are paid.
                raise ToolError(f"Vendor still has unpaid invoice(s) {unpaid}. Approve and execute those payments first.")
        elif req["kind"] == "invoice":
            invoice = fetch_one(conn, "SELECT status FROM invoices WHERE id = ?", (req["ref_id"],))
            if invoice["status"] == "paid":
                _decide(conn, req["id"], "rejected", "system", "Invoice was already paid")
                _close_if_done(conn, req["ticket_id"], today)
                return {"approval_request_id": req["id"], "status": "rejected", "error": f"Invoice {req['ref_id']} is already paid"}

        balance = fetch_one(conn, "SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],))["balance"]
        if balance - req["amount"] < 0:
            # Returned, not raised, so the rejection is committed.
            message = f"Insufficient funds: {req['account']} has {balance:.2f}, payment is {req['amount']:.2f}"
            _decide(conn, req["id"], "rejected", "system", message)
            if po:
                conn.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (po["id"],))
            _close_if_done(conn, req["ticket_id"], today)
            return {"approval_request_id": req["id"], "status": "rejected", "error": message}

        new_balance = round(balance - req["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today, req["account"]))
        payment_id = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            (req["kind"], req["ref_id"], req["amount"], req["account"], today, approved_by),
        ).lastrowid
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        elif req["kind"] == "rent":
            lease = fetch_one(conn, "SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],))
            conn.execute(
                "UPDATE leases SET next_due = ?, notes = ? WHERE id = ?",
                (_add_month(lease["next_due"]), f"Rent due {lease['next_due']} paid {today} (payment {payment_id})", req["ref_id"]),
            )
        elif po:
            lead = fetch_one(conn, "SELECT lead_days FROM vendors WHERE id = ?", (po["vendor_id"],))["lead_days"]
            conn.execute(
                "UPDATE purchase_orders SET status = 'placed', expected_date = ? WHERE id = ?",
                ((date.fromisoformat(today) + timedelta(days=lead)).isoformat(), po["id"]),
            )
        _decide(conn, req["id"], "executed", approved_by, f"Paid; balance now {new_balance:.2f}", payment_id)
        _note_ticket(conn, req["ticket_id"], today, f"{req['kind']} payment {req['amount']:.2f} approved by {approved_by} (payment {payment_id})")
        _close_if_done(conn, req["ticket_id"], today)
        return {"approval_request_id": req["id"], "status": "executed", "payment_id": payment_id,
                "amount": req["amount"], "new_balance": new_balance}


def reject_approval_request(approval_request_id: int, decided_by: str, note: str = "") -> dict:
    """HUMAN-ONLY. Reject a pending approval request. A rejected purchase order is cancelled."""
    if not decided_by or not decided_by.strip():
        raise ToolError("decided_by must name the human reviewer")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        req = fetch_one(conn, "SELECT * FROM approval_requests WHERE id = ?", (approval_request_id,))
        if not req:
            raise ToolError(f"Approval request {approval_request_id} not found")
        if req["status"] != "pending":
            raise ToolError(f"Approval request {approval_request_id} is already {req['status']}")
        today = business_date(conn)
        _decide(conn, req["id"], "rejected", decided_by.strip(), note or "Rejected by reviewer")
        if req["kind"] == "purchase_order":
            conn.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (req["ref_id"],))
        _note_ticket(conn, req["ticket_id"], today, f"{req['kind']} request {req['id']} rejected by {decided_by.strip()}")
        _close_if_done(conn, req["ticket_id"], today)
        return {"approval_request_id": req["id"], "status": "rejected"}


def reset_working_database() -> dict:
    """HUMAN-ONLY. Restore data/campus_customs_new.db to the original starting values."""
    reset_working_db()
    with connect() as conn:
        return {
            "reset": True,
            "business_date": business_date(conn),
            "checking_balance": fetch_one(conn, "SELECT balance FROM cash_accounts WHERE name = 'checking'")["balance"],
            "open_tickets": conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0],
        }


TOOLS = [execute_approved_payment, reject_approval_request, reset_working_database]

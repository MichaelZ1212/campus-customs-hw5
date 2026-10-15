"""MCP tools for Campus Customs.

Each tool is a plain function: it reads the working database, returns a dict, and
raises ToolError for missing or invalid records (the message reaches the agent).
server.py registers everything in TOOLS, so a new tool only needs a function here
and an entry in that list.

All three tools are read-only.
"""

from __future__ import annotations

from datetime import date, timedelta

from mcp.server.fastmcp.exceptions import ToolError

from .db import business_date, connect, fetch_all, fetch_one


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _unpaid_invoices(conn, vendor_id: int, today: str) -> list[dict]:
    invoices = fetch_all(
        conn,
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status != 'paid' ORDER BY due_date",
        (vendor_id,),
    )
    for invoice in invoices:
        invoice["days_overdue"] = max(0, _days_between(invoice["due_date"], today))
    return invoices


def _stock_row(conn, sku: str, size: str) -> dict:
    stock = fetch_one(conn, "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?", (sku, size))
    if stock:
        return stock
    sizes = [r["size"] for r in fetch_all(conn, "SELECT size FROM inventory WHERE sku = ?", (sku,))]
    if sizes:
        raise ToolError(f"SKU {sku} has no size '{size}'. Available sizes: {', '.join(sizes)}")
    raise ToolError(f"Unknown SKU '{sku}'")


def _pricing(conn, sku: str) -> dict:
    pricing = fetch_one(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not pricing:
        raise ToolError(f"No pricing record for SKU '{sku}'")
    return pricing


def check_stock_and_vendor_status(sku: str, size: str, qty_needed: int = 1) -> dict:
    """Check whether a product size is in stock and, if not, which vendors can restock it.

    Supports customer orders (ticket 101). Returns on-hand stock, the shortfall,
    restock cost at unit cost, any invoices that mention this SKU, and every vendor
    with its specialty, lead time, unpaid invoices and whether it may take new
    orders (a vendor with unpaid invoices may not).
    """
    if qty_needed <= 0:
        raise ToolError("qty_needed must be a positive integer")
    with connect() as conn:
        today = business_date(conn)
        stock = _stock_row(conn, sku, size)
        pricing = _pricing(conn, sku)
        shortfall = max(0, qty_needed - stock["qty"])

        vendors = fetch_all(conn, "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
        for vendor in vendors:
            unpaid = _unpaid_invoices(conn, vendor["id"], today)
            vendor["unpaid_invoices"] = unpaid
            vendor["can_accept_new_orders"] = not unpaid
            vendor["earliest_delivery_if_ordered_today"] = (
                date.fromisoformat(today) + timedelta(days=vendor["lead_days"])
            ).isoformat()

        related_invoices = fetch_all(
            conn,
            "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.status, i.description "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.description LIKE ? ORDER BY i.id",
            (f"%{sku}%",),
        )
        return {
            "business_date": today,
            "product": {"sku": sku, "name": stock["name"], "size": size, "location": stock["location"]},
            "on_hand": stock["qty"],
            "qty_needed": qty_needed,
            "in_stock": shortfall == 0,
            "shortfall": shortfall,
            "unit_cost": pricing["unit_cost"],
            "list_price": pricing["list_price"],
            "restock_cost_for_shortfall": round(shortfall * pricing["unit_cost"], 2),
            "invoices_mentioning_this_sku": related_invoices,
            "vendors": vendors,
        }


def get_lease_payment_status(lease_id: int) -> dict:
    """Look up a lease's rent, due date and payment history, and whether cash covers it.

    Supports rent notices (ticket 102). Uses desk.date_today for days until due,
    lists rent payments already recorded against the lease, and compares the rent
    with each cash account balance (outflows only: no incoming cash is assumed).
    """
    with connect() as conn:
        today = business_date(conn)
        lease = fetch_one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        if not lease:
            raise ToolError(f"Lease {lease_id} not found")
        days_until_due = _days_between(today, lease["next_due"])
        rent = lease["monthly_rent"]

        accounts = fetch_all(conn, "SELECT name, balance, date FROM cash_accounts ORDER BY name")
        for account in accounts:
            account["can_cover_rent"] = account["balance"] >= rent
            account["balance_after_rent"] = round(account["balance"] - rent, 2)

        unpaid_invoices = fetch_all(conn, "SELECT id, vendor_id, amount, due_date FROM invoices WHERE status != 'paid'")
        return {
            "business_date": today,
            "lease": lease,
            "days_until_due": days_until_due,
            "is_overdue": days_until_due < 0,
            "rent_payments_recorded": fetch_all(
                conn, "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ? ORDER BY paid_at", (lease_id,)
            ),
            "cash_accounts": accounts,
            "other_unpaid_invoices": unpaid_invoices,
            "other_unpaid_invoices_total": round(sum(i["amount"] for i in unpaid_invoices), 2),
            "tickets_for_this_lease": fetch_all(
                conn, "SELECT id, type, subject, status FROM tickets WHERE lease_id = ?", (lease_id,)
            ),
        }


def evaluate_bulk_discount(sku: str, size: str, qty: int, discount_pct: float) -> dict:
    """Evaluate a bulk order with a requested percentage discount off list price.

    Supports price-override requests (ticket 103). Returns stock for the requested
    size (and other sizes), the shortfall and its restock cost, unit and order
    margins at the discount, the break-even discount, and current cash balances.
    """
    if qty <= 0:
        raise ToolError("qty must be a positive integer")
    if not 0 <= discount_pct < 100:
        raise ToolError("discount_pct must be at least 0 and below 100")
    with connect() as conn:
        today = business_date(conn)
        stock = _stock_row(conn, sku, size)
        pricing = _pricing(conn, sku)
        list_price, unit_cost = pricing["list_price"], pricing["unit_cost"]

        unit_price = round(list_price * (1 - discount_pct / 100), 2)
        unit_margin = round(unit_price - unit_cost, 2)
        shortfall = max(0, qty - stock["qty"])
        return {
            "business_date": today,
            "product": {"sku": sku, "name": stock["name"], "size": size},
            "requested_qty": qty,
            "on_hand": stock["qty"],
            "shortfall": shortfall,
            "other_sizes": fetch_all(
                conn, "SELECT size, qty FROM inventory WHERE sku = ? AND size != ? ORDER BY rowid", (sku, size)
            ),
            "restock_cost_for_shortfall": round(shortfall * unit_cost, 2),
            "pricing": {
                "list_price": list_price,
                "unit_cost": unit_cost,
                "margin_at_list_pct": round(100 * (list_price - unit_cost) / list_price, 1),
                "break_even_discount_pct": round(100 * (1 - unit_cost / list_price), 1),
            },
            "at_requested_discount": {
                "discount_pct": discount_pct,
                "unit_price": unit_price,
                "unit_margin": unit_margin,
                "margin_pct": round(100 * unit_margin / unit_price, 1) if unit_price else None,
                "sells_below_cost": unit_margin < 0,
                "order_revenue": round(unit_price * qty, 2),
                "order_margin": round(unit_margin * qty, 2),
                "discount_given": round((list_price - unit_price) * qty, 2),
            },
            "cash_accounts": fetch_all(conn, "SELECT name, balance FROM cash_accounts ORDER BY name"),
        }


TOOLS = [check_stock_and_vendor_status, get_lease_payment_status, evaluate_bulk_discount]

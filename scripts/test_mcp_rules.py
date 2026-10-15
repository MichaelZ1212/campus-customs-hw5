"""Exercise the MCP server's business rules over a real stdio connection.

Resets the working database first and again at the end, and checks that the
original database is never modified.  Usage:  python scripts/test_mcp_rules.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / "data" / "campus_customs.db"
results: list[tuple[str, bool]] = []


def expect(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{' - ' + detail if detail else ''}")


async def main() -> int:
    original_hash = hashlib.md5(ORIGINAL.read_bytes()).hexdigest()
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"],
                                   env={**os.environ, "PYTHONPATH": str(ROOT)}, cwd=str(ROOT))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
        await s.initialize()

        async def call(name: str, **args):
            r = await s.call_tool(name, args)
            text = r.content[0].text if r.content else ""
            return (not r.isError), (json.loads(text) if not r.isError else text)

        names = [t.name for t in (await s.list_tools()).tools]
        print(f"{len(names)} tools: {names}")
        expect("original three tools still registered",
               {"check_stock_and_vendor_status", "get_lease_payment_status", "evaluate_bulk_discount"} <= set(names))

        ok, out = await call("reset_working_database")
        expect("reset restores starting values", ok and out["checking_balance"] == 3400.0 and out["open_tickets"] == 3, str(out))

        ok, out = await call("get_business_date")
        expect("business date comes from desk", ok and out["business_date"] == "2026-08-31")

        ok, out = await call("create_purchase_order", ticket_id=101, vendor_id=1, sku="CC-TEE-WHITE", size="S",
                             qty=1, reason="test", requested_by="Accounting")
        expect("PO refused while vendor invoice 501 unpaid and not queued", not ok and "501" in out, out)

        ok, inv = await call("request_payment", kind="invoice", ref_id=501, ticket_id=101, reason="overdue", requested_by="Accounting")
        expect("invoice 501 payment queued, amount from DB", ok and inv["amount"] == 840.0)

        ok, dup = await call("request_payment", kind="invoice", ref_id=501, ticket_id=101, reason="again", requested_by="Accounting")
        expect("duplicate payment request not created", ok and dup["approval_request_id"] == inv["approval_request_id"])

        ok, po = await call("create_purchase_order", ticket_id=101, vendor_id=1, sku="CC-TEE-WHITE", size="S",
                            qty=1, reason="restock", requested_by="Accounting")
        expect("PO allowed once invoice payment is queued; lead time from DB",
               ok and po["total"] == 8.0 and po["expected_date_if_approved_today"] == "2026-09-05", str(po))

        ok, rent = await call("request_payment", kind="rent", ref_id=1, ticket_id=102, reason="rent", requested_by="Accounting")
        expect("rent payment queued", ok and rent["amount"] == 2400.0 and rent["available_after_all_pending"] == 152.0, str(rent))

        ok, out = await call("create_purchase_order", ticket_id=103, vendor_id=1, sku="CC-HOOD-NAVY", size="M",
                             qty=12, reason="restock", requested_by="Accounting")
        expect("hoodie PO ($264) refused: only $152 uncommitted", not ok and "152.00" in out, out)

        ok, out = await call("request_discount_approval", ticket_id=103, sku="CC-HOOD-NAVY", qty=20, discount_pct=70,
                             reason="t", requested_by="Accounting")
        expect("discount below cost refused", not ok and "below unit cost" in out, out)

        draft = dict(ticket_id=101, audience="customer", recipient="Tauhid Zaman", subject="Your tee", author="Customer Service")
        ok, out = await call("save_message_draft", **draft, body="Your Classic Bulldog Tee depends on the invoice approval.")
        expect("customer draft with internal terms refused", not ok and "invoice" in out and "approval" in out, out)
        ok, out = await call("save_message_draft", **draft, body="Your Classic Bulldog Tee (CC-TEE-WHITE) is on the way.")
        expect("customer draft with SKU code refused", not ok and "SKU" in out, out)
        ok, out = await call("save_message_draft", **draft, body="Your Bulldog tee in size S is on the way.")
        expect("customer draft without catalogue name refused", not ok and "Classic Bulldog Tee" in out, out)
        ok, out = await call("save_message_draft", **draft, body="Hi Tauhid, the Classic Bulldog Tee in size S is out of stock; we're arranging a restock.")
        expect("clean customer message saved as draft", ok and out["status"] == "draft", str(out))
        ok, out = await call("save_message_draft", ticket_id=102, audience="landlord", recipient="Elm City Properties",
                             subject="Rent", body="The rent payment request is pending approval.", author="Facilities")
        expect("non-customer drafts may mention payments", ok, str(out))

        ok, out = await call("update_ticket_status", ticket_id=101, status="resolved", note="t", updated_by="Boss")
        expect("cannot resolve a ticket with pending approvals", not ok, out)
        await call("update_ticket_status", ticket_id=101, status="awaiting_approval", note="t", updated_by="Boss")
        await call("update_ticket_status", ticket_id=102, status="awaiting_approval", note="t", updated_by="Boss")

        ok, out = await call("execute_approved_payment", approval_request_id=inv["approval_request_id"], approved_by="")
        expect("execution needs a named human approver", not ok, out)

        ok, out = await call("execute_approved_payment", approval_request_id=po["approval_request_id"], approved_by="Tester")
        expect("PO cannot execute before invoice is paid", not ok and "501" in out, out)

        ok, out = await call("execute_approved_payment", approval_request_id=inv["approval_request_id"], approved_by="Tester")
        expect("invoice payment executes", ok and out["new_balance"] == 2560.0, str(out))

        ok, out = await call("execute_approved_payment", approval_request_id=inv["approval_request_id"], approved_by="Tester")
        expect("same payment cannot execute twice", not ok and "already executed" in out, out)

        ok, out = await call("execute_approved_payment", approval_request_id=po["approval_request_id"], approved_by="Tester")
        expect("PO executes after invoice paid", ok and out["new_balance"] == 2552.0, str(out))

        ok, out = await call("execute_approved_payment", approval_request_id=rent["approval_request_id"], approved_by="Tester")
        expect("rent executes, balance stays >= 0", ok and out["new_balance"] == 152.0, str(out))

        ok, lease = await call("get_lease_payment_status", lease_id=1)
        expect("lease rolled forward and payment recorded",
               ok and lease["lease"]["next_due"] == "2026-10-02" and len(lease["rent_payments_recorded"]) == 1)

        ok, t101 = await call("get_ticket", ticket_id=101)
        expect("ticket auto-resolves when its approvals are done", ok and t101["status"] == "resolved", t101["status"])

        ok, drafts = await call("list_message_drafts", ticket_id=101)
        expect("drafts written before an approval are flagged needs_review",
               ok and drafts["drafts"] and all(d["status"] == "needs_review" for d in drafts["drafts"]),
               str([d["status"] for d in drafts["drafts"]]) if ok else drafts)

        ok, out = await call("reset_working_database")
        expect("reset after test", ok and out["checking_balance"] == 3400.0)

    expect("original database unchanged", hashlib.md5(ORIGINAL.read_bytes()).hexdigest() == original_hash)
    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f"; FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

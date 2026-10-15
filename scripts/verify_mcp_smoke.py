"""Cross-check output/mcp_smoke.json against the working SQLite database.

Values are compared with the starting data (data/campus_customs.db, which the working copy
matched when the smoke test ran). The expected values are re-queried here with plain SQL, independent of
mcp_server/tools.py, so a bug in a tool would show up as a mismatch.
Also confirms the original database still matches the copy inside data.zip.

Usage (from the project root):  python scripts/verify_mcp_smoke.py
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "output" / "mcp_smoke.json"
# The smoke test (Problem 4) captured the clean starting state, when the working copy was
# identical to the original. Later problems changed the working copy (payments, resolved
# tickets), so the starting values are checked against the original database.
REFERENCE_DB = ROOT / "data" / "campus_customs.db"
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"

failures: list[str] = []


def check(label: str, actual, expected) -> None:
    ok = actual == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: tool={actual!r} db={expected!r}")
    if not ok:
        failures.append(label)


def main() -> int:
    records = {r["tool_name"]: r for r in json.loads(SMOKE.read_text(encoding="utf-8"))}
    db = sqlite3.connect(f"file:{REFERENCE_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    one = lambda sql, *p: db.execute(sql, p).fetchone()
    today = one("SELECT date_today FROM desk")[0]

    print("check_stock_and_vendor_status (ticket 101)")
    out = records["check_stock_and_vendor_status"]["tool_output"]
    t = one("SELECT sku, size, qty FROM tickets WHERE id = 101")
    check("business_date", out["business_date"], today)
    check("sku/size matches ticket 101", (out["product"]["sku"], out["product"]["size"]), (t["sku"], t["size"]))
    check("on_hand", out["on_hand"], one("SELECT qty FROM inventory WHERE sku=? AND size=?", t["sku"], t["size"])[0])
    p = one("SELECT unit_cost, list_price FROM pricing WHERE sku=?", t["sku"])
    check("unit_cost", out["unit_cost"], p["unit_cost"])
    check("list_price", out["list_price"], p["list_price"])
    inv = one("SELECT id, amount, status FROM invoices WHERE id = (SELECT invoice_id FROM tickets WHERE id = 101)")
    found = {i["id"]: i for i in out["invoices_mentioning_this_sku"]}
    check("linked invoice present", inv["id"] in found, True)
    if inv["id"] in found:
        check("invoice amount/status", (found[inv["id"]]["amount"], found[inv["id"]]["status"]), (inv["amount"], inv["status"]))
    for v in out["vendors"]:
        row = one("SELECT lead_days FROM vendors WHERE id=?", v["id"])
        unpaid = [r[0] for r in db.execute("SELECT id FROM invoices WHERE vendor_id=? AND status!='paid'", (v["id"],))]
        check(f"vendor {v['id']} lead_days", v["lead_days"], row["lead_days"])
        check(f"vendor {v['id']} unpaid invoices", [i["id"] for i in v["unpaid_invoices"]], unpaid)

    print("get_lease_payment_status (ticket 102)")
    out = records["get_lease_payment_status"]["tool_output"]
    lease = dict(one("SELECT * FROM leases WHERE id = (SELECT lease_id FROM tickets WHERE id = 102)"))
    check("lease record", out["lease"], lease)
    check("business_date", out["business_date"], today)
    check("checking balance", out["cash_accounts"][0]["balance"], one("SELECT balance FROM cash_accounts WHERE name='checking'")[0])
    check("rent payments recorded", len(out["rent_payments_recorded"]),
          one("SELECT COUNT(*) FROM payments WHERE kind='rent' AND ref_id=?", lease["id"])[0])

    print("evaluate_bulk_discount (ticket 103)")
    out = records["evaluate_bulk_discount"]["tool_output"]
    t = one("SELECT sku, size, qty FROM tickets WHERE id = 103")
    check("sku/size/qty matches ticket 103", (out["product"]["sku"], out["product"]["size"], out["requested_qty"]), (t["sku"], t["size"], t["qty"]))
    on_hand = one("SELECT qty FROM inventory WHERE sku=? AND size=?", t["sku"], t["size"])[0]
    check("on_hand", out["on_hand"], on_hand)
    check("shortfall", out["shortfall"], max(0, t["qty"] - on_hand))
    p = one("SELECT unit_cost, list_price FROM pricing WHERE sku=?", t["sku"])
    check("pricing", (out["pricing"]["unit_cost"], out["pricing"]["list_price"]), (p["unit_cost"], p["list_price"]))
    check("other sizes", {s["size"]: s["qty"] for s in out["other_sizes"]},
          {r[0]: r[1] for r in db.execute("SELECT size, qty FROM inventory WHERE sku=? AND size!=?", (t["sku"], t["size"]))})

    print("original database")
    with zipfile.ZipFile(ROOT / "data.zip") as z:
        archived = hashlib.md5(z.read("data/campus_customs.db")).hexdigest()
    check("data/campus_customs.db matches data.zip", hashlib.md5(ORIGINAL_DB.read_bytes()).hexdigest(), archived)

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} FAILED: {failures}'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

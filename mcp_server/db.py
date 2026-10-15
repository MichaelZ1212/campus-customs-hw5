"""Database connection for the Campus Customs MCP server.

Every tool works against the working copy, data/campus_customs_new.db.
The original data/campus_customs.db is only ever read, by reset_working_db(),
to restore the working copy to its starting values.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKING_DB = Path(os.getenv("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db"))
ORIGINAL_DB = Path(os.getenv("CAMPUS_CUSTOMS_ORIGINAL_DB", ROOT / "data" / "campus_customs.db"))

# Workflow tables that exist only in the working copy. The original schema has
# nowhere to keep approval requests, purchase orders or message drafts.
WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    kind TEXT NOT NULL,             -- invoice | rent | purchase_order | discount
    ref_id INTEGER NOT NULL,        -- invoices.id | leases.id | purchase_orders.id | tickets.id
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | executed | rejected
    decided_by TEXT,
    decision_note TEXT,
    payment_id INTEGER REFERENCES payments(id),
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    expected_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'awaiting_approval',   -- awaiting_approval | placed | cancelled
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    audience TEXT NOT NULL,         -- customer | vendor | landlord | internal
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',      -- draft | needs_review (an approval was decided after it was written); never sent
    created_at TEXT NOT NULL
);
"""


def _open() -> sqlite3.Connection:
    conn = sqlite3.connect(WORKING_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect():
    """Open the working database. Commits on success, rolls back on any error."""
    if not WORKING_DB.exists():
        raise FileNotFoundError(
            f"Working database not found at {WORKING_DB}. "
            "Copy data/campus_customs.db to data/campus_customs_new.db first."
        )
    conn = _open()
    try:
        conn.executescript(WORKFLOW_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_working_db() -> None:
    """Overwrite the working copy with the original database's starting values."""
    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(f"Original database not found at {ORIGINAL_DB}. Extract data.zip first.")
    for suffix in ("-wal", "-shm", "-journal"):
        Path(f"{WORKING_DB}{suffix}").unlink(missing_ok=True)
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def business_date(conn: sqlite3.Connection) -> str:
    """desk.date_today: the official current date for all business logic."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if not row:
        raise LookupError("desk table has no date_today")
    return row[0]

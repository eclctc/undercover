"""The SQLite database behind the UnderCover backend."""

import os
import sqlite3
from collections.abc import Generator
from pathlib import Path

DB_PATH = Path(os.getenv("UNDERCOVER_DB", "backend/undercover.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans (plan TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS add_ons (add_on TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    decision TEXT NOT NULL,
    payout REAL NOT NULL,
    reasons TEXT NOT NULL,
    policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    amount REAL NOT NULL,
    signed_off_by TEXT,
    paid_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL REFERENCES claims,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    """Open the database at path, creating the tables if they are missing."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def session() -> Generator[sqlite3.Connection]:
    """Yield a connection to the database for one request."""
    conn = connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

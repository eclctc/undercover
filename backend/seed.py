"""Seed the database from UnderCover's records in data/."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend import db

DATA_DIR = Path("data")


def load(name: str) -> Any:
    """Load one JSON file from the data folder."""
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def insert(conn: sqlite3.Connection, table: str, key: str, records: list) -> None:
    """Insert records into a table keyed by one of their fields."""
    conn.executemany(
        f"INSERT INTO {table} ({key}, data) VALUES (?, ?)",  # noqa: S608
        [(record[key], json.dumps(record)) for record in records],
    )


def seed(conn: sqlite3.Connection) -> None:
    """Fill an empty database with the queue and the records behind it."""
    claims = load("claims.json")
    conn.executemany(
        "INSERT INTO claims (claim_id, policy_id, customer_id, status, data)"
        " VALUES (?, ?, ?, 'waiting', ?)",
        [
            (c["claim_id"], c["policy_id"], c["customer_id"], json.dumps(c))
            for c in claims
        ],
    )
    insert(conn, "policies", "policy_id", load("policies.json"))
    insert(conn, "customers", "customer_id", load("customers.json"))
    plans = load("plans.json")
    insert(conn, "plans", "plan", plans["plans"])
    insert(conn, "add_ons", "add_on", plans["add_ons"])
    insert(conn, "handlers", "handler_id", load("handlers.json"))
    conn.commit()


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Count the rows in each seeded table."""
    tables = ["claims", "policies", "customers", "plans", "add_ons", "handlers"]
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        for table in tables
    }


def ensure_seeded(path: Path) -> None:
    """Seed the database at path if it has no claims yet."""
    conn = db.connect(path)
    if counts(conn)["claims"] == 0:
        seed(conn)
    conn.close()


def reset(path: Path) -> dict[str, int]:
    """Delete the database at path, seed a fresh one and return its counts."""
    path.unlink(missing_ok=True)
    conn = db.connect(path)
    seed(conn)
    result = counts(conn)
    conn.close()
    return result


if __name__ == "__main__":
    for table, count in reset(db.DB_PATH).items():
        print(f"{table}: {count}")

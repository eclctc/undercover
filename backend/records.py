"""Reading UnderCover's records from the database."""

import json
import sqlite3
from typing import Annotated, Any

from fastapi import Depends, HTTPException

from backend import db

Conn = Annotated[sqlite3.Connection, Depends(db.session)]


def fetch(conn: sqlite3.Connection, table: str, key: str, value: str) -> sqlite3.Row:
    """Return one row by its key, or raise 404 if there is none."""
    row = conn.execute(
        f"SELECT * FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {key} {value}")
    return row


def claim_record(conn: sqlite3.Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim with its status, decision and payment."""
    row = fetch(conn, "claims", "claim_id", claim_id)
    decision = conn.execute(
        "SELECT decision, payout, reasons, policy_section, decided_at"
        " FROM decisions WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    payment = conn.execute(
        "SELECT amount, signed_off_by, paid_at FROM payments WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    return {
        **json.loads(row["data"]),
        "status": row["status"],
        "failures": row["failures"],
        "decision": dict(decision) if decision else None,
        "payment": dict(payment) if payment else None,
    }

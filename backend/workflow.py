"""Working a claim: the agent's steps, the decision, payment and sign-off."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend import seed
from backend.records import Conn, claim_record, fetch

PAYOUT_APPROVAL_LIMIT: float = seed.load("company.json")["payout_approval_limit"]

router = APIRouter(prefix="/api/claims/{claim_id}")


class Step(BaseModel):
    """One thing the agent did while working a claim."""

    kind: str
    detail: str


class Decision(BaseModel):
    """The agent's decision on a claim."""

    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    reasons: str
    policy_section: str

    @model_validator(mode="after")
    def only_approvals_pay(self) -> Self:
        """Require a payout of 0 unless the claim is approved."""
        if self.decision != "approve" and self.payout != 0:
            raise ValueError("Only an approval has a payout")
        return self


class Payment(BaseModel):
    """A payment of a claim."""

    amount: float


class SignOff(BaseModel):
    """A handler's sign-off on a payout over the approval limit."""

    handler_id: str


def now() -> str:
    """Return the current time in UTC as ISO 8601."""
    return datetime.now(UTC).isoformat()


def require_status(conn: sqlite3.Connection, claim_id: str, status: str) -> None:
    """Raise 409 unless the claim has the given status."""
    actual = fetch(conn, "claims", "claim_id", claim_id)["status"]
    if actual != status:
        raise HTTPException(409, f"Claim {claim_id} is {actual}, not {status}")


def set_status(conn: sqlite3.Connection, claim_id: str, status: str) -> None:
    """Set a claim's status."""
    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


def record_payment(
    conn: sqlite3.Connection, claim_id: str, amount: float, signed_off_by: str | None
) -> None:
    """Record that a claim was paid."""
    conn.execute(
        "INSERT INTO payments (claim_id, amount, signed_off_by, paid_at)"
        " VALUES (?, ?, ?, ?)",
        (claim_id, amount, signed_off_by, now()),
    )


def payment_refusal(claim: dict[str, Any], amount: float) -> str | None:
    """Return why a payment may not be made, or None if it may."""
    decision = claim["decision"]
    if decision is None or decision["decision"] != "approve":
        return "Only an approved claim can be paid"
    if claim["payment"] is not None:
        return "This claim has already been paid"
    if round(amount, 2) != round(decision["payout"], 2):
        return f"The payment must equal the approved payout of {decision['payout']}"
    if claim["status"] == "awaiting_sign_off":
        return (
            f"A payout over ${PAYOUT_APPROVAL_LIMIT:,.2f} needs a handler's sign-off,"
            " so the payment waits until a handler signs off"
        )
    return None


@router.post("/start", operation_id="start_claim")
def start_claim(claim_id: str, conn: Conn) -> dict[str, Any]:
    """Move a waiting claim to in progress."""
    require_status(conn, claim_id, "waiting")
    set_status(conn, claim_id, "in_progress")
    conn.commit()
    return claim_record(conn, claim_id)


@router.post("/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step, conn: Conn) -> dict[str, str]:
    """Record one step the agent took on a claim."""
    fetch(conn, "claims", "claim_id", claim_id)
    conn.execute(
        "INSERT INTO steps (claim_id, kind, detail, recorded_at) VALUES (?, ?, ?, ?)",
        (claim_id, step.kind, step.detail, now()),
    )
    conn.commit()
    return {"status": "recorded"}


@router.get("/steps", operation_id="list_steps")
def list_steps(claim_id: str, conn: Conn) -> list[dict[str, Any]]:
    """List the steps the agent took on a claim, in order."""
    fetch(conn, "claims", "claim_id", claim_id)
    rows = conn.execute(
        "SELECT step_id, kind, detail, recorded_at FROM steps"
        " WHERE claim_id = ? ORDER BY step_id",
        (claim_id,),
    )
    return [dict(row) for row in rows]


@router.post("/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: Decision, conn: Conn) -> dict[str, Any]:
    """Record the decision on a claim that is in progress."""
    require_status(conn, claim_id, "in_progress")
    conn.execute(
        "INSERT INTO decisions"
        " (claim_id, decision, payout, reasons, policy_section, decided_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (claim_id, *decision.model_dump().values(), now()),
    )
    over_limit = decision.payout > PAYOUT_APPROVAL_LIMIT
    set_status(conn, claim_id, "awaiting_sign_off" if over_limit else "decided")
    conn.commit()
    return claim_record(conn, claim_id)


@router.post("/payments", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment, conn: Conn) -> dict[str, Any]:
    """Pay an approved claim its payout, if it needs no sign-off or has one."""
    claim = claim_record(conn, claim_id)
    refusal = payment_refusal(claim, payment.amount)
    if refusal:
        raise HTTPException(409, refusal)
    record_payment(conn, claim_id, payment.amount, None)
    conn.commit()
    return claim_record(conn, claim_id)


@router.post("/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOff, conn: Conn) -> dict[str, Any]:
    """Sign off a payout over the approval limit and release the payment."""
    require_status(conn, claim_id, "awaiting_sign_off")
    handler = json.loads(
        fetch(conn, "handlers", "handler_id", sign_off.handler_id)["data"]
    )
    if not handler["can_approve_over_limit"]:
        raise HTTPException(409, f"{handler['name']} cannot sign off this payout")
    payout = claim_record(conn, claim_id)["decision"]["payout"]
    record_payment(conn, claim_id, payout, sign_off.handler_id)
    set_status(conn, claim_id, "decided")
    conn.commit()
    return claim_record(conn, claim_id)

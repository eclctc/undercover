"""The UnderCover backend."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from backend import db, documents, runs, seed, workflow
from backend.records import Conn, claim_record, fetch

INSTRUCTIONS_DIR = Path("backend/instructions")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Seed the database on first start."""
    seed.ensure_seeded(db.DB_PATH)
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
app.include_router(workflow.router)
app.include_router(documents.router)
app.include_router(runs.router)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(conn: Conn) -> list[dict[str, Any]]:
    """List every claim in the queue with where it stands."""
    rows = conn.execute("SELECT status, data FROM claims ORDER BY claim_id")
    fields = ["claim_id", "claim_type", "summary", "amount_claimed", "submitted_on"]
    return [
        {field: json.loads(row["data"])[field] for field in fields}
        | {"status": row["status"]}
        for row in rows
    ]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Conn) -> dict[str, Any]:
    """Get a claim in full, with its status, decision and payment."""
    return claim_record(conn, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, conn: Conn) -> dict[str, Any]:
    """Get a policy with its plan's limits and the add-ons it has."""
    policy = json.loads(fetch(conn, "policies", "policy_id", policy_id)["data"])
    plan = json.loads(fetch(conn, "plans", "plan", policy["plan"])["data"])
    add_ons = [
        json.loads(fetch(conn, "add_ons", "add_on", add_on)["data"])
        for add_on in policy["add_ons"]
    ]
    return {**policy, "plan_details": plan, "add_on_details": add_ons}


@app.get("/api/customers/{customer_id}/claim-history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, conn: Conn) -> dict[str, Any]:
    """Get a customer's name and earlier claims, without their contact details."""
    customer = json.loads(fetch(conn, "customers", "customer_id", customer_id)["data"])
    fields = ["customer_id", "name", "customer_since", "previous_claims"]
    return {field: customer[field] for field in fields}


@app.get("/api/agent-instructions", operation_id="get_agent_instructions")
def get_agent_instructions() -> dict[str, str]:
    """Get the agent's instructions for running the queue and for working a claim."""
    return {
        name: (INSTRUCTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")
        for name in ["queue", "claim"]
    }


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(conn: Conn) -> list[dict[str, Any]]:
    """List the claims handlers."""
    rows = conn.execute("SELECT data FROM handlers ORDER BY handler_id")
    return [json.loads(row["data"]) for row in rows]

"""The agent's tools, each a call to the UnderCover backend's API."""

import json
from typing import Any, Literal

import httpx
from langchain_core.tools import tool

BACKEND_URL = "http://localhost:8000"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend and return its JSON, raising on a server error."""
    with backend() as client:
        response = client.request(method, path, json=body)
    response.raise_for_status()
    return response.json()


def call_for_model(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return the reply as text, including a refusal's reason."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_client_error:
        return f"Refused ({response.status_code}): {response.json()['detail']}"
    response.raise_for_status()
    return json.dumps(response.json())


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim in full: the story, the items claimed and the documents."""
    return call_for_model("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy with its plan's limits, its add-ons, the trip and the travelers."""
    return call_for_model("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> str:
    """Get a customer's earlier claims."""
    return call_for_model("GET", f"/api/customers/{customer_id}/claim-history")


@tool
def get_policy_wording() -> str:
    """Get the policy wording, the contract that decisions follow."""
    return call("GET", "/api/policy-wording")["text"]


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reasons: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim, with the payout (0 unless approved)."""
    body = {
        "decision": decision,
        "payout": payout,
        "reasons": reasons,
        "policy_section": policy_section,
    }
    return call_for_model("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim exactly its approved payout."""
    return call_for_model(
        "POST", f"/api/claims/{claim_id}/payments", {"amount": amount}
    )


TOOLS = [
    get_claim,
    get_policy,
    get_claim_history,
    get_policy_wording,
    record_decision,
    pay_claim,
]

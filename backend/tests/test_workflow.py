import pytest

from backend import db

CLAIM = "/api/claims/CLM-1001"


def approve(client, payout):
    client.post(f"{CLAIM}/start")
    return client.post(
        f"{CLAIM}/decision",
        json={
            "decision": "approve",
            "payout": payout,
            "reasons": "Covered delay.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def test_start_claim(client):
    assert client.post(f"{CLAIM}/start").json()["status"] == "in_progress"
    assert client.post(f"{CLAIM}/start").status_code == 409


def test_steps_come_back_in_order(client):
    for n in range(3):
        client.post(f"{CLAIM}/steps", json={"kind": "tool_call", "detail": f"step {n}"})
    steps = client.get(f"{CLAIM}/steps").json()
    assert [s["detail"] for s in steps] == ["step 0", "step 1", "step 2"]


def test_steps_need_a_known_claim(client):
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404
    step = {"kind": "tool_call", "detail": "x"}
    assert client.post("/api/claims/CLM-9999/steps", json=step).status_code == 404


def test_decision_needs_a_claim_in_progress(client):
    decision = {
        "decision": "decline",
        "payout": 0,
        "reasons": "Not covered.",
        "policy_section": "Section 9",
    }
    assert client.post(f"{CLAIM}/decision", json=decision).status_code == 409


def test_only_approvals_have_a_payout(client):
    client.post(f"{CLAIM}/start")
    decision = {
        "decision": "refer",
        "payout": 10,
        "reasons": "Needs a look.",
        "policy_section": "Section 11",
    }
    assert client.post(f"{CLAIM}/decision", json=decision).status_code == 422


def test_approval_under_the_limit_is_decided_and_paid_once(client):
    claim = approve(client, 420.0).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0
    paid = client.post(f"{CLAIM}/payments", json={"amount": 420.0}).json()
    assert paid["payment"]["amount"] == 420.0
    second = client.post(f"{CLAIM}/payments", json={"amount": 420.0})
    assert second.status_code == 409
    assert "already been paid" in second.json()["detail"]


def test_approval_over_the_limit_waits_for_sign_off(client):
    assert approve(client, 1250.0).json()["status"] == "awaiting_sign_off"
    blocked = client.post(f"{CLAIM}/payments", json={"amount": 1250.0})
    assert blocked.status_code == 409
    assert "sign-off" in blocked.json()["detail"]
    signed = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-01"}).json()
    assert signed["status"] == "decided"
    assert signed["payment"] == {
        "amount": 1250.0,
        "signed_off_by": "HND-01",
        "paid_at": signed["payment"]["paid_at"],
    }


def test_payment_must_match_the_payout(client):
    approve(client, 420.0)
    response = client.post(f"{CLAIM}/payments", json={"amount": 500.0})
    assert response.status_code == 409


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_only_approved_claims_are_paid(client, decision):
    client.post(f"{CLAIM}/start")
    client.post(
        f"{CLAIM}/decision",
        json={
            "decision": decision,
            "payout": 0,
            "reasons": "No.",
            "policy_section": "Section 9",
        },
    )
    assert client.post(f"{CLAIM}/payments", json={"amount": 0}).status_code == 409


def test_sign_off_needs_a_claim_awaiting_it(client):
    approve(client, 420.0)
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-01"})
    assert response.status_code == 409


def test_sign_off_needs_a_handler_who_may_approve(client, fresh_db):
    db.connect(fresh_db).execute(
        "INSERT INTO handlers VALUES ('HND-99', ?)",
        ('{"name": "Trainee", "can_approve_over_limit": false}',),
    ).connection.commit()
    approve(client, 1250.0)
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-99"})
    assert response.status_code == 409
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-00"})
    assert response.status_code == 404

import pytest

from backend import seed
from backend.runs import STOPPED_RUN_REASON

CLAIM = "/api/claims/CLM-1001"
TODOS = [
    {"content": "Work CLM-1001", "status": "done"},
    {"content": "Work CLM-1002", "status": "in_progress"},
    {"content": "Work CLM-1003", "status": "to_do"},
    {"content": "Work CLM-1004", "status": "left_for_handler"},
]


def fail(client, reason="The model timed out"):
    return client.post(f"{CLAIM}/fail", json={"reason": reason})


def test_no_run_before_the_first(client):
    assert client.get("/api/runs/latest").json() is None


def test_a_run_starts_with_its_cap_and_an_empty_list(client):
    run = client.post("/api/runs", json={"cap": 5}).json()
    assert run["cap"] == 5
    assert run["todos"] == []
    assert run["finished_at"] is None
    assert run["summary"] is None


def test_a_cap_must_be_at_least_one(client):
    assert client.post("/api/runs", json={"cap": 0}).status_code == 422


def test_record_todos_replaces_the_list(client):
    run_id = client.post("/api/runs", json={"cap": 5}).json()["run_id"]
    client.put(f"/api/runs/{run_id}/todos", json={"todos": TODOS})
    run = client.put(f"/api/runs/{run_id}/todos", json={"todos": TODOS[:1]}).json()
    assert run["todos"] == TODOS[:1]


def test_a_todo_needs_a_known_status(client):
    run_id = client.post("/api/runs", json={"cap": 5}).json()["run_id"]
    todos = [{"content": "Work CLM-1001", "status": "pending"}]
    response = client.put(f"/api/runs/{run_id}/todos", json={"todos": todos})
    assert response.status_code == 422


def test_finish_saves_the_summary(client):
    run_id = client.post("/api/runs", json={"cap": 5}).json()["run_id"]
    run = client.post(
        f"/api/runs/{run_id}/finish", json={"summary": "Worked five claims."}
    ).json()
    assert run["summary"] == "Worked five claims."
    assert run["finished_at"]


def test_the_latest_run_is_the_newest(client):
    client.post("/api/runs", json={"cap": 5})
    client.post("/api/runs", json={"cap": 2})
    run = client.get("/api/runs/latest").json()
    client.put(f"/api/runs/{run['run_id']}/todos", json={"todos": TODOS})
    latest = client.get("/api/runs/latest").json()
    assert latest["cap"] == 2
    assert latest["todos"] == TODOS


def test_todos_need_a_known_run(client):
    response = client.put("/api/runs/99/todos", json={"todos": []})
    assert response.status_code == 404


def test_finish_needs_a_known_run(client):
    response = client.post("/api/runs/99/finish", json={"summary": "x"})
    assert response.status_code == 404


def test_a_first_failure_puts_the_claim_back_in_the_queue(client):
    client.post(f"{CLAIM}/start")
    claim = fail(client).json()
    assert claim["status"] == "waiting"
    assert claim["failures"] == 1
    steps = client.get(f"{CLAIM}/steps").json()
    assert [(s["kind"], s["detail"]) for s in steps] == [
        ("error", "The model timed out")
    ]


def test_a_second_failure_leaves_the_claim_for_a_handler(client):
    client.post(f"{CLAIM}/start")
    fail(client)
    client.post(f"{CLAIM}/start")
    claim = fail(client).json()
    assert claim["status"] == "needs_handler"
    assert claim["failures"] == 2
    assert client.post(f"{CLAIM}/start").status_code == 409


def test_a_waiting_claim_cannot_fail(client):
    assert fail(client).status_code == 409


@pytest.mark.parametrize(
    ("payout", "status"), [(420.0, "decided"), (1250.0, "awaiting_sign_off")]
)
def test_a_decided_claim_never_goes_back_in_the_queue(client, payout, status):
    client.post(f"{CLAIM}/start")
    client.post(
        f"{CLAIM}/decision",
        json={
            "decision": "approve",
            "payout": payout,
            "reasons": "Covered.",
            "policy_section": "Section 3",
        },
    )
    assert client.get(CLAIM).json()["status"] == status
    assert fail(client).status_code == 409


def test_a_run_fails_claims_a_stopped_run_left_in_progress(client):
    client.post(f"{CLAIM}/start")
    client.post("/api/runs", json={"cap": 5})
    claim = client.get(CLAIM).json()
    assert claim["status"] == "waiting"
    assert claim["failures"] == 1
    assert client.get(f"{CLAIM}/steps").json()[-1]["detail"] == STOPPED_RUN_REASON


def test_a_retried_claim_is_decided_and_paid_once(client):
    client.post(f"{CLAIM}/start")
    fail(client)
    client.post(f"{CLAIM}/start")
    client.post(
        f"{CLAIM}/decision",
        json={
            "decision": "approve",
            "payout": 420.0,
            "reasons": "Covered.",
            "policy_section": "Section 3",
        },
    )
    second_decision = client.post(
        f"{CLAIM}/decision",
        json={
            "decision": "decline",
            "payout": 0,
            "reasons": "No.",
            "policy_section": "Section 9",
        },
    )
    assert second_decision.status_code == 409
    assert client.post(f"{CLAIM}/payments", json={"amount": 420.0}).is_success
    assert client.post(f"{CLAIM}/payments", json={"amount": 420.0}).status_code == 409


def test_reseeding_clears_failures(client, fresh_db):
    client.post(f"{CLAIM}/start")
    fail(client)
    seed.reset(fresh_db)
    assert client.get(CLAIM).json()["failures"] == 0

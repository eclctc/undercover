import pytest


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
    }


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert claim["payment"] is None


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["add_on_details"] == []


def test_get_policy_with_add_ons(client):
    policies = [client.get(f"/api/policies/POL-{n}").json() for n in range(2001, 2026)]
    with_add_ons = [p for p in policies if p["add_ons"]]
    assert with_add_ons
    policy = with_add_ons[0]
    assert [a["add_on"] for a in policy["add_on_details"]] == policy["add_ons"]


def test_get_claim_history_leaves_out_contact_details(client):
    history = client.get("/api/customers/CUS-3001/claim-history").json()
    assert history["name"] == "Maya Patel"
    assert [c["claim_id"] for c in history["previous_claims"]] == ["CLM-0412"]
    assert not {"address", "phone", "email", "date_of_birth"} & history.keys()


def test_get_policy_wording(client):
    text = client.get("/api/policy-wording").json()["text"]
    assert text.startswith("# UnderCover Travel Insurance: Policy Wording")


def test_get_agent_instructions(client):
    text = client.get("/api/agent-instructions").json()["text"]
    assert "UnderCover Agent" in text


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/claims/CLM-9999",
        "/api/policies/POL-9999",
        "/api/customers/CUS-9999/claim-history",
    ],
)
def test_unknown_records_are_404(client, path):
    assert client.get(path).status_code == 404


def test_every_operation_is_well_defined(client):
    spec = client.get("/openapi.json").json()
    for path in spec["paths"].values():
        for operation in path.values():
            assert operation["operationId"]
            assert "\n" not in operation["description"].strip()
            assert all(p["required"] for p in operation.get("parameters", []))
            body = operation.get("requestBody")
            if body:
                schema_ref = body["content"]["application/json"]["schema"]["$ref"]
                schema = spec["components"]["schemas"][schema_ref.split("/")[-1]]
                assert set(schema["required"]) == set(schema["properties"])

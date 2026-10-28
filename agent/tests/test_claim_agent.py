from langchain_core.messages import AIMessage

from agent import claim_agent, model, tools
from agent.tests.stubs import FailingModel, StubModel, decline, tool_call

CLAIM = "/api/claims/CLM-1001"


def decide(payout):
    return [
        tool_call("get_claim", claim_id="CLM-1001"),
        tool_call("get_policy", policy_id="POL-2001"),
        tool_call("get_claim_history", customer_id="CUS-3001"),
        tool_call("get_document_contents", document="policy_wording"),
        tool_call("get_document_section", document="policy_wording", section="3"),
        tool_call("get_document_section", document="claims_manual", section="10"),
        tool_call(
            "record_decision",
            claim_id="CLM-1001",
            decision="approve",
            payout=payout,
            reasons="A covered crew problem delayed the flight.",
            policy_section="Section 3, Trip Delay",
        ),
        tool_call("pay_claim", claim_id="CLM-1001", amount=payout),
        AIMessage(content="Approved."),
    ]


def work(replies, llm_class=StubModel, **fields):
    llm = llm_class(messages=iter(replies), **fields)
    return claim_agent.work_claim("CLM-1001", llm)


def steps(client):
    return client.get(f"{CLAIM}/steps").json()


def test_a_claim_is_decided_paid_and_reported_in_a_line(client):
    assert work(decide(420.0)) == "CLM-1001: approve, $420.00, paid"
    claim = client.get(CLAIM).json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0


def test_sections_read_are_recorded_in_order(client):
    work(decide(420.0))
    reads = [s["detail"] for s in steps(client) if s["kind"] == "read"]
    assert reads == [
        "Policy wording, 3. Trip Delay",
        "Claims manual, 10. Meals without receipts",
    ]
    kinds = [s["kind"] for s in steps(client)]
    assert kinds == ["tool_call", "tool_result"] * 4 + ["tool_call", "read"] * 2 + [
        "tool_call",
        "tool_result",
    ] * 2 + ["message"]


def test_long_results_are_cut_short(client):
    work(decide(420.0))
    result = steps(client)[1]["detail"]
    assert result.startswith("get_claim: ")
    assert len(result) == len("get_claim: ") + claim_agent.STEP_DETAIL_LENGTH + 3


def test_a_missing_section_comes_back_as_a_refusal(client):
    work(
        [
            tool_call("get_document_section", document="claims_manual", section="99"),
            *decide(420.0),
        ]
    )
    assert steps(client)[1]["detail"].startswith("get_document_section: Refused (404)")


def test_a_payout_over_the_limit_waits_for_sign_off(client):
    report = work(decide(1250.0))
    assert report == "CLM-1001: approve, $1,250.00, waiting for a handler's sign-off"
    claim = client.get(CLAIM).json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    results = [s["detail"] for s in steps(client)]
    assert any(r.startswith("pay_claim: Refused (409)") for r in results)


def test_a_passing_model_failure_is_retried(client):
    assert work(decide(420.0), FailingModel, failures=1).endswith("paid")


def test_a_failing_model_puts_the_claim_back_in_the_queue(client):
    report = work([], FailingModel)
    assert report == (
        "CLM-1001: failed (TimeoutError: The model provider timed out),"
        " back in the queue"
    )
    claim = client.get(CLAIM).json()
    assert claim["status"] == "waiting"
    assert claim["failures"] == 1
    assert steps(client)[-1]["kind"] == "error"


def test_stopping_without_a_decision_is_a_failure(client):
    report = work([AIMessage(content="I am not sure.")])
    assert report == f"CLM-1001: failed ({claim_agent.NO_DECISION}), back in the queue"


def test_a_looping_agent_stops_at_the_call_limit(client, monkeypatch):
    monkeypatch.setattr(claim_agent, "MODEL_CALL_LIMIT", 3)
    looping = [tool_call("get_claim", claim_id="CLM-1001")] * 10
    assert work(looping).endswith("back in the queue")
    assert len([s for s in steps(client) if s["kind"] == "tool_call"]) == 3


def test_a_second_failure_leaves_the_claim_for_a_handler(client):
    work([], FailingModel)
    report = work([], FailingModel)
    assert report.endswith("left for a handler")
    assert client.get(CLAIM).json()["status"] == "needs_handler"


def test_a_claim_that_is_not_waiting_is_refused_without_a_failure(client):
    work(decide(420.0))
    report = work(decide(420.0))
    assert report.startswith("CLM-1001: Refused (409)")
    assert client.get(CLAIM).json()["failures"] == 0


def test_the_claim_agent_reaches_only_the_backend_api():
    assert {t.name for t in tools.CLAIM_TOOLS} == {
        "get_claim",
        "get_policy",
        "get_claim_history",
        "get_document_contents",
        "get_document_section",
        "record_decision",
        "pay_claim",
    }


def test_unknown_claim_comes_back_as_a_refusal():
    assert tools.get_claim.invoke({"claim_id": "CLM-9999"}).startswith("Refused (404)")


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert model.model().model_name == "deepseek/deepseek-v4.1-flash"
    assert model.model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert model.model().model_name == "openrouter/free"
    assert model.model().reasoning_effort is None


def test_a_decline_is_reported_without_a_payment(client):
    assert work(decline("CLM-1001")) == "CLM-1001: decline, $0.00"

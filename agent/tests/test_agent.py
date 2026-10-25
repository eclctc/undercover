from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import __main__ as cli
from agent import main, tools


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def decide(payout):
    return [
        tool_call("get_claim", claim_id="CLM-1001"),
        tool_call("get_policy", policy_id="POL-2001"),
        tool_call("get_claim_history", customer_id="CUS-3001"),
        tool_call("get_policy_wording"),
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


def run_stub(replies):
    return main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))


def test_run_decides_and_pays(client):
    assert run_stub(decide(420.0)) == "Approved."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "approve"
    assert claim["payment"]["amount"] == 420.0


def test_run_cannot_pay_over_the_limit(client):
    run_stub(decide(1250.0))
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    results = [s["detail"] for s in client.get("/api/claims/CLM-1001/steps").json()]
    assert any(r.startswith("pay_claim: Refused (409)") for r in results)


def test_run_records_steps_in_order(client):
    run_stub(decide(420.0))
    steps = client.get("/api/claims/CLM-1001/steps").json()
    kinds = [s["kind"] for s in steps]
    assert kinds == ["tool_call", "tool_result"] * 6 + ["message"]
    assert steps[0]["detail"] == 'get_claim {"claim_id": "CLM-1001"}'
    assert steps[1]["detail"].startswith("get_claim: ")
    assert steps[1]["detail"].endswith("...")
    assert len(steps[1]["detail"]) == len("get_claim: ") + main.STEP_DETAIL_LENGTH + 3


def test_agent_reaches_only_the_backend_api():
    assert {t.name for t in tools.TOOLS} == {
        "get_claim",
        "get_policy",
        "get_claim_history",
        "get_policy_wording",
        "record_decision",
        "pay_claim",
    }


def test_unknown_claim_comes_back_as_a_refusal():
    assert tools.get_claim.invoke({"claim_id": "CLM-9999"}).startswith("Refused (404)")


def test_cli_works_the_waiting_claims(monkeypatch, capsys):
    worked = []
    monkeypatch.setattr(cli, "run", lambda claim_id, _: worked.append(claim_id) or "ok")
    cli.main([])
    assert len(worked) == 25
    cli.main(["CLM-1001"])
    assert worked[-1] == "CLM-1001"
    assert "CLM-1001: ok" in capsys.readouterr().out


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    assert main.model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"

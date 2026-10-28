from langchain_core.messages import AIMessage

from agent import __main__ as cli
from agent.queue_agent import work_queue
from agent.tests.stubs import FailingModel, decline, stub, tool_call


def failing():
    return FailingModel(messages=iter([]))


def declines(claim_id):
    return stub(decline(claim_id))


def todos(*statuses):
    return tool_call(
        "update_todos",
        todos=[
            {"content": f"Work CLM-100{n}", "status": status}
            for n, status in enumerate(statuses, start=1)
        ],
    )


def work(claim_id):
    return tool_call("work_claim", claim_id=claim_id)


def done(summary="Worked the queue."):
    return AIMessage(content=summary)


def status(client, claim_id):
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def waiting(client):
    return [c for c in client.get("/api/claims").json() if c["status"] == "waiting"]


def models_in_turn(**models):
    """Give each claim its models in turn, one for each time it is worked."""
    turns = {claim_id.replace("_", "-"): iter(m) for claim_id, m in models.items()}
    return lambda claim_id: next(turns[claim_id])


def test_a_run_keeps_its_to_do_list_and_summary(client):
    replies = [
        tool_call("list_waiting_claims"),
        todos("to_do", "to_do"),
        todos("in_progress", "to_do"),
        work("CLM-1001"),
        todos("done", "in_progress"),
        work("CLM-1002"),
        todos("done", "done"),
        done("Declined two claims."),
    ]
    summary = work_queue(2, stub(replies), declines)
    assert summary == "Declined two claims."
    run = client.get("/api/runs/latest").json()
    assert [t["status"] for t in run["todos"]] == ["done", "done"]
    assert run["summary"] == "Declined two claims."
    assert run["finished_at"]
    assert status(client, "CLM-1001") == "decided"
    assert status(client, "CLM-1002") == "decided"


def test_the_cap_leaves_the_rest_waiting(client, capsys):
    replies = [work("CLM-1001"), work("CLM-1002"), work("CLM-1003"), done()]
    work_queue(2, stub(replies), declines)
    assert status(client, "CLM-1003") == "waiting"
    assert len(waiting(client)) == 23
    printed = capsys.readouterr().out
    assert "CLM-1001: decline, $0.00" in printed
    assert "Refused: this run's cap of 2 claims is reached" in printed


def test_a_failed_claim_does_not_stop_the_run(client):
    replies = [work("CLM-1001"), work("CLM-1002"), work("CLM-1001"), done()]
    claim_models = models_in_turn(
        CLM_1001=[failing(), declines("CLM-1001")], CLM_1002=[declines("CLM-1002")]
    )
    work_queue(2, stub(replies), claim_models)
    assert status(client, "CLM-1002") == "decided"


def test_a_failed_claim_is_tried_again_and_decided_once(client):
    replies = [work("CLM-1001"), work("CLM-1001"), done()]
    claim_models = models_in_turn(CLM_1001=[failing(), declines("CLM-1001")])
    work_queue(1, stub(replies), claim_models)
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["failures"] == 1
    assert claim["decision"]["decision"] == "decline"


def test_a_claim_that_fails_twice_is_left_for_a_handler(client):
    replies = [work("CLM-1001"), work("CLM-1001"), done()]
    claim_models = models_in_turn(CLM_1001=[failing(), failing()])
    summary = work_queue(1, stub(replies), claim_models)
    assert summary == "Worked the queue."
    assert status(client, "CLM-1001") == "needs_handler"


def test_a_missed_claim_sends_the_agent_back(client):
    replies = [work("CLM-1001"), done("Finished early."), work("CLM-1002"), done()]
    work_queue(2, stub(replies), declines)
    assert status(client, "CLM-1002") == "decided"
    assert client.get("/api/runs/latest").json()["summary"] == "Worked the queue."


def test_a_failed_claim_left_waiting_sends_the_agent_back(client):
    replies = [work("CLM-1001"), done("Finished early."), work("CLM-1001"), done()]
    claim_models = models_in_turn(CLM_1001=[failing(), declines("CLM-1001")])
    work_queue(1, stub(replies), claim_models)
    assert status(client, "CLM-1001") == "decided"


def test_no_claim_is_missed_once_the_cap_is_reached(client):
    replies = [work("CLM-1001"), done()]
    assert work_queue(1, stub(replies), declines) == "Worked the queue."
    assert len(waiting(client)) == 24


def test_cli_works_one_named_claim(monkeypatch, capsys):
    monkeypatch.setattr(cli, "work_claim", lambda claim_id: f"{claim_id}: ok")
    cli.main(["CLM-1001"])
    assert capsys.readouterr().out == "CLM-1001: ok\n"


def test_cli_runs_the_queue_with_a_cap(monkeypatch):
    caps = []
    monkeypatch.setattr(cli, "work_queue", lambda cap: caps.append(cap) or "Done.")
    cli.main(["--cap", "5"])
    cli.main([])
    assert caps == [5, 25]

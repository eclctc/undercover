"""The queue agent: works the waiting claims, one fresh claim agent per claim."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.runtime import Runtime
from pydantic import BaseModel

from agent import claim_agent
from agent.harness import messages_in, retry_middleware
from agent.model import model
from agent.tools import call

RECURSION_LIMIT = 500

ClaimModel = Callable[[str], BaseChatModel]


class Todo(BaseModel):
    """One item on the to-do list."""

    content: str
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


@dataclass
class QueueRun:
    """One run over the queue: its id, its cap and the claims it has worked."""

    run_id: int
    cap: int
    claim_model: ClaimModel
    worked: set[str] = field(default_factory=set)

    def may_work(self, claim_id: str) -> bool:
        """Say whether the cap leaves room for this claim."""
        return claim_id in self.worked or len(self.worked) < self.cap

    def missed_claims(self) -> list[str]:
        """List the waiting claims this run could still work within its cap."""
        waiting = [c["claim_id"] for c in waiting_claims()]
        retries = [c for c in waiting if c in self.worked]
        new = [c for c in waiting if c not in self.worked]
        return retries + new[: self.cap - len(self.worked)]


def waiting_claims() -> list[dict[str, Any]]:
    """Return every claim waiting in the queue."""
    return [c for c in call("GET", "/api/claims") if c["status"] == "waiting"]


def queue_tools(run: QueueRun) -> list[BaseTool]:
    """Build the queue agent's tools for one run."""

    @tool
    def list_waiting_claims() -> str:
        """List the claims waiting in the queue, with their type, summary and amount."""
        return json.dumps(waiting_claims())

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand one waiting claim to a fresh claim agent and get a one-line report."""
        if not run.may_work(claim_id):
            return f"Refused: this run's cap of {run.cap} claims is reached"
        report = claim_agent.work_claim(claim_id, run.claim_model(claim_id))
        if not report.startswith(f"{claim_id}: Refused"):
            run.worked.add(claim_id)
        return report

    @tool
    def update_todos(todos: list[Todo]) -> str:
        """Save the whole to-do list, replacing the last one."""
        body = {"todos": [todo.model_dump() for todo in todos]}
        call("PUT", f"/api/runs/{run.run_id}/todos", body)
        return "Saved the to-do list"

    return [list_waiting_claims, work_claim, update_todos]


class MissedClaimsCheck(AgentMiddleware[AgentState[Any], Any]):
    """Send the queue agent back when it finishes with claims missed within its cap."""

    def __init__(self, run: QueueRun) -> None:
        super().__init__()
        self.run = run

    @hook_config(can_jump_to=["model"])
    def after_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """Name the missed claims and jump back to the model, if there are any."""
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return None
        missed = self.run.missed_claims()
        if not missed:
            return None
        reminder = (
            "Before you finish: these claims are still waiting and within this"
            f" run's cap, so please work them: {', '.join(missed)}."
        )
        return {"messages": [HumanMessage(reminder)], "jump_to": "model"}


def work_queue(
    cap: int, llm: BaseChatModel | None = None, claim_model: ClaimModel | None = None
) -> str:
    """Work up to cap waiting claims, printing each report, and return the summary."""
    run_id = call("POST", "/api/runs", {"cap": cap})["run_id"]
    run = QueueRun(run_id, cap, claim_model or (lambda _claim_id: model()))
    agent = create_agent(
        llm or model(),
        tools=queue_tools(run),
        system_prompt=call("GET", "/api/agent-instructions")["queue"],
        middleware=[*retry_middleware(), MissedClaimsCheck(run)],
    )
    request = f"Please work the queue. This run's cap is {cap} claims."
    summary = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": request}]},
        config={"recursion_limit": RECURSION_LIMIT},
        stream_mode="updates",
    ):
        for message in messages_in(update):
            if isinstance(message, ToolMessage) and message.name == "work_claim":
                print(message.text)
            if isinstance(message, AIMessage):
                summary = message.text
    call("POST", f"/api/runs/{run_id}/finish", {"summary": summary})
    return summary

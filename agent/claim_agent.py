"""The claim agent: a fresh subagent that works one claim and reports in a line."""

import json
import uuid
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agent.harness import messages_in, retry_middleware
from agent.model import model
from agent.tools import CLAIM_TOOLS, call, call_for_model

STEP_DETAIL_LENGTH = 200
MODEL_CALL_LIMIT = 30
NO_DECISION = "The agent stopped without recording a decision"
DOCUMENT_NAMES = {"policy_wording": "Policy wording", "claims_manual": "Claims manual"}


def read_step(message: ToolMessage) -> dict[str, str] | None:
    """Describe a section the agent read, or None if the message is not one."""
    if message.name != "get_document_section" or message.text.startswith("Refused"):
        return None
    section = json.loads(message.text)
    name = DOCUMENT_NAMES[section["document"]]
    return {
        "kind": "read",
        "detail": f"{name}, {section['section']}. {section['title']}",
    }


def tool_result_step(message: ToolMessage) -> dict[str, str]:
    """Describe a tool's result, cut short for the dashboard."""
    text = message.text
    if len(text) > STEP_DETAIL_LENGTH:
        text = text[:STEP_DETAIL_LENGTH] + "..."
    return {"kind": "tool_result", "detail": f"{message.name}: {text}"}


def steps_from(message: BaseMessage) -> list[dict[str, str]]:
    """Describe what one message from the agent did, as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        return [read_step(message) or tool_result_step(message)]
    if not isinstance(message, AIMessage):
        return []
    steps = [{"kind": "message", "detail": message.text}] if message.text else []
    return steps + [
        {"kind": "tool_call", "detail": f"{c['name']} {json.dumps(c['args'])}"}
        for c in message.tool_calls
    ]


def record_step(claim_id: str, step: dict[str, str]) -> None:
    """Record one of the agent's steps on a claim."""
    call("POST", f"/api/claims/{claim_id}/steps", step)


def middleware() -> list[AgentMiddleware[Any, Any]]:
    """Retry the model and the tools after a passing failure, and cap model calls."""
    return [
        *retry_middleware(),
        ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="end"),
    ]


def run_claim_agent(claim_id: str, llm: BaseChatModel) -> None:
    """Run a fresh claim agent on a started claim, recording each step."""
    instructions = call("GET", "/api/agent-instructions")["claim"]
    agent = create_agent(
        llm, tools=CLAIM_TOOLS, system_prompt=instructions, middleware=middleware()
    )
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": uuid.uuid4().hex}},
        stream_mode="updates",
    ):
        for message in messages_in(update):
            for step in steps_from(message):
                record_step(claim_id, step)


def report(claim: dict[str, Any]) -> str:
    """Report a decided claim in one line: the decision, the payout and the payment."""
    decision = claim["decision"]
    line = f"{claim['claim_id']}: {decision['decision']}, ${decision['payout']:,.2f}"
    if claim["payment"]:
        return f"{line}, paid"
    if claim["status"] == "awaiting_sign_off":
        return f"{line}, waiting for a handler's sign-off"
    return line


def fail(claim_id: str, problem: str) -> str:
    """Record a failed claim and report where it went."""
    claim = call("POST", f"/api/claims/{claim_id}/fail", {"reason": problem})
    where = (
        "back in the queue" if claim["status"] == "waiting" else "left for a handler"
    )
    return f"{claim_id}: failed ({problem}), {where}"


def work_claim(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one waiting claim with a fresh claim agent and report on it in one line."""
    started = call_for_model("POST", f"/api/claims/{claim_id}/start")
    if started.startswith("Refused"):
        return f"{claim_id}: {started}"
    try:
        run_claim_agent(claim_id, llm or model())
        problem = NO_DECISION
    except Exception as error:  # noqa: BLE001
        problem = f"{type(error).__name__}: {error}"
    claim = call("GET", f"/api/claims/{claim_id}")
    return report(claim) if claim["decision"] else fail(claim_id, problem)

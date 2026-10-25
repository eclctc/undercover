"""The UnderCover Agent."""

import json
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent.tools import TOOLS, call

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_DETAIL_LENGTH = 200


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def steps_from(message: BaseMessage) -> list[dict[str, str]]:
    """Describe what one message from the agent did, as steps for the dashboard."""
    if isinstance(message, ToolMessage):
        text = message.text
        if len(text) > STEP_DETAIL_LENGTH:
            text = text[:STEP_DETAIL_LENGTH] + "..."
        detail = f"{message.name}: {text}"
        return [{"kind": "tool_result", "detail": detail}]
    steps = []
    if isinstance(message, AIMessage) and message.text:
        steps.append({"kind": "message", "detail": message.text})
    if isinstance(message, AIMessage):
        steps += [
            {"kind": "tool_call", "detail": f"{c['name']} {json.dumps(c['args'])}"}
            for c in message.tool_calls
        ]
    return steps


def record_step(claim_id: str, step: dict[str, str]) -> None:
    """Record one of the agent's steps on a claim."""
    call("POST", f"/api/claims/{claim_id}/steps", step)


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one waiting claim, recording each step, and return the final reply."""
    instructions = call("GET", "/api/agent-instructions")["text"]
    call("POST", f"/api/claims/{claim_id}/start")
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions)
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in node["messages"]:
                for step in steps_from(message):
                    record_step(claim_id, step)
                reply = message.text
    return reply

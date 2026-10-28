"""Pieces of the harness shared by the queue agent and the claim agent."""

from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.messages import BaseMessage

MESSAGE_NODES = ("model", "tools")
RETRY_INITIAL_DELAY_SECONDS = 2.0


def retry_middleware() -> list[AgentMiddleware[Any, Any]]:
    """Retry a failed model call or tool call with backoff before giving up."""
    return [
        ModelRetryMiddleware(
            initial_delay=RETRY_INITIAL_DELAY_SECONDS, on_failure="error"
        ),
        ToolRetryMiddleware(initial_delay=RETRY_INITIAL_DELAY_SECONDS),
    ]


def messages_in(update: dict[str, Any]) -> list[BaseMessage]:
    """Return the new messages in one streamed update, skipping middleware nodes."""
    return [
        message
        for name, node in update.items()
        if name in MESSAGE_NODES
        for message in node["messages"]
    ]

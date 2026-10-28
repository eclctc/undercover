"""Stub chat models that stand in for a real model in the agent's tests."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class FailingModel(StubModel):
    """A chat model whose provider fails the first `failures` calls."""

    failures: int = 1_000

    def _generate(self, *args, **kwargs):
        if self.failures:
            self.failures -= 1
            raise TimeoutError("The model provider timed out")
        return super()._generate(*args, **kwargs)


def stub(replies):
    """Return a stub model that gives these replies in order."""
    return StubModel(messages=iter(replies))


def tool_call(name, **args):
    """Return a reply from the model that calls one tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def decline(claim_id):
    """Return the replies of a claim agent that declines a claim."""
    return [
        tool_call(
            "record_decision",
            claim_id=claim_id,
            decision="decline",
            payout=0,
            reasons="Not a covered reason.",
            policy_section="Section 9, General exclusions",
        ),
        AIMessage(content="Declined."),
    ]

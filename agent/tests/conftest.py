import pytest
from fastapi.testclient import TestClient

from agent import harness, tools
from backend.main import app
from backend.testing import client, fresh_db

__all__ = ["client", "fresh_db"]


@pytest.fixture(autouse=True)
def test_backend(monkeypatch):
    """Send the agent's API calls to the test backend."""
    monkeypatch.setattr(tools, "backend", lambda: TestClient(app))


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    """Retry at once, so tests of failures run fast."""
    monkeypatch.setattr(harness, "RETRY_INITIAL_DELAY_SECONDS", 0)

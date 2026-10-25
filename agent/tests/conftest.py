import pytest
from fastapi.testclient import TestClient

from agent import tools
from backend.main import app
from backend.testing import client, fresh_db

__all__ = ["client", "fresh_db"]


@pytest.fixture(autouse=True)
def test_backend(monkeypatch):
    """Send the agent's API calls to the test backend."""
    monkeypatch.setattr(tools, "backend", lambda: TestClient(app))

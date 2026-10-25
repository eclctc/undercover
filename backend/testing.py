"""Test fixtures shared by the backend and agent tests."""

import pytest
from fastapi.testclient import TestClient

from backend import db, seed
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Point the backend at a freshly seeded database for each test."""
    path = tmp_path / "test.db"
    seed.reset(path)
    monkeypatch.setattr(db, "DB_PATH", path)
    return path


@pytest.fixture
def client():
    """Return a test client for the backend."""
    return TestClient(app)

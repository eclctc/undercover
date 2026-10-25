import json
from pathlib import Path

from backend import db, seed


def test_reset_seeds_the_queue(tmp_path):
    counts = seed.reset(tmp_path / "test.db")
    assert counts == {
        "claims": 25,
        "policies": len(seed.load("policies.json")),
        "customers": len(seed.load("customers.json")),
        "plans": 3,
        "add_ons": 3,
        "handlers": 3,
    }


def test_every_claim_starts_waiting(tmp_path):
    path = tmp_path / "test.db"
    seed.reset(path)
    conn = db.connect(path)
    statuses = {row["status"] for row in conn.execute("SELECT status FROM claims")}
    assert statuses == {"waiting"}
    row = conn.execute("SELECT data FROM claims WHERE claim_id = 'CLM-1001'").fetchone()
    assert json.loads(row["data"])["policy_id"] == "POL-2001"


def test_seed_never_reads_evals_or_security(tmp_path, monkeypatch):
    read: list[Path] = []
    original = Path.read_text

    def recording_read_text(self, *args, **kwargs):
        read.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    seed.reset(tmp_path / "test.db")
    assert read
    assert all(path.parent == seed.DATA_DIR for path in read)


def test_ensure_seeded_only_seeds_once(tmp_path):
    path = tmp_path / "test.db"
    seed.ensure_seeded(path)
    seed.ensure_seeded(path)
    assert seed.counts(db.connect(path))["claims"] == 25


def test_session_closes_its_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    sessions = db.session()
    conn = next(sessions)
    assert conn.execute("SELECT 1").fetchone()[0] == 1
    sessions.close()

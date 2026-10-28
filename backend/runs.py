"""The agent's runs over the queue, each with its to-do list and summary."""

import json
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.records import Conn, fetch
from backend.workflow import fail, now

STOPPED_RUN_REASON = "The run working this claim stopped before it was decided"

router = APIRouter(prefix="/api/runs")


class RunStart(BaseModel):
    """The most claims a run may work."""

    cap: int = Field(ge=1)


class Todo(BaseModel):
    """One item on the agent's to-do list."""

    content: str
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


class Todos(BaseModel):
    """The agent's whole to-do list."""

    todos: list[Todo]


class RunFinish(BaseModel):
    """The agent's summary of a run for the handlers."""

    summary: str


def run_record(conn: sqlite3.Connection, run_id: int) -> dict[str, Any]:
    """Return a run with its to-do list."""
    row = dict(fetch(conn, "runs", "run_id", str(run_id)))
    return {**row, "todos": json.loads(row["todos"])}


def fail_stopped_claims(conn: sqlite3.Connection) -> None:
    """Fail every claim left in progress by a run that stopped."""
    rows = conn.execute("SELECT claim_id FROM claims WHERE status = 'in_progress'")
    for row in rows.fetchall():
        fail(conn, row["claim_id"], STOPPED_RUN_REASON)


@router.post("", operation_id="start_run")
def start_run(start: RunStart, conn: Conn) -> dict[str, Any]:
    """Start a run over the queue, failing claims a stopped run left in progress."""
    fail_stopped_claims(conn)
    cursor = conn.execute(
        "INSERT INTO runs (cap, started_at, todos) VALUES (?, ?, '[]')",
        (start.cap, now()),
    )
    conn.commit()
    return run_record(conn, cursor.lastrowid or 0)


@router.put("/{run_id}/todos", operation_id="record_todos")
def record_todos(run_id: int, todos: Todos, conn: Conn) -> dict[str, Any]:
    """Replace a run's to-do list."""
    fetch(conn, "runs", "run_id", str(run_id))
    conn.execute(
        "UPDATE runs SET todos = ? WHERE run_id = ?",
        (json.dumps(todos.model_dump()["todos"]), run_id),
    )
    conn.commit()
    return run_record(conn, run_id)


@router.post("/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: RunFinish, conn: Conn) -> dict[str, Any]:
    """Finish a run with the agent's summary for the handlers."""
    fetch(conn, "runs", "run_id", str(run_id))
    conn.execute(
        "UPDATE runs SET summary = ?, finished_at = ? WHERE run_id = ?",
        (finish.summary, now(), run_id),
    )
    conn.commit()
    return run_record(conn, run_id)


@router.get("/latest", operation_id="get_latest_run")
def get_latest_run(conn: Conn) -> dict[str, Any] | None:
    """Get the newest run, or null if the agent has never run."""
    row = conn.execute("SELECT MAX(run_id) FROM runs").fetchone()
    return run_record(conn, row[0]) if row[0] else None

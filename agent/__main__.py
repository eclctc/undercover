"""Work claims from the command line: `uv run -m agent [claim_id ...]`."""

import sys
import uuid

from agent.main import run
from agent.tools import call


def waiting_claims() -> list[str]:
    """Return the ids of every claim waiting in the queue."""
    return [
        c["claim_id"] for c in call("GET", "/api/claims") if c["status"] == "waiting"
    ]


def main(claim_ids: list[str]) -> None:
    """Work the given claims, or every waiting claim if none are given."""
    for claim_id in claim_ids or waiting_claims():
        print(f"{claim_id}: {run(claim_id, uuid.uuid4().hex)}")


if __name__ == "__main__":
    main(sys.argv[1:])

"""Work the queue, or one claim, from the command line: `uv run -m agent`."""

import argparse
import sys

from agent.claim_agent import work_claim
from agent.queue_agent import work_queue
from agent.tools import call


def parse(args: list[str]) -> argparse.Namespace:
    """Read the claim id or the cap from the command line."""
    parser = argparse.ArgumentParser(
        prog="uv run -m agent",
        description="Work every waiting claim, at most a cap of them, or one claim.",
    )
    parser.add_argument("claim_id", nargs="?", help="work only this claim")
    parser.add_argument("--cap", type=int, help="work at most this many claims")
    return parser.parse_args(args)


def main(args: list[str]) -> None:
    """Work one named claim, or run the queue agent over the waiting claims."""
    options = parse(args)
    if options.claim_id:
        print(work_claim(options.claim_id))
        return
    cap = options.cap or len(call("GET", "/api/claims"))
    print(work_queue(cap))


if __name__ == "__main__":
    main(sys.argv[1:])

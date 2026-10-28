# Status

The pilot is built, from `docs/PLAN.md`. The harness is built, from `docs/PLAN_HARNESS.md`, and checked with a live run of five claims on the default model.

- `backend/`: FastAPI and SQLite. The database (`backend/undercover.db`) is seeded from `data/` on first start, never from `data/evals/` or `data/security/`. The API serves claims, policies, claim history (without contact details), the policy wording and the claims manual by section, the agent's instructions (`backend/instructions/`, one for running the queue and one for working a claim) and the handlers. It runs the workflow: starting a claim, the agent's steps, the decision, payment and sign-off. A claim that fails before it is decided goes back in the queue, and after a second failure is left for a handler (`needs_handler`). Runs over the queue keep the agent's to-do list and summary. A payout over $1,000 is refused until a handler signs off.
- `agent/`: the UnderCover Agent. `work_queue(cap)` runs the queue agent: it plans a to-do list (saved on the run), hands each waiting claim to a claim agent, retries a failed claim once, is sent back if it tries to finish with a waiting claim missed within its cap, and ends with a summary for the handlers. `work_claim(claim_id)` runs a fresh claim agent that looks up the sections of the wording and the manual it needs, records each step (including each section read) and reports in one line. Model and tool failures are retried; a claim that still fails, or ends without a decision, goes back in the queue or to a handler. It uses `deepseek/deepseek-v4.1-flash` with low reasoning, or `MODEL_NAME` if set.
- `dashboard/`: the queue with the latest agent run (its to-do list and summary), each claim in full with the agent's decision, its steps (live while it works), the sections of the wording and the manual it read, how often it failed on the claim and sign-off for payouts over $1,000, and the agent's instructions for running the queue and for working a claim, read only.
- `e2e/`: Playwright tests of the queue, a decided and paid claim, sign-off over the limit, the instructions, the to-do list and a claim left for a handler. They run on their own database and ports (8001 and 5174).

## Run it

- `npm run dev` starts the backend (port 8000) and the dashboard (http://localhost:5173)
- `uv run -m agent` works every waiting claim; `uv run -m agent --cap 5` works at most five; `uv run -m agent CLM-1001` works one claim. It needs the backend running
- `npm run reset` rebuilds the database from `data/`, so the queue can be worked again
- `npm run check` runs every check

## Not built yet

- Scoring the agent against `data/evals/`
- Sign-in, real payments and messages to customers

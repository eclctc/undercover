# Status

The pilot is built, from `docs/PLAN.md`. The harness (`docs/PLAN_HARNESS.md`) is in progress: Phases 1 and 2 are done.

- `backend/`: FastAPI and SQLite. The database (`backend/undercover.db`) is seeded from `data/` on first start, never from `data/evals/` or `data/security/`. The API serves claims, policies, claim history (without contact details), the policy wording, the policy wording and the claims manual by section, the agent's instructions (`backend/instructions/`, one for running the queue and one for working a claim) and the handlers. It runs the workflow: starting a claim, the agent's steps, the decision, payment and sign-off. A claim that fails before it is decided goes back in the queue, and after a second failure is left for a handler (`needs_handler`). Runs over the queue keep the agent's to-do list and summary. A payout over $1,000 is refused until a handler signs off.
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` fetches its instructions from the backend, works the claim with tools that call the API, and records each step. It uses `openai/gpt-6-luna` with low reasoning, or `MODEL_NAME` if set.
- `dashboard/`: the queue, each claim in full with the agent's decision, its steps (live while it works) and sign-off for payouts over $1,000, and the agent's instructions, read only.
- `e2e/`: Playwright tests of the queue, a decided and paid claim, sign-off over the limit, and the instructions. They run on their own database and ports (8001 and 5174).

## Run it

- `npm run dev` starts the backend (port 8000) and the dashboard (http://localhost:5173)
- `uv run -m agent CLM-1001` works one claim; `uv run -m agent` works every waiting claim. It needs the backend running
- `npm run reset` rebuilds the database from `data/`, so the queue can be worked again
- `npm run check` runs every check

## Not built yet

- Scoring the agent against `data/evals/`
- The claims manual, sign-in, real payments and messages to customers

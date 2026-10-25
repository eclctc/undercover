# Status

The pilot is being built from `docs/PLAN.md`.

- `backend/`: a SQLite database (`backend/undercover.db`) seeded from `data/` on first start, and the read API: claims, policies, claim history, the policy wording, the agent's instructions (`backend/agent_instructions.md`) and the handlers. The decision workflow: starting a claim, the agent's steps, the decision, payment, and handler sign-off. A payout over $1,000 is refused until a handler signs off
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` fetches its instructions from the backend, works the claim with tools that call the API, and records each step
- `dashboard/`: the queue, each claim in full with the agent's decision, its steps (live while it works) and sign-off for payouts over $1,000, and the agent's instructions, read only
- `e2e/`: one test of that page

## Run it

- `npm run reset` rebuilds the database from `data/`
- `npm run dev` starts the backend and the dashboard
- `uv run -m agent CLM-1001` works one claim; `uv run -m agent` works every waiting claim. It needs the backend running

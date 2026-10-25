# Status

The pilot is being built from `docs/PLAN.md`.

- `backend/`: a SQLite database (`backend/undercover.db`) seeded from `data/` on first start, and the read API: claims, policies, claim history, the policy wording, the agent's instructions (`backend/agent_instructions.md`) and the handlers
- `agent/`: the hello-world entry point `run(claim_id, thread_id)`
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Run it

- `npm run reset` rebuilds the database from `data/`
- `npm run dev` starts the backend and the dashboard

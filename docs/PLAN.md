# Plan: the claims pilot

The pilot builds the backend, the dashboard and a first UnderCover Agent from `docs/SPEC.md`. It goes in six phases, each building on the last: data first, then the API on top of it, then the agent and the dashboard that use the API, then end-to-end tests over the whole thing.

## Key choices

- **The backend is the single source of truth.** The agent and the dashboard both work only through its API. The agent never touches the database or `data/` directly, so the API is the one place where the rules are enforced.
- **The $1,000 rule is enforced in the backend, not the prompt.** `pay_claim` refuses a payment over the limit (from `data/company.json`) until a handler has signed off. The agent can try to pay; the backend says no. A prompt can be ignored, an API check cannot.
- **SQLite seeded from `data/`.** One file, `backend/undercover.db`, created and seeded on first start. Nested records (a claim's items and documents, a policy's trip) are stored as JSON columns: the pilot reads them whole and never queries inside them. The seed reads only the queue files and never `data/evals/` or `data/security/`. A test proves it.
- **The agent's instructions live in the backend**, in `backend/agent_instructions.md`, served by `get_agent_instructions`. The agent fetches its system prompt from there, and the dashboard shows the same text read only, so what the team sees is what the agent uses.
- **Least personal data to the model.** The agent gets a customer's claim history through `get_claim_history`, not their address, phone or date of birth.
- **Steps are recorded by the agent's runner, not by the model.** `run()` streams the agent and posts each tool call and result to the backend as a step. The model cannot skip or invent steps, and the dashboard polls them to show the work live.
- **Statuses**: `waiting` (seeded from `open`), `in_progress`, `awaiting_sign_off` and `decided`. Payment is tracked separately from status: paid, waiting for sign-off, or none.
- **Payout arithmetic is the agent's job in the pilot.** It follows section 10 of the policy wording. Extra tools such as a calculator are harness work for a later day.

## API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | dashboard |
| `GET /api/claims` | `list_claims` | dashboard |
| `GET /api/claims/{claim_id}` | `get_claim` | agent, dashboard |
| `GET /api/policies/{policy_id}` | `get_policy` | agent, dashboard |
| `GET /api/customers/{customer_id}/claim-history` | `get_claim_history` | agent, dashboard |
| `GET /api/policy-wording` | `get_policy_wording` | agent |
| `GET /api/agent-instructions` | `get_agent_instructions` | agent, dashboard |
| `GET /api/handlers` | `list_handlers` | dashboard |
| `POST /api/claims/{claim_id}/start` | `start_claim` | agent runner |
| `POST /api/claims/{claim_id}/steps` | `record_step` | agent runner |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | dashboard |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | agent |
| `POST /api/claims/{claim_id}/payments` | `pay_claim` | agent |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off_claim` | dashboard |

`get_policy` includes the plan's limits and the add-ons on the policy. A decision is `{decision: approve | decline | refer, payout, reasons, policy_section}`, with a payout of 0 unless approved. `pay_claim` takes `{amount}`. `sign_off_claim` takes `{handler_id}` and releases the payment of the approved payout.

## Phase 1: Database and seed data

Builds `backend/db.py`: the SQLite schema (claims, policies, customers, plans, add-ons, handlers, decisions, payments, steps) and a seed from `data/`. Adds `npm run reset`, which rebuilds the database from `data/` so the queue can be worked again.

- [x] `uv run pytest backend` passes, with tests for the schema and the seed
- [x] After a seed, the database holds 25 claims, all `waiting`, plus every policy, customer, plan and handler in `data/`
- [x] A test proves the seed opens no file under `data/evals/` or `data/security/`
- [x] `npm run reset` recreates `backend/undercover.db` and prints the counts
- [x] `backend/undercover.db` is in `.gitignore`
- [x] `npm run check:python` passes

## Phase 2: The read API

Adds the read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_agent_instructions` and `list_handlers`, plus a first version of `backend/agent_instructions.md`.

- [x] Tests cover every route, including 404 for an unknown claim, policy or customer
- [x] `curl localhost:8000/api/claims` returns 25 claims with id, type, summary, amount claimed and status
- [x] `curl localhost:8000/api/claims/CLM-1001` returns the story, items and documents
- [x] `curl localhost:8000/api/policies/POL-2001` includes the Premium plan's limits
- [x] `curl localhost:8000/api/customers/CUS-3001/claim-history` returns CLM-0412 and no address, phone or date of birth
- [x] A test checks every route in `/openapi.json` has an `operation_id`, a summary and no optional parameters
- [x] `npm run check:python` passes

## Phase 3: The decision workflow and the sign-off rule

Adds `start_claim`, `record_step`, `list_steps`, `record_decision`, `pay_claim` and `sign_off_claim`, with the rules:

- `start_claim` moves a `waiting` claim to `in_progress`; any other status returns 409.
- `record_decision` on an `in_progress` claim sets `awaiting_sign_off` for an approval over $1,000, otherwise `decided`.
- `pay_claim` returns 409 unless the claim is approved, the amount equals the approved payout, it has not been paid, and the payout is $1,000 or less or has been signed off.
- `sign_off_claim` works only on `awaiting_sign_off`, records the handler, pays the payout and sets `decided`.

- [x] Tests cover every rule above, each with its 409 case
- [x] A test approves $1,250.00, calls `pay_claim` for $1,250.00 and gets 409 with a message that a handler's sign-off is needed; after `sign_off_claim` the claim shows paid
- [x] A test approves $420.00, pays it, and a second payment returns 409
- [x] Steps come back from `list_steps` in the order they were recorded
- [x] Coverage stays at or above 80% and `npm run check:python` passes

## Phase 4: The UnderCover Agent

Replaces the hello-world agent. `run(claim_id, thread_id)` fetches the instructions from the API, starts the claim, and runs `create_agent` with tools that wrap the API: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. A refused payment comes back to the model as the backend's message, so it can carry on. It posts each tool call and result as a step. `uv run -m agent CLM-1001` works one claim; `uv run -m agent` works every waiting claim in the queue. The instructions tell it to read everything, decide from the policy wording alone, work out the payout, explain in two or three sentences with the section, record the decision, then pay.

- [x] Stub-model tests (no real model) run a claim through `get_claim`, `record_decision` and `pay_claim` against the test backend, and the claim ends `decided` and paid
- [x] A stub-model test approves over $1,000 and tries to pay; the backend refuses, the claim ends `awaiting_sign_off` and unpaid
- [x] A test shows the steps for a run are recorded in order
- [x] A test checks the agent's tools cannot reach `data/evals/` (no tool reads files)
- [x] `test_model_name` still passes: `openai/gpt-6-luna` with low reasoning by default, `MODEL_NAME` when set
- [x] A live run, `uv run -m agent CLM-1001` with the backend up, records a decision with reasons and a policy section (one claim, a few cents, or free with `MODEL_NAME=openrouter/free`)
- [x] `npm run check:python` passes

## Phase 5: The dashboard

Builds three pages with React Router, styled to `docs/BRAND.md` (Instrument Sans, Instrument Serif, JetBrains Mono for ids and amounts, light and dark mode, rounded panels with no outline):

- **Queue** (`/`): every claim with its id, type, summary, amount and a status label. Statuses use Sea Green, Marigold, Coral and Cerulean.
- **Claim** (`/claims/:claimId`): the story, items, documents, the policy and plan, the claim history, the agent's decision with its reasons and policy section, the payment state, and the agent's steps. Steps refresh every two seconds while the claim is `in_progress`. A claim waiting for sign-off shows a handler picker and a Sign off button.
- **Instructions** (`/instructions`): the agent's instructions, read only.

Money shows as $1,250.00. Types come from one `api.ts`, with no `any`.

- [x] Vitest tests with a stubbed `fetch` cover each page, the status labels, live steps and sign-off; coverage at or above 80%
- [x] `npm run check:ts` passes
- [x] In the browser (Playwright MCP), the queue shows all 25 claims with their status (24 Waiting and CLM-1001 Decided, after the live run)
- [x] In the browser, CLM-1001 shows its story, items, documents and policy
- [x] In the browser, after a live agent run on a claim, its page shows the steps, the decision and the reasons
- [x] In the browser, the Instructions page shows the same text as `backend/agent_instructions.md`
- [x] Screenshots in light and dark mode match the brand

## Phase 6: End-to-end tests and handover

Adds Playwright tests over the real backend and dashboard. They run against their own fresh database (`UNDERCOVER_DB`) on ports 8001 and 5174, so they never touch the dev data or clash with `npm run dev`. They stand in for the agent by calling the API directly, so they never call a model. Updates `docs/STATUS.md` and `README.md`.

- [x] An e2e test opens the queue and a claim, and sees its details
- [x] An e2e test records an approval of $420.00 and a payment through the API, then sees Decided and Paid on the claim page
- [x] An e2e test records an approval of $1,250.00, sees the payment blocked, signs off as a handler in the dashboard, and sees Paid
- [x] An e2e test opens the Instructions page
- [x] `docs/STATUS.md` says what's built and how to run it: `npm run dev`, `uv run -m agent`, `npm run reset`
- [x] `npm run check` passes in full

## Not in the pilot

- Scoring the agent against `data/evals/`. The spec keeps the answer key for checking later, and nothing in the pilot opens it.
- The claims manual, sign-in, real payments and messages to customers, as the spec says.
- A button in the dashboard to run the agent. The agent runs from the command line; the dashboard shows its work.

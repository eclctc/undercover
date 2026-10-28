# Plan: the agent's harness

The harness brief (`docs/HARNESS.md`) moves the organizing from our code into the agent. One run works the whole queue: a **queue agent** plans the work as a to-do list, hands each claim to a fresh **claim agent** (a subagent), and finishes with a summary. The claim agent looks up the sections of the policy wording and the claims manual it needs. Failures are retried once and then left for a handler, and nothing is decided or paid twice.

It goes in six phases: the backend first (documents by section, runs and to-do lists, failures), then the claim agent, then the queue agent on top of it, then the dashboard, and last the live run and the docs.

## Key choices

- **Our own harness on `create_agent`, no new framework.** The brief rules out Deep Agents and the like. We use LangChain's built-in middleware where it fits (`ModelRetryMiddleware`, `ToolRetryMiddleware`, `ModelCallLimitMiddleware`) and write the rest as small tools and one `after_model` hook.
- **The subagent is a tool.** The queue agent's `work_claim(claim_id)` tool runs the claim agent with a new thread, so each claim starts clean. The tool replies in one line built by our code from the backend's record, such as `CLM-1001: approve, $420.00, paid`, not from the model's prose. That keeps the queue agent's context small and the line reliable. The claim agent records its steps on the claim as today.
- **Our own to-do tool, not `TodoListMiddleware`.** The brief wants four states (to do, in progress, done, left for a handler); `TodoListMiddleware` has a fixed three. An `update_todos` tool that saves the whole list to the backend is about as small, and the dashboard reads it from there.
- **The rules live in the backend and the harness, not the prompt.** The backend refuses a second decision or payment (as in the pilot) and owns the retry rule: `fail_claim` puts a claim back in the queue after its first failure and leaves it for a handler after its second. The cap on a run is enforced in `work_claim`, and the check for missed claims is middleware. The instructions explain these rules, but nothing depends on the model following them.
- **A failure is anything that ends a claim without a decision**: an exception (timeout, provider error, a tool that keeps failing after its retries) or the claim agent stopping, including at its model-call limit, without recording a decision. `work_claim` catches it, calls `fail_claim`, and reports the line back, so the run carries on. This is the one place the harness handles exceptions.
- **No claim is stuck in progress.** Starting a run fails any claim still `in_progress` from a run that was stopped, so it goes back in the queue (or to a handler) by the same rule.
- **Documents by section.** The backend splits `data/policy_wording.md` and `data/claims_manual.md` on their `## N. Title` headings. The claim agent gets a table of contents and reads one section at a time. The runner records each section read as a step of kind `read`, such as `Claims manual, 9. Repeat claims`, which the claim page lists under "What the agent read".
- **A new status, `needs_handler`**, shown as "Left for a handler" in Raspberry, the brand's fifth color. Payment stays tracked apart from status as before.
- **Two sets of instructions**, `backend/instructions/queue.md` and `backend/instructions/claim.md`, served together and shown on the Instructions page. Written from the policy wording and the manual only; nothing opens `data/evals/`.
- **The model** becomes `deepseek/deepseek-v4.1-flash` with low reasoning and a 120-second timeout. `MODEL_NAME` still overrides it.

## API changes

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/documents/{document}` | `get_document_contents` | claim agent |
| `GET /api/documents/{document}/sections/{section}` | `get_document_section` | claim agent |
| `GET /api/agent-instructions` | `get_agent_instructions` (now `{queue, claim}`) | agents, dashboard |
| `POST /api/claims/{claim_id}/fail` | `fail_claim` | claim runner |
| `POST /api/runs` | `start_run` | queue runner |
| `PUT /api/runs/{run_id}/todos` | `record_todos` | queue agent |
| `POST /api/runs/{run_id}/finish` | `finish_run` | queue runner |
| `GET /api/runs/latest` | `get_latest_run` | dashboard |

`document` is `policy_wording` or `claims_manual`; `section` is its number. `get_policy_wording` goes in Phase 3, when the agent's tools move to the two document operations. `fail_claim` takes `{reason}`, works only on an `in_progress` claim, records the reason as a step of kind `error`, adds one to the claim's failures, and sets `waiting` after the first failure or `needs_handler` after the second. `start_run` takes `{cap}`. A to-do item is `{content, status}` with status `to_do`, `in_progress`, `done` or `left_for_handler`. A run is `{run_id, cap, started_at, finished_at, todos, summary}`; `get_latest_run` returns `null` before the first run.

## Phase 1: The documents by section and the claims manual

Adds `backend/documents.py`, which splits the wording and the manual into numbered sections, and the two document operations. Moves the instructions into `backend/instructions/` as `queue.md` and `claim.md` (first drafts; Phases 3 and 4 write them properly) and serves both from `get_agent_instructions`. Updates `docs/SPEC.md`: the claims manual leaves "Not for now", and decisions follow the manual as well as the wording.

- [x] Tests: the contents of each document list every `##` section with its number and title (12 for the wording, 14 for the manual)
- [x] Tests: a section comes back with its heading and full text; an unknown section returns 404 and an unknown document 422
- [x] `curl localhost:8000/api/documents/claims_manual` lists the 14 sections; `curl localhost:8000/api/documents/claims_manual/sections/9` returns "Repeat claims"
- [x] `curl localhost:8000/api/agent-instructions` returns `queue` and `claim`
- [x] The `/openapi.json` test still passes: every route has an `operation_id`, a summary and no optional inputs
- [x] `docs/SPEC.md` covers the claims manual
- [x] `npm run check:python` passes

## Phase 2: Runs, the to-do list and failures in the backend

Adds a `runs` table and a `failures` column on claims, with `start_run`, `record_todos`, `finish_run`, `get_latest_run` and `fail_claim`, and the `needs_handler` status.

- [x] Tests: `start_run` creates a run with its cap; `record_todos` replaces the list; `finish_run` saves the summary and the finish time; `get_latest_run` returns the newest run, or `null` before any
- [x] Tests: a to-do item with an unknown status is rejected (422)
- [x] Tests: `fail_claim` on an `in_progress` claim records an `error` step and sets `waiting`; a second failure on the same claim sets `needs_handler`
- [x] Tests: `fail_claim` on a claim that is `waiting`, `decided` or `awaiting_sign_off` returns 409, so a decided claim can never go back in the queue
- [x] Tests: `start_run` fails a claim left `in_progress` by an earlier run, which then shows `waiting` with one failure
- [x] Tests: a claim that failed once and then is started and decided has exactly one decision, and a second `pay_claim` is still refused
- [x] Reseeding sets every claim's failures to 0
- [x] `npm run check:python` passes

## Phase 3: The claim agent

Reworks `agent/` around the claim agent. `work_claim(claim_id)` starts the claim, runs a fresh `create_agent` with the claim instructions, and returns a one-line report. Its tools: `get_claim`, `get_policy`, `get_claim_history`, `get_document_contents`, `get_document_section`, `record_decision` and `pay_claim`. Its middleware: `ModelRetryMiddleware` and `ToolRetryMiddleware` (backoff on timeouts and provider errors) and `ModelCallLimitMiddleware` (a claim agent that loops ends). A claim that raises, or ends without a decision, is sent to `fail_claim` with the reason, and the report says so. A claim that isn't waiting is refused with the backend's message and not counted as a failure. The default model becomes DeepSeek V4.1 Flash. Removes `get_policy_wording`. Writes `backend/instructions/claim.md` from the wording and the manual: work in the manual's order (section 4), look up the sections needed, and the rules for each decision.

- [x] Stub-model test: a claim is worked through the contents, two section reads, `record_decision` and `pay_claim`; the claim ends `decided` and paid, and the report is `CLM-1001: approve, $420.00, paid`
- [x] Stub-model test: each section read is recorded as a `read` step naming the document and section, in order with the other steps
- [x] Stub-model test: a model that raises leaves the claim `waiting` with one failure and an `error` step, and the report says it went back in the queue
- [x] Stub-model test: a model that stops without a decision counts as a failure in the same way
- [x] Stub-model test: a second failure leaves the claim `needs_handler`, and the report says so
- [x] Stub-model test: the over-$1,000 approval still ends `awaiting_sign_off` and unpaid
- [x] `test_model_name`: `deepseek/deepseek-v4.1-flash` with low reasoning by default, `MODEL_NAME` when set
- [x] A test checks the tools reach only the backend's API (no tool reads files)
- [x] `npm run check:python` passes

## Phase 4: The queue agent

Adds the queue agent: one `work_queue(cap)` entry point that calls `start_run`, runs `create_agent` with the queue instructions, and saves the final message with `finish_run`. Its tools: `list_waiting_claims`, `work_claim` (the subagent) and `update_todos`. `work_claim` refuses a new claim once the run has worked `cap` claims; trying again on a claim it already worked doesn't count against the cap. An `after_model` hook checks for missed claims: when the queue agent tries to finish while a claim is still waiting within the cap, it adds a message naming the claims and sends it back to work them. The CLI becomes:

- `uv run -m agent` works every waiting claim
- `uv run -m agent --cap 5` works at most five
- `uv run -m agent CLM-1001` works one named claim with the claim agent

Writes `backend/instructions/queue.md`: list the waiting claims, write the to-do list, choose the order, keep the list up to date, retry a claim that went back in the queue, and finish with a short summary for the handlers.

- [x] Stub-model test: a run writes a to-do list, works two claims, ticks them off and finishes; `get_latest_run` returns the list with both `done` and the summary
- [x] Stub-model test: a run capped at 2 on a queue of 25 works two claims; the third `work_claim` is refused and 23 claims stay `waiting`
- [x] Stub-model test: one claim's model raises and the run goes on to decide the next claim
- [x] Stub-model test: a failed claim goes back in the queue, the queue agent works it again, and it ends decided, with one decision
- [x] Stub-model test: a claim that fails twice ends `needs_handler` and the run finishes
- [x] Stub-model test: the queue agent tries to finish with a claim still waiting within its cap; the hook sends it back, and it works that claim before finishing
- [x] Stub-model test: the hook does not send it back once the cap is reached
- [x] `uv run -m agent --help` shows the cap and the claim id
- [x] `npm run check:python` passes

## Phase 5: The dashboard

- **Queue**: an "Agent run" panel above the table with the latest run's start time, cap, to-do list (each item with a status badge: To do, In progress, Done, Left for a handler) and, when finished, the summary. It polls with the queue. The counts and badges gain "Left for a handler".
- **Claim**: a "What the agent read" panel listing the `read` steps. The steps list labels `read` as "Read" and `error` as "Problem". A claim with failures shows how many.
- **Instructions**: two sections, "Running the queue" and "Working a claim".

Types come from `api.ts`, with no `any`. Adds e2e tests that stand in for the agent through the API.

- [ ] Vitest tests: the run panel with each to-do status and the summary; no panel before the first run; the new status; the read panel; both instruction sections. Coverage at or above 80%
- [ ] E2E: start a run and record a to-do list through the API, then see it on the queue page; update an item to done and see it ticked off
- [ ] E2E: fail a claim twice through the API and see "Left for a handler" on the queue and the claim page
- [ ] E2E: the Instructions page shows both sections
- [ ] `npm run check` passes
- [ ] Screenshots of the queue with a run, in light and dark mode, match the brand

## Phase 6: The live run and handover

Reseeds, starts the dev servers and runs `uv run -m agent --cap 5` on the default model, then checks the dashboard in the browser with the Playwright MCP server. Updates `docs/TECH_STACK.md` (the model and the two agents) and `docs/STATUS.md` (what's built and how to run it). Refines the instructions if the run shows a gap, using only the wording and the manual.

- [ ] `npm run reset` then `uv run -m agent --cap 5` works five claims on its own and prints a summary
- [ ] In the browser, the queue page shows the to-do list filling in and being ticked off during the run, and the summary after it
- [ ] In the browser, each of the five claims shows its steps, including the sections read, and a decision; 20 claims stay `waiting`
- [ ] No claim is left `in_progress` after the run
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is
- [ ] `npm run check` passes in full

## Not in this build

- Scoring the agent against `data/evals/`, and anything that opens it.
- Working claims in parallel. The queue agent works one claim at a time, which keeps the run easy to follow.
- A button in the dashboard to start a run. Runs start from the command line, as in the pilot.
- Durable state and a graph for the claim agent, which come with a later brief.

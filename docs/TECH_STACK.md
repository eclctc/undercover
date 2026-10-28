# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: LangChain's `create_agent` on OpenRouter, with our own harness and no other agent framework. Two entry points: `work_queue(cap)`, the queue agent, which plans a to-do list and hands each claim to a subagent; and `work_claim(claim_id)`, the claim agent, a fresh `create_agent` for one claim. LangChain's middleware retries model and tool calls (`ModelRetryMiddleware`, `ToolRetryMiddleware`) and caps a claim agent's model calls (`ModelCallLimitMiddleware`); our own `after_model` middleware checks for missed claims. The agent reaches claims, the policy wording, the claims manual and its instructions only through the backend's API. It uses `deepseek/deepseek-v4.1-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.

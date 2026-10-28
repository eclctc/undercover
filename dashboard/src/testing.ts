import { vi } from "vitest";
import type {
  Claim,
  ClaimHistory,
  ClaimSummary,
  Handler,
  Policy,
  Run,
  Step,
} from "./api";

export const SUMMARY: ClaimSummary = {
  claim_id: "CLM-1001",
  claim_type: "trip_delay",
  summary: "Flight home canceled by the airline",
  amount_claimed: 420,
  submitted_on: "2026-06-24",
  status: "waiting",
};

export const CLAIM: Claim = {
  ...SUMMARY,
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  story: "My flight home from Rome was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
  ],
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Total paid: $245.00." },
  ],
  failures: 0,
  decision: null,
  payment: null,
};

export const POLICY: Policy = {
  policy_id: "POL-2001",
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  plan_details: { name: "UnderCover Premium", deductible: 50 },
  add_on_details: [],
};

export const HISTORY: ClaimHistory = {
  name: "Maya Patel",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const STEP: Step = {
  step_id: 1,
  kind: "tool_call",
  detail: 'get_claim {"claim_id": "CLM-1001"}',
  recorded_at: "2026-10-25T20:07:30+00:00",
};

export const RUN: Run = {
  run_id: 1,
  cap: 5,
  started_at: "2026-10-28T14:00:00+00:00",
  finished_at: null,
  todos: [
    { content: "Work CLM-1001", status: "done" },
    { content: "Work CLM-1002", status: "in_progress" },
    { content: "Work CLM-1003", status: "to_do" },
    { content: "Work CLM-1004", status: "left_for_handler" },
  ],
  summary: null,
};

export const HANDLERS: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
];

/** Stub fetch so each path returns the JSON in routes, and anything else a 404. */
export function stubApi(routes: Record<string, unknown>) {
  const fetchStub = vi.fn((path: string, init?: RequestInit) => {
    const key = init?.method === "POST" ? `POST ${path}` : path;
    const status = key in routes ? 200 : 404;
    return Promise.resolve(
      new Response(JSON.stringify(key in routes ? routes[key] : {}), {
        status,
      }),
    );
  });
  vi.stubGlobal("fetch", fetchStub);
  return fetchStub;
}

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim, Decision } from "./api";
import { App } from "./App";
import {
  CLAIM,
  HANDLERS,
  HISTORY,
  POLICY,
  STEP,
  stubApi,
  SUMMARY,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function claimRoutes(claim: Claim) {
  return {
    "/api/claims/CLM-1001": claim,
    "/api/claims/CLM-1001/steps": [STEP],
    "/api/policies/POL-2001": POLICY,
    "/api/customers/CUS-3001/claim-history": HISTORY,
    "/api/handlers": HANDLERS,
  };
}

const APPROVAL: Decision = {
  decision: "approve",
  payout: 420,
  reasons: "A covered crew problem delayed the flight.",
  policy_section: "Section 3, Trip Delay",
  decided_at: "2026-10-25T20:07:36+00:00",
};

const APPROVED: Claim = {
  ...CLAIM,
  status: "decided",
  decision: APPROVAL,
  payment: {
    amount: 420,
    signed_off_by: null,
    paid_at: "2026-10-25T20:07:37+00:00",
  },
};

const OVER_LIMIT: Claim = {
  ...APPROVED,
  status: "awaiting_sign_off",
  decision: { ...APPROVAL, payout: 1250 },
  payment: null,
};

it("shows the queue with each claim's status", async () => {
  stubApi({
    "/api/claims": [
      SUMMARY,
      { ...SUMMARY, claim_id: "CLM-1002", status: "decided" },
    ],
  });
  renderAt("/");
  expect(await screen.findByRole("link", { name: "CLM-1001" })).toBeDefined();
  expect(screen.getAllByText("Trip delay")).toHaveLength(2);
  expect(screen.getAllByText("$420.00")).toHaveLength(2);
  expect(screen.getAllByText("Jun 24, 2026")).toHaveLength(2);
  expect(screen.getAllByText("Waiting")).toHaveLength(2);
  expect(screen.getAllByText("Decided")).toHaveLength(2);
});

it("says when the backend is not responding", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderAt("/");
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("shows a claim in full before it is decided", async () => {
  stubApi(claimRoutes(CLAIM));
  renderAt("/claims/CLM-1001");
  expect(
    await screen.findByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(
    await screen.findByText("Maya Patel", { selector: "h2" }),
  ).toBeDefined();
  expect(
    screen.getByText("The agent has not decided this claim yet."),
  ).toBeDefined();
  expect(await screen.findByText(STEP.detail)).toBeDefined();
});

it("shows the decision, its reasons and the payment", async () => {
  stubApi(claimRoutes(APPROVED));
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("Approved")).toBeDefined();
  expect(
    screen.getByText("A covered crew problem delayed the flight."),
  ).toBeDefined();
  expect(screen.getByText("Section 3, Trip Delay")).toBeDefined();
  expect(screen.getByText("Paid $420.00")).toBeDefined();
});

it("lets a handler sign off a payout over the limit", async () => {
  const fetchStub = stubApi({
    ...claimRoutes(OVER_LIMIT),
    "POST /api/claims/CLM-1001/sign-off": APPROVED,
  });
  renderAt("/claims/CLM-1001");
  expect(
    await screen.findByText("Payment waiting for a handler's sign-off"),
  ).toBeDefined();
  const button = screen.getByRole("button", { name: "Sign off $1,250.00" });
  expect(button).toHaveProperty("disabled", true);
  await screen.findByRole("option", {
    name: "Dana Whitfield, Senior Claims Handler",
  });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(button);
  await vi.waitFor(() => {
    expect(fetchStub).toHaveBeenCalledWith("/api/claims/CLM-1001/sign-off", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ handler_id: "HND-01" }),
    });
  });
});

it("refreshes the steps while the agent works", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchStub = stubApi(claimRoutes({ ...CLAIM, status: "in_progress" }));
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("In progress")).toBeDefined();
  const stepCalls = () =>
    fetchStub.mock.calls.filter(
      ([path]) => path === "/api/claims/CLM-1001/steps",
    ).length;
  const before = stepCalls();
  await vi.advanceTimersByTimeAsync(4000);
  expect(stepCalls()).toBeGreaterThan(before);
});

it("says when a claim does not exist", async () => {
  stubApi({});
  renderAt("/claims/CLM-9999");
  expect(
    await screen.findByText("Claim CLM-9999 was not found."),
  ).toBeDefined();
});

it("shows the agent's instructions", async () => {
  stubApi({ "/api/agent-instructions": { text: "# UnderCover Agent" } });
  renderAt("/instructions");
  expect(await screen.findByText("# UnderCover Agent")).toBeDefined();
});

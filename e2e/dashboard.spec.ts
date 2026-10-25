import { type APIRequestContext, expect, test } from "@playwright/test";
import { BACKEND_URL } from "../playwright.config";

/** Stand in for the agent: start a claim and approve it with a payout. */
async function approve(
  request: APIRequestContext,
  claimId: string,
  payout: number,
) {
  const claim = `${BACKEND_URL}/api/claims/${claimId}`;
  await request.post(`${claim}/start`);
  await request.post(`${claim}/steps`, {
    data: { kind: "tool_call", detail: `get_claim {"claim_id": "${claimId}"}` },
  });
  const response = await request.post(`${claim}/decision`, {
    data: {
      decision: "approve",
      payout,
      reasons: "The loss is covered and the documents support it.",
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  expect(response.ok()).toBe(true);
  return claim;
}

test("the queue lists every claim and opens one in full", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("row")).toHaveCount(26);
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(
    page.getByText("My flight home from Rome", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Airport hotel, one night")).toBeVisible();
  await expect(page.getByText("UnderCover Premium")).toBeVisible();
  await expect(
    page.getByText("The agent has not decided this claim yet."),
  ).toBeVisible();
});

test("an approval under the limit is decided and paid", async ({
  page,
  request,
}) => {
  const claim = await approve(request, "CLM-1002", 420);
  const paid = await request.post(`${claim}/payments`, {
    data: { amount: 420 },
  });
  expect(paid.ok()).toBe(true);
  await page.goto("/claims/CLM-1002");
  await expect(page.getByText("Decided", { exact: true })).toBeVisible();
  await expect(page.getByText("Paid $420.00")).toBeVisible();
  await expect(
    page.getByText('get_claim {"claim_id": "CLM-1002"}'),
  ).toBeVisible();
});

test("a payout over the limit waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  const claim = await approve(request, "CLM-1003", 1250);
  const blocked = await request.post(`${claim}/payments`, {
    data: { amount: 1250 },
  });
  expect(blocked.status()).toBe(409);
  await page.goto("/claims/CLM-1003");
  await expect(
    page.getByText("Payment waiting for a handler's sign-off"),
  ).toBeVisible();
  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off $1,250.00" }).click();
  await expect(page.getByText("Paid $1,250.00")).toBeVisible();
  await expect(page.getByText("after sign-off by HND-01")).toBeVisible();
});

test("the instructions page shows the agent's instructions", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Instructions" }).click();
  await expect(
    page.getByText("You are the UnderCover Agent.", { exact: false }),
  ).toBeVisible();
});

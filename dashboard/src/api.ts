export type Status =
  "waiting" | "in_progress" | "awaiting_sign_off" | "decided";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: "approve" | "decline" | "refer";
  payout: number;
  reasons: string;
  policy_section: string;
  decided_at: string;
}

export interface Payment {
  amount: number;
  signed_off_by: string | null;
  paid_at: string;
}

export interface Claim extends ClaimSummary {
  policy_id: string;
  customer_id: string;
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: ClaimDocument[];
  decision: Decision | null;
  payment: Payment | null;
}

export interface Plan {
  name: string;
  deductible: number;
}

export interface AddOn {
  add_on: string;
  name: string;
}

export interface Policy {
  policy_id: string;
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  plan_details: Plan;
  add_on_details: AddOn[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface ClaimHistory {
  name: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Step {
  step_id: number;
  kind: "tool_call" | "tool_result" | "message";
  detail: string;
  recorded_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export interface Text {
  text: string;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok)
    throw new Error(`${path} returned ${String(response.status)}`);
  return (await response.json()) as T;
}

export async function signOff(
  claimId: string,
  handlerId: string,
): Promise<Claim> {
  const response = await fetch(`/api/claims/${claimId}/sign-off`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handler_id: handlerId }),
  });
  if (!response.ok)
    throw new Error(`Sign-off returned ${String(response.status)}`);
  return (await response.json()) as Claim;
}

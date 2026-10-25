import { useParams } from "react-router";
import type { Claim, ClaimHistory, Policy, Step } from "./api";
import { DecisionPanel } from "./DecisionPanel";
import { day, money, words } from "./format";
import { StatusBadge } from "./StatusBadge";
import { StepsPanel } from "./StepsPanel";
import { useApi } from "./useApi";

const LIVE_POLL_MS = 2000;

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel" aria-label="Claim">
      <h2>What happened</h2>
      <p className="muted">
        {claim.incident_location}, {day(claim.incident_date)}. Submitted{" "}
        {day(claim.submitted_on)}.
      </p>
      <p className="story">{claim.story}</p>
      <h3>Items claimed</h3>
      <table>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{words(item.category)}</td>
              <td className="amount mono">{money(item.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Documents</h3>
      {claim.documents.map((doc) => (
        <details key={doc.name}>
          <summary>{doc.name}</summary>
          <p>{doc.content}</p>
        </details>
      ))}
    </section>
  );
}

function PolicyPanel({ policy }: Readonly<{ policy: Policy }>) {
  const addOns = policy.add_on_details.map((a) => a.name).join(", ") || "None";
  return (
    <section className="panel" aria-label="Policy">
      <h2>Policy</h2>
      <dl>
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan_details.name}</dd>
        <dt>Add-ons</dt>
        <dd>{addOns}</dd>
        <dt>Bought</dt>
        <dd>{day(policy.purchased_on)}</dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {day(policy.trip.departs_on)} to{" "}
          {day(policy.trip.returns_on)}
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
      </dl>
    </section>
  );
}

function HistoryPanel({ history }: Readonly<{ history: ClaimHistory }>) {
  return (
    <section className="panel" aria-label="Claim history">
      <h2>{history.name}</h2>
      <p className="muted">Customer since {day(history.customer_since)}</p>
      {history.previous_claims.length === 0 ? (
        <p>No earlier claims.</p>
      ) : (
        <ul>
          {history.previous_claims.map((c) => (
            <li key={c.claim_id}>
              {day(c.filed_on)}: {c.summary}. {words(c.outcome)},{" "}
              <span className="mono">{money(c.amount_paid)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ClaimView({ claimId }: Readonly<{ claimId: string }>) {
  const claimApi = useApi<Claim>(`/api/claims/${claimId}`, LIVE_POLL_MS);
  const claim = claimApi.data;
  const live = claim?.status === "in_progress" ? LIVE_POLL_MS : null;
  const { data: steps } = useApi<Step[]>(`/api/claims/${claimId}/steps`, live);
  const { data: policy } = useApi<Policy>(
    claim ? `/api/policies/${claim.policy_id}` : null,
    null,
  );
  const { data: history } = useApi<ClaimHistory>(
    claim ? `/api/customers/${claim.customer_id}/claim-history` : null,
    null,
  );

  if (claimApi.failed)
    return <p role="alert">Claim {claimId} was not found.</p>;
  if (!claim) return <p>Loading the claim</p>;

  return (
    <>
      <h1>
        <span className="mono">{claim.claim_id}</span> {words(claim.claim_type)}{" "}
        <StatusBadge status={claim.status} />
      </h1>
      <p className="lead">
        {claim.summary}. Claimed{" "}
        <span className="mono">{money(claim.amount_claimed)}</span>.
      </p>
      <div className="columns">
        <div>
          <DecisionPanel claim={claim} onSigned={claimApi.reload} />
          <ClaimDetails claim={claim} />
          <StepsPanel steps={steps ?? []} />
        </div>
        <div>
          {policy && <PolicyPanel policy={policy} />}
          {history && <HistoryPanel history={history} />}
        </div>
      </div>
    </>
  );
}

export function ClaimPage() {
  const { claimId = "" } = useParams();
  return <ClaimView key={claimId} claimId={claimId} />;
}

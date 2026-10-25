import { type SubmitEvent, useState } from "react";
import { type Claim, type Handler, signOff } from "./api";
import { DECISION_LABELS, money, moment } from "./format";
import { useApi } from "./useApi";

type DecisionProps = Readonly<{ claim: Claim; onSigned: () => void }>;

function PaymentState({ claim }: Readonly<{ claim: Claim }>) {
  if (claim.payment) {
    const by = claim.payment.signed_off_by;
    return (
      <p>
        <strong>Paid {money(claim.payment.amount)}</strong> on{" "}
        {moment(claim.payment.paid_at)}
        {by && <> after sign-off by {by}</>}
      </p>
    );
  }
  if (claim.status === "awaiting_sign_off") {
    return <p>Payment waiting for a handler&apos;s sign-off</p>;
  }
  return <p>Not paid</p>;
}

function SignOffForm({ claim, onSigned }: DecisionProps) {
  const { data: handlers } = useApi<Handler[]>("/api/handlers", null);
  const [handlerId, setHandlerId] = useState("");

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    void signOff(claim.claim_id, handlerId).then(onSigned);
  };

  return (
    <form className="sign-off" onSubmit={submit}>
      <label>
        Handler{" "}
        <select
          value={handlerId}
          onChange={(e) => {
            setHandlerId(e.target.value);
          }}
        >
          <option value="">Choose a handler</option>
          {handlers?.map((h) => (
            <option key={h.handler_id} value={h.handler_id}>
              {h.name}, {h.role}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={!handlerId}>
        Sign off {claim.decision && money(claim.decision.payout)}
      </button>
    </form>
  );
}

export function DecisionPanel({ claim, onSigned }: DecisionProps) {
  const { decision } = claim;
  return (
    <section className="panel" aria-label="Decision">
      <h2>Decision</h2>
      {decision ? (
        <>
          <p>
            <span className={`badge decision-${decision.decision}`}>
              {DECISION_LABELS[decision.decision]}
            </span>{" "}
            <span className="mono payout">{money(decision.payout)}</span>
          </p>
          <p>{decision.reasons}</p>
          <p className="muted">{decision.policy_section}</p>
          <PaymentState claim={claim} />
          {claim.status === "awaiting_sign_off" && (
            <SignOffForm claim={claim} onSigned={onSigned} />
          )}
        </>
      ) : (
        <p className="muted">The agent has not decided this claim yet.</p>
      )}
    </section>
  );
}

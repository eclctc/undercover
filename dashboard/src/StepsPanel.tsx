import type { Step } from "./api";
import { moment } from "./format";

const KIND_LABELS: Record<Step["kind"], string> = {
  tool_call: "Called",
  tool_result: "Result",
  message: "Said",
  read: "Read",
  error: "Problem",
};

export function StepsPanel({ steps }: Readonly<{ steps: Step[] }>) {
  return (
    <section className="panel" aria-label="Agent steps">
      <h2>What the agent did</h2>
      {steps.length === 0 ? (
        <p className="muted">No steps yet.</p>
      ) : (
        <ol className="steps">
          {steps.map((step) => (
            <li key={step.step_id}>
              <span className={`badge kind-${step.kind}`}>
                {KIND_LABELS[step.kind]}
              </span>
              <span className="mono step-detail">{step.detail}</span>
              <time className="muted">{moment(step.recorded_at)}</time>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

import type { Instructions } from "./api";
import { useApi } from "./useApi";

export function InstructionsPage() {
  const { data } = useApi<Instructions>("/api/agent-instructions", null);

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told when it runs the queue and when it
        works a claim. Read only.
      </p>
      <section aria-label="Running the queue">
        <h2>Running the queue</h2>
        <div className="panel instructions">{data?.queue ?? "Loading"}</div>
      </section>
      <section aria-label="Working a claim">
        <h2>Working a claim</h2>
        <div className="panel instructions">{data?.claim ?? "Loading"}</div>
      </section>
    </>
  );
}

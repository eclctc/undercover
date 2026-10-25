import type { Text } from "./api";
import { useApi } from "./useApi";

export function InstructionsPage() {
  const { data } = useApi<Text>("/api/agent-instructions", null);

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told before it works a claim. Read only.
      </p>
      <div className="panel instructions">{data?.text ?? "Loading"}</div>
    </>
  );
}

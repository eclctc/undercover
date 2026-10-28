import type { Run } from "./api";
import { moment, TODO_LABELS } from "./format";

export function RunPanel({ run }: Readonly<{ run: Run }>) {
  return (
    <section className="panel" aria-label="Agent run">
      <h2>Agent run</h2>
      <p className="muted">
        Started {moment(run.started_at)}, up to {run.cap} claims.{" "}
        {run.finished_at ? `Finished ${moment(run.finished_at)}.` : "Running."}
      </p>
      {run.todos.length === 0 ? (
        <p className="muted">No to-do list yet.</p>
      ) : (
        <ol className="todos" aria-label="To-do list">
          {run.todos.map((todo) => (
            <li key={todo.content}>
              <span className={`badge todo-${todo.status}`}>
                {TODO_LABELS[todo.status]}
              </span>
              <span>{todo.content}</span>
            </li>
          ))}
        </ol>
      )}
      {run.summary && (
        <>
          <h3>Summary</h3>
          <p className="summary">{run.summary}</p>
        </>
      )}
    </section>
  );
}

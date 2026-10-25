import { Link } from "react-router";
import type { ClaimSummary, Status } from "./api";
import { day, money, STATUS_LABELS, words } from "./format";
import { StatusBadge } from "./StatusBadge";
import { useApi } from "./useApi";

const STATUSES = Object.keys(STATUS_LABELS) as Status[];
const POLL_MS = 5000;

export function QueuePage() {
  const { data: claims, failed } = useApi<ClaimSummary[]>(
    "/api/claims",
    POLL_MS,
  );
  if (failed) return <p role="alert">The backend is not responding.</p>;
  if (!claims) return <p>Loading the queue</p>;

  return (
    <>
      <h1>Claims queue</h1>
      <ul className="counts" aria-label="Claims by status">
        {STATUSES.map((status) => (
          <li key={status} className="panel">
            <span className="number">
              {claims.filter((c) => c.status === status).length}
            </span>
            <StatusBadge status={status} />
          </li>
        ))}
      </ul>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Type</th>
              <th>Summary</th>
              <th>Submitted</th>
              <th className="amount">Claimed</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td>
                  <Link className="mono" to={`/claims/${claim.claim_id}`}>
                    {claim.claim_id}
                  </Link>
                </td>
                <td>{words(claim.claim_type)}</td>
                <td>{claim.summary}</td>
                <td className="nowrap">{day(claim.submitted_on)}</td>
                <td className="amount mono">{money(claim.amount_claimed)}</td>
                <td>
                  <StatusBadge status={claim.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

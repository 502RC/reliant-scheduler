import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { actions } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import StatusBadge from "@/components/shared/StatusBadge";
import { formatDateTime } from "@/utils/format";

export default function ActionHistory() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(1);

  const actionResult = useApi(() => actions.get(id!), [id]);
  const execResult = useApi(() => actions.executions(id!, page, 20), [id, page]);

  if (actionResult.loading || execResult.loading) {
    return <LoadingSpinner message="Loading execution history..." />;
  }

  const action = actionResult.data;
  const items = execResult.data?.items ?? [];
  const totalPages = execResult.data?.pages ?? 1;

  return (
    <>
      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
            <Link to="/actions" style={{ color: "#2563eb" }}>Actions</Link>
            {" / "}
            <Link to={`/actions/${id}/edit`} style={{ color: "#2563eb" }}>
              {action?.name ?? "Action"}
            </Link>
            {" / History"}
          </div>
          <h2>Execution History</h2>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="card" style={{ padding: 24, textAlign: "center", color: "#6b7280" }}>
          No executions recorded yet.
        </div>
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Action execution history">
            <thead>
              <tr>
                <th>Status</th>
                <th>Triggered</th>
                <th>Completed</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {items.map((exec) => (
                <tr key={exec.id}>
                  <td>
                    <StatusBadge
                      status={exec.status === "success" ? "success" : exec.status === "failed" ? "failed" : "pending"}
                    />
                  </td>
                  <td>{formatDateTime(exec.triggered_at)}</td>
                  <td>{formatDateTime(exec.completed_at)}</td>
                  <td style={{ color: exec.error_message ? "#dc2626" : "#9ca3af", fontSize: 12 }}>
                    {exec.error_message ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="data-table-footer">
              <span>Page {page} of {totalPages}</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
                <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

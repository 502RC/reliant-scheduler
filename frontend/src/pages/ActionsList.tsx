import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { actions } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import type { ActionType } from "@/types/api";
import { formatRelativeTime } from "@/utils/format";

const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  email: "Email",
  webhook: "Webhook",
  slack: "Slack",
  teams: "Teams",
  itsm: "ITSM",
};

const ACTION_TYPE_COLORS: Record<ActionType, { bg: string; color: string; border: string }> = {
  email: { bg: "#eff6ff", color: "#1d4ed8", border: "#bfdbfe" },
  webhook: { bg: "#f0fdf4", color: "#15803d", border: "#bbf7d0" },
  slack: { bg: "#fefce8", color: "#a16207", border: "#fef08a" },
  teams: { bg: "#faf5ff", color: "#7e22ce", border: "#e9d5ff" },
  itsm: { bg: "#fff1f2", color: "#be123c", border: "#fecdd3" },
};

export default function ActionsList() {
  const [page, setPage] = useState(1);
  const result = useApi(() => actions.list(page, 20), [page]);

  if (result.loading) return <LoadingSpinner message="Loading actions..." />;

  if (result.error) {
    return (
      <div className="card" role="alert" style={{ color: "#dc2626" }}>
        Failed to load actions: {result.error}
      </div>
    );
  }

  const items = result.data?.items ?? [];
  const totalPages = result.data?.pages ?? 1;

  return (
    <>
      <div className="page-header">
        <h2>Notification Actions</h2>
        <Link to="/actions/new" className="btn btn-primary">
          Create Action
        </Link>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No actions configured"
          description="Create notification actions to receive alerts for job events via email, Slack, Teams, webhooks, or ITSM integration."
          actionLabel="Create Action"
          actionTo="/actions/new"
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Notification actions">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((action) => {
                const typeStyle = ACTION_TYPE_COLORS[action.action_type] ?? ACTION_TYPE_COLORS.webhook;
                return (
                  <tr key={action.id}>
                    <td>
                      <Link
                        to={`/actions/${action.id}/edit`}
                        style={{ color: "#2563eb", textDecoration: "none", fontWeight: 500 }}
                      >
                        {action.name}
                      </Link>
                    </td>
                    <td>
                      <span
                        className="conn-type-badge"
                        style={{
                          background: typeStyle.bg,
                          color: typeStyle.color,
                          border: `1px solid ${typeStyle.border}`,
                        }}
                      >
                        {ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
                      </span>
                    </td>
                    <td>{formatRelativeTime(action.updated_at)}</td>
                    <td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <Link to={`/actions/${action.id}/edit`} className="btn btn-sm btn-secondary">
                          Edit
                        </Link>
                        <Link to={`/actions/${action.id}/history`} className="btn btn-sm btn-secondary">
                          History
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="data-table-footer">
              <span>Page {page} of {totalPages}</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </button>
                <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

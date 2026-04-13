import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { agents } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime, formatRelativeTime } from "@/utils/format";

const AGENT_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  online: { label: "Online", color: "#10b981" },
  offline: { label: "Offline", color: "#6b7280" },
  draining: { label: "Draining", color: "#f59e0b" },
};

function AgentStatusBadge({ status }: { status: string }) {
  const config = AGENT_STATUS_CONFIG[status] ?? { label: status, color: "#6b7280" };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 500,
        color: config.color,
        backgroundColor: `${config.color}18`,
        border: `1px solid ${config.color}40`,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: config.color,
          display: "inline-block",
          animation: status === "online" ? "pulse 2s infinite" : undefined,
        }}
        aria-hidden
      />
      {config.label}
    </span>
  );
}

export default function AgentsList() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const { data, loading, error, refetch } = useApi(
    () => agents.list(page, 20, statusFilter || undefined),
    [page, statusFilter]
  );

  if (loading) return <LoadingSpinner message="Loading agents..." />;
  if (error) {
    return (
      <div role="alert" className="card" style={{ color: "#dc2626" }}>
        Failed to load agents: {error}
        <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={refetch}>
          Retry
        </button>
      </div>
    );
  }

  const items = data?.items ?? [];
  const onlineCount = items.filter((a) => a.status === "online").length;
  const offlineCount = items.filter((a) => a.status === "offline").length;
  const drainingCount = items.filter((a) => a.status === "draining").length;

  return (
    <>
      <div className="page-header">
        <h2>Agents</h2>
      </div>

      <div className="card-grid">
        <div className="card">
          <div className="card-label">Online</div>
          <div className="card-value" style={{ color: "#10b981" }}>{onlineCount}</div>
        </div>
        <div className="card">
          <div className="card-label">Offline</div>
          <div className="card-value" style={{ color: "#6b7280" }}>{offlineCount}</div>
        </div>
        <div className="card">
          <div className="card-label">Draining</div>
          <div className="card-value" style={{ color: "#f59e0b" }}>{drainingCount}</div>
        </div>
        <div className="card">
          <div className="card-label">Total</div>
          <div className="card-value">{items.length}</div>
        </div>
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by agent status"
        >
          <option value="">All Statuses</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="draining">Draining</option>
        </select>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No agents found"
          description={statusFilter ? "Try changing the status filter." : "No agents have registered yet."}
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Agents">
            <thead>
              <tr>
                <th>Hostname</th>
                <th>Status</th>
                <th>Last Heartbeat</th>
                <th>Max Concurrent</th>
                <th>Labels</th>
                <th>Version</th>
                <th>Registered</th>
              </tr>
            </thead>
            <tbody>
              {items.map((agent) => (
                <tr key={agent.id}>
                  <td style={{ fontWeight: 500, fontFamily: "monospace", fontSize: 13 }}>
                    {agent.hostname}
                  </td>
                  <td>
                    <AgentStatusBadge status={agent.status} />
                  </td>
                  <td>
                    <span title={formatDateTime(agent.last_heartbeat_at)}>
                      {formatRelativeTime(agent.last_heartbeat_at)}
                    </span>
                  </td>
                  <td>{agent.max_concurrent_jobs}</td>
                  <td>
                    {agent.labels
                      ? Object.entries(agent.labels).map(([k, v]) => (
                          <span
                            key={k}
                            style={{
                              display: "inline-block",
                              padding: "1px 6px",
                              background: "#f3f4f6",
                              borderRadius: 4,
                              fontSize: 11,
                              marginRight: 4,
                              fontFamily: "monospace",
                            }}
                          >
                            {k}: {v}
                          </span>
                        ))
                      : "—"}
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {agent.agent_version ?? "—"}
                  </td>
                  <td>{formatDateTime(agent.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.pages > 1 && (
            <div className="data-table-footer">
              <span>Page {data.page} of {data.pages} ({data.total} total)</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
                <button disabled={page >= (data?.pages ?? 1)} onClick={() => setPage((p) => p + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

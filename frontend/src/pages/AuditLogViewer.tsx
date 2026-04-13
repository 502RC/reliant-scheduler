import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { auditLog } from "@/services/api";
import type { AuditLogResponse } from "@/types/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime } from "@/utils/format";

const RESOURCE_TYPES = [
  "job",
  "schedule",
  "user",
  "workgroup",
  "security_policy",
  "connection",
  "environment",
];

const ACTIONS = ["create", "update", "delete"];

export default function AuditLogViewer() {
  const [page, setPage] = useState(1);
  const [resourceType, setResourceType] = useState("");
  const [action, setAction] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const filters = {
    resource_type: resourceType || undefined,
    action: action || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  };

  const { data, loading, error } = useApi(
    () => auditLog.list(page, 50, filters),
    [page, resourceType, action, startDate, endDate]
  );

  return (
    <div>
      <div className="page-header">
        <h2>Audit Log</h2>
      </div>

      <div className="filter-bar" style={{ flexWrap: "wrap" }}>
        <select
          className="form-select"
          value={resourceType}
          onChange={(e) => { setResourceType(e.target.value); setPage(1); }}
          aria-label="Filter by resource type"
        >
          <option value="">All resources</option>
          {RESOURCE_TYPES.map((r) => (
            <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
          ))}
        </select>
        <select
          className="form-select"
          value={action}
          onChange={(e) => { setAction(e.target.value); setPage(1); }}
          aria-label="Filter by action"
        >
          <option value="">All actions</option>
          {ACTIONS.map((a) => (
            <option key={a} value={a}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>
          ))}
        </select>
        <input
          className="form-input"
          type="date"
          value={startDate}
          onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
          aria-label="Start date"
          style={{ width: "auto" }}
        />
        <input
          className="form-input"
          type="date"
          value={endDate}
          onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
          aria-label="End date"
          style={{ width: "auto" }}
        />
      </div>

      {loading && <LoadingSpinner />}
      {error && <div className="form-error">Failed to load audit log: {error}</div>}
      {data && data.items.length === 0 && (
        <EmptyState title="No audit entries" description="No audit log entries match the current filters." />
      )}
      {data && data.items.length > 0 && (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Resource ID</th>
                <th>User</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((entry: AuditLogResponse) => (
                <tr key={entry.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDateTime(entry.timestamp)}</td>
                  <td>
                    <span className={`trigger-type-badge${entry.action === "delete" ? " conn-type-azure" : ""}`}>
                      {entry.action}
                    </span>
                  </td>
                  <td>{entry.resource_type.replace(/_/g, " ")}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {entry.resource_id ? entry.resource_id.slice(0, 12) + "..." : "—"}
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {entry.user_id ? entry.user_id.slice(0, 8) + "..." : "System"}
                  </td>
                  <td>{entry.ip_address ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="data-table-footer">
              <span>{data.total} entr{data.total !== 1 ? "ies" : "y"}</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
                <span>Page {page} of {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

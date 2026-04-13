import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { slaPolicies } from "@/services/api";
import { usePermission } from "@/hooks/usePermission";
import type { SlaPolicyResponse, SlaStatus } from "@/types/api";
import StatusBadge from "@/components/shared/StatusBadge";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";

const SLA_STATUSES: SlaStatus[] = ["on_track", "at_risk", "breached", "met"];

function slaStatusColor(status: SlaStatus): string {
  switch (status) {
    case "on_track": return "success";
    case "at_risk": return "warning";
    case "breached": return "error";
    case "met": return "info";
    default: return "default";
  }
}

export default function SlaPoliciesList() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const canCreate = usePermission("schedule", "write");

  const { data, loading, error } = useApi(
    () => slaPolicies.list(page, 20, statusFilter || undefined),
    [page, statusFilter]
  );

  return (
    <div>
      <div className="page-header">
        <h2>SLA Policies</h2>
        {canCreate && (
          <Link to="/sla-policies/new" className="btn btn-primary">
            Create SLA Policy
          </Link>
        )}
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          aria-label="Filter by SLA status"
        >
          <option value="">All statuses</option>
          {SLA_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
          ))}
        </select>
      </div>

      {loading && <LoadingSpinner />}
      {error && <div className="form-error">Failed to load SLA policies: {error}</div>}
      {data && data.items.length === 0 && (
        <EmptyState
          title="No SLA policies"
          description="Create an SLA policy to track service level agreements for job completion."
        />
      )}
      {data && data.items.length > 0 && (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Target Time</th>
                <th>Risk Window</th>
                <th>Breach Window</th>
                <th>Compliance</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((sla: SlaPolicyResponse) => (
                <tr key={sla.id}>
                  <td>
                    <Link to={`/sla-policies/${sla.id}`}>{sla.name}</Link>
                  </td>
                  <td>
                    <StatusBadge status={sla.status} variant={slaStatusColor(sla.status)} />
                  </td>
                  <td>{sla.target_completion_time}</td>
                  <td>{sla.risk_window_minutes}m</td>
                  <td>{sla.breach_window_minutes}m</td>
                  <td>
                    {sla.compliance_rate !== null
                      ? `${(sla.compliance_rate * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="data-table-footer">
              <span>{data.total} polic{data.total !== 1 ? "ies" : "y"}</span>
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

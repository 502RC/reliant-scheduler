import { useParams, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { slaPolicies } from "@/services/api";
import { usePermission } from "@/hooks/usePermission";
import type { SlaConstraintResponse, SlaEventResponse, SlaStatus } from "@/types/api";
import StatusBadge from "@/components/shared/StatusBadge";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { formatDateTime } from "@/utils/format";

function slaStatusColor(status: SlaStatus | string): string {
  switch (status) {
    case "on_track": return "success";
    case "at_risk": return "warning";
    case "breached": return "error";
    case "met": return "info";
    default: return "default";
  }
}

export default function SlaPolicyDetail() {
  const { id } = useParams<{ id: string }>();
  const canEdit = usePermission("schedule", "write");

  const { data: policy, loading } = useApi(
    () => slaPolicies.get(id!),
    [id]
  );
  const { data: constraints } = useApi(
    () => slaPolicies.constraints(id!),
    [id]
  );
  const { data: eventsPage } = useApi(
    () => slaPolicies.events(id!, 1, 20),
    [id]
  );

  if (loading) return <LoadingSpinner />;
  if (!policy) return <div className="form-error">SLA policy not found</div>;

  const criticalPath = (constraints ?? []).filter((c: SlaConstraintResponse) => c.track_critical_path);

  return (
    <div>
      <div className="page-header">
        <div>
          <Link to="/sla-policies" className="btn btn-secondary btn-sm" style={{ marginBottom: 8 }}>
            &larr; SLA Policies
          </Link>
          <h2>{policy.name}</h2>
        </div>
        {canEdit && (
          <Link to={`/sla-policies/${id}/edit`} className="btn btn-primary">
            Edit Policy
          </Link>
        )}
      </div>

      <div className="card-grid" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-label">Status</div>
          <div style={{ marginTop: 8 }}>
            <StatusBadge status={policy.status} variant={slaStatusColor(policy.status)} />
          </div>
        </div>
        <div className="card">
          <div className="card-label">Target Completion</div>
          <div className="card-value" style={{ fontSize: 18 }}>{policy.target_completion_time}</div>
        </div>
        <div className="card">
          <div className="card-label">Risk Window</div>
          <div className="card-value" style={{ fontSize: 18 }}>{policy.risk_window_minutes}m</div>
        </div>
        <div className="card">
          <div className="card-label">Breach Window</div>
          <div className="card-value" style={{ fontSize: 18 }}>{policy.breach_window_minutes}m</div>
        </div>
        <div className="card">
          <div className="card-label">Compliance Rate</div>
          <div className="card-value" style={{ fontSize: 18 }}>
            {policy.compliance_rate !== null
              ? `${(policy.compliance_rate * 100).toFixed(1)}%`
              : "—"}
          </div>
        </div>
      </div>

      {policy.description && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-label">Description</div>
          <p style={{ marginTop: 8, fontSize: 13, color: "#374151" }}>{policy.description}</p>
        </div>
      )}

      {/* Job Constraints */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Job Constraints</h3>
      {constraints && constraints.length > 0 ? (
        <div className="data-table-container" style={{ marginBottom: 24 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Critical Path</th>
              </tr>
            </thead>
            <tbody>
              {constraints.map((c: SlaConstraintResponse) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/jobs/${c.job_id}`}>{c.job_id.slice(0, 8)}...</Link>
                  </td>
                  <td>
                    {c.track_critical_path ? (
                      <StatusBadge status="critical" variant="error" />
                    ) : (
                      <span style={{ color: "#9ca3af" }}>No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card" style={{ marginBottom: 24, color: "#6b7280", fontSize: 13 }}>
          No job constraints configured.
        </div>
      )}

      {/* Critical Path Visualization */}
      {criticalPath.length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Critical Path</h3>
          <div className="card" style={{ marginBottom: 24, padding: 20 }}>
            <div className="sla-critical-path">
              {criticalPath.map((c: SlaConstraintResponse, idx: number) => (
                <div key={c.id} className="sla-critical-path-node">
                  <Link to={`/jobs/${c.job_id}`} className="sla-critical-path-box">
                    {c.job_id.slice(0, 8)}
                  </Link>
                  {idx < criticalPath.length - 1 && (
                    <span className="sla-critical-path-arrow">&rarr;</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* SLA Events Timeline */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Events</h3>
      {eventsPage && eventsPage.items.length > 0 ? (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Event</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {eventsPage.items.map((evt: SlaEventResponse) => (
                <tr key={evt.id}>
                  <td>{formatDateTime(evt.timestamp)}</td>
                  <td>
                    <StatusBadge
                      status={evt.event_type.replace(/_/g, " ")}
                      variant={slaStatusColor(evt.event_type)}
                    />
                  </td>
                  <td>{evt.message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card" style={{ color: "#6b7280", fontSize: 13 }}>
          No SLA events recorded.
        </div>
      )}
    </div>
  );
}

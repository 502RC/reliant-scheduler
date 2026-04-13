import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { schedules } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime } from "@/utils/format";

export default function SchedulesList() {
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [toggling, setToggling] = useState<string | null>(null);

  const { data, loading, error, refetch } = useApi(
    () => schedules.list(page),
    [page]
  );

  async function handleToggle(id: string, currentEnabled: boolean) {
    setToggling(id);
    try {
      await schedules.update(id, { enabled: !currentEnabled });
      refetch();
    } catch {
      alert("Failed to update schedule");
    } finally {
      setToggling(null);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this schedule?")) return;
    try {
      await schedules.delete(id);
      refetch();
    } catch {
      alert("Failed to delete schedule");
    }
  }

  if (loading) return <LoadingSpinner message="Loading schedules..." />;
  if (error) {
    return (
      <div role="alert" className="card" style={{ color: "#dc2626" }}>
        Failed to load schedules: {error}
        <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={refetch}>
          Retry
        </button>
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <>
      <div className="page-header">
        <h2>Schedules</h2>
        {hasRole("admin", "scheduler") && (
          <Link to="/schedules/new" className="btn btn-primary">
            + Create Schedule
          </Link>
        )}
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No schedules"
          description="Create a schedule to automate job runs."
          action={
            hasRole("admin", "scheduler") ? (
              <Link to="/schedules/new" className="btn btn-primary">
                Create Schedule
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Schedules">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Type</th>
                <th>Expression / Source</th>
                <th>Timezone</th>
                <th>Next Run</th>
                <th>Enabled</th>
                <th>Created</th>
                {hasRole("admin", "scheduler") && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link
                      to={`/jobs/${s.job_id}`}
                      style={{ color: "#2563eb", fontFamily: "monospace", fontSize: 12 }}
                    >
                      {s.job_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td>
                    <span className="trigger-type-badge">{s.trigger_type}</span>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {s.trigger_type === "cron"
                      ? s.cron_expression ?? "—"
                      : s.event_source ?? "—"}
                  </td>
                  <td>{s.timezone}</td>
                  <td>{formatDateTime(s.next_run_at)}</td>
                  <td>
                    <button
                      className={`toggle-btn ${s.enabled ? "toggle-on" : "toggle-off"}`}
                      onClick={() => handleToggle(s.id, s.enabled)}
                      disabled={toggling === s.id || !hasRole("admin", "scheduler")}
                      aria-label={s.enabled ? "Disable schedule" : "Enable schedule"}
                      aria-pressed={s.enabled}
                    >
                      <span className="toggle-knob" />
                    </button>
                  </td>
                  <td>{formatDateTime(s.created_at)}</td>
                  {hasRole("admin", "scheduler") && (
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <Link to={`/schedules/${s.id}/edit`} className="btn btn-secondary btn-sm">
                          Edit
                        </Link>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(s.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  )}
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

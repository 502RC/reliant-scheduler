import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { jobs } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import StatusBadge from "@/components/shared/StatusBadge";
import { formatDateTime, formatDuration } from "@/utils/format";
import type { RunStatus } from "@/types/api";

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const [tab, setTab] = useState<"details" | "runs">("details");
  const [runsPage, setRunsPage] = useState(1);
  const [deleting, setDeleting] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerSuccess, setTriggerSuccess] = useState(false);

  const jobResult = useApi(() => jobs.get(id!), [id], { refetchInterval: 1000 });
  const runsResult = useApi(() => jobs.runs(id!, runsPage), [id, runsPage], {
    refetchInterval: 1000,
  });
  const depsResult = useApi(() => jobs.dependencies(id!), [id]);

  if (jobResult.loading) return <LoadingSpinner message="Loading job..." />;
  if (jobResult.error || !jobResult.data) {
    return (
      <div role="alert" className="card" style={{ color: "#dc2626" }}>
        {jobResult.error ?? "Job not found"}
      </div>
    );
  }

  const job = jobResult.data;

  async function handleDelete() {
    if (!confirm(`Delete job "${job.name}"?`)) return;
    setDeleting(true);
    try {
      await jobs.delete(job.id);
      navigate("/jobs");
    } catch {
      alert("Failed to delete job");
      setDeleting(false);
    }
  }

  async function handleTrigger() {
    setTriggering(true);
    setTriggerSuccess(false);
    try {
      await jobs.trigger(job.id);
      runsResult.refetch();
      setTriggerSuccess(true);
      setTimeout(() => setTriggerSuccess(false), 3000);
    } catch {
      alert("Failed to trigger job");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h2>{job.name}</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {hasRole("operator", "user", "scheduler") && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleTrigger}
              disabled={triggering}
            >
              {triggering ? "Triggering..." : triggerSuccess ? "✓ Triggered!" : "Run Now"}
            </button>
          )}
          {hasRole("user", "admin") && (
            <Link to={`/jobs/${job.id}/edit`} className="btn btn-secondary btn-sm">
              Edit
            </Link>
          )}
          {hasRole("admin") && (
            <button
              className="btn btn-danger btn-sm"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </button>
          )}
        </div>
      </div>

      <div className="tab-bar">
        <button
          className={`tab-btn${tab === "details" ? " active" : ""}`}
          onClick={() => setTab("details")}
        >
          Details
        </button>
        <button
          className={`tab-btn${tab === "runs" ? " active" : ""}`}
          onClick={() => setTab("runs")}
        >
          Run History
        </button>
        <Link
          to={`/jobs/${job.id}/dependencies`}
          className="tab-btn"
          style={{ textDecoration: "none" }}
        >
          Dependencies
        </Link>
      </div>

      {tab === "details" && (
        <div className="card" style={{ padding: 24 }}>
          <div className="detail-grid">
            <span className="detail-label">ID</span>
            <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>{job.id}</span>

            <span className="detail-label">Status</span>
            <span className="detail-value"><StatusBadge status={job.status as RunStatus} /></span>

            <span className="detail-label">Type</span>
            <span className="detail-value">{job.job_type}</span>

            <span className="detail-label">Command</span>
            <span className="detail-value" style={{ fontFamily: "monospace" }}>
              {job.command ?? "—"}
            </span>

            <span className="detail-label">Description</span>
            <span className="detail-value">{job.description ?? "—"}</span>

            <span className="detail-label">Max Retries</span>
            <span className="detail-value">{job.max_retries}</span>

            <span className="detail-label">Timeout</span>
            <span className="detail-value">{job.timeout_seconds}s</span>

            <span className="detail-label">Environment</span>
            <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>
              {job.environment_id ?? "—"}
            </span>

            <span className="detail-label">Parameters</span>
            <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>
              {job.parameters ? JSON.stringify(job.parameters, null, 2) : "—"}
            </span>

            <span className="detail-label">Tags</span>
            <span className="detail-value">
              {job.tags
                ? Object.entries(job.tags).map(([k, v]) => (
                    <span
                      key={k}
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        background: "#f3f4f6",
                        borderRadius: 4,
                        fontSize: 12,
                        marginRight: 4,
                      }}
                    >
                      {k}: {v}
                    </span>
                  ))
                : "—"}
            </span>

            <span className="detail-label">Dependencies</span>
            <span className="detail-value">
              {depsResult.loading
                ? "Loading..."
                : (depsResult.data ?? []).length === 0
                  ? "None"
                  : (depsResult.data ?? []).map((d) => (
                      <Link
                        key={d.id}
                        to={`/jobs/${d.depends_on_job_id}`}
                        style={{ display: "block", color: "#2563eb", fontSize: 12, fontFamily: "monospace" }}
                      >
                        {d.depends_on_job_id}
                      </Link>
                    ))}
            </span>

            <span className="detail-label">Created</span>
            <span className="detail-value">{formatDateTime(job.created_at)}</span>

            <span className="detail-label">Updated</span>
            <span className="detail-value">{formatDateTime(job.updated_at)}</span>
          </div>
        </div>
      )}

      {tab === "runs" && (
        <>
          {runsResult.loading ? (
            <LoadingSpinner message="Loading runs..." />
          ) : runsResult.error ? (
            <div role="alert" style={{ color: "#dc2626" }}>
              Failed to load runs: {runsResult.error}
            </div>
          ) : (runsResult.data?.items ?? []).length === 0 ? (
            <EmptyState
              title="No runs yet"
              description="Trigger a run or wait for the schedule."
            />
          ) : (
            <div className="data-table-container">
              <table className="data-table" aria-label="Job runs">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Triggered By</th>
                    <th>Attempt</th>
                    <th>Started</th>
                    <th>Duration</th>
                    <th>Exit Code</th>
                    <th>Error</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {(runsResult.data?.items ?? []).map((run) => (
                    <tr key={run.id}>
                      <td><StatusBadge status={run.status} /></td>
                      <td>{run.triggered_by}</td>
                      <td>{run.attempt_number}</td>
                      <td>{formatDateTime(run.started_at)}</td>
                      <td>{formatDuration(run.started_at, run.finished_at)}</td>
                      <td style={{ fontFamily: "monospace" }}>
                        {run.exit_code ?? "—"}
                      </td>
                      <td style={{ color: "#dc2626", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                        {run.error_message ?? "—"}
                      </td>
                      <td>
                        <Link to={`/jobs/${job.id}/runs/${run.id}`} className="btn btn-secondary btn-sm">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {runsResult.data && runsResult.data.pages > 1 && (
                <div className="data-table-footer">
                  <span>Page {runsResult.data.page} of {runsResult.data.pages}</span>
                  <div className="pagination">
                    <button disabled={runsPage <= 1} onClick={() => setRunsPage((p) => p - 1)}>Prev</button>
                    <button disabled={runsPage >= (runsResult.data?.pages ?? 1)} onClick={() => setRunsPage((p) => p + 1)}>Next</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}

import { useParams, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { jobs } from "@/services/api";
import { useJobStatusEvent } from "@/hooks/useLiveJobs";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import StatusBadge from "@/components/shared/StatusBadge";
import LogViewer from "@/components/shared/LogViewer";
import { formatDateTime, formatDuration } from "@/utils/format";

export default function JobRunDetail() {
  const { id: jobId, runId } = useParams<{ id: string; runId: string }>();

  const jobResult = useApi(() => jobs.get(jobId!), [jobId], { refetchInterval: 1000 });
  const runsResult = useApi(() => jobs.runs(jobId!, 1, 100), [jobId], { refetchInterval: 1000 });

  // Live-update when this job's status changes
  useJobStatusEvent(jobId, () => {
    runsResult.refetch();
  });

  const run = runsResult.data?.items.find((r) => r.id === runId) ?? null;

  if (jobResult.loading || runsResult.loading) {
    return <LoadingSpinner message="Loading run details..." />;
  }

  if (!run) {
    return (
      <div className="card" role="alert" style={{ color: "#dc2626" }}>
        Run not found.{" "}
        <Link to={`/jobs/${jobId}`} style={{ color: "#2563eb" }}>
          Back to job
        </Link>
      </div>
    );
  }

  const job = jobResult.data;

  return (
    <>
      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
            <Link to={`/jobs/${jobId}`} style={{ color: "#2563eb" }}>
              {job?.name ?? "Job"}
            </Link>
            {" / Run "}
          </div>
          <h2>Run #{run.attempt_number}</h2>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="card" style={{ padding: 24, marginBottom: 16 }}>
        <div className="detail-grid">
          <span className="detail-label">Run ID</span>
          <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>
            {run.id}
          </span>

          <span className="detail-label">Status</span>
          <span className="detail-value">
            <StatusBadge status={run.status} />
          </span>

          <span className="detail-label">Triggered By</span>
          <span className="detail-value">{run.triggered_by}</span>

          <span className="detail-label">Attempt</span>
          <span className="detail-value">{run.attempt_number}</span>

          <span className="detail-label">Agent</span>
          <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>
            {run.agent_id ?? "—"}
          </span>

          <span className="detail-label">Started</span>
          <span className="detail-value">{formatDateTime(run.started_at)}</span>

          <span className="detail-label">Finished</span>
          <span className="detail-value">{formatDateTime(run.finished_at)}</span>

          <span className="detail-label">Duration</span>
          <span className="detail-value">{formatDuration(run.started_at, run.finished_at)}</span>

          <span className="detail-label">Exit Code</span>
          <span className="detail-value" style={{ fontFamily: "monospace" }}>
            {run.exit_code ?? "—"}
          </span>

          {run.error_message && (
            <>
              <span className="detail-label">Error</span>
              <span className="detail-value" style={{ color: "#dc2626" }}>
                {run.error_message}
              </span>
            </>
          )}

          {run.parameters && (
            <>
              <span className="detail-label">Parameters</span>
              <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>
                {JSON.stringify(run.parameters, null, 2)}
              </span>
            </>
          )}

          {run.metrics && (
            <>
              <span className="detail-label">Metrics</span>
              <span className="detail-value" style={{ fontFamily: "monospace", fontSize: 12 }}>
                {JSON.stringify(run.metrics, null, 2)}
              </span>
            </>
          )}
        </div>
      </div>

      <LogViewer jobId={jobId!} runId={runId!} runStatus={run.status} logUrl={run.log_url} />
    </>
  );
}

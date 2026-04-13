import { useApi } from "@/hooks/useApi";
import { jobs, agents } from "@/services/api";
import { useLiveRefresh } from "@/hooks/useLiveJobs";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import StatusBadge from "@/components/shared/StatusBadge";
import { formatRelativeTime } from "@/utils/format";
import type { RunStatus } from "@/types/api";

export default function Dashboard() {
  const jobsResult = useApi(() => jobs.list(1, 100), []);
  const agentsResult = useApi(() => agents.list(1, 100), []);

  // Live-update dashboard when job/agent events arrive via WebSocket
  useLiveRefresh(() => {
    jobsResult.refetch();
    agentsResult.refetch();
  });

  if (jobsResult.loading || agentsResult.loading) {
    return <LoadingSpinner message="Loading dashboard..." />;
  }

  if (jobsResult.error) {
    return <div role="alert" className="card" style={{ color: "#dc2626" }}>Failed to load jobs: {jobsResult.error}</div>;
  }

  const allJobs = jobsResult.data?.items ?? [];
  const allAgents = agentsResult.data?.items ?? [];

  const totalJobs = allJobs.length;
  const activeAgents = allAgents.filter((a) => a.status === "online").length;
  const totalAgents = allAgents.length;

  // Derive run stats from job statuses
  const activeRuns = allJobs.filter((j) => j.status === "running").length;
  const recentFailures = allJobs.filter(
    (j) => j.status === "failed"
  ).length;
  const waitingJobs = allJobs.filter(
    (j) => j.status === "pending" || j.status === "queued"
  ).length;

  const recentJobs = [...allJobs]
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
    .slice(0, 10);

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
      </div>

      <div className="card-grid">
        <SummaryCard label="Total Jobs" value={totalJobs} />
        <SummaryCard
          label="Active Runs"
          value={activeRuns}
          accent={activeRuns > 0 ? "#3b82f6" : undefined}
        />
        <SummaryCard
          label="Agents Online"
          value={activeAgents}
          sub={`of ${totalAgents} total`}
          accent={activeAgents > 0 ? "#10b981" : undefined}
        />
        <SummaryCard
          label="Recent Failures"
          value={recentFailures}
          accent={recentFailures > 0 ? "#ef4444" : undefined}
        />
        <SummaryCard label="Waiting Jobs" value={waitingJobs} />
      </div>

      <div className="data-table-container">
        <table className="data-table" aria-label="Recent jobs">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {recentJobs.map((job) => (
              <tr key={job.id}>
                <td>
                  <a href={`/jobs/${job.id}`} style={{ color: "#2563eb", textDecoration: "none", fontWeight: 500 }}>
                    {job.name}
                  </a>
                </td>
                <td>{job.job_type}</td>
                <td>
                  <StatusBadge status={job.status as RunStatus} />
                </td>
                <td>{formatRelativeTime(job.updated_at)}</td>
              </tr>
            ))}
            {recentJobs.length === 0 && (
              <tr>
                <td colSpan={4} style={{ textAlign: "center", color: "#9ca3af", padding: 32 }}>
                  No jobs found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="card">
      <div className="card-label">{label}</div>
      <div className="card-value" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {sub && <div className="card-sub">{sub}</div>}
    </div>
  );
}

import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { jobs } from "@/services/api";
import { useLiveRefresh } from "@/hooks/useLiveJobs";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import StatusBadge from "@/components/shared/StatusBadge";
import { formatDateTime } from "@/utils/format";
import type { RunStatus, JobResponse } from "@/types/api";

type SortField = "name" | "job_type" | "status" | "created_at" | "updated_at";
type SortDir = "asc" | "desc";

export default function JobsList() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [sortField, setSortField] = useState<SortField>("updated_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const { data, loading, error, refetch } = useApi(
    () => jobs.list(page, 20, statusFilter || undefined),
    [page, statusFilter]
  );

  // Live-update jobs list when status changes arrive via WebSocket
  useLiveRefresh(refetch);

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir("asc");
      }
    },
    [sortField]
  );

  const sortedItems = [...(data?.items ?? [])].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    if (aVal === null || aVal === undefined) return 1;
    if (bVal === null || bVal === undefined) return -1;
    const cmp = String(aVal).localeCompare(String(bVal));
    return sortDir === "asc" ? cmp : -cmp;
  });

  if (loading) return <LoadingSpinner message="Loading jobs..." />;
  if (error) {
    return (
      <div role="alert" className="card" style={{ color: "#dc2626" }}>
        Failed to load jobs: {error}
        <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={refetch}>
          Retry
        </button>
      </div>
    );
  }

  const SortHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <th onClick={() => handleSort(field)} aria-sort={sortField === field ? sortDir === "asc" ? "ascending" : "descending" : undefined}>
      {children} {sortField === field ? (sortDir === "asc" ? "\u2191" : "\u2193") : ""}
    </th>
  );

  return (
    <>
      <div className="page-header">
        <h2>Jobs</h2>
        <Link to="/jobs/new" className="btn btn-primary">
          + Create Job
        </Link>
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
        >
          <option value="">All Statuses</option>
          <option value="active">Ready</option>
          <option value="inactive">Disabled</option>
          <option value="paused">Paused</option>
        </select>
      </div>

      {sortedItems.length === 0 ? (
        <EmptyState
          title="No jobs found"
          description={statusFilter ? "Try changing the status filter." : "Create your first job to get started."}
          action={
            !statusFilter ? (
              <Link to="/jobs/new" className="btn btn-primary">
                Create Job
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Jobs">
            <thead>
              <tr>
                <SortHeader field="name">Name</SortHeader>
                <SortHeader field="job_type">Type</SortHeader>
                <SortHeader field="status">Status</SortHeader>
                <th>Retries</th>
                <th>Timeout</th>
                <SortHeader field="created_at">Created</SortHeader>
                <SortHeader field="updated_at">Updated</SortHeader>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((job: JobResponse) => (
                <tr key={job.id}>
                  <td>
                    <Link to={`/jobs/${job.id}`} style={{ color: "#2563eb", textDecoration: "none", fontWeight: 500 }}>
                      {job.name}
                    </Link>
                  </td>
                  <td>{job.job_type}</td>
                  <td>
                    <StatusBadge status={job.status as RunStatus} />
                  </td>
                  <td>{job.max_retries}</td>
                  <td>{job.timeout_seconds}s</td>
                  <td>{formatDateTime(job.created_at)}</td>
                  <td>{formatDateTime(job.updated_at)}</td>
                  <td>
                    <Link to={`/jobs/${job.id}/edit`} className="btn btn-secondary btn-sm">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.pages > 1 && (
            <div className="data-table-footer">
              <span>
                Page {data.page} of {data.pages} ({data.total} total)
              </span>
              <Pagination page={data.page} pages={data.pages} onPageChange={setPage} />
            </div>
          )}
        </div>
      )}
    </>
  );
}

function Pagination({
  page,
  pages,
  onPageChange,
}: {
  page: number;
  pages: number;
  onPageChange: (p: number) => void;
}) {
  return (
    <div className="pagination" role="navigation" aria-label="Pagination">
      <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Prev
      </button>
      {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
        const p = i + 1;
        return (
          <button key={p} className={p === page ? "active" : ""} onClick={() => onPageChange(p)}>
            {p}
          </button>
        );
      })}
      <button disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
        Next
      </button>
    </div>
  );
}

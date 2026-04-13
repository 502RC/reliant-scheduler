import { useState, useMemo, useCallback } from "react";
import { useApi } from "@/hooks/useApi";
import { jobs, schedules } from "@/services/api";
import { buildDagGraph } from "@/utils/dagLayout";
import DagCanvas from "@/components/dag/DagCanvas";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import type { JobResponse, JobDependencyResponse, ScheduleResponse } from "@/types/api";

type ViewMode = "all" | "job" | "schedule";

export default function DagExplorer() {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [selectedScheduleId, setSelectedScheduleId] = useState<string>("");
  const [search, setSearch] = useState("");

  const allJobsResult = useApi(() => jobs.list(1, 200), []);
  const schedulesResult = useApi(() => schedules.list(1, 200), []);

  // Collect all dependencies for all jobs
  const [allDeps, setAllDeps] = useState<JobDependencyResponse[]>([]);
  const [depsLoading, setDepsLoading] = useState(false);
  const [depsLoaded, setDepsLoaded] = useState(false);

  const allJobs: JobResponse[] = allJobsResult.data?.items ?? [];
  const allSchedules: ScheduleResponse[] = schedulesResult.data?.items ?? [];

  // Load all dependencies once when data is ready
  const loadAllDeps = useCallback(async () => {
    if (depsLoaded || depsLoading || allJobs.length === 0) return;
    setDepsLoading(true);
    try {
      const depResults = await Promise.all(
        allJobs.map((job) =>
          jobs.dependencies(job.id).catch(() => [] as JobDependencyResponse[])
        )
      );
      const merged = depResults.flat();
      // Deduplicate by id
      const seen = new Set<string>();
      const unique: JobDependencyResponse[] = [];
      for (const dep of merged) {
        if (!seen.has(dep.id)) {
          seen.add(dep.id);
          unique.push(dep);
        }
      }
      setAllDeps(unique);
      setDepsLoaded(true);
    } finally {
      setDepsLoading(false);
    }
  }, [allJobs, depsLoaded, depsLoading]);

  // Trigger dep loading when jobs are ready
  useMemo(() => {
    if (allJobs.length > 0 && !depsLoaded) {
      loadAllDeps();
    }
  }, [allJobs.length, depsLoaded, loadAllDeps]);

  // Filter deps based on view mode
  const filteredDeps = useMemo(() => {
    if (viewMode === "all") return allDeps;

    if (viewMode === "job" && selectedJobId) {
      // Show deps involving this job (2 levels deep)
      const directIds = new Set<string>([selectedJobId]);
      for (const dep of allDeps) {
        if (dep.dependent_job_id === selectedJobId || dep.depends_on_job_id === selectedJobId) {
          directIds.add(dep.dependent_job_id);
          directIds.add(dep.depends_on_job_id);
        }
      }
      // Second level
      const level2Ids = new Set(directIds);
      for (const dep of allDeps) {
        if (directIds.has(dep.dependent_job_id) || directIds.has(dep.depends_on_job_id)) {
          level2Ids.add(dep.dependent_job_id);
          level2Ids.add(dep.depends_on_job_id);
        }
      }
      return allDeps.filter(
        (dep) => level2Ids.has(dep.dependent_job_id) || level2Ids.has(dep.depends_on_job_id)
      );
    }

    if (viewMode === "schedule" && selectedScheduleId) {
      // Show deps for jobs in this schedule
      const scheduleJobIds = new Set(
        allSchedules
          .filter((s) => s.id === selectedScheduleId)
          .map((s) => s.job_id)
      );
      // Expand to include all deps involving those jobs
      const involved = new Set(scheduleJobIds);
      for (const dep of allDeps) {
        if (scheduleJobIds.has(dep.dependent_job_id) || scheduleJobIds.has(dep.depends_on_job_id)) {
          involved.add(dep.dependent_job_id);
          involved.add(dep.depends_on_job_id);
        }
      }
      return allDeps.filter(
        (dep) => involved.has(dep.dependent_job_id) || involved.has(dep.depends_on_job_id)
      );
    }

    return allDeps;
  }, [viewMode, selectedJobId, selectedScheduleId, allDeps, allSchedules]);

  // Filter jobs by search
  const searchFilteredJobs = useMemo(() => {
    if (!search) return allJobs;
    const lower = search.toLowerCase();
    return allJobs.filter(
      (j) => j.name.toLowerCase().includes(lower) || j.job_type.toLowerCase().includes(lower)
    );
  }, [allJobs, search]);

  const graphData = useMemo(() => {
    if (filteredDeps.length === 0) return null;
    const rootId = viewMode === "job" && selectedJobId ? selectedJobId : undefined;
    return buildDagGraph(allJobs, filteredDeps, rootId);
  }, [allJobs, filteredDeps, viewMode, selectedJobId]);

  if (allJobsResult.loading || schedulesResult.loading) {
    return <LoadingSpinner message="Loading DAG data..." />;
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h2>DAG Explorer</h2>
          <p style={{ fontSize: 13, color: "#6b7280", margin: 0 }}>
            Explore job dependency graphs across the system
          </p>
        </div>
      </div>

      <div className="dag-explorer-controls">
        <div className="dag-explorer-filters">
          <div className="form-group" style={{ minWidth: 140 }}>
            <label htmlFor="dag-view-mode" className="form-label">View</label>
            <select
              id="dag-view-mode"
              className="form-select"
              value={viewMode}
              onChange={(e) => {
                setViewMode(e.target.value as ViewMode);
                setSelectedJobId("");
                setSelectedScheduleId("");
              }}
            >
              <option value="all">All Dependencies</option>
              <option value="job">By Job</option>
              <option value="schedule">By Schedule</option>
            </select>
          </div>

          {viewMode === "job" && (
            <div className="form-group" style={{ minWidth: 200 }}>
              <label htmlFor="dag-job-select" className="form-label">Job</label>
              <select
                id="dag-job-select"
                className="form-select"
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
              >
                <option value="">Select a job...</option>
                {searchFilteredJobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {viewMode === "schedule" && (
            <div className="form-group" style={{ minWidth: 200 }}>
              <label htmlFor="dag-schedule-select" className="form-label">Schedule</label>
              <select
                id="dag-schedule-select"
                className="form-select"
                value={selectedScheduleId}
                onChange={(e) => setSelectedScheduleId(e.target.value)}
              >
                <option value="">Select a schedule...</option>
                {allSchedules.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.job_id} — {s.trigger_type} ({s.cron_expression ?? "manual"})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-group" style={{ minWidth: 180 }}>
            <label htmlFor="dag-search" className="form-label">Search Jobs</label>
            <input
              id="dag-search"
              className="form-input"
              type="text"
              placeholder="Filter by name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="dag-explorer-stats">
          <span className="dag-stat">
            <strong>{filteredDeps.length}</strong> dependencies
          </span>
          <span className="dag-stat">
            <strong>{graphData?.nodes.length ?? 0}</strong> nodes
          </span>
        </div>
      </div>

      {depsLoading && <LoadingSpinner message="Loading dependencies..." />}

      {!depsLoading && filteredDeps.length === 0 && (
        <EmptyState
          title="No dependencies found"
          description={
            viewMode === "all"
              ? "No job dependencies have been defined yet."
              : "No dependencies found for this selection."
          }
        />
      )}

      {!depsLoading && graphData && (
        <DagCanvas
          initialNodes={graphData.nodes}
          initialEdges={graphData.edges}
          editable={false}
          showMiniMap
        />
      )}
    </>
  );
}

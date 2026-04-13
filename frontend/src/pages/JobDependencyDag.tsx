import { useState, useCallback, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { jobs } from "@/services/api";
import { buildDagGraph, wouldCreateCycle } from "@/utils/dagLayout";
import DagCanvas from "@/components/dag/DagCanvas";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import type { JobResponse, JobDependencyResponse } from "@/types/api";

export default function JobDependencyDag() {
  const { id } = useParams<{ id: string }>();
  const { hasRole } = useAuth();
  const canEdit = hasRole("admin", "scheduler_admin", "scheduler", "operator");

  const [editMode, setEditMode] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" } | null>(null);

  const jobResult = useApi(() => jobs.get(id!), [id]);
  const depsResult = useApi(() => jobs.dependencies(id!), [id]);
  const allJobsResult = useApi(() => jobs.list(1, 200), []);

  const deps: JobDependencyResponse[] = depsResult.data ?? [];
  const allJobs: JobResponse[] = allJobsResult.data?.items ?? [];

  const graphData = useMemo(() => {
    if (!id || deps.length === 0) return null;
    return buildDagGraph(allJobs, deps, id);
  }, [allJobs, deps, id]);

  const showToast = useCallback((message: string, type: "error" | "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const handleAddDependency = useCallback(
    async (sourceJobId: string, targetJobId: string) => {
      // sourceJobId = depends_on (must finish first), targetJobId = dependent
      if (wouldCreateCycle(deps, sourceJobId, targetJobId)) {
        showToast("Cannot add dependency: this would create a circular dependency.", "error");
        return;
      }

      try {
        await jobs.addDependency(targetJobId, { depends_on_job_id: sourceJobId });
        showToast("Dependency added successfully.", "success");
        depsResult.refetch();
      } catch (err) {
        showToast(
          err instanceof Error ? err.message : "Failed to add dependency.",
          "error"
        );
      }
    },
    [deps, depsResult, showToast]
  );

  const handleRemoveDependency = useCallback(
    async (dependencyId: string) => {
      try {
        // Find the dependency to get the job ID for the API call
        const dep = deps.find((d) => d.id === dependencyId);
        if (!dep) return;
        await jobs.removeDependency(dep.dependent_job_id, dependencyId);
        showToast("Dependency removed.", "success");
        depsResult.refetch();
      } catch (err) {
        showToast(
          err instanceof Error ? err.message : "Failed to remove dependency.",
          "error"
        );
      }
    },
    [deps, depsResult, showToast]
  );

  if (jobResult.loading || depsResult.loading || allJobsResult.loading) {
    return <LoadingSpinner message="Loading dependency graph..." />;
  }

  if (!jobResult.data) {
    return (
      <div className="card" role="alert" style={{ color: "#dc2626" }}>
        Job not found.
      </div>
    );
  }

  if (deps.length === 0) {
    return (
      <>
        <div className="page-header">
          <div>
            <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
              <Link to={`/jobs/${id}`} style={{ color: "#2563eb" }}>
                {jobResult.data.name}
              </Link>
            </div>
            <h2>Dependency Graph</h2>
          </div>
        </div>
        <EmptyState
          title="No dependencies"
          description="This job has no upstream or downstream dependencies."
          action={
            <Link to={`/jobs/${id}`} className="btn btn-secondary">
              Back to Job
            </Link>
          }
        />
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>
            <Link to={`/jobs/${id}`} style={{ color: "#2563eb" }}>
              {jobResult.data.name}
            </Link>
          </div>
          <h2>Dependency Graph</h2>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {canEdit && (
            <button
              className={`btn ${editMode ? "btn-primary" : "btn-secondary"} btn-sm`}
              onClick={() => setEditMode((prev) => !prev)}
            >
              {editMode ? "Done Editing" : "Edit Dependencies"}
            </button>
          )}
          <Link to="/dag" className="btn btn-secondary btn-sm">
            DAG Explorer
          </Link>
        </div>
      </div>

      {toast && (
        <div
          className={`dag-toast dag-toast--${toast.type}`}
          role="alert"
        >
          {toast.message}
        </div>
      )}

      <div className="dag-legend">
        <span className="dag-legend__item">
          <span className="dag-legend__dot" style={{ background: "#10b981" }} />
          Active
        </span>
        <span className="dag-legend__item">
          <span className="dag-legend__dot" style={{ background: "#f59e0b" }} />
          Paused
        </span>
        <span className="dag-legend__item">
          <span className="dag-legend__dot" style={{ background: "#9ca3af" }} />
          Inactive
        </span>
        <span className="dag-legend__item">
          <span className="dag-legend__swatch" style={{ border: "2.5px solid #2563eb", background: "#eff6ff" }} />
          Current Job
        </span>
      </div>

      {graphData && (
        <DagCanvas
          initialNodes={graphData.nodes}
          initialEdges={graphData.edges}
          editable={editMode}
          onAddDependency={handleAddDependency}
          onRemoveDependency={handleRemoveDependency}
        />
      )}
    </>
  );
}

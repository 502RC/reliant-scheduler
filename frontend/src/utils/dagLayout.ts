/**
 * DAG layout utilities using dagre for automatic node positioning.
 * Converts job dependency data into React Flow nodes/edges.
 */
import dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";
import type { JobResponse, JobDependencyResponse } from "@/types/api";

/** Status-based color scheme for DAG nodes */
export const DAG_STATUS_COLORS: Record<
  string,
  { bg: string; border: string; text: string; badge: string }
> = {
  active: { bg: "#ecfdf5", border: "#10b981", text: "#065f46", badge: "#10b981" },
  inactive: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151", badge: "#9ca3af" },
  paused: { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", badge: "#f59e0b" },
  // Run statuses for when nodes show last-run info
  success: { bg: "#ecfdf5", border: "#10b981", text: "#065f46", badge: "#10b981" },
  running: { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af", badge: "#3b82f6" },
  queued: { bg: "#fefce8", border: "#eab308", text: "#854d0e", badge: "#eab308" },
  pending: { bg: "#f3f4f6", border: "#d1d5db", text: "#374151", badge: "#d1d5db" },
  failed: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b", badge: "#ef4444" },
  cancelled: { bg: "#f3f4f6", border: "#9ca3af", text: "#6b7280", badge: "#9ca3af" },
  timed_out: { bg: "#fef2f2", border: "#dc2626", text: "#991b1b", badge: "#dc2626" },
  unknown: { bg: "#f3f4f6", border: "#d1d5db", text: "#374151", badge: "#d1d5db" },
};

export const NODE_WIDTH = 220;
export const NODE_HEIGHT = 72;

export interface DagJobNodeData {
  label: string;
  jobId: string;
  status: string;
  jobType: string;
  isRoot: boolean;
  isCriticalPath: boolean;
  [key: string]: unknown;
}

export interface DagGraphData {
  nodes: Node<DagJobNodeData>[];
  edges: Edge[];
}

/**
 * Build a React Flow graph from job data and dependency relationships.
 */
export function buildDagGraph(
  jobs: JobResponse[],
  dependencies: JobDependencyResponse[],
  rootJobId?: string,
  criticalPathIds?: Set<string>
): DagGraphData {
  const jobMap = new Map(jobs.map((j) => [j.id, j]));

  // Collect all involved job IDs
  const involvedIds = new Set<string>();
  for (const dep of dependencies) {
    involvedIds.add(dep.dependent_job_id);
    involvedIds.add(dep.depends_on_job_id);
  }
  // Include root even if it has no deps
  if (rootJobId) involvedIds.add(rootJobId);

  // Build edges
  const edges: Edge[] = dependencies.map((dep) => ({
    id: `e-${dep.depends_on_job_id}-${dep.dependent_job_id}`,
    source: dep.depends_on_job_id,
    target: dep.dependent_job_id,
    animated: false,
    style: {
      stroke: criticalPathIds?.has(dep.depends_on_job_id) && criticalPathIds?.has(dep.dependent_job_id)
        ? "#2563eb"
        : "#94a3b8",
      strokeWidth: criticalPathIds?.has(dep.depends_on_job_id) && criticalPathIds?.has(dep.dependent_job_id)
        ? 3
        : 1.5,
    },
    data: { dependencyId: dep.id },
  }));

  // Build nodes
  const nodes: Node<DagJobNodeData>[] = [...involvedIds].map((id) => {
    const job = jobMap.get(id);
    return {
      id,
      type: "dagJobNode",
      position: { x: 0, y: 0 }, // Will be set by layout
      data: {
        label: job?.name ?? id.slice(0, 8),
        jobId: id,
        status: job?.status ?? "unknown",
        jobType: job?.job_type ?? "unknown",
        isRoot: id === rootJobId,
        isCriticalPath: criticalPathIds?.has(id) ?? false,
      },
    };
  });

  // Apply dagre layout
  return applyDagreLayout(nodes, edges);
}

/**
 * Apply dagre layout algorithm to position nodes.
 */
function applyDagreLayout(
  nodes: Node<DagJobNodeData>[],
  edges: Edge[]
): DagGraphData {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "LR",
    nodesep: 40,
    ranksep: 80,
    marginx: 20,
    marginy: 20,
  });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const layoutNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
    };
  });

  return { nodes: layoutNodes, edges };
}

/**
 * Detect if adding a dependency would create a cycle.
 * Returns true if adding source -> target would create a circular dependency.
 */
export function wouldCreateCycle(
  existingDeps: JobDependencyResponse[],
  sourceId: string,
  targetId: string
): boolean {
  if (sourceId === targetId) return true;

  // Build adjacency list (depends_on -> dependent means depends_on must finish first)
  const children = new Map<string, Set<string>>();
  for (const dep of existingDeps) {
    const set = children.get(dep.depends_on_job_id) ?? new Set();
    set.add(dep.dependent_job_id);
    children.set(dep.depends_on_job_id, set);
  }
  // Add the proposed edge
  const set = children.get(sourceId) ?? new Set();
  set.add(targetId);
  children.set(sourceId, set);

  // BFS from target to see if we can reach source
  const visited = new Set<string>();
  const queue = [targetId];
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current === sourceId) return true;
    if (visited.has(current)) continue;
    visited.add(current);
    for (const child of children.get(current) ?? []) {
      queue.push(child);
    }
  }
  return false;
}

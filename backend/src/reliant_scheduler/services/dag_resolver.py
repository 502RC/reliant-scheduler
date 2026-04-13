"""DAG-based job dependency resolver.

Resolves execution order using topological sort and detects circular dependencies.
"""

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.job import Job, JobDependency


@dataclass
class DagNode:
    job_id: uuid.UUID
    job_name: str
    dependencies: list[uuid.UUID]


class CircularDependencyError(Exception):
    pass


class DagResolver:
    """Resolves job execution order from dependency graph."""

    async def build_graph(self, session: AsyncSession) -> dict[uuid.UUID, DagNode]:
        """Load all active jobs and their dependencies into a graph."""
        jobs_result = await session.execute(
            select(Job).where(Job.status == "active")
        )
        jobs = {j.id: j for j in jobs_result.scalars().all()}

        deps_result = await session.execute(select(JobDependency))
        deps = deps_result.scalars().all()

        dep_map: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for dep in deps:
            dep_map[dep.dependent_job_id].append(dep.depends_on_job_id)

        graph: dict[uuid.UUID, DagNode] = {}
        for job_id, job in jobs.items():
            graph[job_id] = DagNode(
                job_id=job_id,
                job_name=job.name,
                dependencies=dep_map.get(job_id, []),
            )
        return graph

    def topological_sort(self, graph: dict[uuid.UUID, DagNode]) -> list[uuid.UUID]:
        """Kahn's algorithm for topological ordering. Raises on cycles."""
        in_degree: dict[uuid.UUID, int] = {node_id: 0 for node_id in graph}
        for node in graph.values():
            for dep_id in node.dependencies:
                if dep_id in in_degree:
                    in_degree[dep_id] = in_degree.get(dep_id, 0)

        # Count incoming edges
        reverse_adj: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for node in graph.values():
            for dep_id in node.dependencies:
                if dep_id in graph:
                    reverse_adj[dep_id].append(node.job_id)

        in_degree = {nid: len(n.dependencies) for nid, n in graph.items()}

        queue: deque[uuid.UUID] = deque()
        for nid, degree in in_degree.items():
            if degree == 0:
                queue.append(nid)

        order: list[uuid.UUID] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for dependent in reverse_adj.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(graph):
            resolved = set(order)
            cycle_nodes = [graph[nid].job_name for nid in graph if nid not in resolved]
            raise CircularDependencyError(
                f"Circular dependency detected involving: {', '.join(cycle_nodes)}"
            )

        return order

    def get_ready_jobs(
        self, graph: dict[uuid.UUID, DagNode], completed: set[uuid.UUID]
    ) -> list[uuid.UUID]:
        """Return jobs whose dependencies are all satisfied."""
        ready = []
        for node_id, node in graph.items():
            if node_id in completed:
                continue
            if all(dep_id in completed for dep_id in node.dependencies):
                ready.append(node_id)
        return ready

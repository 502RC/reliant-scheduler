import uuid

import pytest

from reliant_scheduler.services.dag_resolver import DagNode, DagResolver, CircularDependencyError


@pytest.fixture
def resolver() -> DagResolver:
    return DagResolver()


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def test_topological_sort_linear(resolver: DagResolver) -> None:
    """A -> B -> C should produce [A, B, C] or equivalent valid order."""
    graph = {
        _id(1): DagNode(_id(1), "A", []),
        _id(2): DagNode(_id(2), "B", [_id(1)]),
        _id(3): DagNode(_id(3), "C", [_id(2)]),
    }
    order = resolver.topological_sort(graph)
    assert order.index(_id(1)) < order.index(_id(2)) < order.index(_id(3))


def test_topological_sort_diamond(resolver: DagResolver) -> None:
    """Diamond: A -> B, A -> C, B -> D, C -> D."""
    graph = {
        _id(1): DagNode(_id(1), "A", []),
        _id(2): DagNode(_id(2), "B", [_id(1)]),
        _id(3): DagNode(_id(3), "C", [_id(1)]),
        _id(4): DagNode(_id(4), "D", [_id(2), _id(3)]),
    }
    order = resolver.topological_sort(graph)
    assert order.index(_id(1)) < order.index(_id(2))
    assert order.index(_id(1)) < order.index(_id(3))
    assert order.index(_id(2)) < order.index(_id(4))
    assert order.index(_id(3)) < order.index(_id(4))


def test_circular_dependency_detected(resolver: DagResolver) -> None:
    """Circular A -> B -> A should raise."""
    graph = {
        _id(1): DagNode(_id(1), "A", [_id(2)]),
        _id(2): DagNode(_id(2), "B", [_id(1)]),
    }
    with pytest.raises(CircularDependencyError):
        resolver.topological_sort(graph)


def test_get_ready_jobs(resolver: DagResolver) -> None:
    graph = {
        _id(1): DagNode(_id(1), "A", []),
        _id(2): DagNode(_id(2), "B", [_id(1)]),
        _id(3): DagNode(_id(3), "C", []),
    }
    # Nothing completed — A and C are ready (no deps)
    ready = resolver.get_ready_jobs(graph, set())
    assert set(ready) == {_id(1), _id(3)}

    # A completed — B becomes ready
    ready = resolver.get_ready_jobs(graph, {_id(1)})
    assert _id(2) in ready
    assert _id(3) in ready


def test_independent_jobs(resolver: DagResolver) -> None:
    """All independent jobs should all appear in topological sort."""
    graph = {
        _id(i): DagNode(_id(i), f"Job{i}", []) for i in range(1, 6)
    }
    order = resolver.topological_sort(graph)
    assert len(order) == 5

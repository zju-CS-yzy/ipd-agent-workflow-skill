"""Dependency graph checks used by state validation and transitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def find_cycle(graph: Mapping[str, Iterable[str]]) -> tuple[str, ...] | None:
    """Return one deterministic dependency cycle, including its repeated start."""

    visited: set[str] = set()
    active: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> tuple[str, ...] | None:
        if node in active:
            start = stack.index(node)
            return tuple(stack[start:] + [node])
        if node in visited:
            return None

        active.add(node)
        stack.append(node)
        for dependency in sorted(graph.get(node, ())):
            if dependency not in graph:
                continue
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop()
        active.remove(node)
        visited.add(node)
        return None

    for identifier in sorted(graph):
        cycle = visit(identifier)
        if cycle:
            return cycle
    return None


def unmet_dependencies(
    identifier: str,
    graph: Mapping[str, Iterable[str]],
    status_by_id: Mapping[str, str],
) -> tuple[str, ...]:
    """Return dependencies that are missing or not accepted."""

    return tuple(
        dependency
        for dependency in graph.get(identifier, ())
        if status_by_id.get(dependency) != "accepted"
    )

"""Helpers for checking relationships among workflow entities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def collect_entity_ids(state: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    """Return all entity IDs and IDs duplicated across entity collections."""

    identifiers: set[str] = set()
    duplicates: set[str] = set()
    for collection_name in ("claims", "deliverables", "gates"):
        collection = state.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier:
                continue
            if identifier in identifiers:
                duplicates.add(identifier)
            identifiers.add(identifier)
    return identifiers, duplicates


def dangling_links(state: Mapping[str, Any]) -> tuple[tuple[int, str, str], ...]:
    """Return ``(index, field, value)`` for links to unknown entity IDs."""

    identifiers, _ = collect_entity_ids(state)
    problems: list[tuple[int, str, str]] = []
    links = state.get("traceability", [])
    if not isinstance(links, list):
        return ()
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            continue
        for field in ("source", "target"):
            value = link.get(field)
            if isinstance(value, str) and value and value not in identifiers:
                problems.append((index, field, value))
    return tuple(problems)

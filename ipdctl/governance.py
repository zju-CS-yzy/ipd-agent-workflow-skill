"""Shared governance pointers derived from process and state facts."""

from __future__ import annotations

from typing import Any


def phase_pointers(
    state: dict[str, Any], process: dict[str, Any]
) -> dict[str, str | None]:
    """Return the canonical TR, DCP, and next pending Gate for the phase."""

    phase = state.get("project", {}).get("phase")
    gate_status = {
        item.get("id"): item.get("status")
        for item in state.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    def candidates(collection: str) -> list[str]:
        return [
            item["id"]
            for item in process.get(collection, [])
            if isinstance(item, dict)
            and item.get("phase") == phase
            and isinstance(item.get("id"), str)
        ]

    technical_reviews = candidates("technical_reviews")
    decision_checkpoints = candidates("decision_checkpoints")
    gate_rows = [
        item
        for item in process.get("gates", [])
        if isinstance(item, dict)
        and item.get("phase") == phase
        and isinstance(item.get("id"), str)
    ]
    canonical_gate_ids = [f"gate.tr.{phase}", f"gate.dcp.{phase}"]
    available_gate_ids = {item["id"] for item in gate_rows}
    generic_gate_ids = sorted(
        item["id"]
        for item in gate_rows
        if item.get("kind") == "Gate" and item["id"] not in canonical_gate_ids
    )
    gates = [
        identifier
        for identifier in canonical_gate_ids
        if identifier in available_gate_ids
    ] + generic_gate_ids
    next_gate = next(
        (identifier for identifier in gates if gate_status.get(identifier) != "approved"),
        None,
    )
    return {
        "current_tr": technical_reviews[0] if technical_reviews else None,
        "current_dcp": decision_checkpoints[0] if decision_checkpoints else None,
        "current_gate": next_gate,
    }


def apply_phase_pointers(
    state: dict[str, Any], process: dict[str, Any]
) -> dict[str, Any]:
    """Update pointers on an already independent mutable state value."""

    state["project"].update(phase_pointers(state, process))
    return state


def phase_history_issues(
    state: dict[str, Any],
    process: dict[str, Any],
    runtime: dict[str, Any] | None = None,
) -> list[str]:
    """Validate that the current Phase was reached by governed transitions."""

    issues: list[str] = []
    phase_rows = sorted(
        [item for item in process.get("phases", []) if isinstance(item, dict)],
        key=lambda item: (item.get("sequence", 0), item.get("id", "")),
    )
    phase_ids = [
        item["id"] for item in phase_rows if isinstance(item.get("id"), str)
    ]
    current = state.get("project", {}).get("phase")
    if not phase_ids or current not in phase_ids:
        return ["current project phase is absent from the governed phase history"]

    current_index = phase_ids.index(current)
    earlier_phases = set(phase_ids[:current_index])
    process_gate_ids = {
        item.get("id")
        for item in process.get("gates", [])
        if isinstance(item, dict)
        and item.get("phase") in earlier_phases
        and isinstance(item.get("id"), str)
    }
    state_gate_status = {
        item.get("id"): item.get("status")
        for item in state.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    unfinished = sorted(
        identifier
        for identifier in process_gate_ids
        if state_gate_status.get(identifier) != "approved"
    )
    if unfinished:
        issues.append(
            "earlier phases contain unapproved gates: " + ", ".join(unfinished)
        )

    if runtime is None:
        return issues
    events = runtime.get("events", [])
    if not isinstance(events, list):
        return issues + ["Agent runtime events are unavailable for phase history"]

    expected_phase = phase_ids[0]
    current_revision = state.get("revision")
    for index, event in enumerate(events):
        if not isinstance(event, dict) or event.get("action") != "advance_phase":
            continue
        from_phase = event.get("from_phase")
        to_phase = event.get("to_phase")
        event_revision = event.get("state_revision")
        if not isinstance(from_phase, str) or not from_phase:
            issues.append(f"phase advancement event {index} has no from_phase")
            continue
        if not isinstance(to_phase, str) or not to_phase:
            issues.append(f"phase advancement event {index} has no to_phase")
            continue
        if type(event_revision) is not int or event_revision < 0:
            issues.append(
                f"phase advancement event {index} has an invalid state_revision"
            )
        elif type(current_revision) is int and event_revision > current_revision:
            issues.append(
                f"phase advancement event {index} exceeds the current state revision"
            )
        if from_phase != expected_phase:
            issues.append(
                f"phase advancement event {index} starts at {from_phase!r}; expected {expected_phase!r}"
            )
            continue
        expected_index = phase_ids.index(expected_phase)
        if expected_index + 1 >= len(phase_ids):
            issues.append(
                f"phase advancement event {index} advances beyond the final phase"
            )
            continue
        expected_next = phase_ids[expected_index + 1]
        if to_phase != expected_next:
            issues.append(
                f"phase advancement event {index} targets {to_phase!r}; expected {expected_next!r}"
            )
            continue
        expected_phase = to_phase

    if current != expected_phase:
        issues.append(
            f"project phase {current!r} does not match phase advancement history {expected_phase!r}"
        )
    return issues


__all__ = [
    "apply_phase_pointers",
    "phase_history_issues",
    "phase_pointers",
]

"""Governed product-phase progression for tailored IPD projects."""

from __future__ import annotations

from typing import Any

from .engine import TransitionError
from .governance import apply_phase_pointers
from .state import revised_copy
from .validation import validate_state


def _phase_records(process: dict[str, Any]) -> list[dict[str, Any]]:
    records = [item for item in process.get("phases", []) if isinstance(item, dict)]
    return sorted(records, key=lambda item: (item.get("sequence", 0), item.get("id", "")))


def _phase_gate_ids(process: dict[str, Any], phase_id: str) -> list[str]:
    return [
        item["id"]
        for item in process.get("gates", [])
        if isinstance(item, dict)
        and item.get("phase") == phase_id
        and isinstance(item.get("id"), str)
    ]


def phase_completion(state: dict[str, Any], process: dict[str, Any]) -> dict[str, Any]:
    """Describe whether the current governed product phase is complete."""

    current = state.get("project", {}).get("phase")
    gate_ids = _phase_gate_ids(process, current)
    state_gates = {
        item.get("id"): item
        for item in state.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    missing = [identifier for identifier in gate_ids if identifier not in state_gates]
    pending = [
        identifier
        for identifier in gate_ids
        if identifier in state_gates and state_gates[identifier].get("status") != "approved"
    ]
    return {
        "phase": current,
        "gate_ids": gate_ids,
        "missing_gates": missing,
        "pending_gates": pending,
        "complete": bool(gate_ids) and not missing and not pending,
    }


def advance_phase(
    state: dict[str, Any],
    process: dict[str, Any],
    *,
    verified_state_revision: int | None = None,
) -> dict[str, Any]:
    """Advance after every Gate is approved and this exact revision is verified."""

    issues = validate_state(state)
    if issues:
        raise TransitionError(f"state is invalid: {issues[0]}")
    phases = _phase_records(process)
    phase_ids = [item.get("id") for item in phases]
    current = state["project"].get("phase")
    if current not in phase_ids:
        raise TransitionError(f"current phase is not in the tailored process: {current!r}")

    completion = phase_completion(state, process)
    if completion["missing_gates"]:
        raise TransitionError(
            "current phase is missing gate state: "
            + ", ".join(completion["missing_gates"])
        )
    if completion["pending_gates"]:
        raise TransitionError(
            "current phase gates are not approved: "
            + ", ".join(completion["pending_gates"])
        )
    if not completion["gate_ids"]:
        raise TransitionError(f"current phase has no governed gates: {current!r}")
    if state["project"].get("workflow_step") != "verify":
        raise TransitionError("current phase must be refreshed before it can advance")
    if verified_state_revision != state.get("revision"):
        raise TransitionError(
            "current state revision must pass verification before phase advancement"
        )

    current_index = phase_ids.index(current)
    if current_index + 1 >= len(phases):
        raise TransitionError(f"final lifecycle phase is already complete: {current!r}")
    next_phase = phase_ids[current_index + 1]

    updated = revised_copy(state)
    updated["project"]["phase"] = next_phase
    # A phase change invalidates every derived view.  Keep the execution loop
    # at refresh until the new phase has been rendered and verified.
    updated["project"]["workflow_step"] = "refresh"
    apply_phase_pointers(updated, process)

    issues = validate_state(updated)
    if issues:
        raise TransitionError(str(issues[0]))
    return updated


__all__ = ["advance_phase", "phase_completion"]

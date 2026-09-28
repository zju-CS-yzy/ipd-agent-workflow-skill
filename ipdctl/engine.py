"""Safe state transitions for the non-negotiable IPD invariants."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .model import DELIVERABLE_TRANSITIONS, REVIEW_DECISIONS, REVIEWER_TYPES, WORKFLOW_STEPS
from .state import revised_copy
from .validation import validate_state


class TransitionError(ValueError):
    """Raised when a requested workflow transition is not valid."""


def _ensure_valid(state: dict[str, Any]) -> None:
    issues = validate_state(state)
    if issues:
        raise TransitionError(f"state is invalid: {issues[0]}")


def _finalize(updated: dict[str, Any]) -> dict[str, Any]:
    issues = validate_state(updated)
    if issues:
        raise TransitionError(str(issues[0]))
    return updated


def _find(items: list[dict[str, Any]], identifier: str, kind: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == identifier:
            return item
    raise TransitionError(f"unknown {kind}: {identifier!r}")


def transition_workflow(state: dict[str, Any], target: str) -> dict[str, Any]:
    """Move one step through context -> claim -> work -> close -> verify."""

    _ensure_valid(state)
    current = state["project"]["workflow_step"]
    current_index = WORKFLOW_STEPS.index(current)
    expected = WORKFLOW_STEPS[(current_index + 1) % len(WORKFLOW_STEPS)]
    if target != expected:
        raise TransitionError(
            f"workflow step {current!r} can only transition to {expected!r}"
        )
    updated = revised_copy(state)
    updated["project"]["workflow_step"] = target
    return _finalize(updated)


def set_deliverable_status(
    state: dict[str, Any],
    identifier: str,
    target: str,
    evidence: Iterable[str] = (),
) -> dict[str, Any]:
    """Apply a legal deliverable transition and optionally add evidence."""

    _ensure_valid(state)
    updated = revised_copy(state)
    deliverable = _find(updated["deliverables"], identifier, "deliverable")
    current = deliverable["status"]
    if target not in DELIVERABLE_TRANSITIONS[current]:
        allowed = ", ".join(sorted(DELIVERABLE_TRANSITIONS[current])) or "none"
        raise TransitionError(
            f"deliverable status {current!r} cannot transition to {target!r}; "
            f"allowed: {allowed}"
        )
    deliverable["status"] = target
    for item in evidence:
        if item not in deliverable["evidence"]:
            deliverable["evidence"].append(item)
    return _finalize(updated)


def record_gate_review(
    state: dict[str, Any],
    gate_id: str,
    *,
    reviewer: str,
    reviewer_type: str,
    authorized: bool,
    decision: str,
    evidence: str,
) -> dict[str, Any]:
    """Record review evidence; this does not itself approve the gate."""

    _ensure_valid(state)
    if reviewer_type not in REVIEWER_TYPES:
        raise TransitionError(f"invalid reviewer type: {reviewer_type!r}")
    if decision not in REVIEW_DECISIONS:
        raise TransitionError(f"invalid review decision: {decision!r}")
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    gate["reviews"].append(
        {
            "reviewer": reviewer,
            "reviewer_type": reviewer_type,
            "authorized": authorized,
            "decision": decision,
            "evidence": evidence,
        }
    )
    return _finalize(updated)


def set_gate_ready(state: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Mark a planned gate ready only after all required deliverables close."""

    _ensure_valid(state)
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    if gate["status"] != "planned":
        raise TransitionError("only a planned gate can be marked ready")
    gate["status"] = "ready"
    return _finalize(updated)


def approve_gate(state: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Finalize a ready gate only when authorized human approval is recorded."""

    _ensure_valid(state)
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    if gate["status"] != "ready":
        raise TransitionError("only a ready gate can be approved")
    gate["status"] = "approved"
    return _finalize(updated)

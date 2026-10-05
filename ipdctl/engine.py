"""Safe state transitions for the non-negotiable IPD invariants."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .dependencies import unmet_dependencies
from .eligibility import (
    deliverable_refinement_status,
    gate_requirement_readiness,
    requirements_fingerprint,
    unresolved_refinement_dependencies,
)
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
    """Move one step through the canonical seven-step Agent runtime loop."""

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
    *,
    blocked_reason: str | None = None,
    replacement: str | None = None,
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
    if blocked_reason is not None:
        deliverable["blocked_reason"] = blocked_reason
    elif target != "blocked":
        deliverable["blocked_reason"] = None
    if replacement is not None:
        deliverable["replacement"] = replacement
    for item in evidence:
        if item not in deliverable["evidence"]:
            deliverable["evidence"].append(item)
    return _finalize(updated)


def record_deliverable_review(
    state: dict[str, Any],
    identifier: str,
    *,
    reviewer: str,
    reviewer_type: str,
    authorized: bool,
    decision: str,
    evidence: str,
) -> dict[str, Any]:
    """Append an auditable review record to a deliverable."""

    _ensure_valid(state)
    if reviewer_type not in REVIEWER_TYPES:
        raise TransitionError(f"invalid reviewer type: {reviewer_type!r}")
    if decision not in REVIEW_DECISIONS:
        raise TransitionError(f"invalid review decision: {decision!r}")
    if not reviewer.strip() or not evidence.strip():
        raise TransitionError("reviewer and review evidence must not be empty")
    updated = revised_copy(state)
    deliverable = _find(updated["deliverables"], identifier, "deliverable")
    deliverable.setdefault("reviews", []).append(
        {
            "reviewer": reviewer,
            "reviewer_type": reviewer_type,
            "authorized": authorized,
            "decision": decision,
            "evidence": evidence,
        }
    )
    return _finalize(updated)


def claim_deliverable(state: dict[str, Any], identifier: str) -> dict[str, Any]:
    """Claim planned, blocked, or rejected work and enter ``in_progress``."""

    _ensure_valid(state)
    deliverable = _find(state["deliverables"], identifier, "deliverable")
    refinement = deliverable_refinement_status(state, identifier)
    if not refinement["claimable"]:
        raise TransitionError(
            "REFINEMENT_REQUIRED: "
            f"deliverable {identifier!r} is {refinement['definition_state']!r} "
            f"with refinement status {refinement['refinement_status']!r}; "
            "apply an authorized refinement plan before Claim"
        )
    deliverable_phase = deliverable.get("phase")
    current_phase = state["project"].get("phase")
    if deliverable_phase is not None and deliverable_phase != current_phase:
        raise TransitionError(
            f"deliverable {identifier!r} belongs to phase {deliverable_phase!r}; "
            f"current phase is {current_phase!r}"
        )
    graph = {
        item["id"]: item.get("depends_on", []) for item in state["deliverables"]
    }
    refinement_dependencies = unresolved_refinement_dependencies(
        state, identifier
    )
    if refinement_dependencies:
        raise TransitionError(
            "REFINEMENT_DEPENDENCY_REQUIRED: "
            f"deliverable {identifier!r} depends on unresolved refinement "
            f"roots: {', '.join(refinement_dependencies)}"
        )
    statuses = {item["id"]: item.get("status") for item in state["deliverables"]}
    unmet = list(unmet_dependencies(identifier, graph, statuses))
    if unmet:
        raise TransitionError(
            f"deliverable {identifier!r} has unmet dependencies: {', '.join(unmet)}"
        )
    return set_deliverable_status(state, identifier, "in_progress")


def close_deliverable(
    state: dict[str, Any], identifier: str, *, evidence: Iterable[str]
) -> dict[str, Any]:
    """Submit completed work for review; this never accepts it."""

    entries = tuple(evidence)
    if not entries:
        raise TransitionError("closing a deliverable requires evidence")
    return set_deliverable_status(
        state, identifier, "ready_for_review", evidence=entries
    )


def start_deliverable_review(
    state: dict[str, Any], identifier: str
) -> dict[str, Any]:
    return set_deliverable_status(state, identifier, "in_review")


def approve_deliverable(
    state: dict[str, Any],
    identifier: str,
    *,
    reviewer: str,
    reviewer_type: str,
    authorized: bool,
    evidence: str,
) -> dict[str, Any]:
    """Accept reviewed work only with an explicitly authorized human record."""

    if reviewer_type != "human" or not authorized:
        raise TransitionError(
            "final deliverable approval requires an authorized human reviewer"
        )
    updated = record_deliverable_review(
        state,
        identifier,
        reviewer=reviewer,
        reviewer_type=reviewer_type,
        authorized=authorized,
        decision="approve",
        evidence=evidence,
    )
    return set_deliverable_status(updated, identifier, "accepted")


def reject_deliverable(
    state: dict[str, Any],
    identifier: str,
    *,
    reviewer: str,
    reviewer_type: str,
    authorized: bool,
    evidence: str,
) -> dict[str, Any]:
    """Reject reviewed work while preserving a human review record."""

    if reviewer_type != "human" or not authorized:
        raise TransitionError(
            "final deliverable rejection requires an authorized human reviewer"
        )
    updated = record_deliverable_review(
        state,
        identifier,
        reviewer=reviewer,
        reviewer_type=reviewer_type,
        authorized=authorized,
        decision="reject",
        evidence=evidence,
    )
    return set_deliverable_status(updated, identifier, "rejected")


def record_gate_review(
    state: dict[str, Any],
    gate_id: str,
    *,
    reviewer: str,
    reviewer_type: str,
    authorized: bool,
    decision: str,
    evidence: str,
    gate_epoch: int | None = None,
) -> dict[str, Any]:
    """Record review evidence; this does not itself approve the gate."""

    _ensure_valid(state)
    if reviewer_type not in REVIEWER_TYPES:
        raise TransitionError(f"invalid reviewer type: {reviewer_type!r}")
    if decision not in REVIEW_DECISIONS:
        raise TransitionError(f"invalid review decision: {decision!r}")
    if not reviewer.strip() or not evidence.strip():
        raise TransitionError("reviewer and review evidence must not be empty")
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    _ensure_gate_requirements_current(updated, gate)
    if gate.get("stale") is True:
        raise TransitionError(
            f"gate {gate_id!r} is stale and must be made ready before review"
        )
    current_epoch = gate.get("review_epoch", 0)
    if type(current_epoch) is not int or current_epoch < 0:
        raise TransitionError("gate review_epoch must be a non-negative integer")
    if gate_epoch is not None and gate_epoch != current_epoch:
        raise TransitionError(
            f"gate review epoch {gate_epoch} is stale; current epoch is {current_epoch}"
        )
    review = {
        "reviewer": reviewer,
        "reviewer_type": reviewer_type,
        "authorized": authorized,
        "decision": decision,
        "evidence": evidence,
    }
    if gate_epoch is not None or "review_epoch" in gate:
        review["gate_epoch"] = current_epoch
    gate["reviews"].append(review)
    return _finalize(updated)


def _ensure_gate_requirements_ready(
    state: dict[str, Any], gate: dict[str, Any]
) -> None:
    readiness = gate_requirement_readiness(state, gate)
    if readiness["refinement_due"]:
        raise TransitionError(
            "REFINEMENT_REQUIRED: "
            f"gate {gate.get('id')!r} has unresolved refinement requirements: "
            + ", ".join(readiness["refinement_due"])
        )
    if readiness["incomplete"]:
        gate_index = next(
            (
                index
                for index, item in enumerate(state.get("gates", []))
                if item.get("id") == gate.get("id")
            ),
            0,
        )
        raise TransitionError(
            f"$.gates[{gate_index}].required_deliverables: "
            "gate prerequisites are not accepted: "
            + ", ".join(readiness["incomplete"])
        )


def _ensure_gate_requirements_current(
    state: dict[str, Any], gate: dict[str, Any]
) -> str:
    current = requirements_fingerprint(
        gate.get("required_deliverables", []), state
    )
    recorded = gate.get("requirements_fingerprint")
    if recorded is not None and recorded != current:
        raise TransitionError(
            f"gate {gate.get('id')!r} requirements are stale; "
            "apply or reconcile the current process refinement first"
        )
    if recorded is None:
        gate["requirements_fingerprint"] = current
    return current


def set_gate_ready(state: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Mark a planned or rejected gate ready after its prerequisites close."""

    _ensure_valid(state)
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    if gate["status"] not in {"planned", "rejected"}:
        raise TransitionError("only a planned or rejected gate can be marked ready")
    _ensure_gate_requirements_current(updated, gate)
    _ensure_gate_requirements_ready(updated, gate)
    gate["status"] = "ready"
    gate["approval"] = None
    if "stale" in gate:
        gate["stale"] = False
    if "stale_reason" in gate:
        gate["stale_reason"] = None
    if isinstance(gate.get("blockers"), list):
        gate["blockers"] = [
            item
            for item in gate["blockers"]
            if item
            not in {
                "GATE_REQUIREMENTS_CHANGED",
                "DEPENDENCY_CONTRACT_CHANGED",
            }
        ]
    return _finalize(updated)


def approve_gate(state: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Finalize a ready gate only when authorized human approval is recorded."""

    _ensure_valid(state)
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    if gate["status"] != "ready":
        raise TransitionError("only a ready gate can be approved")
    if gate.get("stale") is True:
        raise TransitionError(
            f"gate {gate_id!r} is stale and must be made ready in the current review epoch"
        )
    _ensure_gate_requirements_current(updated, gate)
    _ensure_gate_requirements_ready(updated, gate)
    current_epoch = gate.get("review_epoch", 0)
    authorized_human = [
        review
        for review in gate.get("reviews", [])
        if review.get("reviewer_type") == "human"
        and review.get("authorized") is True
        and review.get("gate_epoch", 0) == current_epoch
    ]
    if not authorized_human or authorized_human[-1].get("decision") != "approve":
        raise TransitionError(
            "gate approval requires a latest authorized human approval "
            f"in review epoch {current_epoch}"
        )
    gate["status"] = "approved"
    gate["approval"] = authorized_human[-1].get("reviewer")
    return _finalize(updated)


def reject_gate(state: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Reject a ready gate only when its latest human decision is a rejection."""

    _ensure_valid(state)
    updated = revised_copy(state)
    gate = _find(updated["gates"], gate_id, "gate")
    if gate["status"] != "ready":
        raise TransitionError("only a ready gate can be rejected")
    gate["status"] = "rejected"
    gate["approval"] = None
    current_epoch = gate.get("review_epoch", 0)
    reviews = gate.get("reviews", [])
    authorized_human = [
        review
        for review in reviews
        if review.get("reviewer_type") == "human"
        and review.get("authorized") is True
        and review.get("gate_epoch", 0) == current_epoch
    ]
    if not authorized_human or authorized_human[-1].get("decision") != "reject":
        raise TransitionError(
            "gate rejection requires a latest authorized human rejection review"
        )
    return _finalize(updated)

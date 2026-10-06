"""Shared artifact-binding eligibility used by every lifecycle surface.

The reconciliation module owns repository/binding interpretation.  This module
keeps the public readiness contract stable so context, claim preflight,
Dashboard refresh, and verification cannot disagree about actionability.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping


ELIGIBILITY_SCHEMA_VERSION = "1.0"
_STATUSES = {"passed", "warning", "failed"}
_WORKABLE_STATUSES = {"planned", "blocked", "rejected"}


def deliverable_actionability(
    deliverable: Mapping[str, Any],
    *,
    current_phase: str | None,
    active_claim: bool,
    unmet: Iterable[str] = (),
    binding_status: Mapping[str, Any] | None = None,
    claim_readiness: Mapping[str, Any] | None = None,
    refinement: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one shared actionability and blocker-classification record.

    ``blocked_items`` historically mixed ordinary dependency waits with actual
    lifecycle and governance blockers.  The shared classifier keeps that
    compatibility aggregation reproducible while exposing the three distinct
    causes used by context and Dashboard projections.
    """

    status = str(deliverable.get("status") or "planned")
    phase = deliverable.get("phase")
    in_current_scope = not current_phase or phase in {None, current_phase}
    unmet_dependencies = sorted(
        {str(item) for item in unmet if isinstance(item, str) and item}
    )
    binding = binding_status if isinstance(binding_status, Mapping) else {}
    readiness = claim_readiness if isinstance(claim_readiness, Mapping) else {}
    refinement_row = refinement if isinstance(refinement, Mapping) else {}

    orphaned_claim = status == "in_progress" and not active_claim
    binding_blocked = (
        status in _WORKABLE_STATUSES or orphaned_claim
    ) and binding.get("binding_ready") is False
    refinement_status = str(
        refinement_row.get("refinement_status") or "not_required"
    )
    refinement_claimable = refinement_row.get("claimable") is not False
    claim_ready = readiness.get("eligible") is True if readiness else True

    if status in {"accepted", "superseded"}:
        state = "inactive"
    elif active_claim:
        state = "claimed"
    elif not in_current_scope:
        state = "inactive"
    elif not refinement_claimable:
        state = "waiting_on_refinement"
    elif unmet_dependencies:
        state = "waiting_on_dependencies"
    elif binding_blocked:
        state = "waiting_on_bindings"
    elif status in _WORKABLE_STATUSES and not claim_ready:
        state = "waiting_on_protocol"
    elif status in _WORKABLE_STATUSES:
        state = "actionable"
    else:
        state = "inactive"

    if orphaned_claim:
        attention = "orphan_claim"
    elif status == "blocked":
        attention = "explicitly_blocked"
    elif status == "rejected":
        attention = "rework_required"
    elif binding_blocked:
        attention = "binding_blocked"
    elif refinement_status == "due":
        attention = "refinement_due"
    else:
        attention = None

    governance_codes: set[str] = set()
    if orphaned_claim:
        governance_codes.add("ORPHAN_CLAIM")
    if binding_blocked:
        governance_codes.update(
            str(item)
            for item in binding.get("issue_codes", [])
            if isinstance(item, str) and item
        )
        if not governance_codes:
            governance_codes.add("BINDING_NOT_READY")
    if refinement_status == "due":
        governance_codes.add(
            str(refinement_row.get("refinement_reason") or "REFINEMENT_REQUIRED")
        )

    return {
        "state": state,
        "actionable": state == "actionable",
        "in_current_scope": in_current_scope,
        "unmet_dependencies": unmet_dependencies,
        "attention": attention,
        "orphaned_claim": orphaned_claim,
        "binding_blocked": binding_blocked,
        "waiting_item": (
            in_current_scope
            and status not in {"accepted", "superseded"}
            and bool(unmet_dependencies)
        ),
        "explicit_blocker": in_current_scope and status == "blocked",
        "governance_blocker": in_current_scope and bool(governance_codes),
        "governance_codes": sorted(governance_codes),
    }


def _deliverable_records(state: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        item["id"]: item
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and item["id"]
    }


def _gate_records(state: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        item["id"]: item
        for item in state.get("gates", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and item["id"]
    }


def _refinement_children(
    deliverables: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for identifier, deliverable in deliverables.items():
        parent = deliverable.get("refines")
        if isinstance(parent, str) and parent:
            children.setdefault(parent, []).append(identifier)
    for identifiers in children.values():
        identifiers.sort()
    return children


def _refinement_leaf_ids(
    identifier: str,
    deliverables: Mapping[str, Mapping[str, Any]],
    children: Mapping[str, list[str]],
) -> tuple[list[str], list[str]]:
    """Return concrete and unresolved leaves below one refinement root."""

    concrete: list[str] = []
    unresolved: list[str] = []
    pending = list(reversed(children.get(identifier, [])))
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        descendants = children.get(child_id, [])
        if descendants:
            pending.extend(reversed(descendants))
            continue
        child = deliverables.get(child_id, {})
        if child.get("definition_state", "concrete") == "concrete":
            concrete.append(child_id)
        else:
            unresolved.append(child_id)
    return sorted(concrete), sorted(unresolved)


def _refinement_trigger_satisfied(
    trigger: Any,
    deliverables: Mapping[str, Mapping[str, Any]],
    gates: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, list[str]]:
    if not isinstance(trigger, Mapping):
        return False, ["invalid refinement trigger"]
    conditions = trigger.get("all_of")
    if not isinstance(conditions, list) or not conditions:
        return False, ["invalid refinement trigger"]
    pending: list[str] = []
    for condition in conditions:
        if not isinstance(condition, Mapping):
            pending.append("invalid refinement trigger condition")
            continue
        subject = condition.get("subject")
        expected = condition.get("condition")
        if not isinstance(subject, str) or not subject:
            pending.append("invalid refinement trigger subject")
        elif expected == "accepted":
            if deliverables.get(subject, {}).get("status") != "accepted":
                pending.append(f"{subject} must be accepted")
        elif expected == "approved":
            gate = gates.get(subject, {})
            if gate.get("status") != "approved" or gate.get("stale") is True:
                pending.append(f"{subject} must be currently approved")
        else:
            pending.append(f"{subject} has an invalid refinement condition")
    return not pending, pending


def deliverable_refinement_status(
    state: Mapping[str, Any], deliverable_id: str
) -> dict[str, Any]:
    """Derive refinement state without changing the Deliverable lifecycle.

    Old project states have no refinement fields and therefore remain concrete,
    claimable, and ``not_required`` by default.
    """

    deliverables = _deliverable_records(state)
    deliverable = deliverables.get(deliverable_id)
    if deliverable is None:
        return {
            "definition_state": None,
            "refinement_required": False,
            "refinement_status": "unknown",
            "refinement_reason": "UNKNOWN_DELIVERABLE",
            "claimable": False,
            "leaf_deliverables": [],
            "unresolved_leaves": [],
        }

    definition_state = deliverable.get("definition_state", "concrete")
    required = deliverable.get("refinement_required") is True
    children = _refinement_children(deliverables)
    concrete_leaves, unresolved_leaves = _refinement_leaf_ids(
        deliverable_id, deliverables, children
    )

    status = "not_required"
    reason: str | None = None
    if required:
        trigger = deliverable.get("refinement_trigger")
        trigger_satisfied = True
        pending_conditions: list[str] = []
        if trigger is not None:
            trigger_satisfied, pending_conditions = _refinement_trigger_satisfied(
                trigger, deliverables, _gate_records(state)
            )
        if not trigger_satisfied:
            status = "pending"
            reason = "REFINEMENT_TRIGGER_PENDING"
        elif concrete_leaves and not unresolved_leaves:
            status = "resolved"
        else:
            status = "due"
            reason = "REFINEMENT_REQUIRED"
    elif definition_state in {"abstract", "placeholder"} and not concrete_leaves:
        # Non-concrete nodes are never directly executable, even when they are
        # aggregate-only rather than explicitly trigger-driven.
        reason = "REFINEMENT_REQUIRED"

    claimable = definition_state == "concrete" and status != "due"
    if not claimable and reason is None:
        reason = "REFINEMENT_REQUIRED"
    result = {
        "definition_state": definition_state,
        "refinement_required": required,
        "refinement_status": status,
        "refinement_reason": reason,
        "claimable": claimable,
        "leaf_deliverables": concrete_leaves,
        "unresolved_leaves": unresolved_leaves,
    }
    if required and status == "pending":
        result["pending_conditions"] = pending_conditions
    return result


def unresolved_refinement_dependencies(
    state: Mapping[str, Any], deliverable_id: str
) -> list[str]:
    """Return transitive prerequisites whose process definition is unresolved."""

    deliverables = _deliverable_records(state)
    target = deliverables.get(deliverable_id)
    if target is None:
        return []
    pending = list(target.get("depends_on", []))
    visited: set[str] = set()
    blockers: set[str] = set()
    while pending:
        dependency = pending.pop()
        if not isinstance(dependency, str) or dependency in visited:
            continue
        visited.add(dependency)
        record = deliverables.get(dependency)
        if record is None:
            continue
        refinement = deliverable_refinement_status(state, dependency)
        if refinement.get("refinement_status") in {"pending", "due"}:
            blockers.add(dependency)
        pending.extend(record.get("depends_on", []))
    return sorted(blockers)


def gate_requirement_readiness(
    state: Mapping[str, Any], gate: Mapping[str, Any]
) -> dict[str, Any]:
    """Evaluate Gate prerequisites using concrete refinement leaf closure."""

    deliverables = _deliverable_records(state)
    incomplete: set[str] = set()
    refinement_due: set[str] = set()
    evaluated: dict[str, list[str]] = {}
    required = gate.get("required_deliverables", [])
    if not isinstance(required, list):
        required = []
    for identifier in required:
        if not isinstance(identifier, str) or identifier not in deliverables:
            continue
        row = deliverable_refinement_status(state, identifier)
        definition_state = row["definition_state"]
        if row["refinement_status"] in {"pending", "due"}:
            refinement_due.add(identifier)
        leaves = list(row["leaf_deliverables"])
        if row["unresolved_leaves"]:
            refinement_due.update(row["unresolved_leaves"])
        if definition_state in {"abstract", "placeholder"}:
            evaluated[identifier] = leaves
            if not leaves:
                refinement_due.add(identifier)
                incomplete.add(identifier)
            for leaf_id in leaves:
                if deliverables.get(leaf_id, {}).get("status") != "accepted":
                    incomplete.add(leaf_id)
        else:
            evaluated[identifier] = [identifier]
            if deliverables[identifier].get("status") != "accepted":
                incomplete.add(identifier)
    return {
        "ready": not incomplete and not refinement_due,
        "incomplete": sorted(incomplete),
        "refinement_due": sorted(refinement_due),
        "requirements": evaluated,
    }


def requirements_fingerprint(
    required_deliverables: Iterable[str], process: Mapping[str, Any]
) -> str:
    """Hash a Gate's sorted concrete leaf closure without lifecycle status."""

    deliverables = _deliverable_records(process)
    children = _refinement_children(deliverables)
    closure: list[dict[str, Any]] = []
    for identifier in sorted({str(item) for item in required_deliverables}):
        deliverable = deliverables.get(identifier)
        if deliverable is None:
            leaves: list[str] = []
        elif deliverable.get("definition_state", "concrete") == "concrete":
            leaves = [identifier]
        else:
            leaves, _ = _refinement_leaf_ids(identifier, deliverables, children)
        closure.append({"root": identifier, "concrete_leaves": sorted(leaves)})
    encoded = json.dumps(
        closure, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def claim_protocol_readiness(
    project_root: str | Path,
    state: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    verification_succeeded: bool = False,
) -> dict[str, Any]:
    """Return whether a new work iteration may be claimed right now.

    This is the shared protocol gate consumed by the CLI context, Claim
    command, and Dashboard. Recovery of an already in-progress Claim is a
    separate path and deliberately does not use this predicate.
    """

    project = state.get("project", {})
    workflow_step = (
        project.get("workflow_step") if isinstance(project, Mapping) else None
    )
    result = {
        "schema_version": "1.0",
        "eligible": False,
        "workflow_step": workflow_step,
        "reason_code": None,
        "required_action": None,
    }
    if workflow_step == "context":
        result["eligible"] = True
        return result
    if workflow_step != "verify":
        result["reason_code"] = "CLAIM_WORKFLOW_STEP_NOT_READY"
        result["required_action"] = (
            "refresh" if workflow_step == "refresh" else workflow_step
        )
        return result
    if verification_succeeded:
        result["eligible"] = True
        return result

    verification = runtime.get("last_verification")
    if (
        not isinstance(verification, Mapping)
        or verification.get("status") != "passed"
        or verification.get("state_revision") != state.get("revision")
    ):
        result["reason_code"] = "CLAIM_VERIFICATION_REQUIRED"
        result["required_action"] = "verify"
        return result

    from .project import verification_input_fingerprint

    actual_fingerprint = verification_input_fingerprint(
        project_root,
        state=dict(state),
        runtime=dict(runtime),
    )
    if verification.get("input_fingerprint") != actual_fingerprint:
        result["reason_code"] = "CLAIM_VERIFICATION_INPUTS_CHANGED"
        result["required_action"] = "refresh"
        return result
    result["eligible"] = True
    return result


def eligibility_fingerprint(value: Mapping[str, Any] | None) -> str:
    """Hash actionable eligibility facts without volatile derived counters.

    ``summary`` includes counts of ignored framework files. Rendering the
    Dashboard creates more such files, so hashing those counters would make a
    newly generated Dashboard stale immediately. Status, issues, governed
    paths, and per-Deliverable decisions remain covered.
    """

    document = deepcopy(dict(value)) if isinstance(value, Mapping) else {}
    document.pop("summary", None)
    encoded = json.dumps(
        document, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _diagnostic_failure(
    state: Mapping[str, Any],
    *,
    code: str,
    message: str,
    target_deliverable: str | None = None,
) -> dict[str, Any]:
    identifiers = [
        item.get("id")
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and (target_deliverable is None or item.get("id") == target_deliverable)
    ]
    issue = {
        "code": code,
        "severity": "error",
        "reason_code": code,
        "message": message,
    }
    return {
        "schema_version": ELIGIBILITY_SCHEMA_VERSION,
        "status": "failed",
        "eligible": False,
        "bindings_sha256": None,
        "baseline_id": None,
        "issues": [issue],
        "paths": {},
        "deliverables": {
            identifier: {
                "eligible": False,
                "binding_ready": False,
                "issue_codes": [code],
                "blockers": [deepcopy(issue)],
            }
            for identifier in identifiers
        },
        "summary": {
            "deliverables": len(identifiers),
            "eligible_deliverables": 0,
            "blocked_deliverables": len(identifiers),
            "errors": 1,
            "warnings": 0,
        },
    }


def _normalize_deliverable(
    value: Any,
    *,
    global_eligible: bool,
    default_issue_codes: list[str] | None = None,
    default_blockers: list[str] | None = None,
) -> dict[str, Any]:
    row = deepcopy(dict(value)) if isinstance(value, Mapping) else {}
    blockers = row.get("blockers")
    if not isinstance(blockers, list):
        blockers = []
    if not blockers and not global_eligible:
        blockers = list(default_blockers or [])
    issue_codes = row.get("issue_codes")
    if not isinstance(issue_codes, list):
        issue_codes = [
            item.get("code")
            for item in blockers
            if isinstance(item, Mapping) and isinstance(item.get("code"), str)
        ]
    if not issue_codes and not global_eligible:
        issue_codes = list(default_issue_codes or [])
    row["binding_ready"] = bool(row.get("binding_ready", global_eligible))
    row["eligible"] = bool(
        row.get("eligible", global_eligible and row["binding_ready"])
    )
    row["issue_codes"] = sorted(
        {str(item) for item in issue_codes if isinstance(item, str) and item}
    )
    row["blockers"] = blockers
    return row


def normalize_eligibility(
    value: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    target_deliverable: str | None = None,
) -> dict[str, Any]:
    """Return the complete deterministic shared eligibility contract."""

    result = deepcopy(dict(value))
    issues = result.get("issues")
    if not isinstance(issues, list):
        issues = []
    paths = result.get("paths")
    if not isinstance(paths, Mapping):
        paths = {}
    raw_deliverables = result.get("deliverables")
    if not isinstance(raw_deliverables, Mapping):
        raw_deliverables = {}

    status = result.get("status")
    if status not in _STATUSES:
        status = (
            "failed"
            if any(
                isinstance(item, Mapping) and item.get("severity") == "error"
                for item in issues
            )
            else "warning"
            if issues
            else "passed"
        )
    global_eligible = bool(result.get("eligible", status != "failed"))
    identifiers = [
        item.get("id")
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and (target_deliverable is None or item.get("id") == target_deliverable)
    ]
    global_error_issues = [
        item
        for item in issues
        if isinstance(item, Mapping)
        and item.get("severity") == "error"
        and not item.get("deliverable_id")
    ]
    default_issue_codes = sorted(
        {
            str(item["code"])
            for item in global_error_issues
            if isinstance(item.get("code"), str) and item.get("code")
        }
    )
    default_blockers = sorted(
        {
            str(item.get("reason_code") or item.get("code"))
            for item in global_error_issues
            if item.get("reason_code") or item.get("code")
        }
    )
    deliverables: dict[str, dict[str, Any]] = {}
    for identifier in identifiers:
        row = _normalize_deliverable(
            raw_deliverables.get(identifier),
            global_eligible=global_eligible,
            default_issue_codes=default_issue_codes,
            default_blockers=default_blockers,
        )
        refinement = deliverable_refinement_status(state, identifier)
        row.update(refinement)
        if not refinement["claimable"]:
            code = str(refinement["refinement_reason"] or "REFINEMENT_REQUIRED")
            row["eligible"] = False
            row["issue_codes"] = sorted({*row["issue_codes"], code})
            row["blockers"].append(
                {
                    "code": code,
                    "severity": "error",
                    "deliverable_id": identifier,
                    "reason_code": code,
                    "message": (
                        f"Deliverable {identifier!r} requires process refinement "
                        "before it can be claimed."
                    ),
                }
            )
        refinement_dependencies = unresolved_refinement_dependencies(
            state, identifier
        )
        if refinement_dependencies:
            code = "REFINEMENT_DEPENDENCY_REQUIRED"
            row["eligible"] = False
            row["issue_codes"] = sorted({*row["issue_codes"], code})
            row["blockers"].append(
                {
                    "code": code,
                    "severity": "error",
                    "deliverable_id": identifier,
                    "reason_code": code,
                    "dependencies": refinement_dependencies,
                    "message": (
                        f"Deliverable {identifier!r} depends on unresolved "
                        "refinement roots: " + ", ".join(refinement_dependencies)
                    ),
                }
            )
        deliverables[identifier] = row
    summary = result.get("summary")
    if not isinstance(summary, Mapping):
        summary = {}
    summary = deepcopy(dict(summary))
    summary["deliverables"] = len(deliverables)
    summary["eligible_deliverables"] = sum(
        1 for row in deliverables.values() if row["eligible"]
    )
    summary["blocked_deliverables"] = sum(
        1 for row in deliverables.values() if not row["eligible"]
    )
    summary.setdefault(
        "errors",
        sum(
            1
            for item in issues
            if isinstance(item, Mapping) and item.get("severity") == "error"
        ),
    )
    summary.setdefault(
        "warnings",
        sum(
            1
            for item in issues
            if isinstance(item, Mapping) and item.get("severity") == "warning"
        ),
    )
    return {
        "schema_version": str(
            result.get("schema_version") or ELIGIBILITY_SCHEMA_VERSION
        ),
        "status": status,
        "eligible": global_eligible,
        "bindings_sha256": result.get("bindings_sha256"),
        "baseline_id": result.get("baseline_id"),
        "issues": deepcopy(issues),
        "paths": deepcopy(dict(paths)),
        "deliverables": deliverables,
        "summary": summary,
    }


def binding_eligibility(
    project_root: str | Path,
    state: Mapping[str, Any],
    runtime: Mapping[str, Any] | None = None,
    bindings_path: str | Path | None = None,
    *,
    target_deliverable: str | None = None,
) -> dict[str, Any]:
    """Calculate binding readiness and convert load errors into diagnostics."""

    from .reconcile import ReconcileError, binding_readiness

    try:
        value = binding_readiness(
            project_root,
            state,
            runtime=runtime,
            bindings_path=bindings_path,
            target_deliverable=target_deliverable,
        )
    except (OSError, ReconcileError, ValueError) as exc:
        return normalize_eligibility(
            _diagnostic_failure(
                state,
                code="ARTIFACT_BINDINGS_INVALID",
                message=str(exc),
                target_deliverable=target_deliverable,
            ),
            state,
            target_deliverable=target_deliverable,
        )
    if not isinstance(value, Mapping):
        return normalize_eligibility(
            _diagnostic_failure(
                state,
                code="ARTIFACT_BINDINGS_INVALID",
                message="binding readiness must be an object",
                target_deliverable=target_deliverable,
            ),
            state,
            target_deliverable=target_deliverable,
        )
    return normalize_eligibility(
        value, state, target_deliverable=target_deliverable
    )


def deliverable_binding_status(
    eligibility: Mapping[str, Any], deliverable_id: str
) -> dict[str, Any]:
    """Return one normalized Deliverable eligibility row."""

    rows = eligibility.get("deliverables", {})
    if isinstance(rows, Mapping) and isinstance(rows.get(deliverable_id), Mapping):
        return deepcopy(dict(rows[deliverable_id]))
    issue = {
        "code": "BINDING_READINESS_UNAVAILABLE",
        "severity": "error",
        "deliverable_id": deliverable_id,
        "reason_code": "binding_readiness_unavailable",
    }
    return {
        "eligible": False,
        "binding_ready": False,
        "issue_codes": [issue["code"]],
        "blockers": [issue],
    }

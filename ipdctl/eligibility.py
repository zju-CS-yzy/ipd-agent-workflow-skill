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
from typing import Any, Mapping


ELIGIBILITY_SCHEMA_VERSION = "1.0"
_STATUSES = {"passed", "warning", "failed"}


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
    deliverables = {
        identifier: _normalize_deliverable(
            raw_deliverables.get(identifier),
            global_eligible=global_eligible,
            default_issue_codes=default_issue_codes,
            default_blockers=default_blockers,
        )
        for identifier in identifiers
    }
    summary = result.get("summary")
    if not isinstance(summary, Mapping):
        summary = {}
    summary = deepcopy(dict(summary))
    summary.setdefault("deliverables", len(deliverables))
    summary.setdefault(
        "eligible_deliverables",
        sum(1 for row in deliverables.values() if row["eligible"]),
    )
    summary.setdefault(
        "blocked_deliverables",
        sum(1 for row in deliverables.values() if not row["eligible"]),
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
        return _diagnostic_failure(
            state,
            code="ARTIFACT_BINDINGS_INVALID",
            message=str(exc),
            target_deliverable=target_deliverable,
        )
    if not isinstance(value, Mapping):
        return _diagnostic_failure(
            state,
            code="ARTIFACT_BINDINGS_INVALID",
            message="binding readiness must be an object",
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

"""Structural and semantic validation for IPD project state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .dependencies import find_cycle, unmet_dependencies
from .model import (
    CLAIM_STATUSES,
    DELIVERABLE_STATUSES,
    GATE_KINDS,
    GATE_STATUSES,
    PROJECT_PHASES,
    REVIEW_DECISIONS,
    REVIEWER_TYPES,
    SCHEMA_VERSION,
    TRACE_RELATIONS,
    WORKFLOW_STEPS,
)
from .traceability import collect_entity_ids, dangling_links

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True, order=True)
class ValidationIssue:
    """A stable path and message suitable for CLI output."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _required(
    value: dict[str, Any], fields: set[str], path: str, issues: list[ValidationIssue]
) -> None:
    for field in sorted(fields - value.keys()):
        issues.append(ValidationIssue(f"{path}.{field}", "required field is missing"))


def _reject_unknown(
    value: dict[str, Any], fields: set[str], path: str, issues: list[ValidationIssue]
) -> None:
    for field in sorted(value.keys() - fields):
        issues.append(ValidationIssue(f"{path}.{field}", "unknown field"))


def _non_empty_string(
    value: Any, path: str, issues: list[ValidationIssue]
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(path, "must be a non-empty string"))
        return None
    return value


def _enum_string(
    value: Any, allowed: tuple[str, ...], path: str, issues: list[ValidationIssue]
) -> str | None:
    parsed = _non_empty_string(value, path, issues)
    if parsed is not None and parsed not in allowed:
        issues.append(
            ValidationIssue(path, f"must be one of: {', '.join(allowed)}")
        )
        return None
    return parsed


def _identifier(value: Any, path: str, issues: list[ValidationIssue]) -> str | None:
    parsed = _non_empty_string(value, path, issues)
    if parsed is not None and not ID_PATTERN.fullmatch(parsed):
        issues.append(
            ValidationIssue(
                path,
                "must start with a lowercase letter or digit and contain only "
                "lowercase letters, digits, '.', '_' or '-'",
            )
        )
        return None
    return parsed


def _string_list(value: Any, path: str, issues: list[ValidationIssue]) -> list[str]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(path, "must be an array"))
        return []
    parsed: list[str] = []
    for index, item in enumerate(value):
        text = _non_empty_string(item, f"{path}[{index}]", issues)
        if text is not None:
            parsed.append(text)
    duplicates = sorted({item for item in parsed if parsed.count(item) > 1})
    if duplicates:
        issues.append(
            ValidationIssue(path, f"must not contain duplicates: {', '.join(duplicates)}")
        )
    return parsed


def _object_collection(
    value: Any, path: str, issues: list[ValidationIssue]
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(path, "must be an array"))
        return []
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            issues.append(ValidationIssue(f"{path}[{index}]", "must be an object"))
            continue
        parsed.append(item)
    return parsed


def validate_state(value: Any) -> list[ValidationIssue]:
    """Validate the state contract and non-negotiable workflow invariants."""

    issues: list[ValidationIssue] = []
    if not isinstance(value, dict):
        return [ValidationIssue("$", "must be an object")]

    top_fields = {
        "schema_version",
        "revision",
        "project",
        "claims",
        "deliverables",
        "gates",
        "traceability",
    }
    _required(value, top_fields, "$", issues)
    _reject_unknown(value, top_fields, "$", issues)

    if "schema_version" in value and value["schema_version"] != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "$.schema_version", f"must equal supported version {SCHEMA_VERSION!r}"
            )
        )
    if "revision" in value and (
        type(value["revision"]) is not int or value["revision"] < 0
    ):
        issues.append(
            ValidationIssue("$.revision", "must be a non-negative integer")
        )

    project = value.get("project")
    if not isinstance(project, dict):
        if "project" in value:
            issues.append(ValidationIssue("$.project", "must be an object"))
    else:
        project_fields = {"name", "phase", "workflow_step", "repository"}
        _required(project, {"name", "phase", "workflow_step"}, "$.project", issues)
        _reject_unknown(project, project_fields, "$.project", issues)
        if "name" in project:
            _non_empty_string(project["name"], "$.project.name", issues)
        if "phase" in project:
            _enum_string(project["phase"], PROJECT_PHASES, "$.project.phase", issues)
        if "workflow_step" in project:
            _enum_string(
                project["workflow_step"],
                WORKFLOW_STEPS,
                "$.project.workflow_step",
                issues,
            )
        if "repository" in project:
            _validate_repository(project["repository"], issues)

    claims = _object_collection(value.get("claims"), "$.claims", issues)
    for index, claim in enumerate(claims):
        path = f"$.claims[{index}]"
        fields = {"id", "statement", "status", "evidence"}
        _required(claim, fields, path, issues)
        _reject_unknown(claim, fields, path, issues)
        if "id" in claim:
            _identifier(claim["id"], f"{path}.id", issues)
        if "statement" in claim:
            _non_empty_string(claim["statement"], f"{path}.statement", issues)
        status = None
        if "status" in claim:
            status = _enum_string(
                claim["status"], CLAIM_STATUSES, f"{path}.status", issues
            )
        evidence = (
            _string_list(claim["evidence"], f"{path}.evidence", issues)
            if "evidence" in claim
            else []
        )
        if status == "supported" and not evidence:
            issues.append(
                ValidationIssue(
                    f"{path}.evidence", "a supported claim requires evidence"
                )
            )

    deliverables = _object_collection(
        value.get("deliverables"), "$.deliverables", issues
    )
    graph: dict[str, list[str]] = {}
    deliverable_status: dict[str, str] = {}
    deliverable_paths: dict[str, str] = {}
    for index, deliverable in enumerate(deliverables):
        path = f"$.deliverables[{index}]"
        fields = {"id", "title", "status", "depends_on", "evidence"}
        _required(deliverable, fields, path, issues)
        _reject_unknown(deliverable, fields, path, issues)
        identifier = (
            _identifier(deliverable["id"], f"{path}.id", issues)
            if "id" in deliverable
            else None
        )
        if "title" in deliverable:
            _non_empty_string(deliverable["title"], f"{path}.title", issues)
        status = (
            _enum_string(
                deliverable["status"],
                DELIVERABLE_STATUSES,
                f"{path}.status",
                issues,
            )
            if "status" in deliverable
            else None
        )
        dependencies = (
            _string_list(deliverable["depends_on"], f"{path}.depends_on", issues)
            if "depends_on" in deliverable
            else []
        )
        evidence = (
            _string_list(deliverable["evidence"], f"{path}.evidence", issues)
            if "evidence" in deliverable
            else []
        )
        if status == "accepted" and not evidence:
            issues.append(
                ValidationIssue(
                    f"{path}.evidence", "an accepted deliverable requires evidence"
                )
            )
        if identifier is not None:
            graph[identifier] = dependencies
            deliverable_paths[identifier] = path
            if status is not None:
                deliverable_status[identifier] = status

    for identifier, dependencies in graph.items():
        path = deliverable_paths[identifier]
        for dependency in dependencies:
            if dependency == identifier:
                issues.append(
                    ValidationIssue(f"{path}.depends_on", "must not depend on itself")
                )
            elif dependency not in graph:
                issues.append(
                    ValidationIssue(
                        f"{path}.depends_on",
                        f"references unknown deliverable {dependency!r}",
                    )
                )
        if deliverable_status.get(identifier) in {"ready_for_review", "accepted"}:
            unmet = unmet_dependencies(identifier, graph, deliverable_status)
            if unmet:
                issues.append(
                    ValidationIssue(
                        f"{path}.depends_on",
                        f"dependencies must be accepted first: {', '.join(unmet)}",
                    )
                )
    cycle = find_cycle(graph)
    if cycle:
        issues.append(
            ValidationIssue(
                "$.deliverables", f"dependency cycle detected: {' -> '.join(cycle)}"
            )
        )

    gates = _object_collection(value.get("gates"), "$.gates", issues)
    for index, gate in enumerate(gates):
        _validate_gate(gate, index, graph, deliverable_status, issues)

    links = _object_collection(value.get("traceability"), "$.traceability", issues)
    for index, link in enumerate(links):
        path = f"$.traceability[{index}]"
        fields = {"source", "target", "relation"}
        _required(link, fields, path, issues)
        _reject_unknown(link, fields, path, issues)
        source = (
            _identifier(link["source"], f"{path}.source", issues)
            if "source" in link
            else None
        )
        target = (
            _identifier(link["target"], f"{path}.target", issues)
            if "target" in link
            else None
        )
        if source is not None and target == source:
            issues.append(ValidationIssue(path, "source and target must differ"))
        if "relation" in link:
            _enum_string(
                link["relation"], TRACE_RELATIONS, f"{path}.relation", issues
            )

    _, duplicates = collect_entity_ids(value)
    for identifier in sorted(duplicates):
        issues.append(
            ValidationIssue("$", f"entity id is not globally unique: {identifier!r}")
        )
    for index, field, identifier in dangling_links(value):
        issues.append(
            ValidationIssue(
                f"$.traceability[{index}].{field}",
                f"references unknown entity {identifier!r}",
            )
        )

    return sorted(set(issues))


def _validate_repository(value: Any, issues: list[ValidationIssue]) -> None:
    path = "$.project.repository"
    if not isinstance(value, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return
    fields = {"kind", "revision", "dirty"}
    _required(value, {"kind"}, path, issues)
    _reject_unknown(value, fields, path, issues)
    if "kind" in value:
        _enum_string(value["kind"], ("none", "git", "svn"), f"{path}.kind", issues)
    if "revision" in value and value["revision"] is not None:
        _non_empty_string(value["revision"], f"{path}.revision", issues)
    if "dirty" in value and value["dirty"] is not None and type(value["dirty"]) is not bool:
        issues.append(ValidationIssue(f"{path}.dirty", "must be a boolean or null"))


def _validate_gate(
    gate: dict[str, Any],
    index: int,
    graph: dict[str, list[str]],
    deliverable_status: dict[str, str],
    issues: list[ValidationIssue],
) -> None:
    path = f"$.gates[{index}]"
    fields = {"id", "title", "kind", "status", "required_deliverables", "reviews"}
    _required(gate, fields, path, issues)
    _reject_unknown(gate, fields, path, issues)
    if "id" in gate:
        _identifier(gate["id"], f"{path}.id", issues)
    if "title" in gate:
        _non_empty_string(gate["title"], f"{path}.title", issues)
    if "kind" in gate:
        _enum_string(gate["kind"], GATE_KINDS, f"{path}.kind", issues)
    status = (
        _enum_string(gate["status"], GATE_STATUSES, f"{path}.status", issues)
        if "status" in gate
        else None
    )
    required_deliverables = (
        _string_list(
            gate["required_deliverables"], f"{path}.required_deliverables", issues
        )
        if "required_deliverables" in gate
        else []
    )
    for identifier in required_deliverables:
        if identifier not in graph:
            issues.append(
                ValidationIssue(
                    f"{path}.required_deliverables",
                    f"references unknown deliverable {identifier!r}",
                )
            )

    reviews = _object_collection(gate.get("reviews"), f"{path}.reviews", issues)
    valid_reviews: list[dict[str, Any]] = []
    for review_index, review in enumerate(reviews):
        review_path = f"{path}.reviews[{review_index}]"
        review_fields = {
            "reviewer",
            "reviewer_type",
            "authorized",
            "decision",
            "evidence",
        }
        _required(review, review_fields, review_path, issues)
        _reject_unknown(review, review_fields, review_path, issues)
        if "reviewer" in review:
            _non_empty_string(review["reviewer"], f"{review_path}.reviewer", issues)
        if "reviewer_type" in review:
            _enum_string(
                review["reviewer_type"],
                REVIEWER_TYPES,
                f"{review_path}.reviewer_type",
                issues,
            )
        if "authorized" in review and type(review["authorized"]) is not bool:
            issues.append(
                ValidationIssue(f"{review_path}.authorized", "must be a boolean")
            )
        if "decision" in review:
            _enum_string(
                review["decision"],
                REVIEW_DECISIONS,
                f"{review_path}.decision",
                issues,
            )
        if "evidence" in review:
            _non_empty_string(review["evidence"], f"{review_path}.evidence", issues)
        valid_reviews.append(review)

    if status in {"ready", "approved"}:
        incomplete = [
            identifier
            for identifier in required_deliverables
            if deliverable_status.get(identifier) != "accepted"
        ]
        if incomplete:
            issues.append(
                ValidationIssue(
                    f"{path}.required_deliverables",
                    f"gate prerequisites are not accepted: {', '.join(incomplete)}",
                )
            )

    if status == "approved":
        human_approvals = [
            review
            for review in valid_reviews
            if review.get("reviewer_type") == "human"
            and review.get("authorized") is True
            and review.get("decision") == "approve"
        ]
        human_rejections = [
            review
            for review in valid_reviews
            if review.get("reviewer_type") == "human"
            and review.get("authorized") is True
            and review.get("decision") == "reject"
        ]
        if not human_approvals:
            issues.append(
                ValidationIssue(
                    f"{path}.reviews",
                    "approved TR/DCP gate requires an authorized human approval",
                )
            )
        if human_rejections:
            issues.append(
                ValidationIssue(
                    f"{path}.reviews",
                    "approved gate conflicts with an authorized human rejection",
                )
            )

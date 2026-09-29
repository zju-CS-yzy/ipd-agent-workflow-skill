"""Structural and semantic validation for the v0.2 IPD state contract."""

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
    TASK_TYPES,
    TRACE_RELATIONS,
    WORKFLOW_STEPS,
)
from .traceability import collect_entity_ids, dangling_links

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True, order=True)
class ValidationIssue:
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


def _nullable_string(value: Any, path: str, issues: list[ValidationIssue]) -> None:
    if value is not None:
        _non_empty_string(value, path, issues)


def _enum_string(
    value: Any, allowed: tuple[str, ...], path: str, issues: list[ValidationIssue]
) -> str | None:
    parsed = _non_empty_string(value, path, issues)
    if parsed is not None and parsed not in allowed:
        issues.append(ValidationIssue(path, f"must be one of: {', '.join(allowed)}"))
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
        else:
            parsed.append(item)
    return parsed


def _validate_review(
    review: dict[str, Any], path: str, issues: list[ValidationIssue]
) -> None:
    fields = {"reviewer", "reviewer_type", "authorized", "decision", "evidence"}
    _required(review, fields, path, issues)
    _reject_unknown(review, fields, path, issues)
    if "reviewer" in review:
        _non_empty_string(review["reviewer"], f"{path}.reviewer", issues)
    if "reviewer_type" in review:
        _enum_string(review["reviewer_type"], REVIEWER_TYPES, f"{path}.reviewer_type", issues)
    if "authorized" in review and type(review["authorized"]) is not bool:
        issues.append(ValidationIssue(f"{path}.authorized", "must be a boolean"))
    if "decision" in review:
        _enum_string(review["decision"], REVIEW_DECISIONS, f"{path}.decision", issues)
    if "evidence" in review:
        _non_empty_string(review["evidence"], f"{path}.evidence", issues)


def _authorized_reviews(
    reviews: list[dict[str, Any]], decision: str
) -> list[dict[str, Any]]:
    return [
        review
        for review in reviews
        if review.get("reviewer_type") == "human"
        and review.get("authorized") is True
        and review.get("decision") == decision
    ]


def validate_state(value: Any) -> list[ValidationIssue]:
    """Validate both the v0.2 contract and the non-negotiable IPD invariants."""

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
    version = value.get("schema_version")
    if version not in {"1.0", SCHEMA_VERSION}:
        issues.append(
            ValidationIssue(
                "$.schema_version", f"must equal '1.0' or supported version {SCHEMA_VERSION!r}"
            )
        )
    is_v2 = version == SCHEMA_VERSION
    if "revision" in value and (type(value["revision"]) is not int or value["revision"] < 0):
        issues.append(ValidationIssue("$.revision", "must be a non-negative integer"))

    project = value.get("project")
    if not isinstance(project, dict):
        if "project" in value:
            issues.append(ValidationIssue("$.project", "must be an object"))
    else:
        fields = {
            "name",
            "task_types",
            "phase",
            "workflow_step",
            "current_tr",
            "current_dcp",
            "current_gate",
            "repository",
        }
        required = {"name", "phase", "workflow_step"}
        if is_v2:
            required |= {"task_types", "current_tr", "current_dcp", "current_gate"}
        _required(project, required, "$.project", issues)
        _reject_unknown(project, fields, "$.project", issues)
        if "name" in project:
            _non_empty_string(project["name"], "$.project.name", issues)
        if "task_types" in project:
            task_types = _string_list(project["task_types"], "$.project.task_types", issues)
            for index, task_type in enumerate(task_types):
                if task_type not in TASK_TYPES:
                    issues.append(
                        ValidationIssue(
                            f"$.project.task_types[{index}]",
                            f"must be one of: {', '.join(TASK_TYPES)}",
                        )
                    )
        if "phase" in project:
            _enum_string(project["phase"], PROJECT_PHASES, "$.project.phase", issues)
        if "workflow_step" in project:
            _enum_string(
                project["workflow_step"], WORKFLOW_STEPS, "$.project.workflow_step", issues
            )
        for field in ("current_tr", "current_dcp", "current_gate"):
            if field in project:
                _nullable_string(project[field], f"$.project.{field}", issues)
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
        status = (
            _enum_string(claim["status"], CLAIM_STATUSES, f"{path}.status", issues)
            if "status" in claim
            else None
        )
        evidence = _string_list(claim.get("evidence"), f"{path}.evidence", issues)
        if status == "supported" and not evidence:
            issues.append(ValidationIssue(f"{path}.evidence", "a supported claim requires evidence"))

    deliverables = _object_collection(value.get("deliverables"), "$.deliverables", issues)
    graph: dict[str, list[str]] = {}
    deliverable_status: dict[str, str] = {}
    deliverable_paths: dict[str, str] = {}
    superseded: list[tuple[str, str, str]] = []
    legacy_statuses = ("planned", "in_progress", "blocked", "ready_for_review", "accepted")
    for index, deliverable in enumerate(deliverables):
        path = f"$.deliverables[{index}]"
        fields = {
            "id",
            "title",
            "status",
            "phase",
            "activity_id",
            "review_required",
            "depends_on",
            "evidence",
            "reviews",
            "blocked_reason",
            "replacement",
        }
        required = {"id", "title", "status", "depends_on", "evidence"}
        if is_v2:
            required |= {"review_required", "reviews"}
        _required(deliverable, required, path, issues)
        _reject_unknown(deliverable, fields, path, issues)
        identifier = (
            _identifier(deliverable["id"], f"{path}.id", issues)
            if "id" in deliverable
            else None
        )
        if "title" in deliverable:
            _non_empty_string(deliverable["title"], f"{path}.title", issues)
        allowed_statuses = DELIVERABLE_STATUSES if is_v2 else legacy_statuses
        status = (
            _enum_string(deliverable["status"], allowed_statuses, f"{path}.status", issues)
            if "status" in deliverable
            else None
        )
        for field in ("phase", "activity_id"):
            if field in deliverable:
                _nullable_string(deliverable[field], f"{path}.{field}", issues)
        if "review_required" in deliverable and type(deliverable["review_required"]) is not bool:
            issues.append(ValidationIssue(f"{path}.review_required", "must be a boolean"))
        dependencies = _string_list(deliverable.get("depends_on"), f"{path}.depends_on", issues)
        evidence = _string_list(deliverable.get("evidence"), f"{path}.evidence", issues)
        review_values = deliverable.get("reviews", [])
        reviews = _object_collection(review_values, f"{path}.reviews", issues)
        for review_index, review in enumerate(reviews):
            _validate_review(review, f"{path}.reviews[{review_index}]", issues)
        if "blocked_reason" in deliverable:
            _nullable_string(deliverable["blocked_reason"], f"{path}.blocked_reason", issues)
        replacement = deliverable.get("replacement")
        if replacement is not None:
            replacement = _identifier(replacement, f"{path}.replacement", issues)

        if status == "accepted":
            if not evidence:
                issues.append(ValidationIssue(f"{path}.evidence", "an accepted deliverable requires evidence"))
            if not _authorized_reviews(reviews, "approve"):
                issues.append(
                    ValidationIssue(
                        f"{path}.reviews",
                        "an accepted deliverable requires an authorized human approval review",
                    )
                )
            if _authorized_reviews(reviews, "reject"):
                issues.append(
                    ValidationIssue(
                        f"{path}.reviews",
                        "accepted deliverable conflicts with an authorized human rejection",
                    )
                )
        if status == "rejected" and not _authorized_reviews(reviews, "reject"):
            issues.append(
                ValidationIssue(
                    f"{path}.reviews",
                    "a rejected deliverable requires an authorized human rejection review",
                )
            )
        if status == "superseded":
            if not replacement:
                issues.append(
                    ValidationIssue(
                        f"{path}.replacement", "a superseded deliverable requires a replacement"
                    )
                )
            elif identifier:
                superseded.append((identifier, replacement, path))

        if identifier is not None:
            graph[identifier] = dependencies
            deliverable_paths[identifier] = path
            if status is not None:
                deliverable_status[identifier] = status

    for identifier, dependencies in graph.items():
        path = deliverable_paths[identifier]
        for dependency in dependencies:
            if dependency == identifier:
                issues.append(ValidationIssue(f"{path}.depends_on", "must not depend on itself"))
            elif dependency not in graph:
                issues.append(
                    ValidationIssue(
                        f"{path}.depends_on", f"references unknown deliverable {dependency!r}"
                    )
                )
        closed_statuses = {"ready_for_review", "accepted"}
        if is_v2:
            closed_statuses |= {"in_review"}
        if deliverable_status.get(identifier) in closed_statuses:
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
            ValidationIssue("$.deliverables", f"dependency cycle detected: {' -> '.join(cycle)}")
        )

    gates = _object_collection(value.get("gates"), "$.gates", issues)
    for index, gate in enumerate(gates):
        _validate_gate(gate, index, graph, deliverable_status, issues)

    links = _object_collection(value.get("traceability"), "$.traceability", issues)
    normalized_links: set[tuple[str, str, str]] = set()
    for index, link in enumerate(links):
        path = f"$.traceability[{index}]"
        fields = {"source", "target", "relation"}
        _required(link, fields, path, issues)
        _reject_unknown(link, fields, path, issues)
        source = _identifier(link.get("source"), f"{path}.source", issues)
        target = _identifier(link.get("target"), f"{path}.target", issues)
        relation = (
            _enum_string(link["relation"], TRACE_RELATIONS, f"{path}.relation", issues)
            if "relation" in link
            else None
        )
        if source is not None and target == source:
            issues.append(ValidationIssue(path, "source and target must differ"))
        if source and target and relation:
            normalized_links.add((source, target, relation))

    _, duplicates = collect_entity_ids(value)
    for identifier in sorted(duplicates):
        issues.append(ValidationIssue("$", f"entity id is not globally unique: {identifier!r}"))
    for index, field, identifier in dangling_links(value):
        issues.append(
            ValidationIssue(
                f"$.traceability[{index}].{field}",
                f"references unknown entity {identifier!r}",
            )
        )
    for identifier, replacement, path in superseded:
        if replacement not in graph:
            issues.append(
                ValidationIssue(
                    f"{path}.replacement", f"references unknown replacement {replacement!r}"
                )
            )
        elif not (
            (replacement, identifier, "supersedes") in normalized_links
            or (identifier, replacement, "supersedes") in normalized_links
        ):
            issues.append(
                ValidationIssue(
                    "$.traceability",
                    f"superseded deliverable {identifier!r} requires a supersedes trace link",
                )
            )
    return sorted(set(issues))


def _validate_repository(value: Any, issues: list[ValidationIssue]) -> None:
    path = "$.project.repository"
    if not isinstance(value, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return
    fields = {"kind", "root", "branch", "revision", "dirty", "remote"}
    _required(value, {"kind"}, path, issues)
    _reject_unknown(value, fields, path, issues)
    if "kind" in value:
        _enum_string(value["kind"], ("none", "git", "svn"), f"{path}.kind", issues)
    for field in ("root", "branch", "revision", "remote"):
        if field in value:
            _nullable_string(value[field], f"{path}.{field}", issues)
    if "dirty" in value and value["dirty"] is not None and type(value["dirty"]) is not bool:
        issues.append(ValidationIssue(f"{path}.dirty", "must be a boolean or null"))
    remote = value.get("remote")
    if isinstance(remote, str) and "://" in remote:
        authority = remote.split("://", 1)[1].split("/", 1)[0]
        if "@" in authority:
            issues.append(ValidationIssue(f"{path}.remote", "must not contain embedded credentials"))


def _validate_gate(
    gate: dict[str, Any],
    index: int,
    graph: dict[str, list[str]],
    deliverable_status: dict[str, str],
    issues: list[ValidationIssue],
) -> None:
    path = f"$.gates[{index}]"
    fields = {
        "id",
        "title",
        "kind",
        "status",
        "phase",
        "required_deliverables",
        "reviews",
        "evidence",
        "blockers",
        "approval",
    }
    required = {"id", "title", "kind", "status", "required_deliverables", "reviews"}
    _required(gate, required, path, issues)
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
    if "phase" in gate:
        _nullable_string(gate["phase"], f"{path}.phase", issues)
    required_deliverables = _string_list(
        gate.get("required_deliverables"), f"{path}.required_deliverables", issues
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
    for review_index, review in enumerate(reviews):
        _validate_review(review, f"{path}.reviews[{review_index}]", issues)
    for field in ("evidence", "blockers"):
        if field in gate:
            _string_list(gate[field], f"{path}.{field}", issues)
    if "approval" in gate:
        _nullable_string(gate["approval"], f"{path}.approval", issues)

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
        if not _authorized_reviews(reviews, "approve"):
            issues.append(
                ValidationIssue(
                    f"{path}.reviews",
                    "approved TR/DCP gate requires an authorized human approval",
                )
            )
        if _authorized_reviews(reviews, "reject"):
            issues.append(
                ValidationIssue(
                    f"{path}.reviews",
                    "approved gate conflicts with an authorized human rejection",
                )
            )

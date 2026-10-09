"""Structural and semantic validation for the v0.2 IPD state contract."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .dependencies import find_cycle, unmet_dependencies
from .eligibility import gate_requirement_readiness
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
    review: dict[str, Any],
    path: str,
    issues: list[ValidationIssue],
    *,
    allow_gate_epoch: bool = False,
) -> None:
    required = {"reviewer", "reviewer_type", "authorized", "decision", "evidence"}
    fields = set(required)
    if allow_gate_epoch:
        fields.add("gate_epoch")
    _required(review, required, path, issues)
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
    if "gate_epoch" in review and (
        type(review["gate_epoch"]) is not int or review["gate_epoch"] < 0
    ):
        issues.append(
            ValidationIssue(f"{path}.gate_epoch", "must be a non-negative integer")
        )


def _validate_refinement_trigger(
    value: Any, path: str, issues: list[ValidationIssue]
) -> list[tuple[str, str, str]]:
    """Validate trigger syntax and return conditions for cross-reference checks."""

    if not isinstance(value, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return []
    _required(value, {"all_of"}, path, issues)
    _reject_unknown(value, {"all_of"}, path, issues)
    conditions = _object_collection(value.get("all_of"), f"{path}.all_of", issues)
    if isinstance(value.get("all_of"), list) and not value["all_of"]:
        issues.append(ValidationIssue(f"{path}.all_of", "must not be empty"))
    parsed: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, condition in enumerate(conditions):
        condition_path = f"{path}.all_of[{index}]"
        _required(condition, {"subject", "condition"}, condition_path, issues)
        _reject_unknown(condition, {"subject", "condition"}, condition_path, issues)
        subject = _identifier(
            condition.get("subject"), f"{condition_path}.subject", issues
        )
        expected = (
            _enum_string(
                condition["condition"],
                ("accepted", "approved"),
                f"{condition_path}.condition",
                issues,
            )
            if "condition" in condition
            else None
        )
        if subject and expected:
            key = (subject, expected)
            if key in seen:
                issues.append(ValidationIssue(condition_path, "duplicates a condition"))
            seen.add(key)
            parsed.append((subject, expected, condition_path))
    return parsed


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


def _latest_authorized_human_decision(
    reviews: list[dict[str, Any]],
) -> str | None:
    """Return the latest governed decision while preserving earlier review history."""

    for review in reversed(reviews):
        if (
            review.get("reviewer_type") == "human"
            and review.get("authorized") is True
            and review.get("decision") in REVIEW_DECISIONS
        ):
            return review["decision"]
    return None


def validate_state(value: Any) -> list[ValidationIssue]:
    """Validate both the v0.2 contract and the non-negotiable IPD invariants."""

    issues: list[ValidationIssue] = []
    workflow_step: str | None = None
    current_iteration_subject: str | None = None
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
            "current_iteration_subject",
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
            workflow_step = _enum_string(
                project["workflow_step"], WORKFLOW_STEPS, "$.project.workflow_step", issues
            )
        if "current_iteration_subject" in project:
            raw_subject = project["current_iteration_subject"]
            if raw_subject is not None:
                current_iteration_subject = _identifier(
                    raw_subject,
                    "$.project.current_iteration_subject",
                    issues,
                )
        if workflow_step == "review":
            if current_iteration_subject is None:
                issues.append(
                    ValidationIssue(
                        "$.project.current_iteration_subject",
                        "must identify the globally locked review subject when workflow_step is 'review'",
                    )
                )
        elif current_iteration_subject is not None:
            issues.append(
                ValidationIssue(
                    "$.project.current_iteration_subject",
                    "must be null outside workflow_step 'review'",
                )
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
    deliverable_phases: dict[str, Any] = {}
    refinement_parents: dict[str, str] = {}
    refinement_triggers: list[
        tuple[str, Any, Any, str, str, str]
    ] = []
    superseded: list[tuple[str, tuple[str, ...], str]] = []
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
            "replacements",
            "provenance",
            "maturity",
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
            "requires_artifact_owner",
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
        raw_replacements = deliverable.get("replacements", [])
        replacements = _string_list(
            raw_replacements, f"{path}.replacements", issues
        ) if "replacements" in deliverable else []
        normalized_replacements: list[str] = []
        for replacement_index, candidate in enumerate(replacements):
            valid = _identifier(
                candidate,
                f"{path}.replacements[{replacement_index}]",
                issues,
            )
            if valid is not None:
                normalized_replacements.append(valid)
        if "replacements" in deliverable and not normalized_replacements:
            issues.append(
                ValidationIssue(
                    f"{path}.replacements", "must contain at least one replacement"
                )
            )
        if replacement is not None and normalized_replacements:
            if normalized_replacements[0] != replacement:
                issues.append(
                    ValidationIssue(
                        f"{path}.replacements",
                        "the first replacement must equal the legacy replacement field",
                    )
                )
        provenance = deliverable.get("provenance")
        if provenance is not None:
            provenance_path = f"{path}.provenance"
            if not isinstance(provenance, dict):
                issues.append(ValidationIssue(provenance_path, "must be an object"))
            else:
                _required(provenance, {"layer", "source_id"}, provenance_path, issues)
                _reject_unknown(
                    provenance, {"layer", "source_id"}, provenance_path, issues
                )
                if "layer" in provenance:
                    _enum_string(
                        provenance["layer"],
                        ("core", "task_type", "capability", "project"),
                        f"{provenance_path}.layer",
                        issues,
                    )
                if "source_id" in provenance:
                    _identifier(
                        provenance["source_id"],
                        f"{provenance_path}.source_id",
                        issues,
                    )
        if "maturity" in deliverable:
            _enum_string(
                deliverable["maturity"],
                ("defined", "selected", "integrated", "verified", "released", "monitored"),
                f"{path}.maturity",
                issues,
            )
        if "definition_state" in deliverable:
            _enum_string(
                deliverable["definition_state"],
                ("concrete", "abstract", "placeholder"),
                f"{path}.definition_state",
                issues,
            )
        if "refinement_required" in deliverable and type(
            deliverable["refinement_required"]
        ) is not bool:
            issues.append(
                ValidationIssue(f"{path}.refinement_required", "must be a boolean")
            )
        if (
            deliverable.get("definition_state") == "placeholder"
            and deliverable.get("refinement_required") is not True
        ):
            issues.append(
                ValidationIssue(
                    f"{path}.refinement_required",
                    "must be true when definition_state is placeholder",
                )
            )
        if (
            deliverable.get("refinement_required") is True
            and "refinement_trigger" not in deliverable
        ):
            issues.append(
                ValidationIssue(
                    f"{path}.refinement_trigger",
                    "required when refinement_required is true",
                )
            )
        if "requires_artifact_owner" in deliverable and type(
            deliverable["requires_artifact_owner"]
        ) is not bool:
            issues.append(
                ValidationIssue(
                    f"{path}.requires_artifact_owner", "must be a boolean"
                )
            )
        if "refines" in deliverable:
            parent = _identifier(deliverable["refines"], f"{path}.refines", issues)
            if parent is not None and identifier is not None:
                refinement_parents[identifier] = parent
        if "refinement_trigger" in deliverable:
            conditions = _validate_refinement_trigger(
                deliverable["refinement_trigger"],
                f"{path}.refinement_trigger",
                issues,
            )
            if identifier is not None:
                refinement_triggers.extend(
                    (
                        identifier,
                        deliverable.get("phase"),
                        deliverable.get("definition_state"),
                        subject,
                        expected,
                        condition_path,
                    )
                    for subject, expected, condition_path in conditions
                )

        if status == "accepted":
            if not evidence:
                issues.append(ValidationIssue(f"{path}.evidence", "an accepted deliverable requires evidence"))
            if _latest_authorized_human_decision(reviews) != "approve":
                issues.append(
                    ValidationIssue(
                        f"{path}.reviews",
                        "an accepted deliverable requires an authorized human approval review",
                    )
                )
        if status == "rejected" and _latest_authorized_human_decision(reviews) != "reject":
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
                effective_replacements = tuple(normalized_replacements or [replacement])
                superseded.append((identifier, effective_replacements, path))

        if identifier is not None:
            graph[identifier] = dependencies
            deliverable_paths[identifier] = path
            deliverable_phases[identifier] = deliverable.get("phase")
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

    refinement_graph = {identifier: [] for identifier in graph}
    for identifier, parent in refinement_parents.items():
        path = deliverable_paths[identifier]
        if parent == identifier:
            issues.append(ValidationIssue(f"{path}.refines", "must not refine itself"))
        elif parent not in graph:
            issues.append(
                ValidationIssue(
                    f"{path}.refines",
                    f"references unknown deliverable {parent!r}",
                )
            )
        else:
            refinement_graph[identifier] = [parent]
            if deliverable_phases.get(identifier) != deliverable_phases.get(parent):
                issues.append(
                    ValidationIssue(
                        f"{path}.refines",
                        f"must refine a deliverable in the same phase as {identifier!r}",
                    )
                )
    refinement_cycle = find_cycle(refinement_graph)
    if refinement_cycle:
        issues.append(
            ValidationIssue(
                "$.deliverables",
                f"refinement cycle detected: {' -> '.join(refinement_cycle)}",
            )
        )

    gates = _object_collection(value.get("gates"), "$.gates", issues)
    for index, gate in enumerate(gates):
        _validate_gate(gate, index, value, graph, issues)

    gate_by_id = {
        gate.get("id"): gate
        for gate in gates
        if isinstance(gate.get("id"), str) and gate.get("id")
    }
    gate_ids = set(gate_by_id)
    if (
        workflow_step == "review"
        and current_iteration_subject is not None
        and current_iteration_subject not in graph
        and current_iteration_subject not in gate_ids
    ):
        issues.append(
            ValidationIssue(
                "$.project.current_iteration_subject",
                f"references unknown Deliverable or Gate {current_iteration_subject!r}",
            )
        )
    phase_sequence = {phase: index for index, phase in enumerate(PROJECT_PHASES)}

    def depends_on_subject(start: str, target: str) -> bool:
        pending = list(graph.get(start, []))
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(graph.get(current, []))
        return False

    for owner, owner_phase, definition_state, subject, expected, condition_path in refinement_triggers:
        if expected == "accepted" and subject not in graph:
            message = (
                "condition 'accepted' must reference a Deliverable"
                if subject in gate_ids
                else f"references unknown Deliverable {subject!r}"
            )
            issues.append(ValidationIssue(condition_path, message))
        elif expected == "approved" and subject not in gate_ids:
            message = (
                "condition 'approved' must reference a Gate"
                if subject in graph
                else f"references unknown Gate {subject!r}"
            )
            issues.append(ValidationIssue(condition_path, message))
        elif expected == "accepted":
            if phase_sequence.get(deliverable_phases.get(subject), -1) > phase_sequence.get(
                owner_phase, -1
            ):
                issues.append(
                    ValidationIssue(
                        condition_path,
                        f"later-phase Deliverable {subject!r} cannot trigger refinement",
                    )
                )
            if definition_state == "placeholder" and (
                subject == owner or depends_on_subject(subject, owner)
            ):
                issues.append(
                    ValidationIssue(
                        condition_path,
                        f"placeholder refinement root {owner!r} cannot be required to complete before its trigger",
                    )
                )
        elif expected == "approved":
            gate_phase = gate_by_id[subject].get("phase")
            if phase_sequence.get(gate_phase, -1) >= phase_sequence.get(owner_phase, -1):
                issues.append(
                    ValidationIssue(
                        condition_path,
                        f"Gate {subject!r} must belong to a phase before refinement root {owner!r}",
                    )
                )

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
            _enum_string(
                link["relation"],
                TRACE_RELATIONS + (() if "refines" in TRACE_RELATIONS else ("refines",)),
                f"{path}.relation",
                issues,
            )
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
    for identifier, replacements, path in superseded:
        for replacement in replacements:
            if replacement not in graph:
                issues.append(
                    ValidationIssue(
                        f"{path}.replacements",
                        f"references unknown replacement {replacement!r}",
                    )
                )
            elif not (
                (replacement, identifier, "supersedes") in normalized_links
                or (identifier, replacement, "supersedes") in normalized_links
            ):
                issues.append(
                    ValidationIssue(
                        "$.traceability",
                        f"superseded deliverable {identifier!r} requires a supersedes "
                        f"trace link to {replacement!r}",
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
    state: dict[str, Any],
    graph: dict[str, list[str]],
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
        "requirements_fingerprint",
        "review_epoch",
        "stale",
        "stale_reason",
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
        _validate_review(
            review,
            f"{path}.reviews[{review_index}]",
            issues,
            allow_gate_epoch=True,
        )
    for field in ("evidence", "blockers"):
        if field in gate:
            _string_list(gate[field], f"{path}.{field}", issues)
    if "approval" in gate:
        _nullable_string(gate["approval"], f"{path}.approval", issues)
    if "requirements_fingerprint" in gate:
        _non_empty_string(
            gate["requirements_fingerprint"],
            f"{path}.requirements_fingerprint",
            issues,
        )
    review_epoch = gate.get("review_epoch", 0)
    if "review_epoch" in gate and (
        type(review_epoch) is not int or review_epoch < 0
    ):
        issues.append(
            ValidationIssue(f"{path}.review_epoch", "must be a non-negative integer")
        )
        review_epoch = 0
    if "stale" in gate and type(gate["stale"]) is not bool:
        issues.append(ValidationIssue(f"{path}.stale", "must be a boolean"))
    if "stale_reason" in gate:
        _nullable_string(gate["stale_reason"], f"{path}.stale_reason", issues)
    if gate.get("stale") is True and not gate.get("stale_reason"):
        issues.append(
            ValidationIssue(
                f"{path}.stale_reason", "is required when the gate is stale"
            )
        )

    if status in {"ready", "approved"}:
        readiness = gate_requirement_readiness(state, gate)
        if readiness["refinement_due"]:
            issues.append(
                ValidationIssue(
                    f"{path}.required_deliverables",
                    "REFINEMENT_REQUIRED: unresolved refinement requirements: "
                    + ", ".join(readiness["refinement_due"]),
                )
            )
        if readiness["incomplete"]:
            issues.append(
                ValidationIssue(
                    f"{path}.required_deliverables",
                    "gate prerequisites are not accepted: "
                    + ", ".join(readiness["incomplete"]),
                )
            )
    if status == "approved":
        if gate.get("stale") is True:
            issues.append(
                ValidationIssue(
                    f"{path}.stale", "an approved gate must not be stale"
                )
            )
        current_reviews = [
            review
            for review in reviews
            if review.get("gate_epoch", 0) == review_epoch
        ]
        if _latest_authorized_human_decision(current_reviews) != "approve":
            issues.append(
                ValidationIssue(
                    f"{path}.reviews",
                    "approved TR/DCP gate requires an authorized human approval "
                    f"in review epoch {review_epoch}",
                )
            )

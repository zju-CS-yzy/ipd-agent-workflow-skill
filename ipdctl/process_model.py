"""Domain-neutral IPD process model and task-type policy loading."""

from __future__ import annotations

import re
from copy import deepcopy
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

from .model import TASK_TYPES, TRACE_RELATIONS
from .refinement import DEFINITION_STATES, validate_refinement_trigger
from .yamlio import YamlError, load_yaml

PROCESS_SCHEMA_VERSION = "2.0"
LEGACY_PROCESS_SCHEMA_VERSION = "1.0"
SUPPORTED_PROCESS_SCHEMA_VERSIONS = (
    LEGACY_PROCESS_SCHEMA_VERSION,
    PROCESS_SCHEMA_VERSION,
)
TASK_POLICY_SCHEMA_VERSION = "1.0"
CAPABILITY_POLICY_SCHEMA_VERSION = "1.0"
CAPABILITY_PATTERNS = ("sourced_component_integration",)


class ProcessModelError(ValueError):
    """Raised when a task type or process policy violates the model contract."""


def _refinement_node_issues(value: dict[str, Any], path: str) -> list[str]:
    issues: list[str] = []
    if "definition_state" in value and value.get("definition_state") not in DEFINITION_STATES:
        issues.append(
            f"{path}.definition_state: must be one of: "
            + ", ".join(DEFINITION_STATES)
        )
    if "refinement_required" in value and type(value.get("refinement_required")) is not bool:
        issues.append(f"{path}.refinement_required: must be a boolean")
    if "refinement_trigger" in value:
        issues.extend(
            validate_refinement_trigger(
                value.get("refinement_trigger"), f"{path}.refinement_trigger"
            )
        )
    refines = value.get("refines")
    if "refines" in value and (
        not isinstance(refines, str) or not refines.strip()
    ):
        issues.append(f"{path}.refines: must be a non-empty string")
    return issues


_TYPE_SEPARATOR = re.compile(r"[\s-]+")
_TASK_TYPE_ALIASES = {
    "software": "software",
    "hardware": "hardware",
    "embedded": "embedded",
    "robotics": "robotics",
    "ai_system": "ai_system",
    "material_change": "material_change",
}

PHASES: tuple[dict[str, Any], ...] = (
    {"id": "concept", "title": "Concept", "sequence": 1},
    {"id": "plan", "title": "Plan", "sequence": 2},
    {"id": "develop", "title": "Develop", "sequence": 3},
    {"id": "qualify", "title": "Qualify", "sequence": 4},
    {"id": "launch", "title": "Launch", "sequence": 5},
    {"id": "lifecycle", "title": "Lifecycle", "sequence": 6},
)

PHASE_MATURITY = {
    "concept": "defined",
    "plan": "selected",
    "develop": "integrated",
    "qualify": "verified",
    "launch": "released",
    "lifecycle": "monitored",
}

BASE_ACTIVITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "concept.scope",
        "title": "Define opportunity, stakeholders, and intended outcomes",
        "phase": "concept",
        "sequence": 10,
    },
    {
        "id": "plan.integrated_planning",
        "title": "Create the integrated delivery and assurance plan",
        "phase": "plan",
        "sequence": 20,
    },
    {
        "id": "develop.solution_realization",
        "title": "Realize and integrate the solution",
        "phase": "develop",
        "sequence": 30,
    },
    {
        "id": "qualify.solution_validation",
        "title": "Verify and validate the integrated solution",
        "phase": "qualify",
        "sequence": 40,
    },
    {
        "id": "launch.release",
        "title": "Prepare and authorize release",
        "phase": "launch",
        "sequence": 50,
    },
    {
        "id": "lifecycle.monitoring",
        "title": "Monitor outcomes and control lifecycle changes",
        "phase": "lifecycle",
        "sequence": 60,
    },
)

BASE_DELIVERABLES: tuple[dict[str, Any], ...] = (
    {
        "id": "concept.problem_definition",
        "title": "Problem and outcome definition",
        "phase": "concept",
        "activity_id": "concept.scope",
        "review_required": True,
        "depends_on": [],
    },
    {
        "id": "plan.integrated_plan",
        "title": "Integrated delivery and assurance plan",
        "phase": "plan",
        "activity_id": "plan.integrated_planning",
        "review_required": True,
        "depends_on": ["concept.problem_definition"],
    },
    {
        "id": "develop.solution_baseline",
        "title": "Integrated solution baseline",
        "phase": "develop",
        "activity_id": "develop.solution_realization",
        "review_required": True,
        "depends_on": ["plan.integrated_plan"],
    },
    {
        "id": "qualify.validation_report",
        "title": "Verification and validation report",
        "phase": "qualify",
        "activity_id": "qualify.solution_validation",
        "review_required": True,
        "depends_on": ["develop.solution_baseline"],
    },
    {
        "id": "launch.release_package",
        "title": "Release readiness package",
        "phase": "launch",
        "activity_id": "launch.release",
        "review_required": True,
        "depends_on": ["qualify.validation_report"],
    },
    {
        "id": "lifecycle.performance_review",
        "title": "Lifecycle performance and change review",
        "phase": "lifecycle",
        "activity_id": "lifecycle.monitoring",
        "review_required": True,
        "depends_on": ["launch.release_package"],
    },
)


def normalize_task_type(value: str) -> str:
    """Return the canonical task type, accepting spaces and hyphens as aliases."""

    if not isinstance(value, str) or not value.strip():
        raise ProcessModelError("task type must be a non-empty string")
    key = _TYPE_SEPARATOR.sub("_", value.strip().lower())
    canonical = _TASK_TYPE_ALIASES.get(key)
    if canonical is None:
        allowed = ", ".join(TASK_TYPES)
        raise ProcessModelError(f"unknown task type {value!r}; expected one of: {allowed}")
    return canonical


def normalize_task_types(values: str | Iterable[str]) -> tuple[str, ...]:
    """Normalize, de-duplicate, and canonically order task types."""

    if isinstance(values, str):
        raw_values = [values]
    else:
        try:
            raw_values = list(values)
        except TypeError as exc:
            raise ProcessModelError("task_types must be a string or an array of strings") from exc
    if not raw_values:
        raise ProcessModelError("at least one task type is required")
    normalized = {normalize_task_type(value) for value in raw_values}
    return tuple(task_type for task_type in TASK_TYPES if task_type in normalized)


def normalize_capability_patterns(values: str | Iterable[str] | None) -> tuple[str, ...]:
    """Validate, de-duplicate, and canonically order capability pattern IDs."""

    if values is None:
        return ()
    if isinstance(values, str):
        raw_values = [values]
    else:
        try:
            raw_values = list(values)
        except TypeError as exc:
            raise ProcessModelError(
                "capability_patterns must be a string or an array of strings"
            ) from exc
    if not all(isinstance(value, str) and value.strip() for value in raw_values):
        raise ProcessModelError(
            "capability_patterns must contain non-empty string identifiers"
        )
    normalized = {value.strip() for value in raw_values}
    unknown = sorted(normalized - set(CAPABILITY_PATTERNS))
    if unknown:
        allowed = ", ".join(CAPABILITY_PATTERNS)
        raise ProcessModelError(
            f"unknown capability pattern {unknown[0]!r}; expected one of: {allowed}"
        )
    return tuple(pattern for pattern in CAPABILITY_PATTERNS if pattern in normalized)


def task_policy_directory() -> Path:
    """Return the repository/package task-policy directory."""

    source_tree = Path(__file__).resolve().parents[1] / "policies" / "task-types"
    if source_tree.is_dir():
        return source_tree
    try:
        distribution = metadata.distribution("ipd-agent-workflow-skill")
    except metadata.PackageNotFoundError as exc:
        raise ProcessModelError("task-type policy resources are unavailable") from exc
    marker = "share/ipd-agent-workflow-skill/policies/task-types/software.yaml"
    for entry in distribution.files or ():
        rendered = str(entry).replace("\\", "/")
        if rendered.endswith(marker):
            return Path(distribution.locate_file(entry)).parent
    raise ProcessModelError("installed task-type policy resources are unavailable")


def capability_policy_directory() -> Path:
    """Return the repository/package capability-policy directory."""

    source_tree = Path(__file__).resolve().parents[1] / "policies" / "capabilities"
    if source_tree.is_dir():
        return source_tree
    try:
        distribution = metadata.distribution("ipd-agent-workflow-skill")
    except metadata.PackageNotFoundError as exc:
        raise ProcessModelError("capability policy resources are unavailable") from exc
    marker = (
        "share/ipd-agent-workflow-skill/policies/capabilities/"
        "sourced_component_integration.yaml"
    )
    for entry in distribution.files or ():
        rendered = str(entry).replace("\\", "/")
        if rendered.endswith(marker):
            return Path(distribution.locate_file(entry)).parent
    raise ProcessModelError("installed capability policy resources are unavailable")


def validate_capability_policy(
    value: Any,
    expected_pattern: str | None = None,
) -> list[str]:
    """Return stable validation messages for one reusable capability policy."""

    issues: list[str] = []
    if not isinstance(value, dict):
        return ["$: must be an object"]
    allowed = {
        "schema_version",
        "capability_pattern",
        "title",
        "activities",
        "deliverables",
        "dependencies",
        "checkpoint_criteria",
    }
    required = allowed
    for field in sorted(required - value.keys()):
        issues.append(f"$.{field}: required field is missing")
    for field in sorted(value.keys() - allowed):
        issues.append(f"$.{field}: unknown field")
    if value.get("schema_version") != CAPABILITY_POLICY_SCHEMA_VERSION:
        issues.append(
            f"$.schema_version: must equal {CAPABILITY_POLICY_SCHEMA_VERSION!r}"
        )
    pattern = value.get("capability_pattern")
    try:
        normalized = normalize_capability_patterns([pattern])
        if expected_pattern is not None and normalized != (expected_pattern,):
            issues.append(
                "$.capability_pattern: policy for "
                f"{expected_pattern!r} declares {pattern!r}"
            )
    except ProcessModelError as exc:
        issues.append(f"$.capability_pattern: {exc}")
    if not isinstance(value.get("title"), str) or not value.get("title", "").strip():
        issues.append("$.title: must be a non-empty string")

    phase_ids = {phase["id"] for phase in PHASES}
    activity_ids: set[str] = set()
    activities = value.get("activities")
    if not isinstance(activities, list) or not activities:
        issues.append("$.activities: must be a non-empty array")
        activities = []
    for index, activity in enumerate(activities):
        path = f"$.activities[{index}]"
        if not isinstance(activity, dict):
            issues.append(f"{path}: must be an object")
            continue
        required_fields = {"id", "title", "phase", "sequence"}
        fields = required_fields | {
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
        }
        for field in sorted(required_fields - activity.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(activity.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        identifier = activity.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(f"{path}.id: must be a non-empty string")
        elif identifier in activity_ids:
            issues.append(f"{path}.id: duplicate activity id {identifier!r}")
        else:
            activity_ids.add(identifier)
        if not isinstance(activity.get("title"), str) or not activity.get(
            "title", ""
        ).strip():
            issues.append(f"{path}.title: must be a non-empty string")
        if activity.get("phase") not in phase_ids:
            issues.append(f"{path}.phase: unknown phase {activity.get('phase')!r}")
        if type(activity.get("sequence")) is not int or activity.get("sequence", -1) < 0:
            issues.append(f"{path}.sequence: must be a non-negative integer")
        issues.extend(_refinement_node_issues(activity, path))

    deliverable_ids: set[str] = set()
    deliverables = value.get("deliverables")
    if not isinstance(deliverables, list) or not deliverables:
        issues.append("$.deliverables: must be a non-empty array")
        deliverables = []
    for index, deliverable in enumerate(deliverables):
        path = f"$.deliverables[{index}]"
        if not isinstance(deliverable, dict):
            issues.append(f"{path}: must be an object")
            continue
        required_fields = {
            "id",
            "title",
            "phase",
            "activity_id",
            "review_required",
            "depends_on",
        }
        fields = required_fields | {
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
            "requires_artifact_owner",
        }
        for field in sorted(required_fields - deliverable.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(deliverable.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        identifier = deliverable.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(f"{path}.id: must be a non-empty string")
        elif identifier in deliverable_ids:
            issues.append(f"{path}.id: duplicate deliverable id {identifier!r}")
        else:
            deliverable_ids.add(identifier)
        if not isinstance(deliverable.get("title"), str) or not deliverable.get(
            "title", ""
        ).strip():
            issues.append(f"{path}.title: must be a non-empty string")
        if deliverable.get("phase") not in phase_ids:
            issues.append(f"{path}.phase: unknown phase {deliverable.get('phase')!r}")
        if not isinstance(deliverable.get("activity_id"), str):
            issues.append(f"{path}.activity_id: must be a non-empty string")
        if deliverable.get("review_required") is not True:
            issues.append(f"{path}.review_required: must equal true")
        dependencies = deliverable.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item.strip() for item in dependencies
        ):
            issues.append(f"{path}.depends_on: must be an array of non-empty strings")
        elif len(dependencies) != len(set(dependencies)):
            issues.append(f"{path}.depends_on: must not contain duplicates")
        if "requires_artifact_owner" in deliverable and type(
            deliverable.get("requires_artifact_owner")
        ) is not bool:
            issues.append(f"{path}.requires_artifact_owner: must be a boolean")
        issues.extend(_refinement_node_issues(deliverable, path))

    dependencies = value.get("dependencies")
    if not isinstance(dependencies, list):
        issues.append("$.dependencies: must be an array")
        dependencies = []
    seen_edges: set[tuple[str, str, str]] = set()
    for index, dependency in enumerate(dependencies):
        path = f"$.dependencies[{index}]"
        if not isinstance(dependency, dict):
            issues.append(f"{path}: must be an object")
            continue
        fields = {"source", "target", "relation"}
        for field in sorted(fields - dependency.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(dependency.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        source = dependency.get("source")
        target = dependency.get("target")
        relation = dependency.get("relation")
        if not isinstance(source, str) or not source.strip():
            issues.append(f"{path}.source: must be a non-empty string")
        if not isinstance(target, str) or not target.strip():
            issues.append(f"{path}.target: must be a non-empty string")
        if relation not in TRACE_RELATIONS:
            issues.append(
                f"{path}.relation: must be one of: {', '.join(TRACE_RELATIONS)}"
            )
        if isinstance(source, str) and isinstance(target, str) and isinstance(relation, str):
            key = (source, target, relation)
            if key in seen_edges:
                issues.append(f"{path}: duplicate typed dependency {key!r}")
            seen_edges.add(key)

    criteria = value.get("checkpoint_criteria")
    if not isinstance(criteria, list):
        issues.append("$.checkpoint_criteria: must be an array")
        criteria = []
    seen_criteria: set[str] = set()
    canonical_checkpoints = {
        f"{prefix}.{phase['id']}"
        for prefix in ("tr", "dcp")
        for phase in PHASES
    }
    for index, criterion in enumerate(criteria):
        path = f"$.checkpoint_criteria[{index}]"
        if not isinstance(criterion, dict):
            issues.append(f"{path}: must be an object")
            continue
        fields = {"id", "checkpoint_id", "description", "evidence_required"}
        for field in sorted(fields - criterion.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(criterion.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        identifier = criterion.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(f"{path}.id: must be a non-empty string")
        elif identifier in seen_criteria:
            issues.append(f"{path}.id: duplicate criterion id {identifier!r}")
        else:
            seen_criteria.add(identifier)
        if criterion.get("checkpoint_id") not in canonical_checkpoints:
            issues.append(f"{path}.checkpoint_id: must reference a canonical TR or DCP")
        if not isinstance(criterion.get("description"), str) or not criterion.get(
            "description", ""
        ).strip():
            issues.append(f"{path}.description: must be a non-empty string")
        if criterion.get("evidence_required") is not True:
            issues.append(f"{path}.evidence_required: must equal true")
    return sorted(set(issues))


def load_capability_policy(pattern: str) -> dict[str, Any]:
    """Load and validate one canonical reusable capability policy."""

    canonical = normalize_capability_patterns([pattern])[0]
    path = capability_policy_directory() / f"{canonical}.yaml"
    try:
        value = load_yaml(path)
    except YamlError as exc:
        raise ProcessModelError(str(exc)) from exc
    issues = validate_capability_policy(value, canonical)
    if issues:
        raise ProcessModelError(
            f"invalid capability policy {path}:\n- " + "\n- ".join(issues)
        )
    return deepcopy(value)


def validate_task_type_policy(value: Any, expected_type: str | None = None) -> list[str]:
    """Return stable validation messages for one task-type extension policy."""

    issues: list[str] = []
    if not isinstance(value, dict):
        return ["$: must be an object"]
    allowed = {"schema_version", "task_type", "activities", "deliverables"}
    required = allowed
    for field in sorted(required - value.keys()):
        issues.append(f"$.{field}: required field is missing")
    for field in sorted(value.keys() - allowed):
        issues.append(f"$.{field}: unknown field")
    if value.get("schema_version") != TASK_POLICY_SCHEMA_VERSION:
        issues.append(
            f"$.schema_version: must equal {TASK_POLICY_SCHEMA_VERSION!r}"
        )
    task_type = value.get("task_type")
    try:
        canonical = normalize_task_type(task_type)
        if expected_type is not None and canonical != expected_type:
            issues.append(
                f"$.task_type: policy for {expected_type!r} declares {canonical!r}"
            )
    except ProcessModelError as exc:
        issues.append(f"$.task_type: {exc}")

    activities = value.get("activities")
    if not isinstance(activities, list) or not activities:
        issues.append("$.activities: must be a non-empty array")
        activities = []
    activity_ids: set[str] = set()
    for index, activity in enumerate(activities):
        path = f"$.activities[{index}]"
        if not isinstance(activity, dict):
            issues.append(f"{path}: must be an object")
            continue
        required_fields = {"id", "title", "phase", "sequence"}
        fields = required_fields | {
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
        }
        for field in sorted(required_fields - activity.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(activity.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        identifier = activity.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(f"{path}.id: must be a non-empty string")
        elif identifier in activity_ids:
            issues.append(f"{path}.id: duplicate activity id {identifier!r}")
        else:
            activity_ids.add(identifier)
        if not isinstance(activity.get("title"), str) or not activity.get("title", "").strip():
            issues.append(f"{path}.title: must be a non-empty string")
        if activity.get("phase") not in {phase["id"] for phase in PHASES}:
            issues.append(f"{path}.phase: unknown phase {activity.get('phase')!r}")
        if type(activity.get("sequence")) is not int or activity.get("sequence", 0) < 0:
            issues.append(f"{path}.sequence: must be a non-negative integer")
        issues.extend(_refinement_node_issues(activity, path))

    deliverables = value.get("deliverables")
    if not isinstance(deliverables, list) or not deliverables:
        issues.append("$.deliverables: must be a non-empty array")
        deliverables = []
    deliverable_ids: set[str] = set()
    for index, deliverable in enumerate(deliverables):
        path = f"$.deliverables[{index}]"
        if not isinstance(deliverable, dict):
            issues.append(f"{path}: must be an object")
            continue
        required_fields = {
            "id",
            "title",
            "phase",
            "activity_id",
            "review_required",
            "depends_on",
        }
        fields = required_fields | {
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
            "requires_artifact_owner",
        }
        for field in sorted(required_fields - deliverable.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(deliverable.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        identifier = deliverable.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(f"{path}.id: must be a non-empty string")
        elif identifier in deliverable_ids:
            issues.append(f"{path}.id: duplicate deliverable id {identifier!r}")
        else:
            deliverable_ids.add(identifier)
        if not isinstance(deliverable.get("title"), str) or not deliverable.get("title", "").strip():
            issues.append(f"{path}.title: must be a non-empty string")
        if deliverable.get("phase") not in {phase["id"] for phase in PHASES}:
            issues.append(f"{path}.phase: unknown phase {deliverable.get('phase')!r}")
        if deliverable.get("activity_id") not in activity_ids:
            issues.append(
                f"{path}.activity_id: references unknown policy activity "
                f"{deliverable.get('activity_id')!r}"
            )
        if type(deliverable.get("review_required")) is not bool:
            issues.append(f"{path}.review_required: must be a boolean")
        dependencies = deliverable.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item.strip() for item in dependencies
        ):
            issues.append(f"{path}.depends_on: must be an array of non-empty strings")
        elif len(dependencies) != len(set(dependencies)):
            issues.append(f"{path}.depends_on: must not contain duplicates")
        if "requires_artifact_owner" in deliverable and type(
            deliverable.get("requires_artifact_owner")
        ) is not bool:
            issues.append(f"{path}.requires_artifact_owner: must be a boolean")
        issues.extend(_refinement_node_issues(deliverable, path))
    return issues


def load_task_type_policy(task_type: str) -> dict[str, Any]:
    """Load and validate the extension policy for a canonical task type."""

    canonical = normalize_task_type(task_type)
    path = task_policy_directory() / f"{canonical}.yaml"
    try:
        value = load_yaml(path)
    except YamlError as exc:
        raise ProcessModelError(str(exc)) from exc
    issues = validate_task_type_policy(value, canonical)
    if issues:
        raise ProcessModelError(
            f"invalid task-type policy {path}:\n- " + "\n- ".join(issues)
        )
    return deepcopy(value)


def base_activities() -> list[dict[str, Any]]:
    return deepcopy(list(BASE_ACTIVITIES))


def base_deliverables() -> list[dict[str, Any]]:
    return deepcopy(list(BASE_DELIVERABLES))


def phases() -> list[dict[str, Any]]:
    return deepcopy(list(PHASES))


__all__ = [
    "BASE_ACTIVITIES",
    "BASE_DELIVERABLES",
    "CAPABILITY_PATTERNS",
    "CAPABILITY_POLICY_SCHEMA_VERSION",
    "LEGACY_PROCESS_SCHEMA_VERSION",
    "PHASES",
    "PHASE_MATURITY",
    "PROCESS_SCHEMA_VERSION",
    "ProcessModelError",
    "SUPPORTED_PROCESS_SCHEMA_VERSIONS",
    "base_activities",
    "base_deliverables",
    "capability_policy_directory",
    "load_capability_policy",
    "load_task_type_policy",
    "normalize_capability_patterns",
    "normalize_task_type",
    "normalize_task_types",
    "phases",
    "task_policy_directory",
    "validate_capability_policy",
    "validate_task_type_policy",
]

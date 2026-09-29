"""Domain-neutral IPD process model and task-type policy loading."""

from __future__ import annotations

import re
from copy import deepcopy
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

from .model import TASK_TYPES
from .yamlio import YamlError, load_yaml

PROCESS_SCHEMA_VERSION = "1.0"
TASK_POLICY_SCHEMA_VERSION = "1.0"


class ProcessModelError(ValueError):
    """Raised when a task type or process policy violates the model contract."""


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
        fields = {"id", "title", "phase", "sequence"}
        for field in sorted(fields - activity.keys()):
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
        fields = {
            "id",
            "title",
            "phase",
            "activity_id",
            "review_required",
            "depends_on",
        }
        for field in sorted(fields - deliverable.keys()):
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
    "PHASES",
    "PROCESS_SCHEMA_VERSION",
    "ProcessModelError",
    "base_activities",
    "base_deliverables",
    "load_task_type_policy",
    "normalize_task_type",
    "normalize_task_types",
    "phases",
    "task_policy_directory",
    "validate_task_type_policy",
]

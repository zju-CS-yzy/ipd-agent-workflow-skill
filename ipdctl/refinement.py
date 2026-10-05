"""Pure progressive-refinement contracts and helpers.

Refinement is structural process evolution, not execution.  ``refines`` edges
therefore never participate in the ``depends_on`` execution graph.  This
module intentionally contains no project-state mutation or CLI authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .model import TRACE_RELATIONS
from .yamlio import YamlError, load_yaml

REFINEMENT_PLAN_SCHEMA_VERSION = "1.0"
REFINEMENT_MODES = ("expand",)
DEFINITION_STATES = ("concrete", "placeholder", "abstract")
REFINEMENT_CONDITIONS = ("accepted", "approved")
REFINEMENT_STATUSES = ("pending", "due", "resolved")

_AUTHORITY_ACTIVITY_FIELDS = (
    "id",
    "title",
    "phase",
    "sequence",
    "definition_state",
    "refines",
    "provenance",
)
_AUTHORITY_DELIVERABLE_FIELDS = (
    "id",
    "title",
    "phase",
    "activity_id",
    "review_required",
    "depends_on",
    "definition_state",
    "refinement_required",
    "refinement_trigger",
    "refines",
    "requires_artifact_owner",
    "completion_policy",
    "provenance",
    "maturity",
)

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_PHASE_IDS = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")


class RefinementPlanError(ValueError):
    """Raised when a refinement plan is invalid or cannot be merged safely."""


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_PATTERN.fullmatch(value))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def process_fingerprint(process: Mapping[str, Any]) -> str:
    """Return the stable SHA-256 fingerprint used by refinement plans.

    Applied-refinement result audit fields attest to this fingerprint and are
    therefore excluded from its payload to avoid a self-referential digest.
    They remain governed process facts and are cross-checked with Agent runtime.
    """

    if not isinstance(process, Mapping):
        raise RefinementPlanError("process must be an object")
    normalized = deepcopy(dict(process))
    refinements = normalized.get("refinements", [])
    if isinstance(refinements, list):
        for refinement in refinements:
            if isinstance(refinement, dict):
                refinement.pop("result_process_fingerprint", None)
                refinement.pop("invalidated_gates", None)
    payload = _canonical(normalized).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def finalize_refinement_record(
    extension: Mapping[str, Any],
    *,
    plan_id: str,
    result_process_fingerprint: str,
    invalidated_gates: Iterable[str],
) -> dict[str, Any]:
    """Bind one applied plan record to its exact result and Gate impact."""

    from .process_extensions import load_process_extension

    if not re.fullmatch(r"sha256:[0-9a-f]{64}", result_process_fingerprint):
        raise RefinementPlanError(
            "result_process_fingerprint must use sha256:<64 lowercase hex>"
        )
    gates = sorted(set(invalidated_gates))
    if any(not _valid_id(identifier) for identifier in gates):
        raise RefinementPlanError(
            "invalidated_gates must contain only valid identifiers"
        )
    updated = load_process_extension(extension)
    matches = [
        item
        for item in updated.get("refinements", [])
        if isinstance(item, dict) and item.get("id") == plan_id
    ]
    if len(matches) != 1:
        raise RefinementPlanError(
            f"applied refinement record {plan_id!r} is missing or ambiguous"
        )
    record = matches[0]
    expected = {
        "result_process_fingerprint": result_process_fingerprint,
        "invalidated_gates": gates,
    }
    for field, value in expected.items():
        if field in record and record[field] != value:
            raise RefinementPlanError(
                f"applied refinement record {plan_id!r} conflicts on {field}"
            )
        record[field] = deepcopy(value)
    return load_process_extension(updated)


def _authority_fields(
    item: Mapping[str, Any], fields: Iterable[str]
) -> dict[str, Any]:
    return {field: deepcopy(item[field]) for field in fields if field in item}


def refinement_authority_projection(
    process: Mapping[str, Any],
    *,
    protected_roots: Iterable[str] | None = None,
    mutable_requirement_roots: Iterable[str] = (),
) -> dict[str, Any]:
    """Project process facts owned by already-declared refinements.

    Ordinary re-tailoring may add unrelated project or capability facts, but it
    must not mutate an existing refinement root, any of its descendants, their
    activities, or relations sourced from those nodes. ``protected_roots`` is
    intentionally supplied from the current process when comparing a
    candidate: a newly declared unrelated requirement remains additive, while
    a child smuggled under an existing root is detected.
    """

    if not isinstance(process, Mapping):
        raise RefinementPlanError("process must be an object")
    requirements = [
        item
        for item in process.get("refinement_requirements", [])
        if isinstance(item, Mapping) and isinstance(item.get("root"), str)
    ]
    deliverables = [
        item
        for item in process.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    ]
    declared_roots = {
        item["root"] for item in requirements
    } | {
        item["id"]
        for item in deliverables
        if item.get("refinement_required") is True
    } | {
        item["root"]
        for item in process.get("refinements", [])
        if isinstance(item, Mapping) and isinstance(item.get("root"), str)
    }
    roots = {
        root
        for root in (
            protected_roots
            if protected_roots is not None
            else declared_roots
        )
        if isinstance(root, str)
    }
    mutable_roots = {
        root for root in mutable_requirement_roots if isinstance(root, str)
    }
    protected_deliverables = set(roots)
    changed = True
    while changed:
        changed = False
        for item in deliverables:
            identifier = item["id"]
            if (
                identifier not in protected_deliverables
                and item.get("refines") in protected_deliverables
            ):
                protected_deliverables.add(identifier)
                changed = True

    activities = [
        item
        for item in process.get("activities", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    ]
    protected_activities = {
        item["activity_id"]
        for item in deliverables
        if item["id"] in protected_deliverables
        and isinstance(item.get("activity_id"), str)
    }
    changed = True
    while changed:
        changed = False
        for item in activities:
            identifier = item["id"]
            if (
                identifier not in protected_activities
                and item.get("refines") in protected_activities
            ):
                protected_activities.add(identifier)
                changed = True

    projected_requirements = [
        deepcopy(dict(item))
        for item in requirements
        if item["root"] in protected_deliverables
    ]
    projected_refinements = [
        deepcopy(dict(item))
        for item in process.get("refinements", [])
        if isinstance(item, Mapping)
        and (
            item.get("root") in protected_deliverables
            or bool(set(item.get("children", [])) & protected_deliverables)
        )
    ]
    protected_sources = protected_deliverables | protected_activities
    projected_relations = [
        deepcopy(dict(item))
        for item in process.get("dependencies", [])
        if isinstance(item, Mapping) and item.get("source") in protected_sources
    ]
    sort_key = lambda item: _canonical(item)
    return {
        "roots": sorted(roots),
        "refinement_requirements": sorted(projected_requirements, key=sort_key),
        "refinements": sorted(projected_refinements, key=sort_key),
        "activities": sorted(
            (
                _authority_fields(item, _AUTHORITY_ACTIVITY_FIELDS)
                for item in activities
                if item["id"] in protected_activities
            ),
            key=sort_key,
        ),
        "deliverables": sorted(
            (
                _authority_fields(
                    item,
                    (
                        field
                        for field in _AUTHORITY_DELIVERABLE_FIELDS
                        if item["id"] not in mutable_roots
                        or field
                        not in {
                            "definition_state",
                            "refinement_required",
                            "refinement_trigger",
                            "completion_policy",
                        }
                    ),
                )
                for item in deliverables
                if item["id"] in protected_deliverables
            ),
            key=sort_key,
        ),
        "relations": sorted(projected_relations, key=sort_key),
    }


def _trigger_issues(value: Any, path: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{path}: must be an object"]
    issues: list[str] = []
    fields = {"all_of"}
    for field in sorted(fields - value.keys()):
        issues.append(f"{path}.{field}: required field is missing")
    for field in sorted(value.keys() - fields):
        issues.append(f"{path}.{field}: unknown field")
    clauses = value.get("all_of")
    if not isinstance(clauses, list) or not clauses:
        issues.append(f"{path}.all_of: must be a non-empty array")
        return issues
    seen: set[tuple[str, str]] = set()
    for index, clause in enumerate(clauses):
        clause_path = f"{path}.all_of[{index}]"
        if not isinstance(clause, dict):
            issues.append(f"{clause_path}: must be an object")
            continue
        clause_fields = {"subject", "condition"}
        for field in sorted(clause_fields - clause.keys()):
            issues.append(f"{clause_path}.{field}: required field is missing")
        for field in sorted(clause.keys() - clause_fields):
            issues.append(f"{clause_path}.{field}: unknown field")
        subject = clause.get("subject")
        condition = clause.get("condition")
        if not _valid_id(subject):
            issues.append(
                f"{clause_path}.subject: must be a valid lowercase identifier"
            )
        if condition not in REFINEMENT_CONDITIONS:
            issues.append(
                f"{clause_path}.condition: must be one of: "
                + ", ".join(REFINEMENT_CONDITIONS)
            )
        if isinstance(subject, str) and isinstance(condition, str):
            key = (subject, condition)
            if key in seen:
                issues.append(f"{clause_path}: duplicate trigger clause {key!r}")
            seen.add(key)
    return issues


def trigger_satisfied(
    trigger: Mapping[str, Any],
    statuses: Mapping[str, Any],
) -> bool:
    """Return whether every explicit trigger clause is satisfied.

    A status value may be the status string itself or an object containing a
    ``status`` field.  Missing subjects fail closed.
    """

    if _trigger_issues(trigger, "$"):
        return False
    for clause in trigger["all_of"]:
        actual = statuses.get(clause["subject"])
        if isinstance(actual, Mapping):
            actual = actual.get("status")
        if actual != clause["condition"]:
            return False
    return True


def validate_refinement_trigger(value: Any, path: str = "$") -> list[str]:
    """Return stable structural issues for a refinement trigger."""

    return sorted(set(_trigger_issues(value, path)))


def refinement_status(
    requirement: Mapping[str, Any],
    *,
    statuses: Mapping[str, Any],
    refinements: Iterable[Mapping[str, Any]] = (),
) -> str:
    """Derive ``pending``, ``due``, or ``resolved`` for one requirement."""

    root = requirement.get("root")
    if any(item.get("root") == root for item in refinements):
        return "resolved"
    trigger = requirement.get("trigger")
    if isinstance(trigger, Mapping) and trigger_satisfied(trigger, statuses):
        return "due"
    return "pending"


def _entity_collection(
    process_or_entities: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    collection: str,
) -> list[Mapping[str, Any]]:
    if isinstance(process_or_entities, Mapping):
        raw = process_or_entities.get(collection, [])
    else:
        raw = process_or_entities
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def refinement_children(
    process_or_deliverables: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    root: str,
) -> list[str]:
    """Return direct Deliverable children of ``root`` in stable ID order."""

    children = {
        item["id"]
        for item in _entity_collection(process_or_deliverables, "deliverables")
        if isinstance(item.get("id"), str) and item.get("refines") == root
    }
    return sorted(children)


def refinement_leaf_closure(
    process_or_deliverables: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    root: str,
) -> list[str]:
    """Return concrete structural leaves beneath ``root``.

    A node without children is its own leaf.  Structural cycles fail closed;
    they are not treated as execution dependency cycles.
    """

    entities = _entity_collection(process_or_deliverables, "deliverables")
    children_by_parent: dict[str, list[str]] = {}
    for item in entities:
        identifier = item.get("id")
        parent = item.get("refines")
        if isinstance(identifier, str) and isinstance(parent, str):
            children_by_parent.setdefault(parent, []).append(identifier)
    for children in children_by_parent.values():
        children.sort()

    leaves: list[str] = []

    def visit(identifier: str, stack: tuple[str, ...]) -> None:
        if identifier in stack:
            cycle = " -> ".join((*stack, identifier))
            raise RefinementPlanError(f"refinement cycle detected: {cycle}")
        children = children_by_parent.get(identifier, [])
        if not children:
            leaves.append(identifier)
            return
        for child in children:
            visit(child, (*stack, identifier))

    visit(root, ())
    return sorted(dict.fromkeys(leaves))


def effective_gate_requirements(
    required: Iterable[str],
    process_or_deliverables: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> list[str]:
    """Replace expanded abstract roots with their concrete leaf closure.

    Unresolved placeholders have no children and therefore remain explicit Gate
    requirements.  The result preserves the incoming order and deterministic
    leaf order while removing duplicates.
    """

    entities = _entity_collection(process_or_deliverables, "deliverables")
    by_id = {
        item["id"]: item
        for item in entities
        if isinstance(item.get("id"), str)
    }
    result: list[str] = []
    for identifier in required:
        node = by_id.get(identifier, {})
        children = refinement_children(entities, identifier)
        expanded = node.get("definition_state") == "abstract" and bool(children)
        candidates = (
            refinement_leaf_closure(entities, identifier)
            if expanded
            else [identifier]
        )
        for candidate in candidates:
            if candidate not in result:
                result.append(candidate)
    return result


def _definition_issues(
    value: Mapping[str, Any],
    path: str,
    *,
    allow_refinement_requirement: bool = True,
) -> list[str]:
    issues: list[str] = []
    if "definition_state" in value and value.get("definition_state") not in DEFINITION_STATES:
        issues.append(
            f"{path}.definition_state: must be one of: "
            + ", ".join(DEFINITION_STATES)
        )
    if not allow_refinement_requirement:
        for field in ("refinement_required", "refinement_trigger"):
            if field in value:
                issues.append(
                    f"{path}.{field}: only Deliverables may declare refinement requirements"
                )
    else:
        if "refinement_required" in value and type(value.get("refinement_required")) is not bool:
            issues.append(f"{path}.refinement_required: must be a boolean")
        if (
            value.get("definition_state") == "placeholder"
            and value.get("refinement_required") is not True
        ):
            issues.append(
                f"{path}.refinement_required: must be true when definition_state is placeholder"
            )
        if value.get("refinement_required") is True:
            if "refinement_trigger" not in value:
                issues.append(
                    f"{path}.refinement_trigger: required when refinement_required is true"
                )
            if value.get("definition_state", "concrete") not in {
                "concrete",
                "placeholder",
            }:
                issues.append(
                    f"{path}.definition_state: a refinement requirement root must be "
                    "concrete or placeholder"
                )
        if "refinement_trigger" in value:
            issues.extend(
                _trigger_issues(
                    value.get("refinement_trigger"),
                    f"{path}.refinement_trigger",
                )
            )
    if "refines" in value and not _valid_id(value.get("refines")):
        issues.append(f"{path}.refines: must be a valid lowercase identifier")
    return issues


def validate_refinement_plan(
    value: Any,
    *,
    process: Mapping[str, Any] | None = None,
    extension: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return stable validation issues for one explicit refinement plan."""

    if not isinstance(value, dict):
        return ["$: must be an object"]
    issues: list[str] = []
    fields = {
        "schema_version",
        "id",
        "root",
        "mode",
        "base_process_fingerprint",
        "reason",
        "basis",
        "activities",
        "deliverables",
        "dependencies",
    }
    for field in sorted(fields - value.keys()):
        issues.append(f"$.{field}: required field is missing")
    for field in sorted(value.keys() - fields):
        issues.append(f"$.{field}: unknown field")
    if value.get("schema_version") != REFINEMENT_PLAN_SCHEMA_VERSION:
        issues.append(
            "$.schema_version: must equal "
            f"{REFINEMENT_PLAN_SCHEMA_VERSION!r}"
        )
    for field in ("id", "root"):
        if not _valid_id(value.get(field)):
            issues.append(f"$.{field}: must be a valid lowercase identifier")
    if value.get("mode") not in REFINEMENT_MODES:
        issues.append(f"$.mode: must equal 'expand'")
    fingerprint = value.get("base_process_fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", fingerprint
    ):
        issues.append(
            "$.base_process_fingerprint: must use sha256:<64 lowercase hex>"
        )
    if not isinstance(value.get("reason"), str) or not value.get("reason", "").strip():
        issues.append("$.reason: must be a non-empty string")
    basis = value.get("basis")
    if not isinstance(basis, list) or not basis or not all(
        isinstance(item, str) and item.strip() for item in basis
    ):
        issues.append("$.basis: must be a non-empty array of non-empty strings")
    elif len(basis) != len(set(basis)):
        issues.append("$.basis: must not contain duplicates")

    activity_ids: set[str] = set()
    activities = value.get("activities")
    if not isinstance(activities, list):
        issues.append("$.activities: must be an array")
        activities = []
    for index, activity in enumerate(activities):
        path = f"$.activities[{index}]"
        if not isinstance(activity, dict):
            issues.append(f"{path}: must be an object")
            continue
        required = {"id", "title", "phase", "sequence"}
        allowed = required | {
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
        }
        for field in sorted(required - activity.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(activity.keys() - allowed):
            issues.append(f"{path}.{field}: unknown field")
        identifier = activity.get("id")
        if not _valid_id(identifier):
            issues.append(f"{path}.id: must be a valid lowercase identifier")
        elif identifier in activity_ids:
            issues.append(f"{path}.id: duplicate activity id {identifier!r}")
        else:
            activity_ids.add(identifier)
        if not isinstance(activity.get("title"), str) or not activity.get("title", "").strip():
            issues.append(f"{path}.title: must be a non-empty string")
        if activity.get("phase") not in _PHASE_IDS:
            issues.append(f"{path}.phase: unknown phase {activity.get('phase')!r}")
        if type(activity.get("sequence")) is not int or activity.get("sequence", -1) < 0:
            issues.append(f"{path}.sequence: must be a non-negative integer")
        issues.extend(
            _definition_issues(
                activity,
                path,
                allow_refinement_requirement=False,
            )
        )

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
        required = {
            "id",
            "title",
            "phase",
            "activity_id",
            "review_required",
            "depends_on",
            "refines",
        }
        allowed = required | {
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "requires_artifact_owner",
        }
        for field in sorted(required - deliverable.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(deliverable.keys() - allowed):
            issues.append(f"{path}.{field}: unknown field")
        identifier = deliverable.get("id")
        if not _valid_id(identifier):
            issues.append(f"{path}.id: must be a valid lowercase identifier")
        elif identifier in deliverable_ids:
            issues.append(f"{path}.id: duplicate deliverable id {identifier!r}")
        else:
            deliverable_ids.add(identifier)
        if not isinstance(deliverable.get("title"), str) or not deliverable.get("title", "").strip():
            issues.append(f"{path}.title: must be a non-empty string")
        if deliverable.get("phase") not in _PHASE_IDS:
            issues.append(f"{path}.phase: unknown phase {deliverable.get('phase')!r}")
        if not _valid_id(deliverable.get("activity_id")):
            issues.append(f"{path}.activity_id: must be a valid lowercase identifier")
        if deliverable.get("review_required") is not True:
            issues.append(f"{path}.review_required: must equal true")
        dependencies = deliverable.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            _valid_id(item) for item in dependencies
        ):
            issues.append(f"{path}.depends_on: must be an array of identifiers")
        elif len(dependencies) != len(set(dependencies)):
            issues.append(f"{path}.depends_on: must not contain duplicates")
        if "requires_artifact_owner" in deliverable and type(
            deliverable.get("requires_artifact_owner")
        ) is not bool:
            issues.append(f"{path}.requires_artifact_owner: must be a boolean")
        definition_state = deliverable.get("definition_state", "concrete")
        if (
            "requires_artifact_owner" in deliverable
            and definition_state == "concrete"
            and deliverable.get("requires_artifact_owner") is not True
        ):
            issues.append(
                f"{path}.requires_artifact_owner: concrete Deliverables must require an artifact Owner"
            )
        if (
            "requires_artifact_owner" in deliverable
            and definition_state in {"abstract", "placeholder"}
            and deliverable.get("requires_artifact_owner") is not False
        ):
            issues.append(
                f"{path}.requires_artifact_owner: non-concrete Deliverables must not require an artifact Owner"
            )
        issues.extend(_definition_issues(deliverable, path))

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
        dependency_fields = {"source", "target", "relation"}
        for field in sorted(dependency_fields - dependency.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(dependency.keys() - dependency_fields):
            issues.append(f"{path}.{field}: unknown field")
        source = dependency.get("source")
        target = dependency.get("target")
        relation = dependency.get("relation")
        if not _valid_id(source):
            issues.append(f"{path}.source: must be a valid lowercase identifier")
        if not _valid_id(target):
            issues.append(f"{path}.target: must be a valid lowercase identifier")
        if relation not in TRACE_RELATIONS:
            issues.append(
                f"{path}.relation: must be one of: {', '.join(TRACE_RELATIONS)}"
            )
        if isinstance(source, str) and isinstance(target, str) and isinstance(relation, str):
            key = (source, target, relation)
            if key in seen_edges:
                issues.append(f"{path}: duplicate typed dependency {key!r}")
            seen_edges.add(key)

    root = value.get("root")
    process_activities: set[str] = set()
    process_deliverables: set[str] = set()
    process_entities: set[str] = set()
    process_activity_by_id: dict[str, Mapping[str, Any]] = {}
    process_deliverable_by_id: dict[str, Mapping[str, Any]] = {}
    if process is not None:
        process_activity_by_id = {
            item["id"]: item
            for item in process.get("activities", [])
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
        process_deliverable_by_id = {
            item["id"]: item
            for item in process.get("deliverables", [])
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
        process_activities = {
            *process_activity_by_id
        }
        process_deliverables = {
            *process_deliverable_by_id
        }
        process_entities = process_activities | process_deliverables
        if root not in process_deliverables:
            issues.append(f"$.root: references unknown Deliverable {root!r}")
        if fingerprint != process_fingerprint(process):
            issues.append("$.base_process_fingerprint: does not match the current process")
        for identifier in sorted(activity_ids & process_activities):
            issues.append(f"$.activities: id {identifier!r} already exists in the process")
        for identifier in sorted(deliverable_ids & process_deliverables):
            issues.append(f"$.deliverables: id {identifier!r} already exists in the process")

    if extension is not None:
        requirements = extension.get("refinement_requirements", [])
        declared_roots = {
            item.get("root")
            for item in requirements
            if isinstance(item, Mapping)
        }
        if root not in declared_roots:
            issues.append(
                f"$.root: {root!r} has no declared refinement requirement"
            )

    available_activities = process_activities | activity_ids
    if process is not None:
        for index, deliverable in enumerate(deliverables):
            if not isinstance(deliverable, Mapping):
                continue
            activity_id = deliverable.get("activity_id")
            if activity_id not in available_activities:
                issues.append(
                    f"$.deliverables[{index}].activity_id: references unknown activity "
                    f"{activity_id!r}"
                )

    parent_by_child = {
        item["id"]: item.get("refines")
        for item in deliverables
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    nested_requirement_roots = {
        item["id"]
        for item in deliverables
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and item.get("refinement_required") is True
    }
    for child in sorted(parent_by_child):
        cursor = parent_by_child.get(child)
        seen_ancestors: set[str] = set()
        while isinstance(cursor, str) and cursor not in seen_ancestors:
            if cursor in nested_requirement_roots:
                issues.append(
                    f"$.deliverables: refinement requirement root {cursor!r} "
                    f"must remain a leaf in this plan; descendant {child!r} "
                    "requires a later authorized plan"
                )
                break
            seen_ancestors.add(cursor)
            cursor = parent_by_child.get(cursor)
    plan_deliverable_by_id = {
        item["id"]: item
        for item in deliverables
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    for child, parent in sorted(parent_by_child.items()):
        if parent != root and parent not in deliverable_ids:
            issues.append(
                f"$.deliverables: {child!r} must refine plan root {root!r} "
                "or another plan Deliverable"
            )
            continue
        seen: list[str] = []
        cursor: Any = child
        while cursor in parent_by_child:
            if cursor in seen:
                issues.append(
                    "$.deliverables: refinement cycle detected: "
                    + " -> ".join((*seen, cursor))
                )
                break
            seen.append(cursor)
            cursor = parent_by_child[cursor]
        if cursor != root:
            issues.append(
                f"$.deliverables: refinement ancestry for {child!r} "
                f"does not terminate at root {root!r}"
            )
        child_node = plan_deliverable_by_id.get(child)
        parent_node = plan_deliverable_by_id.get(parent) or process_deliverable_by_id.get(parent)
        if (
            child_node is not None
            and parent_node is not None
            and child_node.get("phase") != parent_node.get("phase")
        ):
            issues.append(
                f"$.deliverables: refinement child {child!r} must remain in "
                f"parent phase {parent_node.get('phase')!r}"
            )

    plan_activity_by_id = {
        item["id"]: item
        for item in activities
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    for child, child_node in sorted(plan_activity_by_id.items()):
        parent = child_node.get("refines")
        if not isinstance(parent, str):
            continue
        parent_node = plan_activity_by_id.get(parent) or process_activity_by_id.get(parent)
        if parent_node is None:
            if process is not None:
                issues.append(
                    f"$.activities: refinement child {child!r} references "
                    f"unknown Activity parent {parent!r}"
                )
        elif child_node.get("phase") != parent_node.get("phase"):
            issues.append(
                f"$.activities: refinement child {child!r} must remain in "
                f"parent phase {parent_node.get('phase')!r}"
            )

    available_entities = process_entities | activity_ids | deliverable_ids
    if process is not None:
        for index, dependency in enumerate(dependencies):
            if not isinstance(dependency, Mapping):
                continue
            source = dependency.get("source")
            target = dependency.get("target")
            relation = dependency.get("relation")
            if source not in available_entities:
                issues.append(
                    f"$.dependencies[{index}].source: references unknown entity {source!r}"
                )
            if target not in available_entities:
                issues.append(
                    f"$.dependencies[{index}].target: references unknown entity {target!r}"
                )
            if relation == "depends_on" and (
                source not in process_deliverables | deliverable_ids
                or target not in process_deliverables | deliverable_ids
            ):
                issues.append(
                    f"$.dependencies[{index}]: depends_on must connect two Deliverables"
                )

    return sorted(set(issues))


def load_refinement_plan(
    source: str | Path | Mapping[str, Any],
    *,
    process: Mapping[str, Any] | None = None,
    extension: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load, normalize, and validate one refinement plan."""

    if isinstance(source, Mapping):
        value: Any = deepcopy(dict(source))
    else:
        try:
            value = load_yaml(source)
        except YamlError as exc:
            raise RefinementPlanError(str(exc)) from exc
    if isinstance(value, dict) and isinstance(value.get("deliverables"), list):
        for deliverable in value["deliverables"]:
            if isinstance(deliverable, dict):
                definition_state = deliverable.setdefault(
                    "definition_state", "concrete"
                )
                if definition_state == "concrete":
                    # A concrete refinement child is executable work and must
                    # never be able to opt out of explicit artifact ownership.
                    deliverable.setdefault("requires_artifact_owner", True)
                else:
                    # Placeholder and abstract nodes are structural.  Their
                    # concrete leaf descendants carry the ownership contract.
                    deliverable.setdefault("requires_artifact_owner", False)
    issues = validate_refinement_plan(value, process=process, extension=extension)
    if issues:
        raise RefinementPlanError("invalid refinement plan:\n- " + "\n- ".join(issues))
    assert isinstance(value, dict)
    return value


def refinement_plan_digest(plan: Mapping[str, Any]) -> str:
    """Return a stable digest of a normalized, context-independent plan."""

    normalized = load_refinement_plan(plan)
    return "sha256:" + hashlib.sha256(_canonical(normalized).encode("utf-8")).hexdigest()


def historical_deliverable_id_reuse(
    plan: Mapping[str, Any],
    state: Mapping[str, Any],
    process: Mapping[str, Any],
) -> list[str]:
    """Return plan IDs that collide with state-only governed history."""

    process_ids = {
        item.get("id")
        for item in process.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    historical_ids = {
        item.get("id")
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and item.get("id") not in process_ids
    }
    return sorted(
        {
            item.get("id")
            for item in plan.get("deliverables", [])
            if isinstance(item, Mapping) and item.get("id") in historical_ids
        }
    )


def historical_dependency_rewrites(
    diff: Mapping[str, Any], state: Mapping[str, Any]
) -> list[str]:
    """Return existing historical nodes whose prerequisites would be rewritten."""

    state_deliverables = {
        item.get("id"): item
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    affected: set[str] = set()
    for change in diff.get("changed", []):
        if (
            not isinstance(change, Mapping)
            or change.get("collection") != "deliverables"
            or "depends_on" not in change.get("fields", [])
        ):
            continue
        prior = state_deliverables.get(change.get("id"), {})
        if (
            prior.get("status", "planned") != "planned"
            or bool(prior.get("evidence"))
            or bool(prior.get("reviews"))
            or bool(prior.get("blocked_reason"))
            or bool(prior.get("replacement"))
            or bool(prior.get("replacements"))
        ):
            affected.add(str(change.get("id")))
    return sorted(affected)


def merge_refinement_plan(
    extension: Mapping[str, Any],
    plan: Mapping[str, Any] | str | Path,
    *,
    process: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Merge a validated plan into an additive process extension.

    Returns ``(extension, applied)``. Reapplying the same plan digest is a
    deterministic no-op; reusing a plan ID with different content fails.
    """

    # Local import keeps process-extension validation independent of this module.
    from .process_extensions import load_process_extension

    normalized_extension = load_process_extension(extension)
    # Normalize and identify an already-applied plan before checking its base
    # fingerprint. Exact replay is an idempotent no-op even though the current
    # process necessarily changed after the first application.
    normalized_plan = load_refinement_plan(plan)
    digest = refinement_plan_digest(normalized_plan)
    plan_id = normalized_plan["id"]
    for applied in normalized_extension["refinements"]:
        if applied.get("id") != plan_id:
            continue
        if applied.get("plan_digest") == digest:
            return normalized_extension, False
        raise RefinementPlanError(
            f"refinement id {plan_id!r} is already applied with a different digest"
        )

    contextual_issues = validate_refinement_plan(
        normalized_plan,
        process=process,
        extension=normalized_extension,
    )
    if contextual_issues:
        raise RefinementPlanError(
            "invalid refinement plan:\n- " + "\n- ".join(contextual_issues)
        )

    merged = deepcopy(normalized_extension)
    merged["activities"].extend(deepcopy(normalized_plan["activities"]))
    merged["deliverables"].extend(deepcopy(normalized_plan["deliverables"]))
    merged["dependencies"].extend(deepcopy(normalized_plan["dependencies"]))
    existing_requirement_roots = {
        item.get("root")
        for item in merged["refinement_requirements"]
        if isinstance(item, Mapping)
    }
    for deliverable in normalized_plan["deliverables"]:
        if deliverable.get("refinement_required") is not True:
            continue
        root = deliverable["id"]
        if root in existing_requirement_roots:
            raise RefinementPlanError(
                f"refinement requirement root {root!r} is already declared"
            )
        trigger = deliverable.get("refinement_trigger")
        if not isinstance(trigger, Mapping):
            # This is already rejected by plan validation; keep the merge
            # boundary fail-closed if a future caller bypasses normalization.
            raise RefinementPlanError(
                f"refinement child {root!r} requires a refinement_trigger"
            )
        merged["refinement_requirements"].append(
            {
                "root": root,
                "definition_state": deliverable.get(
                    "definition_state", "concrete"
                ),
                "refinement_required": True,
                "trigger": deepcopy(dict(trigger)),
                "completion_policy": "all_children_accepted",
            }
        )
        existing_requirement_roots.add(root)
    merged["refinements"].append(
        {
            "id": plan_id,
            "root": normalized_plan["root"],
            "mode": normalized_plan["mode"],
            "base_process_fingerprint": normalized_plan["base_process_fingerprint"],
            "reason": normalized_plan["reason"],
            "basis": deepcopy(normalized_plan["basis"]),
            "plan_digest": digest,
            "children": [
                item["id"] for item in normalized_plan["deliverables"]
            ],
        }
    )
    # Revalidate the materialized extension, including duplicate child IDs.
    return load_process_extension(merged), True


__all__ = [
    "DEFINITION_STATES",
    "REFINEMENT_CONDITIONS",
    "REFINEMENT_MODES",
    "REFINEMENT_PLAN_SCHEMA_VERSION",
    "REFINEMENT_STATUSES",
    "RefinementPlanError",
    "effective_gate_requirements",
    "finalize_refinement_record",
    "historical_deliverable_id_reuse",
    "historical_dependency_rewrites",
    "load_refinement_plan",
    "merge_refinement_plan",
    "process_fingerprint",
    "refinement_authority_projection",
    "refinement_children",
    "refinement_leaf_closure",
    "refinement_plan_digest",
    "refinement_status",
    "trigger_satisfied",
    "validate_refinement_trigger",
    "validate_refinement_plan",
]

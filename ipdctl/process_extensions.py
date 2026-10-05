"""Validated project process extensions and deterministic process previews.

The project extension is an additive input.  It may introduce project-specific
process facts, but it has no vocabulary for deleting or replacing framework
entities and it cannot weaken review or history controls.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .model import TRACE_RELATIONS
from .refinement import DEFINITION_STATES, validate_refinement_trigger
from .yamlio import YamlError, load_yaml

PROCESS_EXTENSION_SCHEMA_VERSION = "1.0"
MIGRATION_STRATEGIES = ("replace", "split")

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_PHASE_IDS = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
_COLLECTIONS = (
    "phases",
    "technical_reviews",
    "decision_checkpoints",
    "gates",
    "activities",
    "deliverables",
    "review_requirements",
    "refinements",
)


class ProcessExtensionError(ValueError):
    """Raised when a project process extension violates the additive contract."""


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_PATTERN.fullmatch(value))


def _validate_entity_common(
    item: Any,
    *,
    path: str,
    required_fields: set[str],
    allowed_fields: set[str],
    issues: list[str],
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        issues.append(f"{path}: must be an object")
        return None
    for field in sorted(required_fields - item.keys()):
        issues.append(f"{path}.{field}: required field is missing")
    for field in sorted(item.keys() - allowed_fields):
        issues.append(f"{path}.{field}: unknown field")
    if not _valid_id(item.get("id")):
        issues.append(f"{path}.id: must be a valid lowercase identifier")
    if not isinstance(item.get("title"), str) or not item.get("title", "").strip():
        issues.append(f"{path}.title: must be a non-empty string")
    if item.get("phase") not in _PHASE_IDS:
        issues.append(f"{path}.phase: unknown phase {item.get('phase')!r}")
    return item


def _validate_definition_fields(
    item: Mapping[str, Any],
    *,
    path: str,
    issues: list[str],
    allow_refinement_requirement: bool = True,
) -> None:
    definition_state = item.get("definition_state")
    if "definition_state" in item and definition_state not in DEFINITION_STATES:
        issues.append(
            f"{path}.definition_state: must be one of: "
            + ", ".join(DEFINITION_STATES)
        )
    if not allow_refinement_requirement:
        for field in ("refinement_required", "refinement_trigger"):
            if field in item:
                issues.append(
                    f"{path}.{field}: only Deliverables may declare refinement requirements"
                )
    else:
        if "refinement_required" in item and type(
            item.get("refinement_required")
        ) is not bool:
            issues.append(f"{path}.refinement_required: must be a boolean")
        if (
            item.get("definition_state") == "placeholder"
            and item.get("refinement_required") is not True
        ):
            issues.append(
                f"{path}.refinement_required: must be true when definition_state is placeholder"
            )
        if item.get("refinement_required") is True and "refinement_trigger" not in item:
            issues.append(
                f"{path}.refinement_trigger: required when refinement_required is true"
            )
        if "refinement_trigger" in item:
            issues.extend(
                validate_refinement_trigger(
                    item.get("refinement_trigger"), f"{path}.refinement_trigger"
                )
            )
    if "refines" in item and not _valid_id(item.get("refines")):
        issues.append(f"{path}.refines: must be a valid lowercase identifier")


def validate_process_extension(value: Any) -> list[str]:
    """Return stable issues for an additive project extension mapping."""

    if not isinstance(value, dict):
        return ["$: must be an object"]
    issues: list[str] = []
    allowed = {
        "schema_version",
        "extension_id",
        "activities",
        "deliverables",
        "dependencies",
        "checkpoint_criteria",
        "migrations",
        "refinement_requirements",
        "refinements",
    }
    required = {"schema_version", "extension_id"}
    for field in sorted(required - value.keys()):
        issues.append(f"$.{field}: required field is missing")
    for field in sorted(value.keys() - allowed):
        issues.append(f"$.{field}: unknown field")
    if value.get("schema_version") != PROCESS_EXTENSION_SCHEMA_VERSION:
        issues.append(
            "$.schema_version: must equal "
            f"{PROCESS_EXTENSION_SCHEMA_VERSION!r}"
        )
    if not _valid_id(value.get("extension_id")):
        issues.append("$.extension_id: must be a valid lowercase identifier")

    seen_ids: set[str] = set()
    activities = value.get("activities", [])
    if not isinstance(activities, list):
        issues.append("$.activities: must be an array")
        activities = []
    for index, raw in enumerate(activities):
        path = f"$.activities[{index}]"
        item = _validate_entity_common(
            raw,
            path=path,
            required_fields={"id", "title", "phase", "sequence"},
            allowed_fields={
                "id",
                "title",
                "phase",
                "sequence",
                "definition_state",
                "refinement_required",
                "refinement_trigger",
                "refines",
            },
            issues=issues,
        )
        if item is None:
            continue
        identifier = item.get("id")
        if isinstance(identifier, str):
            if identifier in seen_ids:
                issues.append(f"{path}.id: duplicate extension entity id {identifier!r}")
            seen_ids.add(identifier)
        if type(item.get("sequence")) is not int or item.get("sequence", -1) < 0:
            issues.append(f"{path}.sequence: must be a non-negative integer")
        _validate_definition_fields(
            item,
            path=path,
            issues=issues,
            allow_refinement_requirement=False,
        )

    deliverables = value.get("deliverables", [])
    if not isinstance(deliverables, list):
        issues.append("$.deliverables: must be an array")
        deliverables = []
    for index, raw in enumerate(deliverables):
        path = f"$.deliverables[{index}]"
        item = _validate_entity_common(
            raw,
            path=path,
            required_fields={
                "id",
                "title",
                "phase",
                "activity_id",
                "review_required",
                "depends_on",
            },
            allowed_fields={
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
            },
            issues=issues,
        )
        if item is None:
            continue
        identifier = item.get("id")
        if isinstance(identifier, str):
            if identifier in seen_ids:
                issues.append(f"{path}.id: duplicate extension entity id {identifier!r}")
            seen_ids.add(identifier)
        if not _valid_id(item.get("activity_id")):
            issues.append(f"{path}.activity_id: must be a valid lowercase identifier")
        if item.get("review_required") is not True:
            issues.append(f"{path}.review_required: must equal true")
        dependencies = item.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            _valid_id(dependency) for dependency in dependencies
        ):
            issues.append(f"{path}.depends_on: must be an array of identifiers")
        elif len(dependencies) != len(set(dependencies)):
            issues.append(f"{path}.depends_on: must not contain duplicates")
        if "requires_artifact_owner" in item and type(
            item.get("requires_artifact_owner")
        ) is not bool:
            issues.append(f"{path}.requires_artifact_owner: must be a boolean")
        _validate_definition_fields(item, path=path, issues=issues)

    dependencies = value.get("dependencies", [])
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
        if not _valid_id(source):
            issues.append(f"{path}.source: must be a valid lowercase identifier")
        if not _valid_id(target):
            issues.append(f"{path}.target: must be a valid lowercase identifier")
        if relation not in TRACE_RELATIONS:
            issues.append(
                f"{path}.relation: must be one of: {', '.join(TRACE_RELATIONS)}"
            )
        if isinstance(source, str) and isinstance(target, str) and isinstance(relation, str):
            edge = (source, target, relation)
            if edge in seen_edges:
                issues.append(f"{path}: duplicate typed dependency {edge!r}")
            seen_edges.add(edge)

    criteria = value.get("checkpoint_criteria", [])
    if not isinstance(criteria, list):
        issues.append("$.checkpoint_criteria: must be an array")
        criteria = []
    seen_criteria: set[str] = set()
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
        if not _valid_id(identifier):
            issues.append(f"{path}.id: must be a valid lowercase identifier")
        elif identifier in seen_criteria:
            issues.append(f"{path}.id: duplicate criterion id {identifier!r}")
        else:
            seen_criteria.add(identifier)
        checkpoint_id = criterion.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not re.fullmatch(
            r"(?:tr|dcp)\.(?:concept|plan|develop|qualify|launch|lifecycle)",
            checkpoint_id,
        ):
            issues.append(f"{path}.checkpoint_id: must reference a canonical TR or DCP")
        if not isinstance(criterion.get("description"), str) or not criterion.get(
            "description", ""
        ).strip():
            issues.append(f"{path}.description: must be a non-empty string")
        if criterion.get("evidence_required") is not True:
            issues.append(f"{path}.evidence_required: must equal true")

    migrations = value.get("migrations", [])
    if not isinstance(migrations, list):
        issues.append("$.migrations: must be an array")
        migrations = []
    seen_migrations: set[tuple[str, str]] = set()
    migration_targets_by_source: dict[str, set[str]] = defaultdict(set)
    migration_sources_by_target: dict[str, set[str]] = defaultdict(set)
    migration_strategies_by_source: dict[str, set[str]] = defaultdict(set)
    for index, migration in enumerate(migrations):
        path = f"$.migrations[{index}]"
        if not isinstance(migration, dict):
            issues.append(f"{path}: must be an object")
            continue
        fields = {"from", "to", "strategy", "reason", "preserve_history"}
        for field in sorted(fields - migration.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(migration.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        source = migration.get("from")
        target = migration.get("to")
        strategy = migration.get("strategy")
        if not _valid_id(source):
            issues.append(f"{path}.from: must be a valid lowercase identifier")
        if not _valid_id(target):
            issues.append(f"{path}.to: must be a valid lowercase identifier")
        if strategy not in MIGRATION_STRATEGIES:
            issues.append(
                f"{path}.strategy: must be one of: {', '.join(MIGRATION_STRATEGIES)}"
            )
        if not isinstance(migration.get("reason"), str) or not migration.get(
            "reason", ""
        ).strip():
            issues.append(f"{path}.reason: must be a non-empty string")
        if migration.get("preserve_history") is not True:
            issues.append(f"{path}.preserve_history: must equal true")
        if isinstance(source, str) and isinstance(target, str) and isinstance(strategy, str):
            key = (source, target)
            if key in seen_migrations:
                issues.append(f"{path}: duplicate migration mapping {key!r}")
            seen_migrations.add(key)
            migration_targets_by_source[source].add(target)
            migration_sources_by_target[target].add(source)
            migration_strategies_by_source[source].add(strategy)
    for source, targets in sorted(migration_targets_by_source.items()):
        strategies = migration_strategies_by_source[source]
        if len(strategies) > 1:
            issues.append(
                f"$.migrations: source {source!r} must use exactly one strategy"
            )
        if len(targets) > 1 and strategies != {"split"}:
            issues.append(
                f"$.migrations: source {source!r} with multiple targets must use split"
            )
    for target, sources in sorted(migration_sources_by_target.items()):
        if len(sources) > 1:
            issues.append(
                f"$.migrations: target {target!r} has multiple sources; merge is unsupported"
            )

    requirements = value.get("refinement_requirements", [])
    if not isinstance(requirements, list):
        issues.append("$.refinement_requirements: must be an array")
        requirements = []
    seen_requirement_roots: set[str] = set()
    for index, requirement in enumerate(requirements):
        path = f"$.refinement_requirements[{index}]"
        if not isinstance(requirement, dict):
            issues.append(f"{path}: must be an object")
            continue
        fields = {
            "root",
            "definition_state",
            "refinement_required",
            "trigger",
            "completion_policy",
        }
        for field in sorted(fields - requirement.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(requirement.keys() - fields):
            issues.append(f"{path}.{field}: unknown field")
        root = requirement.get("root")
        if not _valid_id(root):
            issues.append(f"{path}.root: must be a valid lowercase identifier")
        elif root in seen_requirement_roots:
            issues.append(f"{path}.root: duplicate refinement root {root!r}")
        else:
            seen_requirement_roots.add(root)
        if requirement.get("definition_state") not in {"concrete", "placeholder"}:
            issues.append(
                f"{path}.definition_state: must be concrete or placeholder"
            )
        if requirement.get("refinement_required") is not True:
            issues.append(f"{path}.refinement_required: must equal true")
        issues.extend(
            validate_refinement_trigger(requirement.get("trigger"), f"{path}.trigger")
        )
        if requirement.get("completion_policy") != "all_children_accepted":
            issues.append(
                f"{path}.completion_policy: must equal 'all_children_accepted'"
            )

    refinements = value.get("refinements", [])
    if not isinstance(refinements, list):
        issues.append("$.refinements: must be an array")
        refinements = []
    seen_refinement_ids: set[str] = set()
    seen_refinement_roots: set[str] = set()
    extension_deliverable_ids = {
        item.get("id")
        for item in deliverables
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for index, refinement in enumerate(refinements):
        path = f"$.refinements[{index}]"
        if not isinstance(refinement, dict):
            issues.append(f"{path}: must be an object")
            continue
        fields = {
            "id",
            "root",
            "mode",
            "base_process_fingerprint",
            "reason",
            "basis",
            "plan_digest",
            "children",
        }
        optional_fields = {
            "result_process_fingerprint",
            "invalidated_gates",
        }
        for field in sorted(fields - refinement.keys()):
            issues.append(f"{path}.{field}: required field is missing")
        for field in sorted(refinement.keys() - fields - optional_fields):
            issues.append(f"{path}.{field}: unknown field")
        identifier = refinement.get("id")
        root = refinement.get("root")
        if not _valid_id(identifier):
            issues.append(f"{path}.id: must be a valid lowercase identifier")
        elif identifier in seen_refinement_ids:
            issues.append(f"{path}.id: duplicate refinement id {identifier!r}")
        else:
            seen_refinement_ids.add(identifier)
        if not _valid_id(root):
            issues.append(f"{path}.root: must be a valid lowercase identifier")
        elif root in seen_refinement_roots:
            issues.append(f"{path}.root: root {root!r} is already expanded")
        else:
            seen_refinement_roots.add(root)
        if root not in seen_requirement_roots:
            issues.append(
                f"{path}.root: {root!r} has no declared refinement requirement"
            )
        if refinement.get("mode") != "expand":
            issues.append(f"{path}.mode: must equal 'expand'")
        for digest_field in ("base_process_fingerprint", "plan_digest"):
            digest = refinement.get(digest_field)
            if not isinstance(digest, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", digest
            ):
                issues.append(
                    f"{path}.{digest_field}: must use sha256:<64 lowercase hex>"
                )
        result_fingerprint = refinement.get("result_process_fingerprint")
        if result_fingerprint is not None and (
            not isinstance(result_fingerprint, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", result_fingerprint)
        ):
            issues.append(
                f"{path}.result_process_fingerprint: must use sha256:<64 lowercase hex>"
            )
        invalidated_gates = refinement.get("invalidated_gates")
        if invalidated_gates is not None:
            if not isinstance(invalidated_gates, list) or not all(
                _valid_id(item) for item in invalidated_gates
            ):
                issues.append(
                    f"{path}.invalidated_gates: must be an array of identifiers"
                )
            elif len(invalidated_gates) != len(set(invalidated_gates)):
                issues.append(
                    f"{path}.invalidated_gates: must not contain duplicates"
                )
        if not isinstance(refinement.get("reason"), str) or not refinement.get(
            "reason", ""
        ).strip():
            issues.append(f"{path}.reason: must be a non-empty string")
        basis = refinement.get("basis")
        if not isinstance(basis, list) or not basis or not all(
            isinstance(item, str) and item.strip() for item in basis
        ):
            issues.append(
                f"{path}.basis: must be a non-empty array of non-empty strings"
            )
        elif len(basis) != len(set(basis)):
            issues.append(f"{path}.basis: must not contain duplicates")
        children = refinement.get("children")
        if not isinstance(children, list) or not children or not all(
            _valid_id(item) for item in children
        ):
            issues.append(
                f"{path}.children: must be a non-empty array of identifiers"
            )
        elif len(children) != len(set(children)):
            issues.append(f"{path}.children: must not contain duplicates")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, str) and child not in extension_deliverable_ids:
                    issues.append(
                        f"{path}.children: references missing extension Deliverable "
                        f"{child!r}"
                    )
    parent_by_child = {
        item["id"]: item.get("refines")
        for item in deliverables
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("refines"), str)
    }
    for root in sorted(seen_requirement_roots - seen_refinement_roots):
        for child in sorted(parent_by_child):
            cursor = parent_by_child.get(child)
            seen_ancestors: set[str] = set()
            while isinstance(cursor, str) and cursor not in seen_ancestors:
                if cursor == root:
                    issues.append(
                        f"$.refinement_requirements: root {root!r} is "
                        "pre-expanded without an applied refinement record; "
                        "use ipdctl refine --apply with an authorized plan"
                    )
                    break
                seen_ancestors.add(cursor)
                cursor = parent_by_child.get(cursor)
            if any(
                issue.startswith(
                    f"$.refinement_requirements: root {root!r} is pre-expanded"
                )
                for issue in issues
            ):
                break
    return sorted(set(issues))


def load_process_extension(
    source: str | Path | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Load an extension from a path or mapping and return a normalized copy.

    ``None`` is the explicit no-extension value.  A supplied path must exist so
    misspelled authoritative inputs fail closed instead of being ignored.
    """

    if source is None:
        value: Any = {
            "schema_version": PROCESS_EXTENSION_SCHEMA_VERSION,
            "extension_id": "project",
        }
    elif isinstance(source, Mapping):
        value = deepcopy(dict(source))
    else:
        try:
            value = load_yaml(source)
        except YamlError as exc:
            raise ProcessExtensionError(str(exc)) from exc
    issues = validate_process_extension(value)
    if issues:
        raise ProcessExtensionError(
            "invalid process extension:\n- " + "\n- ".join(issues)
        )
    assert isinstance(value, dict)
    normalized = deepcopy(value)
    for field in (
        "activities",
        "deliverables",
        "dependencies",
        "checkpoint_criteria",
        "migrations",
        "refinement_requirements",
        "refinements",
    ):
        normalized.setdefault(field, [])
    return normalized


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    return sorted(
        key
        for key in set(before) | set(after)
        if _canonical(before.get(key)) != _canonical(after.get(key))
    )


def _indexed(collection: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    indexed: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    if not isinstance(collection, list):
        return indexed, duplicates
    for item in collection:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        identifier = item["id"]
        if identifier in indexed:
            duplicates.append(identifier)
        else:
            indexed[identifier] = item
    return indexed, sorted(set(duplicates))


def preview_process_diff(
    current: Mapping[str, Any] | None,
    candidate: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Return a deterministic, side-effect-free semantic process preview."""

    before = dict(current or {})
    after = dict(candidate)
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for collection in _COLLECTIONS:
        old_index, old_duplicates = _indexed(before.get(collection, []))
        new_index, new_duplicates = _indexed(after.get(collection, []))
        for identifier in old_duplicates:
            ambiguous.append(
                {
                    "kind": "duplicate_identifier",
                    "collection": collection,
                    "id": identifier,
                    "side": "current",
                }
            )
        for identifier in new_duplicates:
            ambiguous.append(
                {
                    "kind": "duplicate_identifier",
                    "collection": collection,
                    "id": identifier,
                    "side": "candidate",
                }
            )
        for identifier in sorted(new_index.keys() - old_index.keys()):
            added.append({"collection": collection, "id": identifier})
        for identifier in sorted(old_index.keys() - new_index.keys()):
            removed.append({"collection": collection, "id": identifier})
        for identifier in sorted(old_index.keys() & new_index.keys()):
            fields = _changed_fields(old_index[identifier], new_index[identifier])
            if fields:
                changed.append(
                    {"collection": collection, "id": identifier, "fields": fields}
                )

    def edge_key(edge: Any) -> str | None:
        if not isinstance(edge, dict):
            return None
        source = edge.get("source")
        target = edge.get("target")
        relation = edge.get("relation")
        if not all(isinstance(item, str) for item in (source, target, relation)):
            return None
        return f"{source}|{relation}|{target}"

    old_edges = {
        key: edge
        for edge in before.get("dependencies", [])
        if (key := edge_key(edge)) is not None
    }
    new_edges = {
        key: edge
        for edge in after.get("dependencies", [])
        if (key := edge_key(edge)) is not None
    }
    added.extend(
        {"collection": "dependencies", "id": key}
        for key in sorted(new_edges.keys() - old_edges.keys())
    )
    removed.extend(
        {"collection": "dependencies", "id": key}
        for key in sorted(old_edges.keys() - new_edges.keys())
    )
    for key in sorted(old_edges.keys() & new_edges.keys()):
        fields = _changed_fields(old_edges[key], new_edges[key])
        if fields:
            changed.append({"collection": "dependencies", "id": key, "fields": fields})

    migrations = sorted(
        (deepcopy(item) for item in after.get("migrations", []) if isinstance(item, dict)),
        key=_canonical,
    )
    targets_by_source: dict[str, set[str]] = defaultdict(set)
    sources_by_target: dict[str, set[str]] = defaultdict(set)
    mappings_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    strategies_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    candidate_deliverables, _ = _indexed(after.get("deliverables", []))
    for mapping in migrations:
        source = mapping.get("from")
        target = mapping.get("to")
        if isinstance(source, str) and isinstance(target, str):
            targets_by_source[source].add(target)
            sources_by_target[target].add(source)
            mappings_by_source[source].append(mapping)
            if isinstance(mapping.get("strategy"), str):
                strategies_by_pair[(source, target)].add(mapping["strategy"])
            if source == target:
                ambiguous.append(
                    {"kind": "self_mapping", "source": source, "target": target}
                )
            if target not in candidate_deliverables:
                ambiguous.append(
                    {"kind": "missing_target", "source": source, "target": target}
                )
            if source in candidate_deliverables:
                ambiguous.append(
                    {
                        "kind": "source_still_present",
                        "source": source,
                        "target": target,
                    }
                )
    for source, targets in sorted(targets_by_source.items()):
        source_strategies = {
            mapping.get("strategy")
            for mapping in mappings_by_source[source]
            if isinstance(mapping.get("strategy"), str)
        }
        if len(source_strategies) > 1:
            ambiguous.append(
                {
                    "kind": "mixed_strategy",
                    "source": source,
                    "strategies": sorted(source_strategies),
                }
            )
        if len(targets) > 1 and not all(
            mapping.get("strategy") == "split"
            for mapping in mappings_by_source[source]
        ):
            ambiguous.append(
                {"kind": "one_to_many", "source": source, "targets": sorted(targets)}
            )
    for (source, target), strategies in sorted(strategies_by_pair.items()):
        if len(strategies) > 1:
            ambiguous.append(
                {
                    "kind": "conflicting_mapping",
                    "source": source,
                    "target": target,
                    "strategies": sorted(strategies),
                }
            )
    for target, sources in sorted(sources_by_target.items()):
        if len(sources) > 1:
            ambiguous.append(
                {"kind": "many_to_one", "target": target, "sources": sorted(sources)}
            )
    migration_sources = set(targets_by_source)
    for item in removed:
        if item["collection"] == "deliverables" and item["id"] not in migration_sources:
            ambiguous.append(
                {"kind": "unmapped_removal", "collection": "deliverables", "id": item["id"]}
            )

    key = lambda item: _canonical(item)
    return {
        "added": sorted(added, key=key),
        "removed": sorted(removed, key=key),
        "changed": sorted(changed, key=key),
        "migrations": migrations,
        "ambiguous": sorted(ambiguous, key=key),
    }


__all__ = [
    "MIGRATION_STRATEGIES",
    "PROCESS_EXTENSION_SCHEMA_VERSION",
    "ProcessExtensionError",
    "load_process_extension",
    "preview_process_diff",
    "validate_process_extension",
]

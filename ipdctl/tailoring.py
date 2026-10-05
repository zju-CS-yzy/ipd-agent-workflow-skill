"""Compile task profiles into deterministic, auditable IPD processes."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .dependencies import find_cycle
from .model import TRACE_RELATIONS
from .process_model import (
    LEGACY_PROCESS_SCHEMA_VERSION,
    PHASE_MATURITY,
    PROCESS_SCHEMA_VERSION,
    SUPPORTED_PROCESS_SCHEMA_VERSIONS,
    ProcessModelError,
    base_activities,
    base_deliverables,
    load_capability_policy,
    load_task_type_policy,
    normalize_capability_patterns,
    normalize_task_types,
    phases,
)
from .process_extensions import (
    MIGRATION_STRATEGIES,
    ProcessExtensionError,
    load_process_extension,
    preview_process_diff,
)
from .refinement import (
    DEFINITION_STATES,
    RefinementPlanError,
    effective_gate_requirements,
    refinement_children,
    refinement_leaf_closure,
    validate_refinement_trigger,
)
from .yamlio import YamlError, load_yaml, write_yaml_atomic

PROFILE_SCHEMA_VERSION = "1.0"
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class TailoringError(ValueError):
    """Raised when a task profile cannot produce a valid process."""


def _profile_name(profile: dict[str, Any]) -> str:
    project = profile.get("project")
    if project is not None and not isinstance(project, dict):
        raise TailoringError("$.project: must be an object")
    candidates = [
        profile.get("project_name"),
        profile.get("name"),
        project.get("name") if isinstance(project, dict) else None,
    ]
    name = next((candidate for candidate in candidates if candidate is not None), "ipd-project")
    if not isinstance(name, str) or not name.strip():
        raise TailoringError("project name must be a non-empty string")
    return name.strip()


def _profile_task_types(profile: dict[str, Any]) -> tuple[str, ...]:
    supplied: list[str] = []
    if "task_type" in profile:
        supplied.append(profile["task_type"])
    if "task_types" in profile:
        values = profile["task_types"]
        if isinstance(values, str):
            supplied.append(values)
        elif isinstance(values, (list, tuple)):
            supplied.extend(values)
        else:
            raise TailoringError("$.task_types: must be a string or an array of strings")
    if not supplied:
        raise TailoringError("task profile must define task_type or task_types")
    try:
        return normalize_task_types(supplied)
    except ProcessModelError as exc:
        raise TailoringError(str(exc)) from exc


def _profile_capability_patterns(profile: dict[str, Any]) -> tuple[str, ...]:
    supplied = profile.get("capability_patterns", [])
    try:
        return normalize_capability_patterns(supplied)
    except ProcessModelError as exc:
        raise TailoringError(str(exc)) from exc


def load_profile(path: str | Path) -> dict[str, Any]:
    """Load and validate the reusable portion of a task profile contract."""

    try:
        value = load_yaml(path)
    except YamlError as exc:
        raise TailoringError(str(exc)) from exc
    if not isinstance(value, dict):
        raise TailoringError(f"task profile root must be an object: {path}")
    version = value.get("schema_version", PROFILE_SCHEMA_VERSION)
    if version != PROFILE_SCHEMA_VERSION:
        raise TailoringError(
            f"$.schema_version: must equal {PROFILE_SCHEMA_VERSION!r}"
        )
    _profile_name(value)
    _profile_task_types(value)
    _profile_capability_patterns(value)
    return value


def _provenance(layer: str, source_id: str) -> dict[str, str]:
    return {"layer": layer, "source_id": source_id}


def _annotate_node(
    node: Mapping[str, Any],
    *,
    layer: str,
    source_id: str,
) -> dict[str, Any]:
    result = deepcopy(dict(node))
    result["provenance"] = _provenance(layer, source_id)
    phase_id = result.get("phase", result.get("id"))
    result["maturity"] = PHASE_MATURITY[phase_id]
    return result


def _checkpoint(
    *,
    prefix: str,
    label: str,
    phase: dict[str, Any],
    required: list[str],
    criteria: list[dict[str, Any]],
) -> dict[str, Any]:
    phase_id = phase["id"]
    return {
        "id": f"{prefix}.{phase_id}",
        "title": f"{phase['title']} {label}",
        "phase": phase_id,
        "sequence": phase["sequence"],
        "gate_id": f"gate.{prefix}.{phase_id}",
        "required_deliverables": list(required),
        "criteria": deepcopy(criteria),
        "provenance": _provenance("core", "ipd-core"),
        "maturity": PHASE_MATURITY[phase_id],
    }


def _gate(checkpoint: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "id": checkpoint["gate_id"],
        "title": checkpoint["title"],
        "kind": kind,
        "phase": checkpoint["phase"],
        "checkpoint_id": checkpoint["id"],
        "required_deliverables": list(checkpoint["required_deliverables"]),
        "review_required": True,
        "final_approval": "authorized_human",
        "provenance": deepcopy(checkpoint["provenance"]),
        "maturity": checkpoint["maturity"],
    }


def _append_unique_entities(
    target: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    collection: str,
) -> None:
    existing = {item["id"] for item in target}
    for item in incoming:
        identifier = item["id"]
        if identifier in existing:
            raise TailoringError(
                f"$.{collection}: extension cannot replace existing id {identifier!r}"
            )
        target.append(item)
        existing.add(identifier)


def _core_checkpoint_criteria(prefix: str, phase: dict[str, Any]) -> list[dict[str, Any]]:
    if prefix == "tr":
        description = (
            f"Technical evidence demonstrates {phase['title'].lower()} phase readiness."
        )
    else:
        description = (
            f"An authorized decision confirms {phase['title'].lower()} phase readiness."
        )
    return [
        {
            "id": f"criterion.{prefix}.{phase['id']}.readiness",
            "description": description,
            "evidence_required": True,
        }
    ]


def _assemble(
    profile: dict[str, Any],
    task_types: tuple[str, ...],
    capability_patterns: tuple[str, ...],
    process_extension: str | Path | Mapping[str, Any] | None,
) -> dict[str, Any]:
    process_phases = [
        _annotate_node(phase, layer="core", source_id="ipd-core")
        for phase in phases()
    ]
    activities = [
        _annotate_node(item, layer="core", source_id="ipd-core")
        for item in base_activities()
    ]
    deliverables = [
        _annotate_node(item, layer="core", source_id="ipd-core")
        for item in base_deliverables()
    ]
    explicit_relations: list[dict[str, Any]] = []
    checkpoint_criteria: list[dict[str, Any]] = []

    # Merge order is a public invariant: core -> task type -> capability -> project.
    for task_type in task_types:
        policy = load_task_type_policy(task_type)
        _append_unique_entities(
            activities,
            [
                _annotate_node(item, layer="task_type", source_id=task_type)
                for item in policy["activities"]
            ],
            collection="activities",
        )
        _append_unique_entities(
            deliverables,
            [
                _annotate_node(item, layer="task_type", source_id=task_type)
                for item in policy["deliverables"]
            ],
            collection="deliverables",
        )

    for pattern in capability_patterns:
        policy = load_capability_policy(pattern)
        _append_unique_entities(
            activities,
            [
                _annotate_node(item, layer="capability", source_id=pattern)
                for item in policy["activities"]
            ],
            collection="activities",
        )
        _append_unique_entities(
            deliverables,
            [
                _annotate_node(item, layer="capability", source_id=pattern)
                for item in policy["deliverables"]
            ],
            collection="deliverables",
        )
        explicit_relations.extend(
            {
                **deepcopy(item),
                "provenance": _provenance("capability", pattern),
            }
            for item in policy["dependencies"]
        )
        checkpoint_criteria.extend(deepcopy(policy["checkpoint_criteria"]))

    try:
        extension = load_process_extension(process_extension)
    except ProcessExtensionError as exc:
        raise TailoringError(str(exc)) from exc
    extension_id = extension["extension_id"]
    _append_unique_entities(
        activities,
        [
            _annotate_node(item, layer="project", source_id=extension_id)
            for item in extension["activities"]
        ],
        collection="activities",
    )
    _append_unique_entities(
        deliverables,
        [
            _annotate_node(item, layer="project", source_id=extension_id)
            for item in extension["deliverables"]
        ],
        collection="deliverables",
    )
    explicit_relations.extend(
        {
            **deepcopy(item),
            "provenance": _provenance("project", extension_id),
        }
        for item in extension["dependencies"]
    )
    checkpoint_criteria.extend(deepcopy(extension["checkpoint_criteria"]))

    activity_by_id = {item["id"]: item for item in activities}
    deliverable_by_id = {item["id"]: item for item in deliverables}

    # A typed refines relation is structural only.  Normalize it onto the
    # source node so every downstream consumer sees one canonical hierarchy.
    for relation in explicit_relations:
        if relation["relation"] != "refines":
            continue
        source_id = relation["source"]
        target_id = relation["target"]
        if source_id in deliverable_by_id and target_id in deliverable_by_id:
            source = deliverable_by_id[source_id]
        elif source_id in activity_by_id and target_id in activity_by_id:
            source = activity_by_id[source_id]
        else:
            raise TailoringError(
                "$.dependencies: refines must connect two Activities or two "
                f"Deliverables, got {source_id!r} -> {target_id!r}"
            )
        if source.get("provenance") != relation.get("provenance"):
            raise TailoringError(
                "$.dependencies: an additive layer cannot assign refines to "
                f"an earlier-layer entity {source_id!r}"
            )
        existing_parent = source.get("refines")
        if existing_parent is not None and existing_parent != target_id:
            raise TailoringError(
                f"refinement child {source_id!r} declares conflicting parents "
                f"{existing_parent!r} and {target_id!r}"
            )
        source["refines"] = target_id

    requirements_by_root: dict[str, dict[str, Any]] = {}
    for requirement in extension["refinement_requirements"]:
        root_id = requirement["root"]
        root = deliverable_by_id.get(root_id)
        if root is None:
            raise TailoringError(
                f"$.refinement_requirements: root {root_id!r} must reference "
                "an existing Deliverable"
            )
        requirements_by_root[root_id] = requirement
        root["definition_state"] = requirement["definition_state"]
        root["refinement_required"] = True
        root["refinement_trigger"] = deepcopy(requirement["trigger"])
        root["completion_policy"] = requirement["completion_policy"]

    applied_refinement_roots: set[str] = set()
    for applied in extension["refinements"]:
        root_id = applied["root"]
        applied_refinement_roots.add(root_id)
        root = deliverable_by_id.get(root_id)
        if root is None or root_id not in requirements_by_root:
            raise TailoringError(
                f"$.refinements: applied root {root_id!r} has no existing "
                "Deliverable refinement requirement"
            )
        root["definition_state"] = "abstract"
        missing_children = sorted(
            set(applied["children"]) - set(deliverable_by_id)
        )
        if missing_children:
            raise TailoringError(
                f"$.refinements: {applied['id']!r} references missing children "
                f"{missing_children!r}"
            )

    for root_id in sorted(requirements_by_root):
        if (
            refinement_children(deliverables, root_id)
            and root_id not in applied_refinement_roots
        ):
            raise TailoringError(
                f"refinement requirement root {root_id!r} is pre-expanded "
                "without an applied refinement record"
            )

    # Materialize node-level structural relationships as typed trace edges.
    structural_relations: list[dict[str, Any]] = []
    for collection in (activities, deliverables):
        by_id = {item["id"]: item for item in collection}
        for item in collection:
            parent = item.get("refines")
            if parent is None:
                continue
            if parent not in by_id:
                raise TailoringError(
                    f"refinement child {item['id']!r} references unknown "
                    f"same-kind parent {parent!r}"
                )
            if item.get("phase") != by_id[parent].get("phase"):
                raise TailoringError(
                    f"refinement child {item['id']!r} must remain in parent "
                    f"phase {by_id[parent].get('phase')!r}"
                )
            structural_relations.append(
                {
                    "source": item["id"],
                    "target": parent,
                    "relation": "refines",
                    "provenance": deepcopy(item["provenance"]),
                }
            )

    # Validate the Deliverable hierarchy before using leaf closure in Gates or
    # execution dependency expansion.
    try:
        for deliverable in deliverables:
            if deliverable.get("refines") is not None:
                refinement_leaf_closure(deliverables, deliverable["id"])
        for root_id in requirements_by_root:
            if deliverable_by_id[root_id].get("definition_state") == "abstract":
                children = refinement_children(deliverables, root_id)
                if not children:
                    raise TailoringError(
                        f"expanded abstract root {root_id!r} must have refinement children"
                    )
    except RefinementPlanError as exc:
        raise TailoringError(str(exc)) from exc

    explicit_dependency_provenance: dict[
        tuple[str, str, str], dict[str, str]
    ] = {}
    for relation in explicit_relations:
        if relation["relation"] != "depends_on":
            continue
        source = deliverable_by_id.get(relation["source"])
        if source is None:
            continue
        target = relation["target"]
        if target not in source["depends_on"]:
            source["depends_on"].append(target)
            explicit_dependency_provenance[
                (relation["source"], target, "depends_on")
            ] = deepcopy(relation["provenance"])

    # Execution dependencies targeting an expanded aggregate are rewritten to
    # its concrete leaf closure. Structural refines edges never enter this list.
    for deliverable in deliverables:
        expanded_dependencies: list[str] = []
        for prerequisite in deliverable["depends_on"]:
            target = deliverable_by_id.get(prerequisite)
            replacements = [prerequisite]
            if target is not None and target.get("definition_state") == "abstract":
                try:
                    replacements = refinement_leaf_closure(deliverables, prerequisite)
                except RefinementPlanError as exc:
                    raise TailoringError(str(exc)) from exc
            provenance = explicit_dependency_provenance.get(
                (deliverable["id"], prerequisite, "depends_on")
            )
            for replacement in replacements:
                if replacement not in expanded_dependencies:
                    expanded_dependencies.append(replacement)
                if provenance is not None:
                    explicit_dependency_provenance[
                        (deliverable["id"], replacement, "depends_on")
                    ] = deepcopy(provenance)
        deliverable["depends_on"] = expanded_dependencies

    criteria_by_checkpoint: dict[str, list[dict[str, Any]]] = {
        f"{prefix}.{phase['id']}": _core_checkpoint_criteria(prefix, phase)
        for prefix in ("tr", "dcp")
        for phase in process_phases
    }
    seen_criteria = {
        criterion["id"]
        for criteria in criteria_by_checkpoint.values()
        for criterion in criteria
    }
    for criterion in checkpoint_criteria:
        identifier = criterion["id"]
        if identifier in seen_criteria:
            raise TailoringError(
                f"$.checkpoint_criteria: extension cannot replace criterion {identifier!r}"
            )
        seen_criteria.add(identifier)
        rendered = {
            key: deepcopy(value)
            for key, value in criterion.items()
            if key != "checkpoint_id"
        }
        criteria_by_checkpoint[criterion["checkpoint_id"]].append(rendered)

    deliverables_by_phase = {
        phase["id"]: effective_gate_requirements(
            [
                item["id"]
                for item in deliverables
                if item["phase"] == phase["id"]
            ],
            deliverables,
        )
        for phase in process_phases
    }
    technical_reviews = [
        _checkpoint(
            prefix="tr",
            label="Technical Review",
            phase=phase,
            required=deliverables_by_phase[phase["id"]],
            criteria=criteria_by_checkpoint[f"tr.{phase['id']}"],
        )
        for phase in process_phases
    ]
    decision_checkpoints = [
        _checkpoint(
            prefix="dcp",
            label="Decision Checkpoint",
            phase=phase,
            required=deliverables_by_phase[phase["id"]],
            criteria=criteria_by_checkpoint[f"dcp.{phase['id']}"],
        )
        for phase in process_phases
    ]

    gates: list[dict[str, Any]] = []
    for tr, dcp in zip(technical_reviews, decision_checkpoints):
        gates.append(_gate(tr, "TR"))
        gates.append(_gate(dcp, "DCP"))

    dependencies = [
        {
            "source": deliverable["id"],
            "target": prerequisite,
            "relation": "depends_on",
            "provenance": deepcopy(
                explicit_dependency_provenance.get(
                    (deliverable["id"], prerequisite, "depends_on"),
                    deliverable["provenance"],
                )
            ),
        }
        for deliverable in deliverables
        for prerequisite in deliverable["depends_on"]
    ]
    dependency_keys = {
        (item["source"], item["target"], item["relation"])
        for item in dependencies
    }
    for relation in [*explicit_relations, *structural_relations]:
        if relation["relation"] == "depends_on":
            continue
        key = (relation["source"], relation["target"], relation["relation"])
        if key not in dependency_keys:
            dependencies.append(relation)
            dependency_keys.add(key)

    review_requirements = [
        {
            "id": f"review.{deliverable['id']}",
            "subject_type": "deliverable",
            "subject_id": deliverable["id"],
            "reviewer_type": "human",
            "authorization_required": True,
            "decision_required": True,
        }
        for deliverable in deliverables
        if deliverable["review_required"]
    ]
    review_requirements.extend(
        {
            "id": f"review.{gate['id']}",
            "subject_type": "gate",
            "subject_id": gate["id"],
            "reviewer_type": "human",
            "authorization_required": True,
            "decision_required": True,
        }
        for gate in gates
    )

    return {
        "schema_version": PROCESS_SCHEMA_VERSION,
        "profile": {
            "name": _profile_name(profile),
            "task_types": list(task_types),
            "capability_patterns": list(capability_patterns),
        },
        "phases": process_phases,
        "technical_reviews": technical_reviews,
        "decision_checkpoints": decision_checkpoints,
        "gates": gates,
        "activities": activities,
        "deliverables": deliverables,
        "dependencies": dependencies,
        "review_requirements": review_requirements,
        "migrations": deepcopy(extension["migrations"]),
        "refinements": deepcopy(extension["refinements"]),
    }


def _duplicate_ids(items: list[dict[str, Any]]) -> list[str]:
    counts = Counter(item.get("id") for item in items if isinstance(item.get("id"), str))
    return sorted(identifier for identifier, count in counts.items() if count > 1)


def _required_deliverable_issues(
    *,
    path: str,
    required: Any,
    expected: set[str],
    deliverable_ids: set[str],
) -> list[str]:
    """Validate the complete, duplicate-free deliverable set for a phase control."""

    if not isinstance(required, list) or not all(
        isinstance(identifier, str) and identifier.strip()
        for identifier in required
    ):
        return [f"{path}: must be an array of non-empty strings"]

    issues: list[str] = []
    if len(required) != len(set(required)):
        issues.append(f"{path}: must not contain duplicates")
    for identifier in required:
        if identifier not in deliverable_ids:
            issues.append(
                f"{path}: references unknown deliverable {identifier!r}"
            )

    actual = set(required)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        detail: list[str] = []
        if missing:
            detail.append(f"missing {missing!r}")
        if unexpected:
            detail.append(f"unexpected {unexpected!r}")
        issues.append(
            f"{path}: must equal the complete deliverable set for its phase"
            + (f" ({'; '.join(detail)})" if detail else "")
        )
    return issues


def _provenance_issues(path: str, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return [f"{path}: must be an object"]
    issues: list[str] = []
    fields = {"layer", "source_id"}
    for field in sorted(fields - value.keys()):
        issues.append(f"{path}.{field}: required field is missing")
    for field in sorted(value.keys() - fields):
        issues.append(f"{path}.{field}: unknown field")
    if value.get("layer") not in {"core", "task_type", "capability", "project"}:
        issues.append(
            f"{path}.layer: must be core, task_type, capability, or project"
        )
    source_id = value.get("source_id")
    if not isinstance(source_id, str) or not _ID_PATTERN.fullmatch(source_id):
        issues.append(f"{path}.source_id: must be a valid lowercase identifier")
    return issues


def _criterion_issues(path: str, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return [f"{path}: must be an object"]
    issues: list[str] = []
    fields = {"id", "description", "evidence_required"}
    for field in sorted(fields - value.keys()):
        issues.append(f"{path}.{field}: required field is missing")
    for field in sorted(value.keys() - fields):
        issues.append(f"{path}.{field}: unknown field")
    identifier = value.get("id")
    if not isinstance(identifier, str) or not _ID_PATTERN.fullmatch(identifier):
        issues.append(f"{path}.id: must be a valid lowercase identifier")
    if not isinstance(value.get("description"), str) or not value.get(
        "description", ""
    ).strip():
        issues.append(f"{path}.description: must be a non-empty string")
    if value.get("evidence_required") is not True:
        issues.append(f"{path}.evidence_required: must equal true")
    return issues


def validate_process(value: Any) -> list[str]:
    """Validate structural references and dependency invariants in a process."""

    issues: list[str] = []
    if not isinstance(value, dict):
        return ["$: must be an object"]
    version = value.get("schema_version")
    is_v2 = version == PROCESS_SCHEMA_VERSION
    required_top_fields = {
        "schema_version",
        "profile",
        "phases",
        "technical_reviews",
        "decision_checkpoints",
        "gates",
        "activities",
        "deliverables",
        "dependencies",
        "review_requirements",
    }
    top_fields = set(required_top_fields)
    # An empty field is tolerated in a mechanically projected legacy process;
    # schema 1.0 still cannot carry applied refinement facts.
    top_fields.add("refinements")
    if is_v2:
        top_fields.add("migrations")
        required_top_fields.add("migrations")
        top_fields.add("refinements")
    for field in sorted(required_top_fields - value.keys()):
        issues.append(f"$.{field}: required field is missing")
    for field in sorted(value.keys() - top_fields):
        issues.append(f"$.{field}: unknown field")
    if version not in SUPPORTED_PROCESS_SCHEMA_VERSIONS:
        rendered = ", ".join(repr(item) for item in SUPPORTED_PROCESS_SCHEMA_VERSIONS)
        issues.append(f"$.schema_version: must equal one of: {rendered}")

    profile = value.get("profile")
    if not isinstance(profile, dict):
        issues.append("$.profile: must be an object")
    else:
        allowed_profile_fields = {"name", "task_types"}
        if is_v2:
            allowed_profile_fields.add("capability_patterns")
        for field in sorted(profile.keys() - allowed_profile_fields):
            issues.append(f"$.profile.{field}: unknown field")
        if not isinstance(profile.get("name"), str) or not profile.get("name", "").strip():
            issues.append("$.profile.name: must be a non-empty string")
        raw_task_types = profile.get("task_types")
        if not isinstance(raw_task_types, list):
            issues.append("$.profile.task_types: must be an array")
        else:
            try:
                normalized = normalize_task_types(raw_task_types)
                if list(normalized) != raw_task_types:
                    issues.append("$.profile.task_types: must use canonical order and names")
            except ProcessModelError as exc:
                issues.append(f"$.profile.task_types: {exc}")
        if is_v2:
            raw_patterns = profile.get("capability_patterns")
            if not isinstance(raw_patterns, list):
                issues.append("$.profile.capability_patterns: must be an array")
            else:
                try:
                    normalized_patterns = normalize_capability_patterns(raw_patterns)
                    if list(normalized_patterns) != raw_patterns:
                        issues.append(
                            "$.profile.capability_patterns: must use canonical order and names"
                        )
                except ProcessModelError as exc:
                    issues.append(f"$.profile.capability_patterns: {exc}")

    collections: dict[str, list[dict[str, Any]]] = {}
    for field in (
        "phases",
        "technical_reviews",
        "decision_checkpoints",
        "gates",
        "activities",
        "deliverables",
        "dependencies",
        "review_requirements",
    ):
        collection = value.get(field)
        if not isinstance(collection, list):
            issues.append(f"$.{field}: must be an array")
            collections[field] = []
        else:
            bad = [index for index, item in enumerate(collection) if not isinstance(item, dict)]
            issues.extend(f"$.{field}[{index}]: must be an object" for index in bad)
            collections[field] = [item for item in collection if isinstance(item, dict)]

    expected_phase_contract = [
        (item["id"], item["sequence"]) for item in phases()
    ]
    actual_phase_contract = [
        (item.get("id"), item.get("sequence")) for item in collections["phases"]
    ]
    if actual_phase_contract != expected_phase_contract:
        issues.append(
            "$.phases: must preserve the canonical concept-to-lifecycle order and sequence"
        )

    for field in (
        "phases",
        "technical_reviews",
        "decision_checkpoints",
        "gates",
        "activities",
        "deliverables",
        "review_requirements",
    ):
        for duplicate in _duplicate_ids(collections[field]):
            issues.append(f"$.{field}: duplicate id {duplicate!r}")
        for index, item in enumerate(collections[field]):
            identifier = item.get("id")
            if not isinstance(identifier, str) or not _ID_PATTERN.fullmatch(identifier):
                issues.append(f"$.{field}[{index}].id: must be a valid lowercase identifier")
            if is_v2 and field != "review_requirements":
                path = f"$.{field}[{index}]"
                issues.extend(_provenance_issues(f"{path}.provenance", item.get("provenance")))
                phase_id = item.get("id") if field == "phases" else item.get("phase")
                expected_maturity = PHASE_MATURITY.get(phase_id)
                if item.get("maturity") != expected_maturity:
                    issues.append(
                        f"{path}.maturity: must equal {expected_maturity!r} for phase {phase_id!r}"
                    )

    phase_ids = {
        item["id"] for item in collections["phases"] if isinstance(item.get("id"), str)
    }
    activity_ids = {
        item["id"]
        for item in collections["activities"]
        if isinstance(item.get("id"), str)
    }
    deliverable_ids = {
        item["id"]
        for item in collections["deliverables"]
        if isinstance(item.get("id"), str)
    }
    gate_ids = {
        item["id"] for item in collections["gates"] if isinstance(item.get("id"), str)
    }
    tr_ids = {
        item["id"]
        for item in collections["technical_reviews"]
        if isinstance(item.get("id"), str)
    }
    dcp_ids = {
        item["id"]
        for item in collections["decision_checkpoints"]
        if isinstance(item.get("id"), str)
    }
    all_entity_ids = phase_ids | activity_ids | deliverable_ids | gate_ids | tr_ids | dcp_ids
    refinement_trigger_records: list[
        tuple[str, str | None, str | None, str, str, str]
    ] = []

    for field in ("activities", "deliverables"):
        entity_ids = activity_ids if field == "activities" else deliverable_ids
        entity_by_id = {
            item["id"]: item
            for item in collections[field]
            if isinstance(item.get("id"), str)
        }
        parent_by_child: dict[str, str] = {}
        for index, item in enumerate(collections[field]):
            path = f"$.{field}[{index}]"
            identifier = item.get("id")
            definition_state = item.get("definition_state")
            if "definition_state" in item and definition_state not in DEFINITION_STATES:
                issues.append(
                    f"{path}.definition_state: must be one of: "
                    + ", ".join(DEFINITION_STATES)
                )
            if field == "activities":
                for refinement_field in (
                    "refinement_required",
                    "refinement_trigger",
                ):
                    if refinement_field in item:
                        issues.append(
                            f"{path}.{refinement_field}: only Deliverables may declare "
                            "refinement requirements"
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
                    trigger = item.get("refinement_trigger")
                    issues.extend(
                        validate_refinement_trigger(trigger, f"{path}.refinement_trigger")
                    )
                    if isinstance(trigger, dict) and isinstance(trigger.get("all_of"), list):
                        for clause_index, clause in enumerate(trigger["all_of"]):
                            if not isinstance(clause, dict):
                                continue
                            subject = clause.get("subject")
                            condition = clause.get("condition")
                            if subject not in all_entity_ids:
                                issues.append(
                                    f"{path}.refinement_trigger.all_of[{clause_index}].subject: "
                                    f"references unknown entity {subject!r}"
                                )
                            if (
                                isinstance(identifier, str)
                                and isinstance(subject, str)
                                and isinstance(condition, str)
                            ):
                                refinement_trigger_records.append(
                                    (
                                        identifier,
                                        item.get("phase"),
                                        item.get("definition_state"),
                                        subject,
                                        condition,
                                        f"{path}.refinement_trigger.all_of[{clause_index}]",
                                    )
                                )
            parent = item.get("refines")
            if parent is not None:
                if not isinstance(parent, str) or not _ID_PATTERN.fullmatch(parent):
                    issues.append(
                        f"{path}.refines: must be a valid lowercase identifier"
                    )
                elif parent not in entity_ids:
                    issues.append(
                        f"{path}.refines: references unknown same-kind parent {parent!r}"
                    )
                elif parent == identifier:
                    issues.append(f"{path}.refines: cannot refine itself")
                elif isinstance(identifier, str):
                    parent_by_child[identifier] = parent
                    if item.get("phase") != entity_by_id[parent].get("phase"):
                        issues.append(
                            f"{path}.phase: refinement child must remain in parent "
                            f"phase {entity_by_id[parent].get('phase')!r}"
                        )
            if field == "deliverables":
                if "completion_policy" in item and item.get(
                    "completion_policy"
                ) != "all_children_accepted":
                    issues.append(
                        f"{path}.completion_policy: must equal 'all_children_accepted'"
                    )
                if "requires_artifact_owner" in item and type(
                    item.get("requires_artifact_owner")
                ) is not bool:
                    issues.append(
                        f"{path}.requires_artifact_owner: must be a boolean"
                    )

        for child in sorted(parent_by_child):
            seen: list[str] = []
            cursor = child
            while cursor in parent_by_child:
                if cursor in seen:
                    issues.append(
                        f"$.{field}: refinement cycle detected: "
                        + " -> ".join((*seen, cursor))
                    )
                    break
                seen.append(cursor)
                cursor = parent_by_child[cursor]

        children_by_parent = {
            parent
            for parent in parent_by_child.values()
        }
        for index, item in enumerate(collections[field]):
            if (
                item.get("definition_state") == "abstract"
                and item.get("id") not in children_by_parent
            ):
                issues.append(
                    f"$.{field}[{index}]: abstract node must have refinement children"
                )

    canonical_phases = phases()
    try:
        deliverables_by_phase = {
            phase["id"]: set(
                effective_gate_requirements(
                    [
                        item["id"]
                        for item in collections["deliverables"]
                        if isinstance(item.get("id"), str)
                        and item.get("phase") == phase["id"]
                    ],
                    collections["deliverables"],
                )
            )
            for phase in canonical_phases
        }
    except RefinementPlanError as exc:
        issues.append(f"$.deliverables: {exc}")
        deliverables_by_phase = {
            phase["id"]: {
                item["id"]
                for item in collections["deliverables"]
                if isinstance(item.get("id"), str)
                and item.get("phase") == phase["id"]
            }
            for phase in canonical_phases
        }

    checkpoint_specs = (
        ("technical_reviews", "tr"),
        ("decision_checkpoints", "dcp"),
    )
    checkpoint_by_id: dict[str, dict[str, Any]] = {}
    seen_criterion_ids: set[str] = set()
    for field, prefix in checkpoint_specs:
        expected_ids = {f"{prefix}.{phase['id']}" for phase in canonical_phases}
        for index, checkpoint in enumerate(collections[field]):
            identifier = checkpoint.get("id")
            if isinstance(identifier, str):
                checkpoint_by_id.setdefault(identifier, checkpoint)
                if identifier not in expected_ids:
                    issues.append(
                        f"$.{field}[{index}].id: only canonical {prefix.upper()} "
                        "checkpoints are allowed"
                    )

        for phase in canonical_phases:
            phase_id = phase["id"]
            checkpoint_id = f"{prefix}.{phase_id}"
            gate_id = f"gate.{checkpoint_id}"
            matching = [
                (index, item)
                for index, item in enumerate(collections[field])
                if item.get("id") == checkpoint_id
            ]
            if not matching:
                issues.append(
                    f"$.{field}: missing canonical checkpoint {checkpoint_id!r}"
                )
                continue

            index, checkpoint = matching[0]
            path = f"$.{field}[{index}]"
            if checkpoint.get("phase") != phase_id:
                issues.append(f"{path}.phase: must equal {phase_id!r}")
            if checkpoint.get("sequence") != phase["sequence"]:
                issues.append(
                    f"{path}.sequence: must equal canonical phase sequence "
                    f"{phase['sequence']!r}"
                )
            if checkpoint.get("gate_id") != gate_id:
                issues.append(f"{path}.gate_id: must equal {gate_id!r}")
            issues.extend(
                _required_deliverable_issues(
                    path=f"{path}.required_deliverables",
                    required=checkpoint.get("required_deliverables"),
                    expected=deliverables_by_phase[phase_id],
                    deliverable_ids=deliverable_ids,
                )
            )
            criteria = checkpoint.get("criteria")
            if is_v2 and (not isinstance(criteria, list) or not criteria):
                issues.append(f"{path}.criteria: must be a non-empty array")
                criteria = []
            elif criteria is None and not is_v2:
                criteria = []
            elif not isinstance(criteria, list):
                issues.append(f"{path}.criteria: must be an array")
                criteria = []
            for criterion_index, criterion in enumerate(criteria):
                criterion_path = f"{path}.criteria[{criterion_index}]"
                issues.extend(_criterion_issues(criterion_path, criterion))
                if isinstance(criterion, dict) and isinstance(criterion.get("id"), str):
                    criterion_id = criterion["id"]
                    if criterion_id in seen_criterion_ids:
                        issues.append(
                            f"{criterion_path}.id: duplicate checkpoint criterion id {criterion_id!r}"
                        )
                    seen_criterion_ids.add(criterion_id)

    gate_by_id = {
        item["id"]: item
        for item in collections["gates"]
        if isinstance(item.get("id"), str)
    }
    canonical_gate_ids: set[str] = set()
    for phase in canonical_phases:
        phase_id = phase["id"]
        for prefix, kind in (("tr", "TR"), ("dcp", "DCP")):
            checkpoint_id = f"{prefix}.{phase_id}"
            gate_id = f"gate.{checkpoint_id}"
            canonical_gate_ids.add(gate_id)
            gate = gate_by_id.get(gate_id)
            if gate is None:
                issues.append(f"$.gates: missing canonical gate {gate_id!r}")
                continue

            index = next(
                index
                for index, item in enumerate(collections["gates"])
                if item.get("id") == gate_id
            )
            path = f"$.gates[{index}]"
            if gate.get("kind") != kind:
                issues.append(f"{path}.kind: must equal {kind!r}")
            if gate.get("phase") != phase_id:
                issues.append(f"{path}.phase: must equal {phase_id!r}")
            if gate.get("checkpoint_id") != checkpoint_id:
                issues.append(
                    f"{path}.checkpoint_id: must equal {checkpoint_id!r}"
                )

    expected_canonical_gate_order = [
        f"gate.{prefix}.{phase['id']}"
        for phase in canonical_phases
        for prefix in ("tr", "dcp")
    ]
    actual_canonical_gate_order = [
        item.get("id")
        for item in collections["gates"]
        if item.get("id") in canonical_gate_ids
    ]
    if actual_canonical_gate_order != expected_canonical_gate_order:
        issues.append(
            "$.gates: must preserve canonical phase order with TR before DCP"
        )

    gate_positions = {
        item.get("id"): index
        for index, item in enumerate(collections["gates"])
        if isinstance(item.get("id"), str)
    }
    for phase in canonical_phases:
        phase_id = phase["id"]
        canonical_positions = [
            gate_positions[identifier]
            for identifier in (f"gate.tr.{phase_id}", f"gate.dcp.{phase_id}")
            if identifier in gate_positions
        ]
        generic_rows = [
            (index, item.get("id"))
            for index, item in enumerate(collections["gates"])
            if item.get("phase") == phase_id
            and item.get("kind") == "Gate"
            and isinstance(item.get("id"), str)
        ]
        if canonical_positions and any(
            index <= max(canonical_positions) for index, _ in generic_rows
        ):
            issues.append(
                f"$.gates: generic gates for phase {phase_id!r} must follow its canonical TR and DCP gates"
            )
        generic_ids = [identifier for _, identifier in generic_rows]
        if generic_ids != sorted(generic_ids):
            issues.append(
                f"$.gates: generic gates for phase {phase_id!r} must be ordered by id"
            )

    for index, gate in enumerate(collections["gates"]):
        path = f"$.gates[{index}]"
        identifier = gate.get("id")
        kind = gate.get("kind")
        if kind in {"TR", "DCP"} and identifier not in canonical_gate_ids:
            issues.append(
                f"{path}.kind: TR and DCP kinds are reserved for canonical gates"
            )
        if gate.get("review_required") is not True:
            issues.append(f"{path}.review_required: must equal true")
        if gate.get("final_approval") != "authorized_human":
            issues.append(
                f"{path}.final_approval: must equal 'authorized_human'"
            )

        gate_phase = gate.get("phase")
        if gate_phase in deliverables_by_phase:
            issues.extend(
                _required_deliverable_issues(
                    path=f"{path}.required_deliverables",
                    required=gate.get("required_deliverables"),
                    expected=deliverables_by_phase[gate_phase],
                    deliverable_ids=deliverable_ids,
                )
            )

        checkpoint_id = gate.get("checkpoint_id")
        checkpoint = checkpoint_by_id.get(checkpoint_id)
        if checkpoint is not None and checkpoint.get("phase") != gate_phase:
            issues.append(
                f"{path}.checkpoint_id: checkpoint phase must match gate phase"
            )

    for field in ("activities", "deliverables", "technical_reviews", "decision_checkpoints", "gates"):
        for index, item in enumerate(collections[field]):
            if item.get("phase") not in phase_ids:
                issues.append(
                    f"$.{field}[{index}].phase: references unknown phase {item.get('phase')!r}"
                )

    phase_sequence_by_id = {item["id"]: item["sequence"] for item in phases()}
    deliverable_phase_by_id = {
        item["id"]: item.get("phase")
        for item in collections["deliverables"]
        if isinstance(item.get("id"), str)
    }
    graph: dict[str, list[str]] = {}
    for index, deliverable in enumerate(collections["deliverables"]):
        path = f"$.deliverables[{index}]"
        if deliverable.get("activity_id") not in activity_ids:
            issues.append(
                f"{path}.activity_id: references unknown activity "
                f"{deliverable.get('activity_id')!r}"
            )
        if type(deliverable.get("review_required")) is not bool:
            issues.append(f"{path}.review_required: must be a boolean")
        dependencies = deliverable.get("depends_on")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item.strip() for item in dependencies
        ):
            issues.append(f"{path}.depends_on: must be an array of non-empty strings")
            dependencies = []
        elif len(dependencies) != len(set(dependencies)):
            issues.append(f"{path}.depends_on: must not contain duplicates")
        identifier = deliverable.get("id")
        if isinstance(identifier, str):
            graph[identifier] = list(dependencies)
        for prerequisite in dependencies:
            if prerequisite == identifier:
                issues.append(f"{path}.depends_on: cannot depend on itself")
            elif prerequisite not in deliverable_ids:
                issues.append(
                    f"{path}.depends_on: references unknown deliverable {prerequisite!r}"
                )
            elif isinstance(identifier, str):
                source_phase = deliverable_phase_by_id.get(identifier)
                target_phase = deliverable_phase_by_id.get(prerequisite)
                if (
                    source_phase in phase_sequence_by_id
                    and target_phase in phase_sequence_by_id
                    and phase_sequence_by_id[source_phase]
                    < phase_sequence_by_id[target_phase]
                ):
                    issues.append(
                        f"{path}.depends_on: earlier phase {source_phase!r} cannot "
                        f"depend on later phase {target_phase!r} deliverable {prerequisite!r}"
                    )
    cycle = find_cycle(graph)
    if cycle:
        issues.append(f"$.deliverables: dependency cycle detected: {' -> '.join(cycle)}")

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

    for owner, owner_phase, definition_state, subject, condition, path in refinement_trigger_records:
        owner_sequence = phase_sequence_by_id.get(owner_phase)
        if condition == "accepted":
            if subject not in deliverable_phase_by_id:
                issues.append(
                    f"{path}.condition: accepted must reference a Deliverable"
                )
                continue
            subject_sequence = phase_sequence_by_id.get(
                deliverable_phase_by_id.get(subject)
            )
            if (
                owner_sequence is not None
                and subject_sequence is not None
                and subject_sequence > owner_sequence
            ):
                issues.append(
                    f"{path}.subject: later-phase Deliverable {subject!r} cannot trigger "
                    f"refinement of {owner!r}"
                )
            if definition_state == "placeholder" and (
                subject == owner or depends_on_subject(subject, owner)
            ):
                issues.append(
                    f"{path}.subject: placeholder refinement root {owner!r} cannot "
                    "be required to complete before its trigger"
                )
        elif condition == "approved":
            gate = gate_by_id.get(subject)
            if gate is None:
                issues.append(
                    f"{path}.condition: approved must reference a Gate"
                )
                continue
            gate_sequence = phase_sequence_by_id.get(gate.get("phase"))
            if (
                owner_sequence is not None
                and gate_sequence is not None
                and gate_sequence >= owner_sequence
            ):
                issues.append(
                    f"{path}.subject: Gate {subject!r} must belong to a phase before "
                    f"refinement root {owner!r}"
                )

    declared_edges: set[tuple[str, str]] = set()
    declared_refinement_edges: set[tuple[str, str]] = set()
    seen_typed_edges: set[tuple[str, str, str]] = set()
    for index, dependency in enumerate(collections["dependencies"]):
        path = f"$.dependencies[{index}]"
        source = dependency.get("source")
        target = dependency.get("target")
        relation = dependency.get("relation")
        if is_v2:
            issues.extend(
                _provenance_issues(
                    f"{path}.provenance", dependency.get("provenance")
                )
            )
        if relation not in TRACE_RELATIONS:
            issues.append(
                f"{path}.relation: must be one of: {', '.join(TRACE_RELATIONS)}"
            )
        if source not in all_entity_ids:
            issues.append(f"{path}.source: references unknown entity {source!r}")
        if target not in all_entity_ids:
            issues.append(f"{path}.target: references unknown entity {target!r}")
        if relation == "depends_on":
            if source not in deliverable_ids or target not in deliverable_ids:
                issues.append(f"{path}: depends_on must connect two deliverables")
            if isinstance(source, str) and isinstance(target, str):
                declared_edges.add((source, target))
        if relation == "refines":
            same_kind = (
                source in deliverable_ids and target in deliverable_ids
            ) or (
                source in activity_ids and target in activity_ids
            )
            if not same_kind:
                issues.append(
                    f"{path}: refines must connect two Activities or two Deliverables"
                )
            if isinstance(source, str) and isinstance(target, str):
                declared_refinement_edges.add((source, target))
        if isinstance(source, str) and isinstance(target, str) and isinstance(relation, str):
            typed_edge = (source, target, relation)
            if typed_edge in seen_typed_edges:
                issues.append(f"{path}: duplicate typed dependency {typed_edge!r}")
            seen_typed_edges.add(typed_edge)
    expected_edges = {
        (identifier, prerequisite)
        for identifier, prerequisites in graph.items()
        for prerequisite in prerequisites
    }
    for edge in sorted(expected_edges - declared_edges):
        issues.append(
            f"$.dependencies: missing depends_on edge {edge[0]!r} -> {edge[1]!r}"
        )
    for edge in sorted(declared_edges - expected_edges):
        issues.append(
            f"$.dependencies: unexpected depends_on edge {edge[0]!r} -> {edge[1]!r}"
        )
    expected_refinement_edges = {
        (item["id"], item["refines"])
        for field in ("activities", "deliverables")
        for item in collections[field]
        if isinstance(item.get("id"), str) and isinstance(item.get("refines"), str)
    }
    for edge in sorted(expected_refinement_edges - declared_refinement_edges):
        issues.append(
            f"$.dependencies: missing refines edge {edge[0]!r} -> {edge[1]!r}"
        )
    for edge in sorted(declared_refinement_edges - expected_refinement_edges):
        issues.append(
            f"$.dependencies: unexpected refines edge {edge[0]!r} -> {edge[1]!r}"
        )

    checkpoint_ids = tr_ids | dcp_ids
    for index, gate in enumerate(collections["gates"]):
        path = f"$.gates[{index}]"
        if gate.get("kind") not in {"TR", "DCP", "Gate"}:
            issues.append(f"{path}.kind: must be TR, DCP, or Gate")
        if gate.get("checkpoint_id") not in checkpoint_ids:
            issues.append(
                f"{path}.checkpoint_id: references unknown checkpoint "
                f"{gate.get('checkpoint_id')!r}"
            )
        required = gate.get("required_deliverables")
        if not isinstance(required, list):
            issues.append(f"{path}.required_deliverables: must be an array")
        else:
            for identifier in required:
                if identifier not in deliverable_ids:
                    issues.append(
                        f"{path}.required_deliverables: references unknown deliverable "
                        f"{identifier!r}"
                    )

    reviewable = deliverable_ids | gate_ids
    for index, requirement in enumerate(collections["review_requirements"]):
        path = f"$.review_requirements[{index}]"
        subject_type = requirement.get("subject_type")
        subject_id = requirement.get("subject_id")
        if subject_type not in {"deliverable", "gate"}:
            issues.append(f"{path}.subject_type: must be deliverable or gate")
        if subject_id not in reviewable:
            issues.append(f"{path}.subject_id: references unknown review subject {subject_id!r}")
        if requirement.get("reviewer_type") not in {"human", "agent"}:
            issues.append(f"{path}.reviewer_type: must be human or agent")
        for field in ("authorization_required", "decision_required"):
            if type(requirement.get(field)) is not bool:
                issues.append(f"{path}.{field}: must be a boolean")

    refinements = value.get("refinements", [])
    if not is_v2 and refinements not in (None, []):
        issues.append("$.refinements: schema 1.0 must not contain refinement facts")
        refinements = []
    elif refinements is None:
        refinements = []
    if is_v2 and not isinstance(refinements, list):
        issues.append("$.refinements: must be an array")
        refinements = []
    seen_refinement_ids: set[str] = set()
    seen_refinement_roots: set[str] = set()
    deliverable_by_id = {
        item["id"]: item
        for item in collections["deliverables"]
        if isinstance(item.get("id"), str)
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
        if not isinstance(identifier, str) or not _ID_PATTERN.fullmatch(identifier):
            issues.append(f"{path}.id: must be a valid lowercase identifier")
        elif identifier in seen_refinement_ids:
            issues.append(f"{path}.id: duplicate refinement id {identifier!r}")
        else:
            seen_refinement_ids.add(identifier)
        if not isinstance(root, str) or not _ID_PATTERN.fullmatch(root):
            issues.append(f"{path}.root: must be a valid lowercase identifier")
        elif root in seen_refinement_roots:
            issues.append(f"{path}.root: root {root!r} is already expanded")
        else:
            seen_refinement_roots.add(root)
        root_node = deliverable_by_id.get(root)
        if root_node is None:
            issues.append(f"{path}.root: references unknown Deliverable {root!r}")
        elif root_node.get("definition_state") != "abstract":
            issues.append(f"{path}.root: applied refinement root must be abstract")
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
                isinstance(item, str) and _ID_PATTERN.fullmatch(item)
                for item in invalidated_gates
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
            isinstance(item, str) and _ID_PATTERN.fullmatch(item)
            for item in children
        ):
            issues.append(
                f"{path}.children: must be a non-empty array of identifiers"
            )
            children = []
        elif len(children) != len(set(children)):
            issues.append(f"{path}.children: must not contain duplicates")
        if isinstance(root, str):
            for child in children:
                if child not in deliverable_ids:
                    issues.append(
                        f"{path}.children: references unknown Deliverable {child!r}"
                    )
                    continue
                cursor = child
                seen: set[str] = set()
                while cursor in deliverable_by_id and cursor not in seen:
                    if cursor == root:
                        break
                    seen.add(cursor)
                    parent = deliverable_by_id[cursor].get("refines")
                    if not isinstance(parent, str):
                        cursor = ""
                        break
                    cursor = parent
                if cursor != root:
                    issues.append(
                        f"{path}.children: {child!r} is not a descendant of root {root!r}"
                    )

    for root, node in sorted(deliverable_by_id.items()):
        if node.get("refinement_required") is not True:
            continue
        has_descendant = False
        for child in deliverable_by_id:
            if child == root:
                continue
            cursor = child
            seen: set[str] = set()
            while cursor in deliverable_by_id and cursor not in seen:
                seen.add(cursor)
                parent = deliverable_by_id[cursor].get("refines")
                if parent == root:
                    has_descendant = True
                    break
                if not isinstance(parent, str):
                    break
                cursor = parent
            if has_descendant:
                break
        if has_descendant and root not in seen_refinement_roots:
            issues.append(
                f"$.deliverables: refinement requirement root {root!r} is "
                "pre-expanded without an applied refinement record"
            )

    migrations = value.get("migrations", []) if is_v2 else []
    if is_v2 and not isinstance(migrations, list):
        issues.append("$.migrations: must be an array")
        migrations = []
    seen_migrations: set[tuple[str, str]] = set()
    migration_targets_by_source: dict[str, set[str]] = {}
    migration_sources_by_target: dict[str, set[str]] = {}
    migration_strategies_by_source: dict[str, set[str]] = {}
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
        if not isinstance(source, str) or not _ID_PATTERN.fullmatch(source):
            issues.append(f"{path}.from: must be a valid lowercase identifier")
        if not isinstance(target, str) or not _ID_PATTERN.fullmatch(target):
            issues.append(f"{path}.to: must be a valid lowercase identifier")
        elif target not in deliverable_ids:
            issues.append(
                f"{path}.to: references unknown target deliverable {target!r}"
            )
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
            migration_targets_by_source.setdefault(source, set()).add(target)
            migration_sources_by_target.setdefault(target, set()).add(source)
            migration_strategies_by_source.setdefault(source, set()).add(strategy)
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
    return sorted(set(issues))


def validate_tailored_process(value: Any) -> list[str]:
    """Publicly named validator for the ``tailored_process.yaml`` contract."""

    return validate_process(value)


def load_process(path: str | Path) -> dict[str, Any]:
    """Load a tailored process and reject broken references or cycles."""

    try:
        value = load_yaml(path)
    except YamlError as exc:
        raise TailoringError(str(exc)) from exc
    issues = validate_tailored_process(value)
    if issues:
        raise TailoringError("invalid tailored process:\n- " + "\n- ".join(issues))
    assert isinstance(value, dict)
    return value


def tailor_profile(
    profile: dict[str, Any],
    process_extension: str | Path | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one in-memory task profile into a tailored process."""

    if not isinstance(profile, dict):
        raise TailoringError("task profile root must be an object")
    version = profile.get("schema_version", PROFILE_SCHEMA_VERSION)
    if version != PROFILE_SCHEMA_VERSION:
        raise TailoringError(
            f"$.schema_version: must equal {PROFILE_SCHEMA_VERSION!r}"
        )
    task_types = _profile_task_types(profile)
    capability_patterns = _profile_capability_patterns(profile)
    try:
        result = _assemble(
            profile,
            task_types,
            capability_patterns,
            process_extension,
        )
    except ProcessModelError as exc:
        raise TailoringError(str(exc)) from exc
    issues = validate_process(result)
    if issues:
        raise TailoringError("generated process is invalid:\n- " + "\n- ".join(issues))
    return result


def tailor_file(
    profile_path: str | Path,
    output_path: str | Path,
    process_extension: str | Path | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a task profile, compile it, and atomically persist the result."""

    profile = load_profile(profile_path)
    result = tailor_profile(profile, process_extension)
    try:
        write_yaml_atomic(output_path, result)
    except YamlError as exc:
        raise TailoringError(str(exc)) from exc
    return result


__all__ = [
    "PROFILE_SCHEMA_VERSION",
    "TailoringError",
    "load_process",
    "load_profile",
    "preview_process_diff",
    "tailor_file",
    "tailor_profile",
    "validate_process",
    "validate_tailored_process",
]

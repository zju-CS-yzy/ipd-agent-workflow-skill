"""Compile task profiles into deterministic, auditable IPD processes."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from .dependencies import find_cycle
from .model import TRACE_RELATIONS
from .process_model import (
    PROCESS_SCHEMA_VERSION,
    ProcessModelError,
    base_activities,
    base_deliverables,
    load_task_type_policy,
    normalize_task_types,
    phases,
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
    return value


def _checkpoint(
    *, prefix: str, label: str, phase: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    phase_id = phase["id"]
    return {
        "id": f"{prefix}.{phase_id}",
        "title": f"{phase['title']} {label}",
        "phase": phase_id,
        "sequence": phase["sequence"],
        "gate_id": f"gate.{prefix}.{phase_id}",
        "required_deliverables": list(required),
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
    }


def _assemble(profile: dict[str, Any], task_types: tuple[str, ...]) -> dict[str, Any]:
    process_phases = phases()
    activities = base_activities()
    deliverables = base_deliverables()

    for task_type in task_types:
        policy = load_task_type_policy(task_type)
        activities.extend(deepcopy(policy["activities"]))
        deliverables.extend(deepcopy(policy["deliverables"]))

    deliverables_by_phase = {
        phase["id"]: [
            item["id"]
            for item in deliverables
            if item["phase"] == phase["id"]
        ]
        for phase in process_phases
    }
    technical_reviews = [
        _checkpoint(
            prefix="tr",
            label="Technical Review",
            phase=phase,
            required=deliverables_by_phase[phase["id"]],
        )
        for phase in process_phases
    ]
    decision_checkpoints = [
        _checkpoint(
            prefix="dcp",
            label="Decision Checkpoint",
            phase=phase,
            required=deliverables_by_phase[phase["id"]],
        )
        for phase in process_phases
    ]

    gates: list[dict[str, Any]] = []
    for tr, dcp in zip(technical_reviews, decision_checkpoints):
        gates.append(_gate(tr, "TR"))
        gates.append(_gate(dcp, "DCP"))

    dependencies = [
        {"source": deliverable["id"], "target": prerequisite, "relation": "depends_on"}
        for deliverable in deliverables
        for prerequisite in deliverable["depends_on"]
    ]

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
        },
        "phases": process_phases,
        "technical_reviews": technical_reviews,
        "decision_checkpoints": decision_checkpoints,
        "gates": gates,
        "activities": activities,
        "deliverables": deliverables,
        "dependencies": dependencies,
        "review_requirements": review_requirements,
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


def validate_process(value: Any) -> list[str]:
    """Validate structural references and dependency invariants in a process."""

    issues: list[str] = []
    if not isinstance(value, dict):
        return ["$: must be an object"]
    top_fields = {
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
    for field in sorted(top_fields - value.keys()):
        issues.append(f"$.{field}: required field is missing")
    for field in sorted(value.keys() - top_fields):
        issues.append(f"$.{field}: unknown field")
    if value.get("schema_version") != PROCESS_SCHEMA_VERSION:
        issues.append(f"$.schema_version: must equal {PROCESS_SCHEMA_VERSION!r}")

    profile = value.get("profile")
    if not isinstance(profile, dict):
        issues.append("$.profile: must be an object")
    else:
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

    canonical_phases = phases()
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
    cycle = find_cycle(graph)
    if cycle:
        issues.append(f"$.deliverables: dependency cycle detected: {' -> '.join(cycle)}")

    declared_edges: set[tuple[str, str]] = set()
    for index, dependency in enumerate(collections["dependencies"]):
        path = f"$.dependencies[{index}]"
        source = dependency.get("source")
        target = dependency.get("target")
        relation = dependency.get("relation")
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


def tailor_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Compile one in-memory task profile into a tailored process."""

    if not isinstance(profile, dict):
        raise TailoringError("task profile root must be an object")
    version = profile.get("schema_version", PROFILE_SCHEMA_VERSION)
    if version != PROFILE_SCHEMA_VERSION:
        raise TailoringError(
            f"$.schema_version: must equal {PROFILE_SCHEMA_VERSION!r}"
        )
    task_types = _profile_task_types(profile)
    try:
        result = _assemble(profile, task_types)
    except ProcessModelError as exc:
        raise TailoringError(str(exc)) from exc
    issues = validate_process(result)
    if issues:
        raise TailoringError("generated process is invalid:\n- " + "\n- ".join(issues))
    return result


def tailor_file(
    profile_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    """Load a task profile, compile it, and atomically persist the result."""

    profile = load_profile(profile_path)
    result = tailor_profile(profile)
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
    "tailor_file",
    "tailor_profile",
    "validate_process",
    "validate_tailored_process",
]

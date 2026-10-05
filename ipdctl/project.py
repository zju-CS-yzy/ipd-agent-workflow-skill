"""Project-level orchestration shared by the CLI and integrations."""

from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .dependencies import unmet_dependencies
from .eligibility import (
    binding_eligibility,
    claim_protocol_readiness,
    deliverable_binding_status,
    deliverable_refinement_status,
    eligibility_fingerprint,
    requirements_fingerprint,
)
from .governance import apply_phase_pointers, phase_history_issues, phase_pointers
from .i18n import get_translator, load_project_locale, normalize_locale
from .repository import changed_paths, inspect_repository
from .runtime import (
    claim_event_issues,
    create_runtime_state,
    expire_claims,
    load_runtime,
    record_artifact_baseline_adoption,
    record_event,
    save_runtime,
)
from .state import create_initial_state, load_state, resolve_state_path, revised_copy, write_state
from .validation import validate_state


class ProjectError(ValueError):
    """Raised when project files cannot be safely initialized or reconciled."""


def _portable_repository_record(info: Any) -> dict[str, Any]:
    """Return repository facts safe to persist in project-local state."""

    record = info.as_dict()
    record["root"] = "." if record.get("kind") in {"git", "svn"} else None
    return record


def _stable_value_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_hash(path: Path, root: Path) -> str | None:
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if resolved.is_file():
        return _file_hash(resolved)
    if resolved.is_dir():
        rows = [
            (child.relative_to(resolved).as_posix(), _file_hash(child))
            for child in sorted(resolved.rglob("*"))
            if child.is_file()
        ]
        return _stable_value_hash(rows)
    return None


def project_consistency_issues(
    state: dict[str, Any],
    process: dict[str, Any],
    runtime: dict[str, Any] | None = None,
) -> list[str]:
    """Validate relationships that span the three authority documents."""

    issues: list[str] = []
    process_deliverables = {
        item.get("id"): item
        for item in process.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    state_deliverables = {
        item.get("id"): item
        for item in state.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    missing_state_ids = set(process_deliverables) - set(state_deliverables)
    if missing_state_ids:
        issues.append("process deliverables are absent from state; run ipdctl tailor")
    historical_state_ids = set(state_deliverables) - set(process_deliverables)
    for identifier in sorted(historical_state_ids):
        historical = state_deliverables[identifier]
        replacements = list(historical.get("replacements", []))
        if not replacements and historical.get("replacement"):
            replacements = [historical["replacement"]]
        if historical.get("status") != "superseded":
            issues.append(
                f"state-only deliverable {identifier!r} must be superseded history"
            )
        elif not replacements or any(
            replacement not in process_deliverables for replacement in replacements
        ):
            issues.append(
                f"state-only deliverable {identifier!r} has invalid process replacements"
            )
    for identifier in sorted(set(process_deliverables) & set(state_deliverables)):
        expected = process_deliverables[identifier]
        actual = state_deliverables[identifier]
        for field in (
            "title",
            "phase",
            "activity_id",
            "review_required",
            "provenance",
            "maturity",
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
            "requires_artifact_owner",
        ):
            if actual.get(field) != expected.get(field):
                issues.append(
                    f"deliverable {identifier!r} field {field!r} differs from the tailored process"
                )
        if list(actual.get("depends_on", [])) != list(expected.get("depends_on", [])):
            issues.append(
                f"deliverable {identifier!r} dependencies differ from the tailored process"
            )

    process_gates = {
        item.get("id"): item
        for item in process.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    state_gates = {
        item.get("id"): item
        for item in state.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if set(process_gates) != set(state_gates):
        issues.append("process and state gate IDs differ; run ipdctl tailor")
    for identifier in sorted(set(process_gates) & set(state_gates)):
        expected = process_gates[identifier]
        actual = state_gates[identifier]
        for field in ("title", "kind", "phase"):
            if actual.get(field) != expected.get(field):
                issues.append(
                    f"gate {identifier!r} field {field!r} differs from the tailored process"
                )
        if list(actual.get("required_deliverables", [])) != list(
            expected.get("required_deliverables", [])
        ):
            issues.append(
                f"gate {identifier!r} requirements differ from the tailored process"
            )

    profile = process.get("profile") if isinstance(process.get("profile"), dict) else {}
    project = state.get("project") if isinstance(state.get("project"), dict) else {}
    if list(project.get("task_types", [])) != list(profile.get("task_types", [])):
        issues.append("project task types differ from the tailored process")
    if project.get("name") != profile.get("name"):
        issues.append("project name differs from the tailored process")
    phase_ids = {
        item.get("id")
        for item in process.get("phases", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if project.get("phase") not in phase_ids:
        issues.append("current project phase is absent from the tailored process")
    issues.extend(phase_history_issues(state, process, runtime))
    expected_pointers = phase_pointers(state, process)
    for field, expected in expected_pointers.items():
        if project.get(field) != expected:
            issues.append(
                f"project pointer {field!r} is stale; expected {expected!r}"
            )

    if runtime is not None:
        claims = runtime.get("active_claims", {})
        if not isinstance(claims, dict):
            issues.append("Agent runtime active_claims must be an object")
            claims = {}
        if len(claims) > 1:
            issues.append("the serialized CLI runtime cannot hold multiple active claims")
        in_progress = {
            identifier
            for identifier, item in state_deliverables.items()
            if item.get("status") == "in_progress"
        }
        active = set(claims)
        for identifier, claim in claims.items():
            if identifier not in state_deliverables:
                issues.append(f"active claim references unknown deliverable {identifier!r}")
                continue
            if not isinstance(claim, dict) or claim.get("deliverable") != identifier:
                issues.append(f"active claim {identifier!r} has an invalid record")
            if state_deliverables[identifier].get("status") != "in_progress":
                issues.append(
                    f"active claim {identifier!r} does not reference an in-progress deliverable"
                )
        for identifier in sorted(in_progress - active):
            issues.append(
                f"in-progress deliverable {identifier!r} has no active claim; recover it before verify"
            )
        if active - in_progress:
            issues.append("Agent runtime contains a ghost active claim")
        workflow_step = project.get("workflow_step")
        if active and workflow_step != "work":
            issues.append("an active claim requires workflow_step 'work'")
        if workflow_step == "work" and not active:
            issues.append("workflow_step 'work' requires one active claim")
        events = runtime.get("events", [])
        if isinstance(events, list):
            process_refinements = {
                item.get("id"): item
                for item in process.get("refinements", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            refinement_event_rows: dict[str, list[dict[str, Any]]] = {}
            for event in events:
                if (
                    isinstance(event, dict)
                    and event.get("action") == "process_refinement_applied"
                    and isinstance(event.get("plan_id"), str)
                ):
                    refinement_event_rows.setdefault(event["plan_id"], []).append(
                        event
                    )
            for identifier, rows in sorted(refinement_event_rows.items()):
                if len(rows) != 1:
                    issues.append(
                        f"runtime refinement plan {identifier!r} must have exactly one authorized event"
                    )
            refinement_events = {
                identifier: rows[0]
                for identifier, rows in refinement_event_rows.items()
                if len(rows) == 1
            }
            for identifier, refinement in sorted(process_refinements.items()):
                event = refinement_events.get(identifier)
                if event is None:
                    issues.append(
                        f"process refinement {identifier!r} has no authorized runtime event"
                    )
                    continue
                for process_field, event_field in (
                    ("plan_digest", "plan_digest"),
                    ("base_process_fingerprint", "base_process_fingerprint"),
                    (
                        "result_process_fingerprint",
                        "result_process_fingerprint",
                    ),
                    ("root", "root"),
                    ("children", "children"),
                    ("invalidated_gates", "invalidated_gates"),
                ):
                    if refinement.get(process_field) != event.get(event_field):
                        issues.append(
                            f"process refinement {identifier!r} differs from its runtime event field {event_field!r}"
                        )
            for identifier in sorted(
                set(refinement_events) - set(process_refinements)
            ):
                issues.append(
                    f"runtime refinement event {identifier!r} is absent from the tailored process"
                )
            current_revision = state.get("revision")
            for index, event in enumerate(events):
                if not isinstance(event, dict) or event.get("action") != "claim":
                    continue
                for issue in claim_event_issues(
                    event,
                    current_state_revision=(
                        current_revision if type(current_revision) is int else None
                    ),
                ):
                    issues.append(f"Claim event {index} {issue}")
                deliverable = event.get("deliverable")
                if isinstance(deliverable, str) and deliverable not in state_deliverables:
                    issues.append(
                        f"Claim event {index} references unknown deliverable {deliverable!r}"
                    )
    return sorted(set(issues))


def verification_input_snapshot(
    project_root: str | Path,
    *,
    state: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture every mutable input whose change invalidates verification."""

    paths = project_paths(project_root)
    root = paths["root"]
    state = state if state is not None else load_state(paths["state"])
    runtime = runtime if runtime is not None else load_runtime(root)
    file_hashes = {
        name: _file_hash(paths[name])
        for name in ("profile", "extensions", "process", "state", "bindings")
    }

    evidence_references: set[str] = set()
    for deliverable in state.get("deliverables", []):
        if not isinstance(deliverable, dict):
            continue
        evidence_references.update(str(item) for item in deliverable.get("evidence", []))
        evidence_references.update(
            str(review.get("evidence"))
            for review in deliverable.get("reviews", [])
            if isinstance(review, dict) and review.get("evidence")
        )
    for gate in state.get("gates", []):
        if not isinstance(gate, dict):
            continue
        evidence_references.update(str(item) for item in gate.get("evidence", []))
        evidence_references.update(
            str(review.get("evidence"))
            for review in gate.get("reviews", [])
            if isinstance(review, dict) and review.get("evidence")
        )
    evidence: dict[str, str | None] = {}
    for reference in sorted(evidence_references):
        if "://" in reference or reference.startswith(("git:", "svn:", "record:")):
            evidence[reference] = "external"
        else:
            evidence[reference] = _path_hash(root / reference, root)

    manifest_path = paths["dashboard"] / "manifest.json"
    dashboard: dict[str, Any] = {
        "manifest": _file_hash(manifest_path),
        "outputs": {},
        "actual_files": {},
    }
    if paths["dashboard"].is_dir():
        dashboard["actual_files"] = {
            candidate.relative_to(paths["dashboard"]).as_posix(): _file_hash(candidate)
            for candidate in sorted(paths["dashboard"].rglob("*"))
            if candidate.is_file()
        }
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        for output in manifest.get("outputs", []) if isinstance(manifest, dict) else []:
            relative = output.get("path") if isinstance(output, dict) else None
            if isinstance(relative, str):
                dashboard["outputs"][relative] = _path_hash(root / relative, root)

    repository, changed = changed_paths(root)
    engineering_changes: dict[str, str | None] = {}
    for relative in changed:
        normalized = str(relative).replace("\\", "/")
        if normalized == ".ipd" or normalized.startswith(".ipd/"):
            continue
        engineering_changes[normalized] = _path_hash(root / normalized, root)

    repository_record = _portable_repository_record(repository)
    # Framework-owned .ipd writes happen as part of verify itself.  Only
    # engineering-path dirtiness may invalidate the verification snapshot.
    repository_record["dirty"] = bool(engineering_changes)
    return {
        "files": file_hashes,
        "active_claims": runtime.get("active_claims", {}),
        "claim_history": [
            {
                key: event.get(key)
                for key in (
                    "action",
                    "deliverable",
                    "actor",
                    "at",
                    "state_revision",
                    "binding_window",
                )
                if key in event
            }
            for event in runtime.get("events", [])
            if isinstance(event, dict) and event.get("action") == "claim"
        ],
        "artifact_baseline_history": [
            {
                key: event.get(key)
                for key in (
                    "action",
                    "actor",
                    "actor_type",
                    "authorized",
                    "reason",
                    "at",
                    "state_revision",
                    "artifact_baseline",
                    "snapshot",
                )
                if key in event
            }
            for event in runtime.get("events", [])
            if isinstance(event, dict)
            and event.get("action") == "artifact_baseline_adopted"
        ],
        "phase_history": [
            {
                key: event.get(key)
                for key in (
                    "action",
                    "from_phase",
                    "to_phase",
                    "at",
                    "state_revision",
                )
                if key in event
            }
            for event in runtime.get("events", [])
            if isinstance(event, dict) and event.get("action") == "advance_phase"
        ],
        "refinement_history": [
            {
                key: event.get(key)
                for key in (
                    "action",
                    "at",
                    "plan_id",
                    "plan_digest",
                    "base_process_fingerprint",
                    "result_process_fingerprint",
                    "actor",
                    "actor_type",
                    "authorized",
                    "reason",
                    "state_revision",
                    "root",
                    "children",
                    "invalidated_gates",
                )
                if key in event
            }
            for event in runtime.get("events", [])
            if isinstance(event, dict)
            and event.get("action") == "process_refinement_applied"
        ],
        "evidence": evidence,
        "dashboard": dashboard,
        "repository": repository_record,
        "engineering_changes": engineering_changes,
    }


def verification_input_fingerprint(
    project_root: str | Path,
    *,
    state: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
) -> str:
    return _stable_value_hash(
        verification_input_snapshot(project_root, state=state, runtime=runtime)
    )


def _legacy_process_projection(process: dict[str, Any]) -> dict[str, Any]:
    """Project a v0.4 compilation onto the readable v0.3 process contract."""

    projected = deepcopy(process)
    projected["schema_version"] = "1.0"
    projected.pop("migrations", None)
    projected.pop("gate_migrations", None)
    projected.pop("dependency_corrections", None)
    projected.pop("refinements", None)
    profile = projected.get("profile")
    if isinstance(profile, dict):
        profile.pop("capability_patterns", None)
    for field in (
        "phases",
        "activities",
        "deliverables",
        "technical_reviews",
        "decision_checkpoints",
        "gates",
        "dependencies",
        "review_requirements",
    ):
        for item in projected.get(field, []):
            if not isinstance(item, dict):
                continue
            item.pop("provenance", None)
            item.pop("maturity", None)
            item.pop("criteria", None)
            item.pop("definition_state", None)
            item.pop("refinement_required", None)
            item.pop("refinement_trigger", None)
            item.pop("refines", None)
            item.pop("requires_artifact_owner", None)
    return projected


def _process_matches_compilation(
    current: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    """Compare a process to its deterministic source compilation."""

    if current.get("schema_version") == "1.0":
        # ``validate_tailored_process`` intentionally accepts mechanically
        # projected schema 1.0 documents that retain the newer optional
        # collections as empty arrays.  Normalize both sides so those harmless
        # empty compatibility fields cannot make an otherwise deterministic
        # legacy process appear stale.
        return _legacy_process_projection(current) == _legacy_process_projection(
            candidate
        )
    return current == candidate


def project_paths(project_root: str | Path) -> dict[str, Path]:
    root = Path(project_root).resolve()
    ipd = root / ".ipd"
    return {
        "root": root,
        "ipd": ipd,
        "profile": ipd / "task_profile.yaml",
        "extensions": ipd / "process_extensions.yaml",
        "process": ipd / "tailored_process.yaml",
        "state": resolve_state_path(root),
        "runtime": ipd / "agent_runtime.yaml",
        "bindings": ipd / "artifact_bindings.yaml",
        "dashboard": ipd / "dashboard",
        "verify_report": ipd / "verify_report.json",
        "reconcile_report": ipd / "reconcile_report.json",
    }


def initialize_project(
    project_root: str | Path,
    *,
    name: str,
    task_types: list[str],
    locale: str = "en",
    force: bool = False,
) -> dict[str, Path]:
    locale = normalize_locale(locale)
    paths = project_paths(project_root)
    state_path = paths["root"] / ".ipd" / "project_state.yaml"
    protected = [
        state_path,
        paths["profile"],
        paths["extensions"],
        paths["runtime"],
    ]
    existing = [path for path in protected if path.exists()]
    if existing and not force:
        raise ProjectError(
            "project is already initialized: " + ", ".join(str(path) for path in existing)
        )
    for directory in (
        paths["ipd"],
        paths["dashboard"],
        paths["root"] / "docs",
        paths["root"] / "src",
        paths["root"] / "tests",
        paths["root"] / "dashboard",
        paths["root"] / "state",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    profile = {
        "schema_version": "1.0",
        "project_name": name,
        "task_types": list(task_types),
        "capability_patterns": [],
        "presentation": {"locale": locale},
    }
    write_state(paths["profile"], profile)
    write_state(state_path, create_initial_state(name, task_types))
    from .process_extensions import load_process_extension

    write_state(paths["extensions"], load_process_extension(None))
    write_state(paths["runtime"], create_runtime_state())
    try:
        from .reconcile import default_artifact_bindings

        write_state(paths["bindings"], default_artifact_bindings())
    except ImportError:
        pass
    paths["state"] = state_path
    return paths


def _gate_records(process: dict[str, Any]) -> list[dict[str, Any]]:
    """Create state only for governed gates; TR/DCP checkpoints remain process facts."""

    records: list[dict[str, Any]] = []
    for item in process.get("gates", []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        required = list(item.get("required_deliverables", []))
        records.append(
            {
                "id": item["id"],
                "title": item.get("title") or item["id"],
                "kind": item.get("kind", "Gate"),
                "status": "planned",
                "phase": item.get("phase"),
                "required_deliverables": required,
                "reviews": [],
                "evidence": [],
                "blockers": [],
                "approval": None,
                "requirements_fingerprint": requirements_fingerprint(
                    required, process
                ),
                "review_epoch": 0,
                "stale": False,
                "stale_reason": None,
            }
        )
    return records


def deliverable_has_history(item: Mapping[str, Any]) -> bool:
    """Return whether removing a Deliverable would discard governed facts."""

    return bool(
        item.get("status", "planned") != "planned"
        or item.get("evidence")
        or item.get("reviews")
        or item.get("blocked_reason")
        or item.get("replacement")
        or item.get("replacements")
    )


def _gate_has_history(item: Mapping[str, Any]) -> bool:
    """Return whether removing or replacing a Gate would discard governed facts."""

    review_epoch = item.get("review_epoch", 0)
    return bool(
        item.get("status", "planned") != "planned"
        or item.get("reviews")
        or item.get("evidence")
        or item.get("blockers")
        or item.get("approval")
        or item.get("stale") is True
        or item.get("stale_reason")
        or (type(review_epoch) is int and review_epoch > 0)
    )


def governed_deliverable_rewrites(
    diff: Mapping[str, Any],
    state: Mapping[str, Any],
    current_process: Mapping[str, Any],
    candidate_process: Mapping[str, Any],
) -> dict[str, list[str]]:
    """Return in-place semantic rewrites of Deliverables with governed facts.

    Removing a historical Deliverable is already handled through explicit
    process migrations.  Reusing the same identifier while changing its
    process contract is equally unsafe: preserving the old status, evidence,
    and reviews would make them appear to approve a different artifact.  The
    caller must therefore require a new identifier plus an explicit migration.
    """

    state_deliverables = {
        item.get("id"): item
        for item in state.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    current_deliverables = {
        item.get("id"): item
        for item in current_process.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    candidate_deliverables = {
        item.get("id"): item
        for item in candidate_process.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    rewrites: dict[str, list[str]] = {}
    for change in diff.get("changed", []):
        if (
            not isinstance(change, Mapping)
            or change.get("collection") != "deliverables"
            or not isinstance(change.get("id"), str)
        ):
            continue
        identifier = change["id"]
        prior = state_deliverables.get(identifier)
        if not isinstance(prior, dict) or not deliverable_has_history(prior):
            continue
        before = current_deliverables.get(identifier, {})
        after = candidate_deliverables.get(identifier, {})
        fields = []
        for field in sorted(
            {
                value
                for value in change.get("fields", [])
                if isinstance(value, str) and value
            }
        ):
            # Schema 2.0 deterministically enriches legacy schema 1.0 nodes
            # with these derived facts.  Only first-time enrichment is safe;
            # changing an already recorded value remains a governed rewrite.
            if (
                field in {"provenance", "maturity"}
                and field not in before
                and field in after
            ):
                continue
            fields.append(field)
        if fields:
            rewrites[identifier] = fields
    return dict(sorted(rewrites.items()))


def closed_phase_process_changes(
    diff: Mapping[str, Any],
    state: Mapping[str, Any],
    current_process: Mapping[str, Any],
    candidate_process: Mapping[str, Any],
) -> list[str]:
    """Return semantic process changes that target an already closed Phase.

    Gate requirement fingerprints deliberately describe Deliverable closure,
    not the complete TR/DCP criteria contract.  This direct semantic guard is
    therefore required in addition to ``phase_history_issues`` so a criteria,
    activity, review rule, or trace edge cannot be added to a closed Phase
    while retaining its historical approval.
    """

    phase_rows = sorted(
        [
            item
            for item in candidate_process.get("phases", [])
            if isinstance(item, Mapping)
            and isinstance(item.get("id"), str)
        ],
        key=lambda item: (item.get("sequence", 0), item["id"]),
    )
    phase_ids = [item["id"] for item in phase_rows]
    current_phase = state.get("project", {}).get("phase")
    if current_phase not in phase_ids:
        return []
    protected_phases = set(phase_ids[: phase_ids.index(current_phase)])
    protected_phases.update(
        item.get("phase")
        for item in state.get("gates", [])
        if isinstance(item, Mapping)
        and item.get("status") == "approved"
        and isinstance(item.get("phase"), str)
    )
    if not protected_phases:
        return []

    phase_collections = {
        "activities",
        "deliverables",
        "technical_reviews",
        "decision_checkpoints",
        "gates",
    }

    def indexed(process: Mapping[str, Any], collection: str) -> dict[str, Mapping[str, Any]]:
        return {
            item["id"]: item
            for item in process.get(collection, [])
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }

    before_indexes = {
        collection: indexed(current_process, collection)
        for collection in phase_collections | {"review_requirements"}
    }
    after_indexes = {
        collection: indexed(candidate_process, collection)
        for collection in phase_collections | {"review_requirements"}
    }
    before_entity_phases = {
        identifier: item.get("phase")
        for collection in phase_collections
        for identifier, item in before_indexes[collection].items()
    }
    after_entity_phases = {
        identifier: item.get("phase")
        for collection in phase_collections
        for identifier, item in after_indexes[collection].items()
    }

    def dependency_index(process: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for item in process.get("dependencies", []):
            if not isinstance(item, Mapping):
                continue
            source = item.get("source")
            target = item.get("target")
            relation = item.get("relation")
            if all(isinstance(value, str) for value in (source, target, relation)):
                result[f"{source}|{relation}|{target}"] = item
        return result

    before_dependencies = dependency_index(current_process)
    after_dependencies = dependency_index(candidate_process)
    legacy_schema_enrichment = (
        current_process.get("schema_version") == "1.0"
        and candidate_process.get("schema_version") == "2.0"
    )

    def canonical_checkpoint_criteria(
        collection: str,
        identifier: str,
        before_item: Mapping[str, Any],
        after_item: Mapping[str, Any],
    ) -> bool:
        if (
            not legacy_schema_enrichment
            or collection not in {"technical_reviews", "decision_checkpoints"}
            or "criteria" in before_item
        ):
            return False
        criteria = after_item.get("criteria")
        return bool(
            isinstance(criteria, list)
            and len(criteria) == 1
            and isinstance(criteria[0], Mapping)
            and criteria[0].get("id") == f"criterion.{identifier}.readiness"
            and criteria[0].get("evidence_required") is True
        )

    affected: set[str] = set()
    for bucket in ("added", "removed", "changed"):
        for change in diff.get(bucket, []):
            if not isinstance(change, Mapping):
                continue
            collection = change.get("collection")
            identifier = change.get("id")
            if not isinstance(collection, str) or not isinstance(identifier, str):
                continue
            if bucket == "changed":
                before_item: Mapping[str, Any] = {}
                after_item: Mapping[str, Any] = {}
                if collection in before_indexes:
                    before_item = before_indexes[collection].get(identifier, {})
                    after_item = after_indexes[collection].get(identifier, {})
                elif collection == "dependencies":
                    before_item = before_dependencies.get(identifier, {})
                    after_item = after_dependencies.get(identifier, {})
                semantic_fields = {
                    field
                    for field in change.get("fields", [])
                    if isinstance(field, str)
                    and not (
                        field in {"provenance", "maturity"}
                        and field not in before_item
                        and field in after_item
                    )
                    and not (
                        field == "criteria"
                        and canonical_checkpoint_criteria(
                            collection,
                            identifier,
                            before_item,
                            after_item,
                        )
                    )
                }
                if not semantic_fields:
                    continue
            phases: set[str] = set()
            if collection in phase_collections:
                for index in (before_indexes, after_indexes):
                    phase = index[collection].get(identifier, {}).get("phase")
                    if isinstance(phase, str):
                        phases.add(phase)
            elif collection == "review_requirements":
                for index, entity_phases in (
                    (before_indexes, before_entity_phases),
                    (after_indexes, after_entity_phases),
                ):
                    subject = index[collection].get(identifier, {}).get("subject_id")
                    phase = entity_phases.get(subject)
                    if isinstance(phase, str):
                        phases.add(phase)
            elif collection == "dependencies":
                parts = identifier.split("|", 2)
                if len(parts) == 3:
                    for endpoint in (parts[0], parts[2]):
                        for entity_phases in (
                            before_entity_phases,
                            after_entity_phases,
                        ):
                            phase = entity_phases.get(endpoint)
                            if isinstance(phase, str):
                                phases.add(phase)
            if phases & protected_phases:
                affected.add(f"{collection}:{identifier}")
    return sorted(affected)


def _historical_replacements(item: dict[str, Any]) -> tuple[str, ...]:
    replacements = item.get("replacements", [])
    if isinstance(replacements, list) and replacements:
        return tuple(
            value for value in replacements if isinstance(value, str) and value
        )
    replacement = item.get("replacement")
    return (replacement,) if isinstance(replacement, str) and replacement else ()


def _has_supersedes_trace(
    state: dict[str, Any], source: str, target: str
) -> bool:
    return any(
        isinstance(link, dict)
        and link.get("relation") == "supersedes"
        and (
            (link.get("source") == source and link.get("target") == target)
            or (link.get("source") == target and link.get("target") == source)
        )
        for link in state.get("traceability", [])
    )


def _migration_targets(
    process: dict[str, Any], process_ids: set[str]
) -> dict[str, tuple[str, ...]]:
    """Return validated Deliverable replacement targets keyed by old ID."""

    targets: dict[str, tuple[str, ...]] = {}
    for index, migration in enumerate(process.get("migrations", [])):
        if not isinstance(migration, dict):
            raise ProjectError(f"process migration {index} must be an object")
        source = migration.get("from")
        raw_targets = migration.get("to")
        if not isinstance(source, str) or not source:
            raise ProjectError(f"process migration {index} has an invalid source")
        if isinstance(raw_targets, str):
            raw_targets = [raw_targets]
        if not isinstance(raw_targets, list) or not raw_targets or any(
            not isinstance(item, str) or not item for item in raw_targets
        ):
            raise ProjectError(f"process migration {source!r} has invalid targets")
        normalized = tuple(dict.fromkeys(raw_targets))
        unknown = sorted(set(normalized) - process_ids)
        if unknown:
            raise ProjectError(
                f"process migration {source!r} references unknown targets: "
                + ", ".join(unknown)
            )
        previous = targets.get(source, ())
        targets[source] = tuple(dict.fromkeys(previous + normalized))
    return targets


def _trace_key(edge: Mapping[str, Any]) -> tuple[str, str, str] | None:
    source = edge.get("source")
    target = edge.get("target")
    relation = edge.get("relation")
    if not all(isinstance(value, str) and value for value in (source, target, relation)):
        return None
    return source, relation, target


def _trace_record(key: tuple[str, str, str]) -> dict[str, str]:
    source, relation, target = key
    return {"source": source, "target": target, "relation": relation}


def _claim_linked_entity_ids(state: Mapping[str, Any]) -> set[str]:
    """Return non-Claim endpoints governed by at least one Claim trace link."""

    claim_ids = {
        item.get("id")
        for item in state.get("claims", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    linked: set[str] = set()
    for edge in state.get("traceability", []):
        if not isinstance(edge, Mapping):
            continue
        key = _trace_key(edge)
        if key is None:
            continue
        source, _, target = key
        if source in claim_ids and target not in claim_ids:
            linked.add(target)
        if target in claim_ids and source not in claim_ids:
            linked.add(source)
    return linked


def _gate_migration_redirects(
    state: Mapping[str, Any], process: Mapping[str, Any]
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Validate explicit one-to-one Gate endpoint redirects.

    A migration whose source is absent is an idempotent no-op after the first
    successful re-tailor.  A source that is referenced by traceability but is
    not an existing Gate is still invalid and therefore blocked below.
    """

    state_gate_ids = {
        item.get("id")
        for item in state.get("gates", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    candidate_gate_ids = {
        item.get("id")
        for item in process.get("gates", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    trace_endpoints = {
        endpoint
        for edge in state.get("traceability", [])
        if isinstance(edge, Mapping)
        for endpoint in (edge.get("source"), edge.get("target"))
        if isinstance(endpoint, str)
    }
    redirects: dict[str, str] = {}
    targets: dict[str, str] = {}
    blocked: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    rows = process.get("gate_migrations", [])
    if not isinstance(rows, list):
        return {}, [{"kind": "invalid_gate_migrations", "path": "$.gate_migrations"}]
    for index, row in enumerate(rows):
        path = f"$.gate_migrations[{index}]"
        if not isinstance(row, Mapping):
            blocked.append({"kind": "invalid_gate_migration", "path": path})
            continue
        source = row.get("from")
        target = row.get("to")
        reason = row.get("reason")
        if (
            not isinstance(source, str)
            or not source
            or not isinstance(target, str)
            or not target
            or not isinstance(reason, str)
            or not reason.strip()
            or row.get("preserve_history") is not True
        ):
            blocked.append({"kind": "invalid_gate_migration", "path": path})
            continue
        pair = (source, target)
        if pair in seen_pairs:
            blocked.append(
                {
                    "kind": "duplicate_gate_migration",
                    "path": path,
                    "from": source,
                    "to": target,
                }
            )
            continue
        seen_pairs.add(pair)
        if source == target:
            blocked.append(
                {
                    "kind": "self_gate_migration",
                    "path": path,
                    "from": source,
                    "to": target,
                }
            )
            continue
        if target not in candidate_gate_ids:
            blocked.append(
                {
                    "kind": "unknown_gate_migration_target",
                    "path": path,
                    "from": source,
                    "to": target,
                }
            )
            continue
        if source in candidate_gate_ids:
            blocked.append(
                {
                    "kind": "gate_migration_source_still_present",
                    "path": path,
                    "from": source,
                    "to": target,
                }
            )
            continue
        if source in redirects and redirects[source] != target:
            blocked.append(
                {
                    "kind": "ambiguous_gate_migration_source",
                    "path": path,
                    "from": source,
                    "targets": sorted({redirects[source], target}),
                }
            )
            continue
        if target in targets and targets[target] != source:
            blocked.append(
                {
                    "kind": "ambiguous_gate_migration_target",
                    "path": path,
                    "to": target,
                    "sources": sorted({targets[target], source}),
                }
            )
            continue
        if source in trace_endpoints and source not in state_gate_ids:
            blocked.append(
                {
                    "kind": "unknown_gate_migration_source",
                    "path": path,
                    "from": source,
                    "to": target,
                }
            )
            continue
        redirects[source] = target
        targets[target] = source
    return redirects, sorted(blocked, key=lambda item: json.dumps(item, sort_keys=True))


def project_traceability_projection(
    state: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    preserved_history: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[list[dict[str, str]], dict[str, list[dict[str, Any]]]]:
    """Project candidate state traceability and describe its semantic impact.

    Process dependencies remain authoritative for process-owned relationships.
    State-owned relationships with at least one Claim endpoint survive when
    both endpoints still exist.  Gate endpoint changes require an explicit,
    unambiguous ``gate_migrations`` record; unexplained Claim-link loss is
    reported as a blocker instead of being silently discarded.
    """

    existing_deliverables = {
        item.get("id"): item
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    process_deliverable_ids = {
        item.get("id")
        for item in process.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    claim_ids = {
        item.get("id")
        for item in state.get("claims", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    candidate_gate_ids = {
        item.get("id")
        for item in process.get("gates", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    if preserved_history is None:
        migration_targets = _migration_targets(dict(process), process_deliverable_ids)
        claim_linked = _claim_linked_entity_ids(state)
        derived_history: dict[str, tuple[str, ...]] = {}
        for identifier, item in existing_deliverables.items():
            if identifier in process_deliverable_ids:
                continue
            replacements = _historical_replacements(dict(item))
            if (
                item.get("status") == "superseded"
                and replacements
                and all(target in process_deliverable_ids for target in replacements)
            ):
                derived_history[identifier] = replacements
            elif identifier in migration_targets and (
                deliverable_has_history(item) or identifier in claim_linked
            ):
                derived_history[identifier] = migration_targets[identifier]
        preserved_history = derived_history
    history = {
        identifier: tuple(targets)
        for identifier, targets in preserved_history.items()
    }
    candidate_entity_ids = (
        claim_ids
        | process_deliverable_ids
        | candidate_gate_ids
        | set(history)
    )
    state_entity_ids = claim_ids | set(existing_deliverables) | {
        item.get("id")
        for item in state.get("gates", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    redirects, blocked = _gate_migration_redirects(state, process)

    projected_keys: set[tuple[str, str, str]] = set()
    for edge in process.get("dependencies", []):
        if not isinstance(edge, Mapping):
            continue
        source = edge.get("source")
        target = edge.get("target")
        relation = edge.get("relation", "depends_on")
        if (
            isinstance(source, str)
            and isinstance(target, str)
            and isinstance(relation, str)
            and source in candidate_entity_ids
            and target in candidate_entity_ids
        ):
            projected_keys.add((source, relation, target))
    for source, replacements in history.items():
        for target in replacements:
            projected_keys.add((source, "supersedes", target))

    old_keys: set[tuple[str, str, str]] = set()
    redirected_rows: list[dict[str, Any]] = []
    for index, edge in enumerate(state.get("traceability", [])):
        if not isinstance(edge, Mapping):
            blocked.append(
                {
                    "kind": "invalid_existing_traceability",
                    "path": f"$.traceability[{index}]",
                }
            )
            continue
        key = _trace_key(edge)
        if key is None:
            blocked.append(
                {
                    "kind": "invalid_existing_traceability",
                    "path": f"$.traceability[{index}]",
                }
            )
            continue
        old_keys.add(key)
        source, relation, target = key
        missing_before = sorted({source, target} - state_entity_ids)
        if missing_before:
            blocked.append(
                {
                    "kind": "dangling_existing_traceability",
                    "edge": _trace_record(key),
                    "missing": missing_before,
                }
            )
            continue
        if source not in claim_ids and target not in claim_ids:
            continue
        redirected_source = redirects.get(source, source)
        redirected_target = redirects.get(target, target)
        redirected_key = (redirected_source, relation, redirected_target)
        missing_after = sorted(
            {redirected_source, redirected_target} - candidate_entity_ids
        )
        if missing_after:
            blocked.append(
                {
                    "kind": "claim_traceability_removal",
                    "edge": _trace_record(key),
                    "missing": missing_after,
                }
            )
            continue
        projected_keys.add(redirected_key)
        if redirected_key != key:
            fields = []
            if redirected_source != source:
                fields.append("source")
            if redirected_target != target:
                fields.append("target")
            redirected_rows.append(
                {
                    "before": _trace_record(key),
                    "after": _trace_record(redirected_key),
                    "fields": fields,
                }
            )

    redirected_before = {
        _trace_key(item["before"])
        for item in redirected_rows
        if isinstance(item.get("before"), Mapping)
    }
    redirected_after = {
        _trace_key(item["after"])
        for item in redirected_rows
        if isinstance(item.get("after"), Mapping)
    }
    added_keys = projected_keys - old_keys - {
        key for key in redirected_after if key is not None
    }
    removed_keys = old_keys - projected_keys - {
        key for key in redirected_before if key is not None
    }
    projected = [_trace_record(key) for key in sorted(projected_keys)]
    impact = {
        "added": [_trace_record(key) for key in sorted(added_keys)],
        "removed": [_trace_record(key) for key in sorted(removed_keys)],
        "redirected": sorted(
            redirected_rows,
            key=lambda item: json.dumps(item, sort_keys=True),
        ),
        "blocked": sorted(
            blocked,
            key=lambda item: json.dumps(item, sort_keys=True),
        ),
    }
    return projected, impact


def effective_dependency_corrections(
    state: Mapping[str, Any], process: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return exact same-ID dependency corrections not yet reflected in state.

    A declaration is replay-safe only when state is already at ``after``.  Any
    other value must match ``before`` exactly; otherwise the declaration was
    authored against another process revision and fails closed.
    """

    state_deliverables = {
        item.get("id"): item
        for item in state.get("deliverables", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    corrections = process.get("dependency_corrections", [])
    if not isinstance(corrections, list):
        raise ProjectError("process dependency_corrections must be an array")
    effective: list[dict[str, Any]] = []
    for index, correction in enumerate(corrections):
        if not isinstance(correction, Mapping):
            raise ProjectError(f"dependency correction {index} must be an object")
        identifier = correction.get("deliverable")
        before = correction.get("before")
        after = correction.get("after")
        prior = state_deliverables.get(identifier)
        if prior is None:
            continue
        prior_dependencies = prior.get("depends_on", [])
        if prior_dependencies == after:
            continue
        if prior_dependencies != before:
            raise ProjectError(
                f"dependency correction for {identifier!r} expected before "
                f"{before!r}, but state contains {prior_dependencies!r}"
            )
        effective.append(deepcopy(dict(correction)))
    return sorted(effective, key=lambda item: str(item.get("deliverable", "")))


def sync_state_with_process(
    state: dict[str, Any],
    process: dict[str, Any],
    *,
    apply_migrations: bool = False,
) -> dict[str, Any]:
    """Merge a deterministic tailored process into state without losing facts."""

    existing_deliverables = {item["id"]: item for item in state.get("deliverables", [])}
    process_ids = {
        item.get("id")
        for item in process.get("deliverables", [])
        if isinstance(item, dict) and item.get("id")
    }
    migration_targets = _migration_targets(process, process_ids)
    dependency_corrections = effective_dependency_corrections(state, process)
    historical_corrections = [
        correction
        for correction in dependency_corrections
        if deliverable_has_history(
            existing_deliverables.get(correction.get("deliverable"), {})
        )
    ]
    if historical_corrections and not apply_migrations:
        raise ProjectError(
            "re-tailoring requires explicit --apply-migrations for dependency "
            "corrections: "
            + ", ".join(
                str(item["deliverable"]) for item in historical_corrections
            )
        )
    corrected_history_ids = {
        str(item["deliverable"]) for item in historical_corrections
    }
    removed_ids = {
        identifier
        for identifier, item in existing_deliverables.items()
        if identifier not in process_ids
    }
    already_superseded_history: dict[str, tuple[str, ...]] = {}
    invalid_superseded_history: list[str] = []
    for identifier in sorted(removed_ids):
        item = existing_deliverables[identifier]
        if item.get("status") != "superseded":
            continue
        replacements = _historical_replacements(item)
        if (
            replacements
            and all(target in process_ids for target in replacements)
            and all(
                _has_supersedes_trace(state, identifier, target)
                for target in replacements
            )
        ):
            already_superseded_history[identifier] = replacements
        else:
            invalid_superseded_history.append(identifier)
    if invalid_superseded_history:
        raise ProjectError(
            "state-only superseded history has invalid replacements or trace links: "
            + ", ".join(invalid_superseded_history)
        )
    claim_linked_entities = _claim_linked_entity_ids(state)
    newly_removed_history = [
        identifier
        for identifier in sorted(removed_ids)
        if identifier not in already_superseded_history
        and (
            deliverable_has_history(existing_deliverables[identifier])
            or identifier in claim_linked_entities
        )
    ]
    unmapped_removed = [
        identifier
        for identifier in newly_removed_history
        if identifier not in migration_targets
    ]
    if unmapped_removed:
        raise ProjectError(
            "re-tailoring would remove unmapped historical deliverables: "
            + ", ".join(sorted(unmapped_removed))
        )
    if newly_removed_history and not apply_migrations:
        raise ProjectError(
            "re-tailoring requires explicit --apply-migrations for historical "
            "deliverables: " + ", ".join(newly_removed_history)
        )

    updated = revised_copy(state)
    deliverables: list[dict[str, Any]] = []
    for item in process.get("deliverables", []):
        identifier = item["id"]
        prior = existing_deliverables.get(identifier, {})
        generated = {
            "id": identifier,
            "title": item.get("title") or identifier,
            "status": prior.get("status", "planned"),
            "phase": item.get("phase"),
            "activity_id": item.get("activity_id"),
            "review_required": bool(item.get("review_required", True)),
            "depends_on": list(item.get("depends_on", [])),
            "evidence": list(prior.get("evidence", [])),
            "reviews": list(prior.get("reviews", [])),
            "blocked_reason": prior.get("blocked_reason"),
            "replacement": prior.get("replacement"),
        }
        if prior.get("replacements"):
            generated["replacements"] = list(prior["replacements"])
        for field in (
            "provenance",
            "maturity",
            "definition_state",
            "refinement_required",
            "refinement_trigger",
            "refines",
            "requires_artifact_owner",
        ):
            if field in item:
                generated[field] = deepcopy(item[field])
        if identifier in corrected_history_ids:
            generated["status"] = "blocked"
            generated["blocked_reason"] = "DEPENDENCY_CONTRACT_CHANGED"
        deliverables.append(generated)
    preserved_history = {
        **already_superseded_history,
        **{
            identifier: migration_targets[identifier]
            for identifier in newly_removed_history
        },
    }
    for identifier in sorted(preserved_history):
        prior = deepcopy(existing_deliverables[identifier])
        replacements = list(preserved_history[identifier])
        if identifier in newly_removed_history:
            prior["status"] = "superseded"
            prior["blocked_reason"] = None
            prior["replacement"] = replacements[0]
            prior["replacements"] = replacements
        prior["depends_on"] = [
            dependency
            for dependency in prior.get("depends_on", [])
            if dependency in process_ids or dependency in preserved_history
        ]
        deliverables.append(prior)
    updated["deliverables"] = deliverables

    existing_gates = {item["id"]: item for item in state.get("gates", [])}
    checkpoint_by_gate = {
        item.get("id"): item.get("checkpoint_id")
        for item in process.get("gates", [])
        if isinstance(item, dict) and item.get("id") and item.get("checkpoint_id")
    }
    gate_redirects, gate_migration_blockers = _gate_migration_redirects(state, process)
    if gate_migration_blockers:
        raise ProjectError(
            "invalid or ambiguous gate migration: "
            + json.dumps(gate_migration_blockers[0], sort_keys=True)
        )
    effective_gate_migrations = sorted(set(gate_redirects) & set(existing_gates))
    if effective_gate_migrations and not apply_migrations:
        raise ProjectError(
            "re-tailoring requires explicit --apply-migrations for gates: "
            + ", ".join(effective_gate_migrations)
        )
    explicit_gate_source = {
        target: source for source, target in gate_redirects.items()
    }
    migrated_checkpoint_ids: set[str] = set()
    gates = []
    for generated in _gate_records(process):
        prior = existing_gates.get(generated["id"], {})
        checkpoint_id = checkpoint_by_gate.get(generated["id"])
        implicit_legacy_id = (
            checkpoint_id
            if checkpoint_id
            and generated["id"] == f"gate.{checkpoint_id}"
            and checkpoint_id not in gate_redirects
            else None
        )
        legacy_id = explicit_gate_source.get(
            generated["id"], implicit_legacy_id
        )
        legacy = existing_gates.get(legacy_id, {}) if legacy_id else {}
        if legacy and _gate_has_history(legacy):
            prior_status = prior.get("status", "planned")
            legacy_status = legacy.get("status", "planned")
            prior_approval = prior.get("approval")
            legacy_approval = legacy.get("approval")
            prior_has_history = _gate_has_history(prior)
            if prior_has_history and (
                prior_status != legacy_status
                or (
                    prior_approval is not None
                    and legacy_approval is not None
                    and prior_approval != legacy_approval
                )
            ):
                raise ProjectError(
                    f"gate migration {legacy_id!r} -> {generated['id']!r} "
                    "has conflicting historical status or approval"
                )
            if not prior_has_history:
                prior = legacy
                migrated_checkpoint_ids.add(legacy_id)
            elif prior_status == legacy_status:
                prior_stale_reason = prior.get("stale_reason")
                legacy_stale_reason = legacy.get("stale_reason")
                if (
                    prior_stale_reason
                    and legacy_stale_reason
                    and prior_stale_reason != legacy_stale_reason
                ):
                    raise ProjectError(
                        f"gate migration {legacy_id!r} -> {generated['id']!r} "
                        "has conflicting historical stale reasons"
                    )
                merged = deepcopy(prior)
                for field in ("reviews", "evidence", "blockers"):
                    values = list(merged.get(field, []))
                    for value in legacy.get(field, []):
                        if value not in values:
                            values.append(deepcopy(value))
                    merged[field] = values
                if merged.get("approval") is None and legacy.get("approval") is not None:
                    merged["approval"] = legacy.get("approval")
                merged["review_epoch"] = max(
                    int(prior.get("review_epoch", 0)),
                    int(legacy.get("review_epoch", 0)),
                )
                merged["stale"] = bool(prior.get("stale")) or bool(
                    legacy.get("stale")
                )
                merged["stale_reason"] = (
                    prior_stale_reason or legacy_stale_reason
                )
                prior = merged
                migrated_checkpoint_ids.add(legacy_id)
        elif legacy and legacy_id in gate_redirects:
            migrated_checkpoint_ids.add(legacy_id)
        old_fingerprint = prior.get("requirements_fingerprint")
        if old_fingerprint is None and prior:
            old_fingerprint = requirements_fingerprint(
                prior.get("required_deliverables", []), state
            )
        for field in (
            "status",
            "reviews",
            "evidence",
            "blockers",
            "approval",
            "review_epoch",
            "stale",
            "stale_reason",
        ):
            if field in prior:
                generated[field] = deepcopy(prior[field])
        new_fingerprint = generated["requirements_fingerprint"]
        if prior and old_fingerprint != new_fingerprint:
            generated["status"] = "planned"
            generated["approval"] = None
            generated["review_epoch"] = int(prior.get("review_epoch", 0)) + 1
            generated["stale"] = True
            generated["stale_reason"] = "GATE_REQUIREMENTS_CHANGED"
            blockers = list(generated.get("blockers", []))
            if "GATE_REQUIREMENTS_CHANGED" not in blockers:
                blockers.append("GATE_REQUIREMENTS_CHANGED")
            generated["blockers"] = blockers
        corrected_requirements = sorted(
            corrected_history_ids & set(generated.get("required_deliverables", []))
        )
        if corrected_requirements:
            if generated.get("status") == "approved":
                raise ProjectError(
                    f"dependency correction cannot invalidate approved gate "
                    f"{generated['id']!r}"
                )
            generated["status"] = "planned"
            generated["approval"] = None
            generated["review_epoch"] = int(prior.get("review_epoch", 0)) + 1
            generated["stale"] = True
            generated["stale_reason"] = "DEPENDENCY_CONTRACT_CHANGED"
            blockers = [
                value
                for value in generated.get("blockers", [])
                if value != "GATE_REQUIREMENTS_CHANGED"
            ]
            if "DEPENDENCY_CONTRACT_CHANGED" not in blockers:
                blockers.append("DEPENDENCY_CONTRACT_CHANGED")
            generated["blockers"] = blockers
        gates.append(generated)
    new_gate_ids = {gate["id"] for gate in gates}
    unsafe_gates = [
        identifier
        for identifier, item in existing_gates.items()
        if identifier not in new_gate_ids
        and identifier not in migrated_checkpoint_ids
        and (
            _gate_has_history(item)
            or identifier in claim_linked_entities
        )
    ]
    if unsafe_gates:
        raise ProjectError(
            "re-tailoring would remove active or historical gates: "
            + ", ".join(sorted(unsafe_gates))
        )
    updated["gates"] = gates

    profile = process.get("profile", {})
    task_types = profile.get("task_types") or updated["project"].get("task_types") or ["software"]
    updated["project"]["task_types"] = list(task_types)
    phase_ids = [item.get("id") for item in process.get("phases", []) if item.get("id")]
    if updated["project"].get("phase") not in phase_ids and phase_ids:
        updated["project"]["phase"] = phase_ids[0]
    updated["project"]["name"] = profile.get("name") or updated["project"]["name"]
    apply_phase_pointers(updated, process)

    traceability, traceability_impact = project_traceability_projection(
        state,
        process,
        preserved_history=preserved_history,
    )
    if traceability_impact["blocked"]:
        raise ProjectError(
            "re-tailoring would remove or ambiguously redirect Claim traceability: "
            + json.dumps(traceability_impact["blocked"][0], sort_keys=True)
        )
    updated["traceability"] = traceability
    problems = validate_state(updated)
    if problems:
        raise ProjectError(f"tailored state is invalid: {problems[0]}")
    unchanged = deepcopy(updated)
    unchanged["revision"] = state.get("revision")
    if unchanged == state:
        return state
    return updated


def load_project(project_root: str | Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    paths = project_paths(project_root)
    state = load_state(paths["state"])
    process = load_state(paths["process"]) if paths["process"].exists() else None
    return state, process


def artifact_baseline_preview(project_root: str | Path) -> dict[str, Any]:
    """Return a no-write baseline preview using the shared readiness contract."""

    paths = project_paths(project_root)
    state = load_state(paths["state"])
    issues = validate_state(state)
    if issues:
        raise ProjectError(f"invalid project state: {issues[0]}")
    from .reconcile import preview_artifact_baseline

    preview = preview_artifact_baseline(
        paths["root"], state, bindings_path=paths["bindings"]
    )
    if not isinstance(preview, dict):
        raise ProjectError("artifact baseline preview must be an object")
    from .eligibility import normalize_eligibility

    return normalize_eligibility(preview, state)


def adopt_artifact_baseline(
    project_root: str | Path,
    *,
    actor: str,
    actor_type: str,
    authorized: bool,
    reason: str,
) -> dict[str, Any]:
    """Append an authorized baseline event without changing project or VCS facts."""

    if not isinstance(actor, str) or not actor.strip():
        raise ProjectError("artifact baseline actor must not be empty")
    if actor_type != "human":
        raise ProjectError("artifact baseline adoption requires actor_type 'human'")
    if authorized is not True:
        raise ProjectError("artifact baseline adoption requires --authorized")
    if not isinstance(reason, str) or not reason.strip():
        raise ProjectError("artifact baseline adoption reason must not be empty")

    paths = project_paths(project_root)
    state = load_state(paths["state"])
    state_issues = validate_state(state)
    if state_issues:
        raise ProjectError(f"invalid project state: {state_issues[0]}")
    runtime = load_runtime(paths["root"])
    preview = artifact_baseline_preview(paths["root"])
    if not preview["eligible"]:
        first = next(
            (
                item.get("code") or item.get("reason_code") or item.get("message")
                for item in preview["issues"]
                if isinstance(item, dict)
            ),
            "ARTIFACT_BASELINE_INELIGIBLE",
        )
        raise ProjectError(f"artifact baseline adoption preflight failed: {first}")

    from .reconcile import build_artifact_baseline_adoption

    event = build_artifact_baseline_adoption(
        paths["root"],
        state,
        actor=actor,
        actor_type=actor_type,
        authorized=authorized,
        reason=reason,
        bindings_path=paths["bindings"],
        preview=preview,
    )
    updated_runtime, appended = record_artifact_baseline_adoption(runtime, event)
    if appended:
        save_runtime(paths["root"], updated_runtime)
    snapshot = event["artifact_baseline"]
    return {
        "schema_version": "1.0",
        "status": "passed",
        "eligible": True,
        "preview": False,
        "adopted": appended,
        "idempotent": not appended,
        "baseline_id": snapshot.get("baseline_id"),
        "artifact_baseline": deepcopy(snapshot),
        "eligibility": preview,
        "runtime_revision": updated_runtime.get("revision"),
    }


def context_snapshot(project_root: str | Path) -> dict[str, Any]:
    paths = project_paths(project_root)
    state, process = load_project(project_root)
    issues = validate_state(state)
    if issues:
        raise ProjectError(f"invalid project state: {issues[0]}")
    runtime, expired = expire_claims(load_runtime(project_root))
    if expired:
        save_runtime(project_root, runtime)
    if process is not None:
        consistency = sorted(
            set(
                project_consistency_issues(state, process, runtime)
                + phase_history_issues(state, process, runtime)
            )
        )
        recoverable = {
            "workflow_step 'work' requires one active claim",
        }
        fatal_consistency = [
            issue
            for issue in consistency
            if issue not in recoverable
            and not (
                issue.startswith("in-progress deliverable ")
                and issue.endswith(" has no active claim; recover it before verify")
            )
        ]
        if fatal_consistency:
            raise ProjectError(
                f"inconsistent project bundle: {fatal_consistency[0]}"
            )
    current_phase = state["project"]["phase"]
    eligibility = binding_eligibility(
        paths["root"], state, runtime, bindings_path=paths["bindings"]
    )
    claim_readiness = claim_protocol_readiness(paths["root"], state, runtime)
    status_by_id = {item["id"]: item["status"] for item in state["deliverables"]}
    graph = {item["id"]: item.get("depends_on", []) for item in state["deliverables"]}
    available: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    refinements: list[dict[str, Any]] = []
    for item in state["deliverables"]:
        refinement = deliverable_refinement_status(state, item["id"])
        if refinement.get("refinement_status") != "not_required":
            refinements.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    **refinement,
                }
            )
        if item.get("phase") not in {None, current_phase}:
            continue
        unmet = list(unmet_dependencies(item["id"], graph, status_by_id))
        active_claim = runtime["active_claims"].get(item["id"])
        binding_status = deliverable_binding_status(eligibility, item["id"])
        binding_blocked = not binding_status["eligible"]
        binding_relevant = item["status"] in {"planned", "blocked", "rejected"}
        if (
            item["status"] in {"planned", "blocked", "rejected"}
            and not unmet
            and not active_claim
            and not binding_blocked
            and claim_readiness["eligible"]
        ):
            available.append({"id": item["id"], "title": item["title"], "status": item["status"]})
        orphaned_claim = item["status"] == "in_progress" and not active_claim
        if (
            item["status"] == "blocked"
            or unmet
            or orphaned_claim
            or (binding_relevant and binding_blocked)
        ):
            binding_blockers = binding_status.get("blockers", [])
            binding_reason = next(
                (
                    (
                        blocker.get("reason_code")
                        or blocker.get("message")
                        or blocker.get("code")
                    )
                    if isinstance(blocker, dict)
                    else str(blocker)
                    for blocker in binding_blockers
                    if isinstance(blocker, (dict, str))
                ),
                None,
            )
            blocked.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "status": item["status"],
                    "unmet_dependencies": unmet,
                    "reason": (
                        "active claim lease is missing; recover this deliverable before work continues"
                        if orphaned_claim
                        else item.get("blocked_reason") or binding_reason
                    ),
                    "code": (
                        binding_status.get("issue_codes", [None])[0]
                        if binding_relevant
                        and binding_blocked
                        and binding_status.get("issue_codes")
                        else None
                    ),
                    "recoverable": orphaned_claim,
                    "binding_ready": binding_status["binding_ready"],
                    "issue_codes": binding_status["issue_codes"],
                    "binding_blockers": binding_blockers,
                }
            )
    repo = inspect_repository(paths["root"])
    from .refinement import process_fingerprint

    return {
        "project": state["project"]["name"],
        "phase": state["project"]["phase"],
        "tr": state["project"].get("current_tr"),
        "dcp": state["project"].get("current_dcp"),
        "gate": state["project"].get("current_gate"),
        "workflow_step": state["project"]["workflow_step"],
        "state_revision": state["revision"],
        "process_fingerprint": (
            process_fingerprint(process) if process is not None else None
        ),
        "refinements": sorted(refinements, key=lambda item: item["id"]),
        "refinement_due": sorted(
            item["id"]
            for item in refinements
            if item.get("refinement_status") == "due"
        ),
        "available_tasks": available,
        "blocked_items": blocked,
        "active_claims": runtime["active_claims"],
        "recoverable_claims": sorted(
            item["id"] for item in blocked if item.get("recoverable") is True
        ),
        "claim_readiness": claim_readiness,
        "eligibility": eligibility,
        "repository": repo.as_dict(),
    }


def refresh_project(project_root: str | Path) -> dict[str, Any]:
    paths = project_paths(project_root)
    locale = load_project_locale(paths["root"])
    state, process = load_project(project_root)
    if process is None:
        raise ProjectError(get_translator(locale).text("error.tailored_process_missing"))
    current_runtime, _ = expire_claims(load_runtime(paths["root"]))
    consistency = sorted(
        set(
            project_consistency_issues(state, process, current_runtime)
            + phase_history_issues(state, process, current_runtime)
        )
    )
    if consistency:
        raise ProjectError(f"inconsistent project bundle: {consistency[0]}")
    eligibility = binding_eligibility(
        paths["root"], state, current_runtime, bindings_path=paths["bindings"]
    )
    bindings = None
    if paths["bindings"].is_file():
        try:
            from .reconcile import load_artifact_bindings

            bindings = load_artifact_bindings(paths["bindings"])
        except (OSError, ValueError):
            # Eligibility already carries a stable diagnostic.  Refresh still
            # publishes a Dashboard that can explain why work is blocked.
            bindings = None
    repo = inspect_repository(paths["root"])
    updated = revised_copy(state)
    updated["project"]["repository"] = _portable_repository_record(repo)
    issues = validate_state(updated)
    if issues:
        raise ProjectError(f"cannot refresh invalid state: {issues[0]}")
    from .dashboard import render_dashboard

    write_state(paths["state"], updated)
    manifest = render_dashboard(
        paths["root"],
        process,
        updated,
        runtime=current_runtime,
        bindings=bindings,
        eligibility=eligibility,
        locale=locale,
    )
    runtime = record_event(
        current_runtime,
        "refresh",
        details={"state_revision": updated["revision"]},
    )
    runtime["last_refresh"] = {
        "state_revision": updated["revision"],
        "manifest": ".ipd/dashboard/manifest.json",
    }
    save_runtime(paths["root"], runtime)
    return manifest


def verify_project(project_root: str | Path) -> dict[str, Any]:
    paths = project_paths(project_root)
    locale = load_project_locale(paths["root"])
    translator = get_translator(locale)
    state, process = load_project(project_root)
    runtime, _ = expire_claims(load_runtime(paths["root"]))
    issue_rows = [
        {"path": issue.path, "message": issue.message} for issue in validate_state(state)
    ]
    eligibility = binding_eligibility(
        paths["root"], state, runtime, bindings_path=paths["bindings"]
    )
    for issue in eligibility["issues"]:
        if not isinstance(issue, dict) or issue.get("severity") != "error":
            continue
        issue_rows.append(
            {
                "path": issue.get("path") or "$.eligibility",
                "code": issue.get("code") or "binding_ineligible",
                "message": (
                    issue.get("message")
                    or issue.get("reason_code")
                    or issue.get("code")
                    or "artifact binding eligibility failed"
                ),
            }
        )
    if process is None:
        issue_rows.append(
            {
                "path": "$.process",
                "code": "tailored_process_missing",
                "message": translator.text("report.dashboard.process_missing"),
            }
        )
    else:
        try:
            from .process_extensions import load_process_extension
            from .tailoring import (
                load_profile,
                tailor_profile,
                validate_tailored_process,
            )

            for message in validate_tailored_process(process):
                issue_rows.append({"path": "$.process", "message": message})
            extension_source = (
                paths["extensions"] if paths["extensions"].is_file() else None
            )
            extension = load_process_extension(extension_source)
            compiled = tailor_profile(load_profile(paths["profile"]), extension)
            legacy_with_v2_inputs = process.get("schema_version") == "1.0" and (
                bool(compiled.get("profile", {}).get("capability_patterns"))
                or any(
                    extension.get(field)
                    for field in (
                        "activities",
                        "deliverables",
                        "dependencies",
                        "checkpoint_criteria",
                        "migrations",
                        "refinement_requirements",
                        "refinements",
                    )
                )
            )
            if legacy_with_v2_inputs or not _process_matches_compilation(
                process, compiled
            ):
                issue_rows.append(
                    {
                        "path": "$.process",
                        "code": "tailored_process_stale",
                        "message": (
                            "tailored process does not match task_profile.yaml and "
                            "process_extensions.yaml; run ipdctl tailor"
                        ),
                    }
                )
        except (ImportError, OSError, TypeError, ValueError) as exc:
            issue_rows.append(
                {
                    "path": "$.tailoring_inputs",
                    "code": "tailoring_input_invalid",
                    "message": str(exc),
                }
            )
        for message in project_consistency_issues(state, process, runtime):
            issue_rows.append(
                {
                    "path": "$.project_bundle",
                    "code": "project_bundle_inconsistent",
                    "message": message,
                }
            )
    required_outputs = {
        ".ipd/dashboard/index.html",
        ".ipd/dashboard/assets/ipd_flow.svg",
        ".ipd/dashboard/assets/current_status_flow.svg",
        ".ipd/dashboard/assets/deliverable_dependency.svg",
        ".ipd/dashboard/phases/concept.svg",
        ".ipd/dashboard/phases/plan.svg",
        ".ipd/dashboard/phases/develop.svg",
        ".ipd/dashboard/phases/qualify.svg",
        ".ipd/dashboard/phases/launch.svg",
        ".ipd/dashboard/phases/lifecycle.svg",
        ".ipd/dashboard/matrices/deliverable_matrix.html",
        ".ipd/dashboard/matrices/gate_matrix.html",
        ".ipd/dashboard/data/state.json",
        ".ipd/dashboard/data/graph.json",
    }
    phase_views = {
        phase: f"phases/{phase}.svg"
        for phase in ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
    }
    expected_views = {
        "dashboard": "index.html",
        "process_flow": "assets/ipd_flow.svg",
        "current_status": "assets/current_status_flow.svg",
        "deliverable_dependency": "assets/deliverable_dependency.svg",
        "deliverable_matrix": "matrices/deliverable_matrix.html",
        "gate_matrix": "matrices/gate_matrix.html",
        "state": "data/state.json",
        "graph": "data/graph.json",
        "phases": phase_views,
    }
    expected_files = sorted(
        Path(relative).relative_to(".ipd/dashboard").as_posix()
        for relative in required_outputs
    ) + ["manifest.json"]
    manifest_path = paths["dashboard"] / "manifest.json"
    if not manifest_path.exists():
        issue_rows.append(
            {
                "path": "$.dashboard",
                "code": "dashboard_manifest_missing",
                "message": translator.text("report.dashboard.manifest_missing"),
            }
        )
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest root must be an object")
            if manifest.get("schema_version") != "2.1":
                issue_rows.append(
                    {
                        "path": "$.dashboard.schema_version",
                        "code": "dashboard_schema_unsupported",
                        "message": translator.text("report.dashboard.schema_unsupported"),
                    }
                )
            expected_contract = {
                "project": state.get("project", {}).get("name"),
                "source_revision": state.get("revision"),
                "process_schema_version": (
                    process.get("schema_version") if process is not None else None
                ),
                "output_directory": ".ipd/dashboard",
            }
            for field, expected in expected_contract.items():
                if manifest.get(field) != expected:
                    issue_rows.append(
                        {
                            "path": f"$.dashboard.{field}",
                            "code": "dashboard_manifest_contract_mismatch",
                            "message": f"dashboard manifest {field} does not match its source facts",
                        }
                    )
            files = manifest.get("files")
            if files != expected_files:
                issue_rows.append(
                    {
                        "path": "$.dashboard.files",
                        "code": "dashboard_manifest_contract_mismatch",
                        "message": "dashboard manifest files do not match the managed output contract",
                    }
                )
            if manifest.get("views") != expected_views:
                issue_rows.append(
                    {
                        "path": "$.dashboard.views",
                        "code": "dashboard_manifest_contract_mismatch",
                        "message": "dashboard manifest views do not match the managed view contract",
                    }
                )
            if manifest.get("state_revision") != state.get("revision"):
                issue_rows.append(
                    {
                        "path": "$.dashboard",
                        "code": "dashboard_state_stale",
                        "message": translator.text("report.dashboard.stale"),
                    }
                )
            if manifest.get("locale") != locale:
                issue_rows.append(
                    {
                        "path": "$.dashboard.locale",
                        "code": "dashboard_locale_stale",
                        "message": translator.text("report.dashboard.locale_stale"),
                    }
                )
            if process is not None and manifest.get("process_sha256") != _stable_value_hash(process):
                issue_rows.append(
                    {
                        "path": "$.dashboard.process_sha256",
                        "code": "dashboard_process_stale",
                        "message": translator.text("report.dashboard.process_stale"),
                    }
                )
            if manifest.get("state_sha256") != _stable_value_hash(state):
                issue_rows.append(
                    {
                        "path": "$.dashboard.state_sha256",
                        "code": "dashboard_state_content_stale",
                        "message": translator.text("report.dashboard.stale"),
                    }
                )
            if manifest.get("runtime_claims_sha256") != _stable_value_hash(
                runtime.get("active_claims", {})
            ):
                issue_rows.append(
                    {
                        "path": "$.dashboard.runtime_claims_sha256",
                        "code": "dashboard_runtime_stale",
                        "message": translator.text("report.dashboard.runtime_stale"),
                    }
                )
            if manifest.get("bindings_sha256") != eligibility.get(
                "bindings_sha256"
            ):
                issue_rows.append(
                    {
                        "path": "$.dashboard.bindings_sha256",
                        "code": "dashboard_bindings_stale",
                        "message": translator.text(
                            "report.dashboard.bindings_stale"
                        ),
                    }
                )
            if manifest.get("eligibility_sha256") != eligibility_fingerprint(
                eligibility
            ):
                issue_rows.append(
                    {
                        "path": "$.dashboard.eligibility_sha256",
                        "code": "dashboard_eligibility_stale",
                        "message": translator.text(
                            "report.dashboard.eligibility_stale"
                        ),
                    }
                )
            outputs = manifest.get("outputs", [])
            if not isinstance(outputs, list) or not outputs:
                issue_rows.append(
                    {
                        "path": "$.dashboard.outputs",
                        "code": "dashboard_outputs_missing",
                        "message": translator.text("report.dashboard.outputs_missing"),
                    }
                )
                outputs = []
            output_records: set[str] = set()
            dashboard_root = paths["dashboard"].resolve()
            for index, output in enumerate(outputs):
                relative = output.get("path") if isinstance(output, dict) else None
                expected_hash = output.get("sha256") if isinstance(output, dict) else None
                if not isinstance(relative, str) or not isinstance(expected_hash, str):
                    issue_rows.append(
                        {"path": f"$.dashboard.outputs[{index}]", "message": "invalid output record"}
                    )
                    continue
                if relative in output_records:
                    issue_rows.append(
                        {
                            "path": f"$.dashboard.outputs[{index}]",
                            "message": f"duplicate output: {relative}",
                        }
                    )
                    continue
                output_records.add(relative)
                output_path = (paths["root"] / relative).resolve()
                try:
                    output_path.relative_to(dashboard_root)
                except ValueError:
                    issue_rows.append(
                        {
                            "path": f"$.dashboard.outputs[{index}]",
                            "message": f"output leaves dashboard directory: {relative}",
                        }
                    )
                    continue
                if not output_path.is_file():
                    issue_rows.append(
                        {"path": f"$.dashboard.outputs[{index}]", "message": f"missing output: {relative}"}
                    )
                    continue
                actual_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    issue_rows.append(
                        {"path": f"$.dashboard.outputs[{index}]", "message": f"output hash mismatch: {relative}"}
                    )
            for missing in sorted(required_outputs - output_records):
                issue_rows.append(
                    {"path": "$.dashboard.outputs", "message": f"required output is missing: {missing}"}
                )
            for unexpected in sorted(output_records - required_outputs):
                issue_rows.append(
                    {
                        "path": "$.dashboard.outputs",
                        "message": f"unexpected managed output: {unexpected}",
                    }
                )
            expected_project_files = required_outputs | {".ipd/dashboard/manifest.json"}
            actual_files = {
                candidate.relative_to(paths["root"]).as_posix()
                for candidate in dashboard_root.rglob("*")
                if candidate.is_file()
            }
            for unexpected in sorted(actual_files - expected_project_files):
                issue_rows.append(
                    {
                        "path": "$.dashboard",
                        "message": f"unexpected dashboard file: {unexpected}",
                    }
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issue_rows.append({"path": "$.dashboard", "message": f"invalid manifest: {exc}"})

    def check_evidence(value: Any, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        if "://" in value or value.startswith(("git:", "svn:", "record:")):
            return
        candidate = (paths["root"] / value).resolve()
        try:
            candidate.relative_to(paths["root"])
        except ValueError:
            issue_rows.append({"path": path, "message": "evidence path leaves project root"})
            return
        if not candidate.exists():
            issue_rows.append({"path": path, "message": f"evidence does not exist: {value}"})

    for index, deliverable in enumerate(state.get("deliverables", [])):
        if deliverable.get("status") not in {"ready_for_review", "in_review", "accepted", "rejected"}:
            continue
        for evidence_index, evidence in enumerate(deliverable.get("evidence", [])):
            check_evidence(evidence, f"$.deliverables[{index}].evidence[{evidence_index}]")
        for review_index, review in enumerate(deliverable.get("reviews", [])):
            check_evidence(
                review.get("evidence"),
                f"$.deliverables[{index}].reviews[{review_index}].evidence",
            )
    for index, gate in enumerate(state.get("gates", [])):
        for review_index, review in enumerate(gate.get("reviews", [])):
            check_evidence(
                review.get("evidence"),
                f"$.gates[{index}].reviews[{review_index}].evidence",
            )

    reconciliation = None
    try:
        from .reconcile import reconcile_project

        reconciliation = reconcile_project(
            paths["root"], state, runtime=runtime, write=False
        )
        for issue in reconciliation.get("issues", []):
            if issue.get("severity") == "error":
                issue_rows.append(
                    {
                        "path": "$.reconciliation",
                        "message": f"{issue.get('code')}: {issue.get('path') or issue.get('message')}",
                    }
                )
    except (ImportError, OSError, ValueError) as exc:
        issue_rows.append({"path": "$.reconciliation", "message": str(exc)})
    artifact_baseline = None
    if not issue_rows:
        try:
            from .reconcile import artifact_baseline_snapshot

            artifact_baseline = artifact_baseline_snapshot(
                paths["root"], state, bindings_path=paths["bindings"]
            )
        except (ImportError, OSError, ValueError) as exc:
            issue_rows.append(
                {
                    "path": "$.artifact_baseline",
                    "code": "artifact_baseline_snapshot_failed",
                    "message": str(exc),
                }
            )
    if process is not None:
        from .dashboard import render_dashboard
        from .reconcile import load_artifact_bindings

        def prospective_runtime_for(status: str) -> dict[str, Any]:
            details: dict[str, Any] = {
                "status": status,
                "state_revision": state.get("revision"),
                "input_fingerprint": "pending-dashboard-render",
            }
            if status == "passed" and artifact_baseline is not None:
                details["artifact_baseline"] = deepcopy(artifact_baseline)
                details["baseline_id"] = artifact_baseline.get("baseline_id")
            candidate = record_event(runtime, "verify", details=details)
            candidate["last_verification"] = {
                "status": status,
                "state_revision": state.get("revision"),
                "input_fingerprint": "pending-dashboard-render",
            }
            previous = runtime.get("last_verification")
            if status == "passed" and artifact_baseline is not None:
                candidate["last_verification"]["artifact_baseline"] = deepcopy(
                    artifact_baseline
                )
            elif isinstance(previous, dict) and isinstance(
                previous.get("artifact_baseline"), dict
            ):
                candidate["last_verification"]["artifact_baseline"] = deepcopy(
                    previous["artifact_baseline"]
                )
            return candidate

        prospective_status = "passed" if not issue_rows else "failed"
        prospective_runtime = prospective_runtime_for(prospective_status)
        prospective_eligibility = binding_eligibility(
            paths["root"],
            state,
            prospective_runtime,
            bindings_path=paths["bindings"],
        )
        if prospective_status == "passed" and not prospective_eligibility.get(
            "eligible"
        ):
            first = next(
                (
                    item.get("code")
                    or item.get("reason_code")
                    or item.get("message")
                    for item in prospective_eligibility.get("issues", [])
                    if isinstance(item, dict)
                ),
                "post-verification eligibility failed",
            )
            issue_rows.append(
                {
                    "path": "$.eligibility",
                    "code": "post_verification_eligibility_failed",
                    "message": str(first),
                }
            )
            prospective_status = "failed"
            prospective_runtime = prospective_runtime_for(prospective_status)
            prospective_eligibility = binding_eligibility(
                paths["root"],
                state,
                prospective_runtime,
                bindings_path=paths["bindings"],
            )
        eligibility = prospective_eligibility
        try:
            bindings = load_artifact_bindings(paths["bindings"])
        except (OSError, ValueError):
            bindings = None
        try:
            render_dashboard(
                paths["root"],
                process,
                state,
                runtime=prospective_runtime,
                bindings=bindings,
                eligibility=eligibility,
                claim_readiness=claim_protocol_readiness(
                    paths["root"],
                    state,
                    prospective_runtime,
                    verification_succeeded=prospective_status == "passed",
                ),
                locale=locale,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ProjectError(
                f"post-verification Dashboard render failed: {exc}"
            ) from exc

    input_fingerprint = verification_input_fingerprint(
        paths["root"], state=state, runtime=runtime
    )
    report = {
        "schema_version": "1.0",
        "locale": locale,
        "status": "passed" if not issue_rows else "failed",
        "state_revision": state.get("revision"),
        "input_fingerprint": input_fingerprint,
        "issues": issue_rows,
        "repository": _portable_repository_record(inspect_repository(paths["root"])),
        "reconciliation": reconciliation,
        "eligibility": eligibility,
    }
    write_state(paths["verify_report"], report)
    verify_details: dict[str, Any] = {
        "status": report["status"],
        "state_revision": state.get("revision"),
        "input_fingerprint": input_fingerprint,
    }
    if report["status"] == "passed" and artifact_baseline is not None:
        verify_details["artifact_baseline"] = deepcopy(artifact_baseline)
        verify_details["baseline_id"] = artifact_baseline.get("baseline_id")
    runtime = record_event(runtime, "verify", details=verify_details)
    if report["status"] == "passed" and process is not None:
        from .lifecycle import phase_completion

        phase_records = sorted(
            [item for item in process.get("phases", []) if isinstance(item, dict)],
            key=lambda item: (item.get("sequence", 0), item.get("id", "")),
        )
        final_phase = phase_records[-1].get("id") if phase_records else None
        completion = phase_completion(state, process)
        already_recorded = any(
            event.get("action") == "lifecycle_complete"
            for event in runtime.get("events", [])
        )
        if (
            final_phase is not None
            and state.get("project", {}).get("phase") == final_phase
            and completion.get("complete") is True
            and not already_recorded
        ):
            runtime = record_event(
                runtime,
                "lifecycle_complete",
                details={
                    "phase": final_phase,
                    "state_revision": state.get("revision"),
                },
            )
    previous_verification = runtime.get("last_verification")
    runtime["last_verification"] = {
        "status": report["status"],
        "state_revision": state.get("revision"),
        "input_fingerprint": input_fingerprint,
    }
    if report["status"] == "passed" and artifact_baseline is not None:
        runtime["last_verification"]["artifact_baseline"] = artifact_baseline
    elif isinstance(previous_verification, dict) and isinstance(
        previous_verification.get("artifact_baseline"), dict
    ):
        # A failed attempt must not erase the exact baseline established by
        # the most recent successful verification.
        runtime["last_verification"]["artifact_baseline"] = deepcopy(
            previous_verification["artifact_baseline"]
        )
    save_runtime(paths["root"], runtime)
    return report

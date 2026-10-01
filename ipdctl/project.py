"""Project-level orchestration shared by the CLI and integrations."""

from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from .dependencies import unmet_dependencies
from .eligibility import (
    binding_eligibility,
    claim_protocol_readiness,
    deliverable_binding_status,
    eligibility_fingerprint,
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
    if set(process_deliverables) != set(state_deliverables):
        issues.append("process and state deliverable IDs differ; run ipdctl tailor")
    for identifier in sorted(set(process_deliverables) & set(state_deliverables)):
        expected = process_deliverables[identifier]
        actual = state_deliverables[identifier]
        for field in ("title", "phase", "activity_id", "review_required"):
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
        for name in ("profile", "process", "state", "bindings")
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


def project_paths(project_root: str | Path) -> dict[str, Path]:
    root = Path(project_root).resolve()
    ipd = root / ".ipd"
    return {
        "root": root,
        "ipd": ipd,
        "profile": ipd / "task_profile.yaml",
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
    protected = [state_path, paths["profile"], paths["runtime"]]
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
        "presentation": {"locale": locale},
    }
    write_state(paths["profile"], profile)
    write_state(state_path, create_initial_state(name, task_types))
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
        records.append(
            {
                "id": item["id"],
                "title": item.get("title") or item["id"],
                "kind": item.get("kind", "Gate"),
                "status": "planned",
                "phase": item.get("phase"),
                "required_deliverables": list(item.get("required_deliverables", [])),
                "reviews": [],
                "evidence": [],
                "blockers": [],
                "approval": None,
            }
        )
    return records


def sync_state_with_process(
    state: dict[str, Any], process: dict[str, Any]
) -> dict[str, Any]:
    """Merge a deterministic tailored process into state without losing facts."""

    existing_deliverables = {item["id"]: item for item in state.get("deliverables", [])}
    process_ids = {
        item.get("id")
        for item in process.get("deliverables", [])
        if isinstance(item, dict) and item.get("id")
    }
    unsafe_removed = [
        identifier
        for identifier, item in existing_deliverables.items()
        if identifier not in process_ids and item.get("status") != "planned"
    ]
    if unsafe_removed:
        raise ProjectError(
            "re-tailoring would remove active or historical deliverables: "
            + ", ".join(sorted(unsafe_removed))
        )

    updated = revised_copy(state)
    deliverables: list[dict[str, Any]] = []
    for item in process.get("deliverables", []):
        identifier = item["id"]
        prior = existing_deliverables.get(identifier, {})
        deliverables.append(
            {
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
        )
    updated["deliverables"] = deliverables

    existing_gates = {item["id"]: item for item in state.get("gates", [])}
    checkpoint_by_gate = {
        item.get("id"): item.get("checkpoint_id")
        for item in process.get("gates", [])
        if isinstance(item, dict) and item.get("id") and item.get("checkpoint_id")
    }
    migrated_checkpoint_ids: set[str] = set()
    gates = []
    for generated in _gate_records(process):
        prior = existing_gates.get(generated["id"], {})
        legacy_id = checkpoint_by_gate.get(generated["id"])
        legacy = existing_gates.get(legacy_id, {}) if legacy_id else {}
        if legacy and legacy.get("status", "planned") != "planned":
            prior_status = prior.get("status", "planned")
            legacy_status = legacy.get("status", "planned")
            if prior_status == "planned":
                prior = legacy
                migrated_checkpoint_ids.add(legacy_id)
            elif prior_status == legacy_status:
                merged = deepcopy(prior)
                for field in ("reviews", "evidence", "blockers"):
                    values = list(merged.get(field, []))
                    for value in legacy.get(field, []):
                        if value not in values:
                            values.append(deepcopy(value))
                    merged[field] = values
                if merged.get("approval") is None and legacy.get("approval") is not None:
                    merged["approval"] = legacy.get("approval")
                prior = merged
                migrated_checkpoint_ids.add(legacy_id)
        for field in ("status", "reviews", "evidence", "blockers", "approval"):
            if field in prior:
                generated[field] = deepcopy(prior[field])
        gates.append(generated)
    new_gate_ids = {gate["id"] for gate in gates}
    unsafe_gates = [
        identifier
        for identifier, item in existing_gates.items()
        if identifier not in new_gate_ids
        and identifier not in migrated_checkpoint_ids
        and item.get("status") != "planned"
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

    entity_ids = {item["id"] for item in deliverables} | {item["id"] for item in gates}
    traceability: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in process.get("dependencies", []):
        source = edge.get("source")
        target = edge.get("target")
        relation = edge.get("relation", "depends_on")
        key = (source, target, relation)
        if source in entity_ids and target in entity_ids and key not in seen:
            traceability.append({"source": source, "target": target, "relation": relation})
            seen.add(key)
    updated["traceability"] = traceability
    problems = validate_state(updated)
    if problems:
        raise ProjectError(f"tailored state is invalid: {problems[0]}")
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
                project_consistency_issues(state, process)
                + phase_history_issues(state, process, runtime)
            )
        )
        if consistency:
            raise ProjectError(f"inconsistent project bundle: {consistency[0]}")
    current_phase = state["project"]["phase"]
    eligibility = binding_eligibility(
        paths["root"], state, runtime, bindings_path=paths["bindings"]
    )
    claim_readiness = claim_protocol_readiness(paths["root"], state, runtime)
    status_by_id = {item["id"]: item["status"] for item in state["deliverables"]}
    graph = {item["id"]: item.get("depends_on", []) for item in state["deliverables"]}
    available: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in state["deliverables"]:
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
    return {
        "project": state["project"]["name"],
        "phase": state["project"]["phase"],
        "tr": state["project"].get("current_tr"),
        "dcp": state["project"].get("current_dcp"),
        "gate": state["project"].get("current_gate"),
        "workflow_step": state["project"]["workflow_step"],
        "state_revision": state["revision"],
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
            project_consistency_issues(state, process)
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
            from .tailoring import validate_tailored_process

            for message in validate_tailored_process(process):
                issue_rows.append({"path": "$.process", "message": message})
        except ImportError:
            pass
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

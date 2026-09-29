"""Project-level orchestration shared by the CLI and integrations."""

from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from .dependencies import unmet_dependencies
from .repository import inspect_repository
from .runtime import (
    create_runtime_state,
    load_runtime,
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
    force: bool = False,
) -> dict[str, Path]:
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
    records: list[dict[str, Any]] = []
    for collection, kind in (
        ("technical_reviews", "TR"),
        ("decision_checkpoints", "DCP"),
        ("gates", "Gate"),
    ):
        for item in process.get(collection, []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            records.append(
                {
                    "id": item["id"],
                    "title": item.get("title") or item["id"],
                    "kind": kind,
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
    gates = []
    for generated in _gate_records(process):
        prior = existing_gates.get(generated["id"], {})
        for field in ("status", "reviews", "evidence", "blockers", "approval"):
            if field in prior:
                generated[field] = deepcopy(prior[field])
        gates.append(generated)
    unsafe_gates = [
        identifier
        for identifier, item in existing_gates.items()
        if identifier not in {gate["id"] for gate in gates} and item.get("status") != "planned"
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
    current_phase = updated["project"].get("phase")
    for project_field, collection in (
        ("current_tr", "technical_reviews"),
        ("current_dcp", "decision_checkpoints"),
        ("current_gate", "gates"),
    ):
        candidates = [
            item["id"]
            for item in process.get(collection, [])
            if item.get("phase") == current_phase
        ]
        updated["project"][project_field] = candidates[0] if candidates else None

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


def context_snapshot(project_root: str | Path) -> dict[str, Any]:
    paths = project_paths(project_root)
    state, _ = load_project(project_root)
    issues = validate_state(state)
    if issues:
        raise ProjectError(f"invalid project state: {issues[0]}")
    runtime = load_runtime(project_root)
    status_by_id = {item["id"]: item["status"] for item in state["deliverables"]}
    graph = {item["id"]: item.get("depends_on", []) for item in state["deliverables"]}
    available: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in state["deliverables"]:
        unmet = list(unmet_dependencies(item["id"], graph, status_by_id))
        active_claim = runtime["active_claims"].get(item["id"])
        if item["status"] in {"planned", "blocked", "rejected"} and not unmet and not active_claim:
            available.append({"id": item["id"], "title": item["title"], "status": item["status"]})
        if item["status"] == "blocked" or unmet:
            blocked.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "status": item["status"],
                    "unmet_dependencies": unmet,
                    "reason": item.get("blocked_reason"),
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
        "repository": repo.as_dict(),
    }


def refresh_project(project_root: str | Path) -> dict[str, Any]:
    paths = project_paths(project_root)
    state, process = load_project(project_root)
    if process is None:
        raise ProjectError("tailored process does not exist; run ipdctl tailor first")
    repo = inspect_repository(paths["root"])
    updated = revised_copy(state)
    updated["project"]["repository"] = _portable_repository_record(repo)
    issues = validate_state(updated)
    if issues:
        raise ProjectError(f"cannot refresh invalid state: {issues[0]}")
    write_state(paths["state"], updated)
    from .dashboard import render_dashboard

    manifest = render_dashboard(paths["root"], process, updated)
    runtime = record_event(
        load_runtime(paths["root"]),
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
    state, process = load_project(project_root)
    issue_rows = [
        {"path": issue.path, "message": issue.message} for issue in validate_state(state)
    ]
    if process is None:
        issue_rows.append({"path": "$.process", "message": "tailored process is missing"})
    else:
        try:
            from .tailoring import validate_tailored_process

            for message in validate_tailored_process(process):
                issue_rows.append({"path": "$.process", "message": message})
        except ImportError:
            pass
    manifest_path = paths["dashboard"] / "manifest.json"
    if not manifest_path.exists():
        issue_rows.append({"path": "$.dashboard", "message": "dashboard manifest is missing"})
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("state_revision") != state.get("revision"):
                issue_rows.append(
                    {"path": "$.dashboard", "message": "dashboard is stale for project state"}
                )
            for index, output in enumerate(manifest.get("outputs", [])):
                relative = output.get("path") if isinstance(output, dict) else None
                expected_hash = output.get("sha256") if isinstance(output, dict) else None
                if not isinstance(relative, str) or not isinstance(expected_hash, str):
                    issue_rows.append(
                        {"path": f"$.dashboard.outputs[{index}]", "message": "invalid output record"}
                    )
                    continue
                output_path = paths["root"] / relative
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
        except (OSError, json.JSONDecodeError) as exc:
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

        reconciliation = reconcile_project(paths["root"], state, write=False)
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
    report = {
        "schema_version": "1.0",
        "status": "passed" if not issue_rows else "failed",
        "state_revision": state.get("revision"),
        "issues": issue_rows,
        "repository": _portable_repository_record(inspect_repository(paths["root"])),
        "reconciliation": reconciliation,
    }
    write_state(paths["verify_report"], report)
    runtime = record_event(
        load_runtime(paths["root"]),
        "verify",
        details={"status": report["status"], "state_revision": state.get("revision")},
    )
    runtime["last_verification"] = {
        "status": report["status"],
        "state_revision": state.get("revision"),
    }
    save_runtime(paths["root"], runtime)
    return report

#!/usr/bin/env python3
"""Qualify an in-place v0.4.1-beta project upgrade to v0.5 source.

The probe creates the legacy project exclusively with the published local Git
tag.  It then switches only the CLI implementation to the current source tree:
``init`` is deliberately never replayed.  The scenario covers preserved
lifecycle history, one applied progressive-refinement event, Agent runtime and
Dashboard readability, a no-op tailoring preview, and an explicit preview of
one v0.5 capability opt-in.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


RELEASE_TAG = "v0.4.1-beta"
ROOT = Path(__file__).resolve().parents[1]
REFINEMENT_ROOT = "concept.legacy_architecture_baseline"
REFINEMENT_CHILD = "concept.legacy_sensor_architecture"
REFINEMENT_PLAN_ID = "refinement.legacy_architecture.v1"
NEW_CAPABILITY = "interface_contract_and_integration"
NEW_CAPABILITY_DELIVERABLES = {
    "interface.contract_baseline",
    "interface.integration_evidence",
    "interface.conformance_report",
}
EXPECTED_DASHBOARD_FILES = {
    "index.html",
    "assets/ipd_flow.svg",
    "assets/current_status_flow.svg",
    "assets/deliverable_dependency.svg",
    "phases/concept.svg",
    "phases/plan.svg",
    "phases/develop.svg",
    "phases/qualify.svg",
    "phases/launch.svg",
    "phases/lifecycle.svg",
    "matrices/deliverable_matrix.html",
    "matrices/gate_matrix.html",
    "data/state.json",
    "data/graph.json",
    "manifest.json",
}


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _cli(source: Path, project: Path, *arguments: str) -> str:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source)
    return _run(
        [sys.executable, "-B", "-m", "ipdctl", *arguments],
        cwd=project,
        env=environment,
    ).stdout


def _json_output(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("CLI JSON output must be an object")
    return value


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"YAML document must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(project: Path) -> dict[str, str]:
    return {
        path.relative_to(project).as_posix(): _sha256(path)
        for path in sorted(project.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(project).parts
    }


def _git(project: Path, *arguments: str) -> None:
    _run(["git", *arguments], cwd=project)


def _record(rows: Sequence[Mapping[str, Any]], identifier: str) -> dict[str, Any]:
    for row in rows:
        if row.get("id") == identifier:
            return dict(row)
    raise RuntimeError(f"missing record: {identifier}")


def _process_fingerprint(process: Mapping[str, Any]) -> str:
    """Mirror the public stable fingerprint contract used by refinement plans."""

    normalized = deepcopy(dict(process))
    refinements = normalized.get("refinements", [])
    if isinstance(refinements, list):
        for refinement in refinements:
            if isinstance(refinement, dict):
                refinement.pop("result_process_fingerprint", None)
                refinement.pop("invalidated_gates", None)
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _dashboard_inventory(project: Path) -> set[str]:
    dashboard = project / ".ipd" / "dashboard"
    return {
        path.relative_to(dashboard).as_posix()
        for path in dashboard.rglob("*")
        if path.is_file()
    }


def _assert_dashboard_readable(project: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    dashboard = project / ".ipd" / "dashboard"
    inventory = _dashboard_inventory(project)
    if inventory != EXPECTED_DASHBOARD_FILES:
        raise RuntimeError(
            "Dashboard inventory mismatch: "
            f"missing={sorted(EXPECTED_DASHBOARD_FILES - inventory)}, "
            f"extra={sorted(inventory - EXPECTED_DASHBOARD_FILES)}"
        )
    if len((dashboard / "index.html").read_text(encoding="utf-8")) < 100:
        raise RuntimeError("Dashboard index.html is empty or truncated")
    state = _json_output((dashboard / "data" / "state.json").read_text(encoding="utf-8"))
    graph = _json_output((dashboard / "data" / "graph.json").read_text(encoding="utf-8"))
    return state, graph


def _assert_zero_diff(preview: Mapping[str, Any]) -> None:
    unexpected = {
        field: preview.get(field)
        for field in ("added", "removed", "changed", "ambiguous", "migrations")
        if preview.get(field)
    }
    if unexpected:
        raise RuntimeError(f"no-op v0.5 tailoring preview changed the process: {unexpected}")


def qualify() -> dict[str, Any]:
    _run(["git", "rev-parse", "--verify", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="ipd-v041-upgrade-") as directory:
        temporary = Path(directory)
        archive = temporary / "legacy.zip"
        legacy_source = temporary / "legacy-source"
        project = temporary / "project"
        _run(
            [
                "git",
                "archive",
                "--format=zip",
                f"--output={archive}",
                RELEASE_TAG,
            ],
            cwd=ROOT,
        )
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(legacy_source)

        project.mkdir()
        _git(project, "init", "-b", "main")
        _git(project, "config", "user.name", "IPD Upgrade Test")
        _git(project, "config", "user.email", "ipd-upgrade@example.invalid")
        (project / "README.md").write_text(
            "# v0.4.1 upgrade fixture\n", encoding="utf-8", newline="\n"
        )
        _git(project, "add", "README.md")
        _git(project, "commit", "-m", "Create project baseline")

        # Build all legacy authorities and history with the published tag only.
        _cli(
            legacy_source,
            project,
            "init",
            str(project),
            "--name",
            "v041-upgrade",
            "--locale",
            "en",
            "--task-type",
            "software",
        )
        profile_path = project / ".ipd" / "task_profile.yaml"
        process_path = project / ".ipd" / "tailored_process.yaml"
        state_path = project / ".ipd" / "project_state.yaml"
        extension_path = project / ".ipd" / "process_extensions.yaml"
        runtime_path = project / ".ipd" / "agent_runtime.yaml"
        bindings_path = project / ".ipd" / "artifact_bindings.yaml"

        profile = _load(profile_path)
        if profile.get("capability_patterns", []) != []:
            raise RuntimeError("legacy profile must not enable a capability pattern")

        extension = _load(extension_path)
        extension["extension_id"] = "upgrade.v041_refinement_fixture"
        extension["activities"].append(
            {
                "id": "concept.define_legacy_architecture",
                "title": "Define legacy project architecture",
                "phase": "concept",
                "sequence": 12,
            }
        )
        extension["deliverables"].append(
            {
                "id": REFINEMENT_ROOT,
                "title": "Legacy project architecture baseline",
                "phase": "concept",
                "activity_id": "concept.define_legacy_architecture",
                "review_required": True,
                "depends_on": [],
                "requires_artifact_owner": False,
            }
        )
        extension["refinement_requirements"].append(
            {
                "root": REFINEMENT_ROOT,
                "definition_state": "concrete",
                "refinement_required": True,
                "trigger": {
                    "all_of": [
                        {"subject": REFINEMENT_ROOT, "condition": "accepted"}
                    ]
                },
                "completion_policy": "all_children_accepted",
            }
        )
        _write(extension_path, extension)
        _cli(legacy_source, project, "tailor", str(project))

        _cli(
            legacy_source,
            project,
            "claim",
            REFINEMENT_ROOT,
            "--project-root",
            str(project),
            "--actor",
            "legacy-agent",
        )
        evidence_root = project / "evidence" / REFINEMENT_ROOT
        evidence_root.mkdir(parents=True, exist_ok=True)
        work = evidence_root / "work.md"
        approval = evidence_root / "approval.md"
        work.write_text("accepted v0.4.1 architecture\n", encoding="utf-8", newline="\n")
        approval.write_text(
            "authorized v0.4.1 architecture review\n",
            encoding="utf-8",
            newline="\n",
        )
        _cli(
            legacy_source,
            project,
            "close",
            REFINEMENT_ROOT,
            "--project-root",
            str(project),
            "--actor",
            "legacy-agent",
            "--evidence",
            work.relative_to(project).as_posix(),
        )
        _cli(
            legacy_source,
            project,
            "review",
            REFINEMENT_ROOT,
            "--project-root",
            str(project),
            "--reviewer",
            "legacy-reviewer",
        )
        _cli(
            legacy_source,
            project,
            "approve",
            REFINEMENT_ROOT,
            "--project-root",
            str(project),
            "--reviewer",
            "legacy-authority",
            "--actor-type",
            "human",
            "--authorized",
            "--evidence",
            approval.relative_to(project).as_posix(),
        )

        process = _load(process_path)
        plan = {
            "schema_version": "1.0",
            "id": REFINEMENT_PLAN_ID,
            "root": REFINEMENT_ROOT,
            "mode": "expand",
            "base_process_fingerprint": _process_fingerprint(process),
            "reason": "Expand the accepted legacy architecture into a sensor module.",
            "basis": [
                work.relative_to(project).as_posix(),
                approval.relative_to(project).as_posix(),
            ],
            "activities": [
                {
                    "id": "concept.define_legacy_sensor_architecture",
                    "title": "Define legacy sensor architecture",
                    "phase": "concept",
                    "sequence": 13,
                }
            ],
            "deliverables": [
                {
                    "id": REFINEMENT_CHILD,
                    "title": "Legacy sensor architecture",
                    "phase": "concept",
                    "activity_id": "concept.define_legacy_sensor_architecture",
                    "review_required": True,
                    "depends_on": [],
                    "refines": REFINEMENT_ROOT,
                    "definition_state": "concrete",
                    "requires_artifact_owner": True,
                }
            ],
            "dependencies": [],
        }
        plan_path = project / ".ipd" / "refinement_plans" / f"{REFINEMENT_PLAN_ID}.yaml"
        _write(plan_path, plan)
        legacy_preview = _json_output(
            _cli(
                legacy_source,
                project,
                "refine",
                str(project),
                "--plan",
                str(plan_path),
                "--preview",
                "--json",
            )
        )
        if legacy_preview.get("applicable") is not True:
            raise RuntimeError(f"legacy refinement was not applicable: {legacy_preview}")
        legacy_apply = _json_output(
            _cli(
                legacy_source,
                project,
                "refine",
                str(project),
                "--plan",
                str(plan_path),
                "--apply",
                "--actor",
                "legacy-project-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Authorize the v0.4.1 refinement fixture.",
                "--json",
            )
        )
        if legacy_apply.get("applied") is not True:
            raise RuntimeError("v0.4.1 refinement was not applied")

        bindings = _load(bindings_path)
        bindings["bindings"].append(
            {
                "id": "owner.concept.legacy_sensor_architecture",
                "glob": "src/sensor/**",
                "deliverable": REFINEMENT_CHILD,
                "role": "owner",
                "critical": True,
                "review_required": True,
                "description": "Owner for the refined legacy sensor architecture.",
            }
        )
        _write(bindings_path, bindings)
        baseline_adoption = _json_output(
            _cli(
                legacy_source,
                project,
                "adopt-baseline",
                str(project),
                "--actor",
                "legacy-project-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Adopt the reviewed refined Deliverable ownership contract.",
                "--json",
            )
        )
        if baseline_adoption.get("adopted") is not True:
            raise RuntimeError("v0.4.1 artifact binding baseline was not adopted")
        _cli(legacy_source, project, "refresh", str(project))
        legacy_verification = _json_output(
            _cli(legacy_source, project, "verify", str(project), "--json")
        )
        if legacy_verification.get("status") != "passed":
            raise RuntimeError(
                f"v0.4.1 refinement fixture verification failed: {legacy_verification}"
            )

        legacy_state = _load(state_path)
        legacy_process = _load(process_path)
        legacy_extension = _load(extension_path)
        legacy_runtime = _load(runtime_path)
        legacy_root = _record(legacy_state["deliverables"], REFINEMENT_ROOT)
        legacy_child = _record(legacy_state["deliverables"], REFINEMENT_CHILD)
        legacy_dashboard_state, legacy_dashboard_graph = _assert_dashboard_readable(project)
        legacy_profile_hash = _sha256(profile_path)
        legacy_process_hash = _sha256(process_path)
        legacy_refinements = deepcopy(legacy_process.get("refinements", []))
        legacy_extension_refinements = deepcopy(legacy_extension.get("refinements", []))
        legacy_runtime_events = deepcopy(legacy_runtime.get("events", []))
        if not any(
            event.get("action") == "process_refinement_applied"
            for event in legacy_runtime_events
            if isinstance(event, dict)
        ):
            raise RuntimeError("legacy Agent runtime omitted the refinement event")

        # Switch only the implementation.  No current-source init or migration
        # command is allowed before proving the legacy project is readable.
        context = _json_output(_cli(ROOT, project, "context", str(project), "--json"))
        validation = _json_output(_cli(ROOT, project, "validate", str(project), "--json"))
        if validation.get("status") != "passed":
            raise RuntimeError(f"v0.4.1 project was not valid under v0.5: {validation}")

        preview_snapshot = _snapshot(project)
        no_op_preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        if preview_snapshot != _snapshot(project):
            raise RuntimeError("v0.5 no-op tailoring preview changed the legacy project")
        _assert_zero_diff(no_op_preview)

        _cli(ROOT, project, "refresh", str(project))
        current_verification = _json_output(
            _cli(ROOT, project, "verify", str(project), "--json")
        )
        if current_verification.get("status") != "passed":
            raise RuntimeError(
                f"v0.4.1 project was not readable under v0.5: {current_verification}"
            )
        if _sha256(profile_path) != legacy_profile_hash:
            raise RuntimeError("v0.5 read path changed the legacy task profile")
        if _sha256(process_path) != legacy_process_hash:
            raise RuntimeError("v0.5 read path changed the legacy tailored process")

        current_state = _load(state_path)
        current_process = _load(process_path)
        current_extension = _load(extension_path)
        current_runtime = _load(runtime_path)
        current_root = _record(current_state["deliverables"], REFINEMENT_ROOT)
        current_child = _record(current_state["deliverables"], REFINEMENT_CHILD)
        current_dashboard_state, current_dashboard_graph = _assert_dashboard_readable(project)
        if (
            current_root.get("status") != legacy_root.get("status")
            or current_root.get("evidence") != legacy_root.get("evidence")
            or current_root.get("reviews") != legacy_root.get("reviews")
        ):
            raise RuntimeError("v0.5 changed accepted Deliverable history")
        if current_child.get("status") != legacy_child.get("status"):
            raise RuntimeError("v0.5 changed refined child lifecycle state")
        if current_process.get("refinements", []) != legacy_refinements:
            raise RuntimeError("v0.5 changed process refinement history")
        if current_extension.get("refinements", []) != legacy_extension_refinements:
            raise RuntimeError("v0.5 changed project refinement authority")
        current_runtime_events = current_runtime.get("events", [])
        if current_runtime_events[: len(legacy_runtime_events)] != legacy_runtime_events:
            raise RuntimeError("v0.5 changed existing Agent runtime events")

        for name, dashboard in (
            ("legacy state", legacy_dashboard_state),
            ("current state", current_dashboard_state),
        ):
            dashboard_ids = {
                item.get("id")
                for item in dashboard.get("deliverables", [])
                if isinstance(item, dict)
            }
            if not {REFINEMENT_ROOT, REFINEMENT_CHILD} <= dashboard_ids:
                raise RuntimeError(f"{name} Dashboard omitted refinement nodes")
        for name, graph in (
            ("legacy graph", legacy_dashboard_graph),
            ("current graph", current_dashboard_graph),
        ):
            graph_text = json.dumps(graph, ensure_ascii=False)
            if REFINEMENT_ROOT not in graph_text or REFINEMENT_CHILD not in graph_text:
                raise RuntimeError(f"{name} Dashboard graph omitted refinement lineage")

        # Explicit opt-in is a user-owned profile edit.  Its current-source
        # preview must be additive and must not mutate any project artifact.
        enabled_profile = _load(profile_path)
        enabled_profile["capability_patterns"] = [NEW_CAPABILITY]
        _write(profile_path, enabled_profile)
        capability_snapshot = _snapshot(project)
        capability_preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        if capability_snapshot != _snapshot(project):
            raise RuntimeError("v0.5 capability preview changed the project")
        if capability_preview.get("ambiguous") or capability_preview.get("removed"):
            raise RuntimeError(
                f"v0.5 capability preview was destructive or ambiguous: {capability_preview}"
            )
        added_deliverables = {
            item.get("id")
            for item in capability_preview.get("added", [])
            if isinstance(item, dict) and item.get("collection") == "deliverables"
        }
        if added_deliverables != NEW_CAPABILITY_DELIVERABLES:
            raise RuntimeError(
                "v0.5 capability preview did not expose the expected Deliverables: "
                f"{sorted(added_deliverables)}"
            )

        checks = {
            "source_release": RELEASE_TAG,
            "init_replayed": False,
            "legacy_capabilities_enabled": 0,
            "legacy_process_readable": current_verification.get("status") == "passed",
            "no_op_preview_zero_write": True,
            "no_op_preview_changes": 0,
            "accepted_status_preserved": current_root.get("status") == "accepted",
            "evidence_preserved": current_root.get("evidence") == legacy_root.get("evidence"),
            "reviews_preserved": current_root.get("reviews") == legacy_root.get("reviews"),
            "refinement_records_preserved": len(legacy_refinements),
            "runtime_events_preserved": len(legacy_runtime_events),
            "dashboard_files": len(EXPECTED_DASHBOARD_FILES),
            "capability_preview": NEW_CAPABILITY,
            "capability_deliverables_previewed": len(added_deliverables),
            "capability_preview_zero_write": True,
            "final_validation": validation.get("status"),
            "final_verification": current_verification.get("status"),
            "context_readable": isinstance(context.get("available_tasks", []), list),
        }
        expected = {
            "source_release": "v0.4.1-beta",
            "init_replayed": False,
            "legacy_capabilities_enabled": 0,
            "legacy_process_readable": True,
            "no_op_preview_zero_write": True,
            "no_op_preview_changes": 0,
            "accepted_status_preserved": True,
            "evidence_preserved": True,
            "reviews_preserved": True,
            "refinement_records_preserved": 1,
            "runtime_events_preserved": len(legacy_runtime_events),
            "dashboard_files": 15,
            "capability_preview": "interface_contract_and_integration",
            "capability_deliverables_previewed": 3,
            "capability_preview_zero_write": True,
            "final_validation": "passed",
            "final_verification": "passed",
            "context_readable": True,
        }
        if checks != expected:
            raise RuntimeError(f"v0.4.1 upgrade qualification mismatch: {checks}")
        return checks


def main() -> int:
    try:
        result = qualify()
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        print(f"v0.4.1 upgrade qualification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

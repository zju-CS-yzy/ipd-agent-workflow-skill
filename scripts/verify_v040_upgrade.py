#!/usr/bin/env python3
"""Qualify an in-place v0.4.0-beta project upgrade to current source."""

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
from typing import Any, Sequence

import yaml


RELEASE_TAG = "v0.4.0-beta"
ROOT = Path(__file__).resolve().parents[1]


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


def _cli_must_fail(
    source: Path, project: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "ipdctl", *arguments],
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    if result.returncode == 0:
        raise RuntimeError(
            f"command unexpectedly passed: {' '.join(arguments)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _json_output(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("CLI JSON output must be an object")
    return value


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


def _record(rows: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    for row in rows:
        if row.get("id") == identifier:
            return row
    raise RuntimeError(f"missing record: {identifier}")


def _edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"source": source, "target": target, "relation": relation}


def _authority_arguments(project: Path) -> tuple[str, ...]:
    return (
        "tailor",
        str(project),
        "--apply-migrations",
        "--actor",
        "upgrade-owner",
        "--actor-type",
        "human",
        "--authorized",
        "--reason",
        "Approve reviewed v0.4.0 project contract corrections.",
        "--json",
    )


def qualify() -> dict[str, Any]:
    _run(["git", "rev-parse", "--verify", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="ipd-v040-upgrade-") as directory:
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
            "# v0.4.0 upgrade fixture\n", encoding="utf-8", newline="\n"
        )
        _git(project, "add", "README.md")
        _git(project, "commit", "-m", "Create project baseline")

        _cli(
            legacy_source,
            project,
            "init",
            str(project),
            "--name",
            "v040-upgrade",
            "--locale",
            "en",
            "--task-type",
            "software",
        )
        _cli(legacy_source, project, "tailor", str(project))

        process_path = project / ".ipd" / "tailored_process.yaml"
        state_path = project / ".ipd" / "project_state.yaml"
        extension_path = project / ".ipd" / "process_extensions.yaml"
        runtime_path = project / ".ipd" / "agent_runtime.yaml"

        # Materialize the tenth project Deliverable using the published version.
        extension = yaml.safe_load(extension_path.read_text(encoding="utf-8"))
        extension["deliverables"].append(
            {
                "id": "project.problem_input",
                "title": "Project problem input",
                "phase": "concept",
                "activity_id": "concept.scope",
                "review_required": True,
                "depends_on": [],
            }
        )
        extension_path.write_text(
            yaml.safe_dump(extension, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )
        _cli(legacy_source, project, "tailor", str(project))
        _cli(legacy_source, project, "refresh", str(project))

        extension_report = _json_output(
            _cli(legacy_source, project, "verify", str(project), "--json")
        )
        if extension_report.get("status") != "passed":
            raise RuntimeError(
                f"v0.4.0 project extension verification failed: {extension_report}"
            )

        governed_id = "concept.problem_definition"
        _cli(
            legacy_source,
            project,
            "claim",
            governed_id,
            "--project-root",
            str(project),
            "--actor",
            "legacy-agent",
        )
        evidence_root = project / "evidence" / governed_id
        evidence_root.mkdir(parents=True, exist_ok=True)
        work = evidence_root / "work.md"
        review = evidence_root / "review.md"
        work.write_text("accepted v0.4.0 work\n", encoding="utf-8", newline="\n")
        review.write_text(
            "authorized v0.4.0 review\n", encoding="utf-8", newline="\n"
        )
        _cli(
            legacy_source,
            project,
            "close",
            governed_id,
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
            governed_id,
            "--project-root",
            str(project),
            "--reviewer",
            "review-agent",
        )
        _cli(
            legacy_source,
            project,
            "approve",
            governed_id,
            "--project-root",
            str(project),
            "--reviewer",
            "design-authority",
            "--actor-type",
            "human",
            "--authorized",
            "--evidence",
            review.relative_to(project).as_posix(),
        )
        _cli(legacy_source, project, "refresh", str(project))
        legacy_report = _json_output(
            _cli(legacy_source, project, "verify", str(project), "--json")
        )
        if legacy_report.get("status") != "passed":
            raise RuntimeError(f"v0.4.0 fixture verification failed: {legacy_report}")

        state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        if len(state["deliverables"]) != 10:
            raise RuntimeError("v0.4.0 fixture must contain ten Deliverables")
        governed = _record(state["deliverables"], governed_id)
        legacy_status = governed["status"]
        legacy_evidence = deepcopy(governed.get("evidence", []))
        legacy_reviews = deepcopy(governed.get("reviews", []))

        gate_pairs = (
            ("gate.legacy.concept_replay", "gate.tr.concept"),
            ("gate.legacy.plan_readiness", "gate.dcp.plan"),
            ("gate.legacy.qualify_readiness", "gate.tr.qualify"),
        )
        for source, target in gate_pairs:
            legacy_gate = deepcopy(_record(state["gates"], target))
            legacy_gate.update(
                {
                    "id": source,
                    "title": f"Legacy generic Gate for {target}",
                    "kind": "Gate",
                }
            )
            state["gates"].append(legacy_gate)

        state["claims"] = [
            {
                "id": f"claim.upgrade_{index}",
                "statement": f"Upgrade evidence claim {index}.",
                "status": "open",
                "evidence": [],
            }
            for index in range(1, 6)
        ]
        claim_edges = [
            _edge("claim.upgrade_1", gate_pairs[0][0], "verifies"),
            _edge("claim.upgrade_2", gate_pairs[1][0], "supports"),
            _edge("claim.upgrade_3", gate_pairs[2][0], "verifies"),
            _edge("claim.upgrade_4", governed_id, "supports"),
            _edge("software.architecture", "claim.upgrade_5", "verifies"),
        ]
        removable_edge = _edge(governed_id, "gate.tr.concept", "supports")
        state["traceability"].extend(claim_edges + [removable_edge])
        state_path.write_text(
            yaml.safe_dump(state, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )

        correction = {
            "deliverable": governed_id,
            "before": [],
            "after": ["project.problem_input"],
            "reason": "Restore the omitted project input dependency.",
            "preserve_history": True,
            "require_reapproval": True,
        }
        extension = yaml.safe_load(extension_path.read_text(encoding="utf-8"))
        extension["gates"] = []
        extension["gate_migrations"] = []
        extension["dependency_corrections"] = [correction]
        extension_path.write_text(
            yaml.safe_dump(extension, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )

        # The preview must expose Claim loss and the real apply path must fail
        # closed while the three legacy Gates have no explicit mapping.
        blocked_snapshot = _snapshot(project)
        blocked_preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        if blocked_snapshot != _snapshot(project):
            raise RuntimeError("blocked migration preview changed the project")
        if not any(
            item.get("kind") == "claim_traceability_removal"
            for item in blocked_preview.get("ambiguous", [])
            if isinstance(item, dict)
        ):
            raise RuntimeError(
                "preview did not expose deletion of surviving Claim traceability"
            )
        _cli_must_fail(ROOT, project, *_authority_arguments(project))
        if blocked_snapshot != _snapshot(project):
            raise RuntimeError("failed Claim migration changed the project")

        gate_migrations = [
            {
                "from": source,
                "to": target,
                "reason": f"Map {source} to the canonical {target} checkpoint.",
                "preserve_history": True,
            }
            for source, target in gate_pairs
        ]
        extension["gate_migrations"] = gate_migrations
        extension_path.write_text(
            yaml.safe_dump(extension, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )

        preview_snapshot = _snapshot(project)
        preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        if preview_snapshot != _snapshot(project):
            raise RuntimeError("authorized migration preview changed the project")
        if preview.get("ambiguous"):
            raise RuntimeError(f"authorized migration preview was ambiguous: {preview}")
        trace_added = [
            item
            for item in preview.get("added", [])
            if item.get("collection") == "state.traceability"
        ]
        trace_removed = [
            item
            for item in preview.get("removed", [])
            if item.get("collection") == "state.traceability"
        ]
        trace_redirected = [
            item
            for item in preview.get("changed", [])
            if item.get("collection") == "state.traceability"
        ]
        typed_gate_migrations = [
            item
            for item in preview.get("migrations", [])
            if item.get("entity_type") == "gate"
        ]
        typed_corrections = [
            item
            for item in preview.get("migrations", [])
            if item.get("entity_type") == "deliverable_dependency"
        ]
        if (
            len(trace_added) != 1
            or len(trace_removed) != 1
            or len(trace_redirected) != 3
            or len(typed_gate_migrations) != 3
            or len(typed_corrections) != 1
        ):
            raise RuntimeError(
                "preview did not expose the expected add/remove/redirect contract: "
                f"{preview}"
            )

        unauthorized_snapshot = _snapshot(project)
        unauthorized = _cli_must_fail(ROOT, project, "tailor", str(project))
        if "--apply-migrations" not in unauthorized.stderr:
            raise RuntimeError(
                "governed migration did not require --apply-migrations: "
                + unauthorized.stderr
            )
        if unauthorized_snapshot != _snapshot(project):
            raise RuntimeError("unauthorized migration changed the project")

        _cli(ROOT, project, *_authority_arguments(project))
        upgraded_state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        upgraded_process = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        upgraded_runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        upgraded = _record(upgraded_state["deliverables"], governed_id)
        gate_ids = {item["id"] for item in upgraded_state["gates"]}
        expected_claim_edges = [
            _edge(
                edge["source"],
                dict(gate_pairs).get(edge["target"], edge["target"]),
                edge["relation"],
            )
            for edge in claim_edges
        ]
        if any(source in gate_ids for source, _ in gate_pairs):
            raise RuntimeError("legacy generic Gates survived explicit migration")
        if not all(target in gate_ids for _, target in gate_pairs):
            raise RuntimeError("canonical Gate migration targets are missing")
        if not all(edge in upgraded_state["traceability"] for edge in expected_claim_edges):
            raise RuntimeError("surviving Claim traceability was not preserved")
        if removable_edge in upgraded_state["traceability"]:
            raise RuntimeError("obsolete state-only traceability was not removed")
        dependency_edge = _edge(
            governed_id, "project.problem_input", "depends_on"
        )
        if dependency_edge not in upgraded_state["traceability"]:
            raise RuntimeError("corrected dependency traceability was not added")
        if (
            legacy_status != "accepted"
            or upgraded.get("status") != "blocked"
            or upgraded.get("blocked_reason") != "DEPENDENCY_CONTRACT_CHANGED"
            or upgraded.get("evidence") != legacy_evidence
            or upgraded.get("reviews") != legacy_reviews
            or upgraded.get("depends_on") != ["project.problem_input"]
        ):
            raise RuntimeError(
                "same-ID dependency correction did not preserve history and require re-review"
            )
        if len(upgraded_state["deliverables"]) != 10:
            raise RuntimeError("upgrade changed the ten-Deliverable project inventory")

        events = [
            event
            for event in upgraded_runtime.get("events", [])
            if event.get("action") == "process_migration"
        ]
        if len(events) != 1:
            raise RuntimeError("upgrade did not record exactly one process migration event")
        if (
            events[0].get("gate_migrations") != gate_migrations
            or events[0].get("dependency_corrections") != [correction]
        ):
            raise RuntimeError("process migration audit omitted governed corrections")

        replay_snapshot = _snapshot(project)
        _cli(ROOT, project, "tailor", str(project))
        if replay_snapshot != _snapshot(project):
            raise RuntimeError("replaying the applied migration was not idempotent")
        replay_preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        if replay_preview.get("ambiguous") or any(
            item.get("collection") == "state.traceability"
            for field in ("added", "removed", "changed")
            for item in replay_preview.get(field, [])
            if isinstance(item, dict)
        ):
            raise RuntimeError(
                f"replayed migration still changes state traceability: {replay_preview}"
            )
        if replay_snapshot != _snapshot(project):
            raise RuntimeError("replayed migration preview changed the project")

        _cli(ROOT, project, "refresh", str(project))
        final_report = _json_output(
            _cli(ROOT, project, "verify", str(project), "--json")
        )
        if final_report.get("status") != "passed":
            raise RuntimeError(f"upgraded project verification failed: {final_report}")
        validation_report = _json_output(
            _cli(ROOT, project, "validate", str(project), "--json")
        )
        if validation_report.get("status") != "passed":
            raise RuntimeError(
                f"upgraded project validation failed: {validation_report}"
            )
        dashboard_files = sum(
            1
            for path in (project / ".ipd" / "dashboard").rglob("*")
            if path.is_file()
        )
        if dashboard_files != 16:
            raise RuntimeError(
                f"upgraded dashboard must contain 16 files, found {dashboard_files}"
            )

        checks = {
            "source_release": RELEASE_TAG,
            "deliverables_preserved": len(upgraded_process["deliverables"]),
            "claim_links_preserved": len(expected_claim_edges),
            "traceability_additions_previewed": len(trace_added),
            "traceability_removals_previewed": len(trace_removed),
            "traceability_redirects_previewed": len(trace_redirected),
            "illegal_claim_deletion_blocked": True,
            "generic_gates_migrated": len(gate_migrations),
            "dependency_history_preserved": True,
            "dependency_reapproval_required": upgraded.get("status") == "blocked",
            "preview_zero_write": True,
            "migration_replay_idempotent": True,
            "dashboard_files": dashboard_files,
            "final_verification": final_report.get("status"),
            "final_validation": validation_report.get("status"),
        }
        expected = {
            "source_release": "v0.4.0-beta",
            "deliverables_preserved": 10,
            "claim_links_preserved": 5,
            "traceability_additions_previewed": 1,
            "traceability_removals_previewed": 1,
            "traceability_redirects_previewed": 3,
            "illegal_claim_deletion_blocked": True,
            "generic_gates_migrated": 3,
            "dependency_history_preserved": True,
            "dependency_reapproval_required": True,
            "preview_zero_write": True,
            "migration_replay_idempotent": True,
            "dashboard_files": 16,
            "final_verification": "passed",
            "final_validation": "passed",
        }
        if checks != expected:
            raise RuntimeError(f"v0.4.0 upgrade qualification mismatch: {checks}")
        return checks


def main() -> int:
    try:
        result = qualify()
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        print(f"v0.4.0 upgrade qualification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

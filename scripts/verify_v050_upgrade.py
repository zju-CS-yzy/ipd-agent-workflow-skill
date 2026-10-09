#!/usr/bin/env python3
"""Qualify an in-place v0.5.0-beta project upgrade to v0.5.1 source.

The fixture is created exclusively with the published v0.5.0-beta Git tag.
Current source is then used without replaying ``init``.  The probe exercises the
legacy mid-review recovery boundary, immutable review-subject lock, pure
Dashboard rendering, strict refresh staging, generated governance-document
drift diagnostics, and the completed review/refresh/verify path.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


RELEASE_TAG = "v0.5.0-beta"
ROOT = Path(__file__).resolve().parents[1]
REVIEW_SUBJECT = "concept.problem_definition"
OTHER_SUBJECT = "plan.integrated_plan"
EXPECTED_DASHBOARD_FILES = {
    "index.html",
    "governance.md",
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
    expect_success: bool = True,
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
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"command unexpectedly passed: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _cli(
    source: Path,
    project: Path,
    *arguments: str,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(source)
    return _run(
        [sys.executable, "-B", "-m", "ipdctl", *arguments],
        cwd=project,
        env=environment,
        expect_success=expect_success,
    )


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"YAML document must be an object: {path}")
    return value


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


def _dashboard_inventory(project: Path) -> set[str]:
    dashboard = project / ".ipd" / "dashboard"
    return {
        path.relative_to(dashboard).as_posix()
        for path in dashboard.rglob("*")
        if path.is_file()
    }


def _git(project: Path, *arguments: str) -> None:
    _run(["git", *arguments], cwd=project)


def _assert_failure_is_zero_write(
    source: Path,
    project: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    before = _snapshot(project)
    result = _cli(
        source,
        project,
        *arguments,
        expect_success=False,
    )
    after = _snapshot(project)
    if after != before:
        changed = sorted(set(before) | set(after))
        changed = [name for name in changed if before.get(name) != after.get(name)]
        raise RuntimeError(
            f"failed command changed project artifacts: {arguments}; {changed}"
        )
    return result


def _issue_codes(report: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in report.get("issues", [])
        if isinstance(item, Mapping) and item.get("code")
    }


def _assert_governance_drift(
    project: Path,
    old: str,
    new: str,
    expected_code: str,
    *,
    exercise_verify: bool = False,
) -> None:
    governance = project / ".ipd" / "dashboard" / "governance.md"
    canonical = governance.read_text(encoding="utf-8")
    if old not in canonical:
        raise RuntimeError(f"governance drift probe token was not found: {old!r}")
    governance.write_text(canonical.replace(old, new, 1), encoding="utf-8")
    validation = _cli(
        ROOT,
        project,
        "validate",
        str(project),
        "--json",
        expect_success=False,
    )
    validation_report = _json_output(validation.stdout)
    if expected_code not in _issue_codes(validation_report):
        raise RuntimeError(
            f"validate omitted {expected_code}: {validation_report}"
        )
    if exercise_verify:
        verification = _cli(
            ROOT,
            project,
            "verify",
            str(project),
            "--json",
            expect_success=False,
        )
        verification_report = _json_output(verification.stdout)
        if expected_code not in _issue_codes(verification_report):
            raise RuntimeError(
                f"verify omitted {expected_code}: {verification_report}"
            )
    _cli(ROOT, project, "render-dashboard", str(project))


def qualify() -> dict[str, Any]:
    _run(["git", "rev-parse", "--verify", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="ipd-v050-upgrade-") as directory:
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
            "# v0.5.0 review upgrade fixture\n",
            encoding="utf-8",
            newline="\n",
        )
        _git(project, "add", "README.md")
        _git(project, "commit", "-m", "Create project baseline")

        # Build the project and enter the legacy review step only through the
        # published v0.5.0 implementation.
        _cli(
            legacy_source,
            project,
            "init",
            str(project),
            "--name",
            "v050-review-upgrade",
            "--locale",
            "en",
            "--task-type",
            "software",
        )
        _cli(legacy_source, project, "tailor", str(project))
        _cli(legacy_source, project, "refresh", str(project))
        legacy_verification = _json_output(
            _cli(
                legacy_source,
                project,
                "verify",
                str(project),
                "--json",
            ).stdout
        )
        if legacy_verification.get("status") != "passed":
            raise RuntimeError(
                f"v0.5.0 fixture verification failed: {legacy_verification}"
            )
        _cli(
            legacy_source,
            project,
            "claim",
            REVIEW_SUBJECT,
            "--project-root",
            str(project),
            "--actor",
            "legacy-agent",
        )
        evidence_root = project / "evidence" / REVIEW_SUBJECT
        evidence_root.mkdir(parents=True, exist_ok=True)
        evidence = evidence_root / "problem.md"
        approval = evidence_root / "problem-approval.md"
        evidence.write_text(
            "reviewed problem definition evidence\n",
            encoding="utf-8",
            newline="\n",
        )
        approval.write_text(
            "authorized problem definition decision\n",
            encoding="utf-8",
            newline="\n",
        )
        _cli(
            legacy_source,
            project,
            "close",
            REVIEW_SUBJECT,
            "--project-root",
            str(project),
            "--actor",
            "legacy-agent",
            "--evidence",
            evidence.relative_to(project).as_posix(),
        )

        state_path = project / ".ipd" / "project_state.yaml"
        runtime_path = project / ".ipd" / "agent_runtime.yaml"
        legacy_state = _load(state_path)
        if legacy_state["project"].get("workflow_step") != "review":
            raise RuntimeError("v0.5.0 fixture did not enter the review step")
        if "current_iteration_subject" in legacy_state["project"]:
            raise RuntimeError("v0.5.0 fixture unexpectedly contains the v0.5.1 lock")
        legacy_manifest = json.loads(
            (project / ".ipd" / "dashboard" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        if legacy_manifest.get("schema_version") != "2.1":
            raise RuntimeError(
                f"unexpected v0.5.0 Dashboard manifest: {legacy_manifest}"
            )
        profile_hash = _sha256(project / ".ipd" / "task_profile.yaml")
        process_hash = _sha256(project / ".ipd" / "tailored_process.yaml")

        # Merely switching implementations cannot infer the review subject.
        initial_validation = _cli(
            ROOT,
            project,
            "validate",
            str(project),
            "--json",
            expect_success=False,
        )
        if initial_validation.returncode == 0:
            raise RuntimeError("legacy mid-review state did not fail closed")
        _assert_failure_is_zero_write(
            ROOT,
            project,
            "approve",
            REVIEW_SUBJECT,
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
        _assert_failure_is_zero_write(
            ROOT,
            project,
            "review",
            REVIEW_SUBJECT,
            "--project-root",
            str(project),
            "--reviewer",
            "unauthorized-reviewer",
            "--actor-type",
            "human",
            "--recover-subject",
            "--reason",
            "Attempt recovery without authorization.",
        )

        recovery = _cli(
            ROOT,
            project,
            "review",
            REVIEW_SUBJECT,
            "--project-root",
            str(project),
            "--reviewer",
            "legacy-authority",
            "--actor-type",
            "human",
            "--authorized",
            "--recover-subject",
            "--reason",
            "Bind the reviewed v0.5.0 iteration to its existing evidence.",
        )
        if "recovered" not in recovery.stdout.lower():
            raise RuntimeError(f"subject recovery was not reported: {recovery.stdout}")
        recovered_state = _load(state_path)
        if recovered_state["project"].get("current_iteration_subject") != REVIEW_SUBJECT:
            raise RuntimeError("subject recovery did not persist the canonical lock")
        recovered_runtime = _load(runtime_path)
        events = recovered_runtime.get("events", [])
        if not events or events[-1].get("action") != "review_subject_recovered":
            raise RuntimeError("subject recovery omitted its Runtime audit event")

        # The lock is global for the iteration. A different Deliverable cannot
        # become the review or approval target.
        _assert_failure_is_zero_write(
            ROOT,
            project,
            "review",
            OTHER_SUBJECT,
            "--project-root",
            str(project),
            "--reviewer",
            "legacy-reviewer",
        )
        _cli(
            ROOT,
            project,
            "review",
            REVIEW_SUBJECT,
            "--project-root",
            str(project),
            "--reviewer",
            "legacy-reviewer",
        )
        _assert_failure_is_zero_write(
            ROOT,
            project,
            "approve",
            OTHER_SUBJECT,
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

        # Rendering may replace derived files but cannot change authoritative
        # state or Runtime bytes. Formal refresh is illegal during review and
        # its transaction must be entirely zero-write.
        state_before_render = state_path.read_bytes()
        runtime_before_render = runtime_path.read_bytes()
        _cli(ROOT, project, "render-dashboard", str(project))
        if state_path.read_bytes() != state_before_render:
            raise RuntimeError("render-dashboard changed project state bytes")
        if runtime_path.read_bytes() != runtime_before_render:
            raise RuntimeError("render-dashboard changed Agent Runtime bytes")
        if _dashboard_inventory(project) != EXPECTED_DASHBOARD_FILES:
            raise RuntimeError(
                "v0.5.1 Dashboard inventory mismatch: "
                f"{sorted(_dashboard_inventory(project))}"
            )
        current_manifest = json.loads(
            (project / ".ipd" / "dashboard" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        if current_manifest.get("schema_version") != "2.2":
            raise RuntimeError("current Dashboard did not use manifest schema 2.2")
        _assert_failure_is_zero_write(ROOT, project, "refresh", str(project))

        # Generated governance semantics must be checked against facts by both
        # validate and verify. Re-render restores canonical content between
        # independent version, Gate-ID, and Gate-status probes.
        _assert_governance_drift(
            project,
            "framework_version: 0.5.1-beta",
            "framework_version: 0.5.0-beta",
            "governance_document_version_stale",
            exercise_verify=True,
        )
        state = _load(state_path)
        first_gate = state.get("gates", [])[0]
        gate_id = str(first_gate["id"])
        gate_status = str(first_gate["status"])
        _assert_governance_drift(
            project,
            f"- {gate_id}",
            "- gate.obsolete.identifier",
            "governance_document_gate_ids_stale",
        )
        replacement_status = "approved" if gate_status != "approved" else "planned"
        _assert_governance_drift(
            project,
            f"{gate_id}: {gate_status}",
            f"{gate_id}: {replacement_status}",
            "governance_document_gate_status_stale",
        )

        _cli(
            ROOT,
            project,
            "approve",
            REVIEW_SUBJECT,
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
        revision_before_refresh = int(_load(state_path)["revision"])
        _cli(ROOT, project, "refresh", str(project))
        revision_after_refresh = int(_load(state_path)["revision"])
        if revision_after_refresh != revision_before_refresh + 1:
            raise RuntimeError(
                "formal refresh did not increment project revision exactly once"
            )
        final_validation = _json_output(
            _cli(ROOT, project, "validate", str(project), "--json").stdout
        )
        final_verification = _json_output(
            _cli(ROOT, project, "verify", str(project), "--json").stdout
        )
        if final_validation.get("status") != "passed":
            raise RuntimeError(f"final validation failed: {final_validation}")
        if final_verification.get("status") != "passed":
            raise RuntimeError(f"final verification failed: {final_verification}")
        if _sha256(project / ".ipd" / "task_profile.yaml") != profile_hash:
            raise RuntimeError("v0.5.1 upgrade changed the task profile")
        if _sha256(project / ".ipd" / "tailored_process.yaml") != process_hash:
            raise RuntimeError("v0.5.1 upgrade changed the tailored process")

        return {
            "source_release": RELEASE_TAG,
            "init_replayed": False,
            "legacy_manifest_schema": "2.1",
            "current_manifest_schema": "2.2",
            "dashboard_files": len(EXPECTED_DASHBOARD_FILES),
            "legacy_mid_review_failed_closed": True,
            "review_subject_recovered": REVIEW_SUBJECT,
            "review_subject_mismatch_zero_write": True,
            "render_dashboard_fact_preserving": True,
            "review_refresh_zero_write": True,
            "refresh_revision_delta": 1,
            "governance_diagnostics": [
                "governance_document_version_stale",
                "governance_document_gate_ids_stale",
                "governance_document_gate_status_stale",
            ],
            "profile_preserved": True,
            "process_preserved": True,
            "final_validation": final_validation.get("status"),
            "final_verification": final_verification.get("status"),
        }


def main() -> int:
    try:
        result = qualify()
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        print(f"v0.5.0 upgrade qualification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

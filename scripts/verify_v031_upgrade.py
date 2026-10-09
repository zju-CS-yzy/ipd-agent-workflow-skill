#!/usr/bin/env python3
"""Qualify an in-place v0.3.1-beta project upgrade to the current source."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Sequence

import yaml


RELEASE_TAG = "v0.3.1-beta"
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
        timeout=180,
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


def _cli_must_fail(source: Path, project: Path, *arguments: str) -> None:
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
        timeout=180,
    )
    if result.returncode == 0:
        raise RuntimeError(
            f"command unexpectedly passed: {' '.join(arguments)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _json_output(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("CLI JSON output must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(project: Path, *arguments: str) -> None:
    _run(["git", *arguments], cwd=project)


def _write_binding(project: Path, deliverable: str) -> None:
    path = project / ".ipd" / "artifact_bindings.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("bindings"), list):
        raise RuntimeError("v0.3.1 artifact bindings are not readable")
    document["bindings"].insert(
        0,
        {
            "id": "legacy-source-owner",
            "glob": "src/preexisting.py",
            "deliverable": deliverable,
            "critical": True,
            "review_required": True,
            "description": "Reviewed legacy source owner",
        },
    )
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def _iteration(
    project: Path,
    deliverable: str,
    *,
    number: int,
    decision: str,
    actor: str | None = None,
    open_claim: bool = True,
) -> None:
    actor = actor or f"agent-{number}"
    if open_claim:
        _cli(
            ROOT,
            project,
            "claim",
            deliverable,
            "--project-root",
            str(project),
            "--actor",
            actor,
        )
    source = project / "src" / "preexisting.py"
    source.write_text(
        source.read_text(encoding="utf-8") + f"ITERATION = {number}\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence_root = project / "evidence" / deliverable
    evidence_root.mkdir(parents=True, exist_ok=True)
    work = evidence_root / f"work-{number}.md"
    review = evidence_root / f"review-{number}.md"
    work.write_text(f"iteration {number} work\n", encoding="utf-8", newline="\n")
    review.write_text(
        f"authorized {decision}\n", encoding="utf-8", newline="\n"
    )
    _cli(
        ROOT,
        project,
        "close",
        deliverable,
        "--project-root",
        str(project),
        "--actor",
        actor,
        "--evidence",
        work.relative_to(project).as_posix(),
    )
    _cli(
        ROOT,
        project,
        "review",
        deliverable,
        "--project-root",
        str(project),
        "--reviewer",
        "review-agent",
    )
    _cli(
        ROOT,
        project,
        decision,
        deliverable,
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
    _cli(ROOT, project, "refresh", str(project))
    report = _json_output(_cli(ROOT, project, "verify", str(project), "--json"))
    if report.get("status") != "passed":
        raise RuntimeError(f"iteration {number} verification failed: {report}")


def qualify() -> dict[str, Any]:
    _run(["git", "rev-parse", "--verify", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="ipd-v031-upgrade-") as directory:
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
            "# v0.3.1 upgrade fixture\n", encoding="utf-8", newline="\n"
        )
        _git(project, "add", "README.md")
        _git(project, "commit", "-m", "Create project baseline")

        _cli(
            legacy_source,
            project,
            "init",
            str(project),
            "--name",
            "legacy-upgrade",
            "--locale",
            "en",
            "--task-type",
            "software",
        )
        _cli(legacy_source, project, "tailor", str(project))
        process_path = project / ".ipd" / "tailored_process.yaml"
        profile_path = project / ".ipd" / "task_profile.yaml"
        process = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        deliverable = process["deliverables"][0]["id"]
        _write_binding(project, deliverable)
        _git(
            project,
            "add",
            ".ipd/task_profile.yaml",
            ".ipd/tailored_process.yaml",
            ".ipd/artifact_bindings.yaml",
        )
        _git(project, "commit", "-m", "Record v0.3.1 IPD authorities")
        original_hashes = {
            "task_profile": _sha256(profile_path),
            "tailored_process": _sha256(process_path),
        }

        _cli(
            legacy_source,
            project,
            "claim",
            deliverable,
            "--project-root",
            str(project),
            "--actor",
            "legacy-agent",
        )
        runtime_path = project / ".ipd" / "agent_runtime.yaml"
        legacy_runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        legacy_runtime["active_claims"][deliverable]["started_at"] = (
            "1999-01-01T00:00:00Z"
        )
        legacy_runtime["active_claims"][deliverable]["expires_at"] = (
            "2000-01-01T00:00:00Z"
        )
        runtime_path.write_text(
            yaml.safe_dump(legacy_runtime, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )

        source = project / "src" / "preexisting.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("VALUE = 1\n", encoding="utf-8", newline="\n")
        context_before = _json_output(
            _cli(ROOT, project, "context", str(project), "--json")
        )
        if context_before["eligibility"]["eligible"] or context_before["available_tasks"]:
            raise RuntimeError("dirty legacy project was claimable before baseline adoption")

        _cli_must_fail(
            ROOT,
            project,
            "claim",
            deliverable,
            "--project-root",
            str(project),
            "--actor",
            "migration-agent",
            "--recover",
        )
        runtime_before_preview = _sha256(runtime_path)
        preview = _json_output(
            _cli(ROOT, project, "adopt-baseline", str(project), "--preview", "--json")
        )
        if not preview.get("eligible") or _sha256(runtime_path) != runtime_before_preview:
            raise RuntimeError("baseline preview was ineligible or mutated Agent Runtime")
        stale_adoption = _json_output(
            _cli(
                ROOT,
                project,
                "adopt-baseline",
                str(project),
                "--actor",
                "release-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Adopt reviewed v0.3.1 working tree",
                "--json",
            )
        )
        if not stale_adoption.get("adopted"):
            raise RuntimeError("authorized baseline adoption did not append an event")

        source.write_text("VALUE = 2\n", encoding="utf-8", newline="\n")
        _cli_must_fail(
            ROOT,
            project,
            "claim",
            deliverable,
            "--project-root",
            str(project),
            "--actor",
            "migration-agent",
            "--recover",
        )
        adoption = _json_output(
            _cli(
                ROOT,
                project,
                "adopt-baseline",
                str(project),
                "--actor",
                "release-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Replace stale S1 with reviewed v0.3.1 working tree S2",
                "--json",
            )
        )
        if not adoption.get("adopted"):
            raise RuntimeError("replacement baseline adoption was not recorded")

        _cli(
            ROOT,
            project,
            "claim",
            deliverable,
            "--project-root",
            str(project),
            "--actor",
            "migration-agent",
            "--recover",
        )

        _iteration(
            project,
            deliverable,
            number=1,
            decision="reject",
            actor="migration-agent",
            open_claim=False,
        )
        _iteration(project, deliverable, number=2, decision="approve")

        context = _json_output(_cli(ROOT, project, "context", str(project), "--json"))
        reconcile = _json_output(
            _cli(ROOT, project, "reconcile", str(project), "--json")
        )
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        dashboard = json.loads(
            (project / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                encoding="utf-8"
            )
        )
        final_hashes = {
            "task_profile": _sha256(profile_path),
            "tailored_process": _sha256(process_path),
        }
        events = runtime.get("events", [])
        claims = [item for item in events if item.get("action") == "claim"]
        adoptions = [
            item for item in events if item.get("action") == "artifact_baseline_adopted"
        ]
        passed_verifications = [
            item
            for item in events
            if item.get("action") == "verify" and item.get("status") == "passed"
        ]
        dashboard_files = sum(
            1
            for path in (project / ".ipd" / "dashboard").rglob("*")
            if path.is_file()
        )
        checks = {
            "profile_unchanged": final_hashes["task_profile"]
            == original_hashes["task_profile"],
            "process_unchanged": final_hashes["tailored_process"]
            == original_hashes["tailored_process"],
            "adoption_events": len(adoptions),
            "claim_events": len(claims),
            "claim_windows": sum("binding_window" in item for item in claims),
            "legacy_claims": sum("binding_window" not in item for item in claims),
            "claim_expirations": sum(
                item.get("action") == "claim_expired" for item in events
            ),
            "passed_verifications": len(passed_verifications),
            "last_verification": runtime.get("last_verification", {}).get("status"),
            "context_eligible": context.get("eligibility", {}).get("eligible"),
            "dashboard_eligible": dashboard.get("eligibility", {}).get("eligible"),
            "reconcile_status": reconcile.get("status"),
            "dashboard_files": dashboard_files,
        }
        expected = {
            "profile_unchanged": True,
            "process_unchanged": True,
            "adoption_events": 2,
            "claim_events": 3,
            "claim_windows": 2,
            "legacy_claims": 1,
            "claim_expirations": 1,
            "passed_verifications": 2,
            "last_verification": "passed",
            "context_eligible": True,
            "dashboard_eligible": True,
            "reconcile_status": "passed",
            "dashboard_files": 16,
        }
        if checks != expected:
            raise RuntimeError(f"v0.3.1 upgrade qualification mismatch: {checks}")
        return checks


def main() -> int:
    try:
        result = qualify()
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        print(f"v0.3.1 upgrade qualification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Qualify an in-place v0.3.2-beta project upgrade to v0.4 source."""

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


RELEASE_TAG = "v0.3.2-beta"
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


def _cli_must_fail_json(
    source: Path, project: Path, *arguments: str
) -> dict[str, Any]:
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
    return _json_output(result.stdout)


def _json_output(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("CLI JSON output must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(project: Path, *arguments: str) -> None:
    _run(["git", *arguments], cwd=project)


def _accepted_record(state: dict[str, Any], identifier: str) -> dict[str, Any]:
    for item in state.get("deliverables", []):
        if isinstance(item, dict) and item.get("id") == identifier:
            return item
    raise RuntimeError(f"missing Deliverable in project state: {identifier}")


def qualify() -> dict[str, Any]:
    _run(["git", "rev-parse", "--verify", f"refs/tags/{RELEASE_TAG}"], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="ipd-v032-upgrade-") as directory:
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
            "# v0.3.2 upgrade fixture\n", encoding="utf-8", newline="\n"
        )
        _git(project, "add", "README.md")
        _git(project, "commit", "-m", "Create project baseline")

        _cli(
            legacy_source,
            project,
            "init",
            str(project),
            "--name",
            "v032-upgrade",
            "--locale",
            "en",
            "--task-type",
            "software",
        )
        _cli(legacy_source, project, "tailor", str(project))
        _cli(legacy_source, project, "refresh", str(project))
        initial = _json_output(
            _cli(legacy_source, project, "verify", str(project), "--json")
        )
        if initial.get("status") != "passed":
            raise RuntimeError(f"v0.3.2 initial verification failed: {initial}")

        profile_path = project / ".ipd" / "task_profile.yaml"
        process_path = project / ".ipd" / "tailored_process.yaml"
        state_path = project / ".ipd" / "project_state.yaml"
        process = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        deliverable = process["deliverables"][0]["id"]
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
        evidence_root = project / "evidence" / deliverable
        evidence_root.mkdir(parents=True, exist_ok=True)
        work = evidence_root / "work.md"
        review = evidence_root / "review.md"
        work.write_text("accepted v0.3.2 work\n", encoding="utf-8", newline="\n")
        review.write_text(
            "authorized v0.3.2 review\n", encoding="utf-8", newline="\n"
        )
        _cli(
            legacy_source,
            project,
            "close",
            deliverable,
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
            deliverable,
            "--project-root",
            str(project),
            "--reviewer",
            "review-agent",
        )
        _cli(
            legacy_source,
            project,
            "approve",
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
        _cli(legacy_source, project, "refresh", str(project))
        accepted_report = _json_output(
            _cli(legacy_source, project, "verify", str(project), "--json")
        )
        if accepted_report.get("status") != "passed":
            raise RuntimeError(
                f"v0.3.2 accepted-state verification failed: {accepted_report}"
            )

        legacy_profile_hash = _sha256(profile_path)
        legacy_process_hash = _sha256(process_path)
        legacy_state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        legacy_record = _accepted_record(legacy_state, deliverable)
        legacy_evidence = list(legacy_record.get("evidence", []))
        legacy_reviews = list(legacy_record.get("reviews", []))

        # A v0.4 runtime must operate on the v0.3.2 process before re-tailoring.
        _cli(ROOT, project, "context", str(project), "--json")
        _cli(ROOT, project, "refresh", str(project))
        readable = _json_output(_cli(ROOT, project, "verify", str(project), "--json"))
        if readable.get("status") != "passed":
            raise RuntimeError(f"v0.3.2 process was not readable under v0.4: {readable}")
        if _sha256(profile_path) != legacy_profile_hash or _sha256(process_path) != legacy_process_hash:
            raise RuntimeError("read-only v0.4 commands changed v0.3.2 authorities")

        preview_snapshot = {
            path.relative_to(project).as_posix(): _sha256(path)
            for path in sorted(project.rglob("*"))
            if path.is_file()
        }
        preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        after_preview = {
            path.relative_to(project).as_posix(): _sha256(path)
            for path in sorted(project.rglob("*"))
            if path.is_file()
        }
        if preview_snapshot != after_preview:
            raise RuntimeError("v0.4 tailor preview changed the upgraded project")
        if preview.get("ambiguous"):
            raise RuntimeError(f"v0.3.2 upgrade preview was ambiguous: {preview}")

        _cli(ROOT, project, "tailor", str(project))
        extension_path = project / ".ipd" / "process_extensions.yaml"
        if not extension_path.is_file():
            raise RuntimeError(
                "v0.4 re-tailor did not materialize the canonical project extension"
            )
        upgraded_process = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        upgraded_state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        upgraded_record = _accepted_record(upgraded_state, deliverable)
        if upgraded_process.get("schema_version") != "2.0":
            raise RuntimeError("re-tailor did not publish process schema 2.0")
        if (
            upgraded_record.get("status") != "accepted"
            or upgraded_record.get("evidence") != legacy_evidence
            or upgraded_record.get("reviews") != legacy_reviews
        ):
            raise RuntimeError("v0.4 re-tailor changed accepted v0.3.2 history")
        _cli(ROOT, project, "refresh", str(project))
        upgraded_report = _json_output(
            _cli(ROOT, project, "verify", str(project), "--json")
        )
        if upgraded_report.get("status") != "passed":
            raise RuntimeError(f"v0.4 re-tailor verification failed: {upgraded_report}")

        # Opting into the reusable capability must be additive and keep history.
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        profile["capability_patterns"] = ["sourced_component_integration"]
        profile_path.write_text(
            yaml.safe_dump(profile, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )
        capability_preview = _json_output(
            _cli(ROOT, project, "tailor", str(project), "--preview", "--json")
        )
        if capability_preview.get("ambiguous"):
            raise RuntimeError(
                f"capability enablement preview was ambiguous: {capability_preview}"
            )
        _cli(ROOT, project, "tailor", str(project))
        _cli(ROOT, project, "refresh", str(project))

        # Tailoring adds framework-managed evidence bindings for the capability.
        # The previously verified binding boundary must therefore fail closed until
        # an authorized human adopts the reviewed replacement baseline.
        stale_binding_report = _cli_must_fail_json(
            ROOT, project, "verify", str(project), "--json"
        )
        stale_issue_codes = {
            issue.get("code")
            for issue in stale_binding_report.get("issues", [])
            if isinstance(issue, dict)
        }
        if "BINDING_BASELINE_STALE" not in stale_issue_codes:
            raise RuntimeError(
                "capability binding change did not fail closed before adoption: "
                f"{stale_binding_report}"
            )

        runtime_path = project / ".ipd" / "agent_runtime.yaml"
        runtime_before_adoption_preview = _sha256(runtime_path)
        adoption_preview = _json_output(
            _cli(ROOT, project, "adopt-baseline", str(project), "--preview", "--json")
        )
        if (
            not adoption_preview.get("eligible")
            or _sha256(runtime_path) != runtime_before_adoption_preview
        ):
            raise RuntimeError(
                "capability binding baseline preview was ineligible or mutated runtime"
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
                "Adopt reviewed v0.4 capability binding contract",
                "--json",
            )
        )
        if not adoption.get("adopted"):
            raise RuntimeError("authorized capability baseline adoption was not recorded")

        _cli(ROOT, project, "refresh", str(project))
        final_report = _json_output(
            _cli(ROOT, project, "verify", str(project), "--json")
        )
        if final_report.get("status") != "passed":
            raise RuntimeError(f"capability-enabled verification failed: {final_report}")

        final_process = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        final_state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        final_record = _accepted_record(final_state, deliverable)
        capability_ids = {
            item["id"]
            for item in final_process.get("deliverables", [])
            if item.get("provenance", {}).get("layer") == "capability"
        }
        capability_state = {
            item["id"]: item
            for item in final_state.get("deliverables", [])
            if item.get("id") in capability_ids
        }
        dashboard_state = json.loads(
            (project / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                encoding="utf-8"
            )
        )
        dashboard_capabilities = {
            item["id"]
            for item in dashboard_state.get("deliverables", [])
            if item.get("provenance", {}).get("layer") == "capability"
        }
        checks = {
            "legacy_process_readable": readable.get("status") == "passed",
            "preview_zero_write": preview_snapshot == after_preview,
            "process_upgraded_to_2_0": upgraded_process.get("schema_version") == "2.0",
            "project_extension_materialized": extension_path.is_file(),
            "accepted_status_preserved": final_record.get("status") == "accepted",
            "accepted_evidence_preserved": final_record.get("evidence") == legacy_evidence,
            "accepted_reviews_preserved": final_record.get("reviews") == legacy_reviews,
            "capability_deliverables": len(capability_ids),
            "capability_nodes_start_planned": all(
                item.get("status") == "planned" for item in capability_state.values()
            ),
            "capability_binding_fail_closed": (
                "BINDING_BASELINE_STALE" in stale_issue_codes
            ),
            "capability_binding_adopted": bool(adoption.get("adopted")),
            "dashboard_capability_provenance": dashboard_capabilities == capability_ids,
            "final_verification": final_report.get("status"),
        }
        expected = {
            "legacy_process_readable": True,
            "preview_zero_write": True,
            "process_upgraded_to_2_0": True,
            "project_extension_materialized": True,
            "accepted_status_preserved": True,
            "accepted_evidence_preserved": True,
            "accepted_reviews_preserved": True,
            "capability_deliverables": 3,
            "capability_nodes_start_planned": True,
            "capability_binding_fail_closed": True,
            "capability_binding_adopted": True,
            "dashboard_capability_provenance": True,
            "final_verification": "passed",
        }
        if checks != expected:
            raise RuntimeError(f"v0.3.2 upgrade qualification mismatch: {checks}")
        return checks


def main() -> int:
    try:
        result = qualify()
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        print(f"v0.3.2 upgrade qualification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

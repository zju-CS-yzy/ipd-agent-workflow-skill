from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ipdctl.reconcile import (
    ReconcileError,
    default_artifact_bindings,
    load_artifact_bindings,
    reconcile_project,
    sync_evidence_bindings,
)
from ipdctl.repository import changed_paths, inspect_repository, sanitize_remote_url
from ipdctl.runtime import (
    RuntimeError as AgentRuntimeError,
    claim,
    create_runtime_state,
    expire_claims,
    validate_runtime,
)


ROOT = Path(__file__).resolve().parents[1]


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


@unittest.skipUnless(shutil.which("git"), "git is not available")
class GitRepositoryRuntimeTests(unittest.TestCase):
    def initialize_repository(self, root: Path) -> None:
        run_git(root, "init")
        run_git(root, "config", "user.name", "IPD Test")
        run_git(root, "config", "user.email", "ipd@example.test")
        (root / "README.md").write_text("initial\n", encoding="utf-8")
        run_git(root, "add", "README.md")
        run_git(root, "commit", "-m", "initial")

    def test_git_metadata_and_changed_paths_are_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            run_git(
                root,
                "remote",
                "add",
                "origin",
                "https://build-user:top-secret@example.test/team/repo.git",
            )

            expected_revision = run_git(root, "rev-parse", "HEAD")
            expected_branch = run_git(root, "branch", "--show-current")
            info = inspect_repository(root)
            self.assertEqual(info.kind, "git")
            self.assertEqual(Path(info.root or "").resolve(), root.resolve())
            self.assertEqual(info.branch, expected_branch)
            self.assertEqual(info.revision, expected_revision)
            self.assertFalse(info.dirty)
            self.assertEqual(
                info.remote, "https://example.test/team/repo.git"
            )

            (root / "README.md").write_text("changed\n", encoding="utf-8")
            (root / "staged.txt").write_text("staged\n", encoding="utf-8")
            (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            run_git(root, "add", "staged.txt")

            dirty_info, paths = changed_paths(root)
            self.assertTrue(dirty_info.dirty)
            self.assertEqual(paths, ["README.md", "staged.txt", "untracked.txt"])
            _, staged_paths = changed_paths(root, staged=True)
            self.assertEqual(staged_paths, ["staged.txt"])

    def test_reconcile_maps_paths_and_classifies_unbound_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.initialize_repository(root)
            (root / ".ipd").mkdir()
            (root / ".ipd" / "artifact_bindings.yaml").write_text(
                """schema_version: \"1.0\"
bindings:
  - id: component
    glob: src/component/**
    deliverable: D-COMPONENT
    critical: true
critical_roots:
  - src/**
  - tests/**
ignore:
  - .ipd/dashboard/**
""",
                encoding="utf-8",
            )
            run_git(root, "add", ".ipd/artifact_bindings.yaml")
            run_git(root, "commit", "-m", "add bindings")

            (root / "src" / "component").mkdir(parents=True)
            (root / "src" / "component" / "runtime.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            (root / "tests").mkdir()
            (root / "tests" / "unbound.py").write_text("pass\n", encoding="utf-8")
            (root / "notes.txt").write_text("note\n", encoding="utf-8")
            (root / ".ipd" / "dashboard").mkdir()
            (root / ".ipd" / "dashboard" / "index.html").write_text(
                "dashboard\n", encoding="utf-8"
            )
            (root / ".ipd" / "project_state.yaml").write_text(
                "schema_version: '1.0'\n", encoding="utf-8"
            )

            state = {
                "revision": 3,
                "deliverables": [
                    {"id": "D-COMPONENT", "status": "in_progress"}
                ]
            }
            report = reconcile_project(root, state)

            self.assertEqual(
                report["mapping"]["deliverables"]["D-COMPONENT"],
                ["src/component/runtime.py"],
            )
            self.assertIn(".ipd/dashboard/index.html", report["mapping"]["ignored"])
            self.assertIn(".ipd/project_state.yaml", report["mapping"]["ignored"])
            severities = {
                issue.get("path"): issue["severity"]
                for issue in report["issues"]
                if issue["code"] == "UNBOUND_CHANGED_PATH"
            }
            self.assertEqual(severities["tests/unbound.py"], "error")
            self.assertEqual(severities["notes.txt"], "warning")
            self.assertEqual(report["status"], "failed")

            saved = json.loads(
                (root / ".ipd" / "reconcile_report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(saved["summary"], report["summary"])

            without_claim = reconcile_project(
                root,
                state,
                runtime={"events": [], "active_claims": {}},
                write=False,
            )
            self.assertTrue(
                any(
                    issue["code"] == "BINDING_UNCLAIMED_DELIVERABLE"
                    and issue["deliverable_id"] == "D-COMPONENT"
                    for issue in without_claim["issues"]
                )
            )
            with_claim = reconcile_project(
                root,
                state,
                runtime={
                    "events": [
                        {
                            "action": "claim",
                            "deliverable": "D-COMPONENT",
                            "actor": "agent-a",
                            "at": "2026-09-30T00:00:00Z",
                            "state_revision": 2,
                        }
                    ],
                    "active_claims": {},
                },
                write=False,
            )
            self.assertFalse(
                any(
                    issue["code"] == "BINDING_UNCLAIMED_DELIVERABLE"
                    for issue in with_claim["issues"]
                )
            )
            self.assertEqual(with_claim["claim_provenance"], ["D-COMPONENT"])

            for label, bad_event in (
                (
                    "missing actor",
                    {
                        "action": "claim",
                        "deliverable": "D-COMPONENT",
                        "at": "2026-09-30T00:00:00Z",
                        "state_revision": 2,
                    },
                ),
                (
                    "missing revision",
                    {
                        "action": "claim",
                        "deliverable": "D-COMPONENT",
                        "actor": "agent-a",
                        "at": "2026-09-30T00:00:00Z",
                    },
                ),
                (
                    "future revision",
                    {
                        "action": "claim",
                        "deliverable": "D-COMPONENT",
                        "actor": "agent-a",
                        "at": "2026-09-30T00:00:00Z",
                        "state_revision": 4,
                    },
                ),
                (
                    "invalid timestamp",
                    {
                        "action": "claim",
                        "deliverable": "D-COMPONENT",
                        "actor": "agent-a",
                        "at": "not-a-time",
                        "state_revision": 2,
                    },
                ),
            ):
                with self.subTest(label=label), self.assertRaises(ReconcileError):
                    reconcile_project(
                        root,
                        state,
                        runtime={"events": [bad_event], "active_claims": {}},
                        write=False,
                    )

    def test_runtime_validator_rejects_claim_without_provenance_fields(self) -> None:
        runtime = create_runtime_state()
        runtime["events"].append(
            {
                "action": "claim",
                "deliverable": "D-COMPONENT",
                "at": "2026-09-30T00:00:00Z",
            }
        )
        issues = validate_runtime(runtime)
        self.assertTrue(any("actor" in issue for issue in issues), issues)
        self.assertTrue(any("state_revision" in issue for issue in issues), issues)

        runtime["events"][0].update(
            actor="agent-a",
            state_revision=0,
            at="not-a-time",
        )
        issues = validate_runtime(runtime)
        self.assertTrue(any("timestamp" in issue for issue in issues), issues)

        runtime = create_runtime_state()
        runtime["events"].append(
            {
                "action": "advance_phase",
                "from_phase": "concept",
                "at": "2026-09-30T00:00:00Z",
            }
        )
        issues = validate_runtime(runtime)
        self.assertTrue(any("to_phase" in issue for issue in issues), issues)
        self.assertTrue(any("state_revision" in issue for issue in issues), issues)

    def test_direct_runtime_helpers_reject_invalid_claim_records(self) -> None:
        runtime = create_runtime_state()
        runtime["active_claims"]["D-COMPONENT"] = {
            "deliverable": "D-COMPONENT",
            "actor": "agent-a",
            "started_at": "not-a-time",
            "expires_at": "2026-09-30T01:00:00Z",
        }
        with self.assertRaises(AgentRuntimeError):
            expire_claims(runtime)
        with self.assertRaises(AgentRuntimeError):
            claim(runtime, "D-OTHER", actor="agent-b", state_revision=0)


class RepositorySafetyTests(unittest.TestCase):
    def test_default_bindings_ignore_all_framework_state(self) -> None:
        bindings = default_artifact_bindings()

        self.assertIn(".ipd/**", bindings["ignore"])
        self.assertNotIn(".ipd/dashboard/**", bindings["ignore"])
        self.assertNotIn(".ipd/reconcile_report.json", bindings["ignore"])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact_bindings.yaml"
            path.write_text(
                "ignore:\n  - build/**\nbindings: []\n",
                encoding="utf-8",
            )
            loaded = load_artifact_bindings(path)

        self.assertIn("build/**", loaded["ignore"])
        self.assertIn(".ipd/**", loaded["ignore"])

    def test_sync_evidence_bindings_preserves_user_rules_and_retailors(self) -> None:
        user_rule = {
            "id": "runtime-owner",
            "glob": "src/runtime/**",
            "deliverable": "develop.runtime",
            "critical": True,
        }
        existing = default_artifact_bindings()
        existing["custom"] = {"keep": True}
        existing["bindings"] = [user_rule]
        initial_process = {
            "deliverables": [
                {"id": "qualify.report"},
                {"id": "develop.runtime"},
            ]
        }

        first = sync_evidence_bindings(existing, initial_process)

        self.assertEqual(first["bindings"][0], user_rule)
        self.assertEqual(first["custom"], {"keep": True})
        self.assertEqual(
            [rule["glob"] for rule in first["bindings"][1:]],
            [
                "evidence/develop.runtime/**",
                "evidence/qualify.report/**",
            ],
        )
        self.assertEqual(existing["bindings"], [user_rule])

        first["bindings"][1]["glob"] = "docs/**"
        retailored = sync_evidence_bindings(
            first,
            {
                "deliverables": [
                    {"id": "develop.runtime"},
                    {"id": "launch.release"},
                ]
            },
        )

        self.assertEqual(retailored["bindings"][0], user_rule)
        self.assertEqual(
            [rule["glob"] for rule in retailored["bindings"][1:]],
            [
                "evidence/develop.runtime/**",
                "evidence/launch.release/**",
            ],
        )
        self.assertNotIn(
            "evidence/qualify.report/**",
            [rule.get("glob") for rule in retailored["bindings"]],
        )
        self.assertFalse(
            any(
                rule.get("glob") in {"docs/**", "src/**", "tests/**"}
                for rule in retailored["bindings"][1:]
            )
        )

    def test_no_repository_degrades_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            info = inspect_repository(directory)
            changed_info, paths = changed_paths(directory)
        self.assertEqual(info.kind, "none")
        self.assertEqual(changed_info.kind, "none")
        self.assertEqual(paths, [])

    def test_remote_credentials_are_removed(self) -> None:
        self.assertEqual(
            sanitize_remote_url(
                "https://user:secret@example.test/team/repo.git?token=hidden&ref=main#secret"
            ),
            "https://example.test/team/repo.git",
        )
        self.assertEqual(
            sanitize_remote_url("git@example.test:team/repo.git"),
            "git@example.test:team/repo.git",
        )

    def test_hook_templates_only_delegate_verification(self) -> None:
        for name in ("git-pre-commit.sh", "git-pre-push.sh", "svn-pre-commit.sh"):
            content = (ROOT / "templates" / "hooks" / name).read_text(
                encoding="utf-8"
            )
            self.assertIn("ipdctl verify", content)
            for forbidden in ("git commit", "git push", "git fetch", "svn update"):
                self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ipdctl.reconcile import reconcile_project
from ipdctl.repository import changed_paths, inspect_repository, sanitize_remote_url


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

            state = {
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


class RepositorySafetyTests(unittest.TestCase):
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

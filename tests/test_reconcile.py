from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from ipdctl.reconcile import (
    ReconcileError,
    artifact_baseline_snapshot,
    artifact_bindings_digest,
    binding_readiness,
    create_claim_binding_window,
    load_artifact_bindings,
    map_paths_to_deliverables,
    path_matches,
    preview_artifact_baseline,
    reconcile_project,
    validate_artifact_bindings,
)
from ipdctl.runtime import claim, create_runtime_state


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


class ArtifactBindingPathMatchingTests(unittest.TestCase):
    def test_patterns_are_rooted_and_segment_aware(self) -> None:
        cases = (
            ("README.md", "README.md", True),
            ("docs/README.md", "README.md", False),
            ("docs/guides/README.md", "README.md", False),
            ("src/main.py", "src/*.py", True),
            ("src/package/main.py", "src/*.py", False),
            ("src", "src/**", True),
            ("src/main.py", "src/**", True),
            ("src/package/main.py", "src/**", True),
            ("README.md", "**/README.md", True),
            ("docs/README.md", "**/README.md", True),
            ("docs/guides/README.md", "**/README.md", True),
            (r"docs\README.md", "docs/*.md", True),
            (r"docs\guides\README.md", "docs/*.md", False),
            (r"docs\guides\README.md", "**/README.md", True),
        )
        for path, pattern, expected in cases:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(path_matches(path, pattern), expected)

    def test_root_literal_does_not_create_nested_double_owner(self) -> None:
        bindings = validate_artifact_bindings(
            {
                "schema_version": "1.0",
                "ignore": [],
                "critical_roots": ["**"],
                "bindings": [
                    {
                        "id": "root-readme",
                        "glob": "README.md",
                        "deliverable": "D-ROOT",
                        "critical": True,
                    },
                    {
                        "id": "docs",
                        "glob": "docs/**",
                        "deliverable": "D-DOCS",
                        "critical": True,
                    },
                ],
            },
            known_deliverables={"D-ROOT", "D-DOCS"},
        )

        mapping = map_paths_to_deliverables(
            ["README.md", "docs/README.md"], bindings
        )

        self.assertEqual(
            [item["owner_deliverable_id"] for item in mapping["paths"]["README.md"]],
            ["D-ROOT"],
        )
        self.assertEqual(
            [
                item["owner_deliverable_id"]
                for item in mapping["paths"]["docs/README.md"]
            ],
            ["D-DOCS"],
        )


class ArtifactBindingSchemaTests(unittest.TestCase):
    def test_strict_validation_and_legacy_noncritical_multi_owner(self) -> None:
        legacy = {
            "schema_version": "1.0",
            "artifact_bindings": [
                {
                    "id": "trace",
                    "paths": ["notes/**"],
                    "deliverables": ["D-A", "D-B"],
                    "critical": False,
                }
            ],
            "critical_roots": [],
            "ignore": [],
            "extensions": {"vendor": {"enabled": True}},
        }
        validated = validate_artifact_bindings(
            legacy, known_deliverables={"D-A", "D-B"}
        )
        self.assertEqual(validated["bindings"][0]["deliverables"], ["D-A", "D-B"])

        critical = deepcopy(legacy)
        critical["artifact_bindings"][0]["critical"] = True
        with self.assertRaises(ReconcileError) as raised:
            validate_artifact_bindings(critical)
        self.assertEqual(raised.exception.code, "BINDING_CRITICAL_MULTIPLE_DELIVERABLES")

        duplicate = deepcopy(legacy)
        duplicate["artifact_bindings"].append(
            {
                "id": "trace",
                "glob": "other/**",
                "deliverable": "D-A",
                "critical": True,
            }
        )
        with self.assertRaises(ReconcileError) as raised:
            validate_artifact_bindings(duplicate)
        self.assertEqual(raised.exception.code, "BINDING_DUPLICATE_RULE_ID")

        invalid_pattern = deepcopy(legacy)
        invalid_pattern["artifact_bindings"][0]["paths"] = ["../outside/**"]
        with self.assertRaises(ReconcileError) as raised:
            validate_artifact_bindings(invalid_pattern)
        self.assertEqual(raised.exception.code, "BINDING_INVALID_PATTERN")

    def test_digest_is_stable_across_aliases_and_order(self) -> None:
        canonical = {
            "schema_version": "1.0",
            "ignore": ["build/**", ".ipd/**"],
            "critical_roots": ["src/**"],
            "bindings": [
                {
                    "id": "owner",
                    "glob": "src/**",
                    "deliverable": "D-A",
                    "critical": True,
                }
            ],
        }
        legacy = {
            "schema_version": "1.0",
            "critical_roots": ["src/**"],
            "artifact_bindings": [
                {
                    "critical": True,
                    "deliverables": ["D-A"],
                    "globs": ["src/**"],
                    "id": "owner",
                }
            ],
            "ignore": [".ipd/**", "build/**"],
        }
        self.assertEqual(
            artifact_bindings_digest(canonical), artifact_bindings_digest(legacy)
        )

    def test_missing_file_fails_closed_except_explicit_init_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "artifact_bindings.yaml"
            with self.assertRaises(ReconcileError) as raised:
                load_artifact_bindings(missing)
            self.assertEqual(raised.exception.code, "ARTIFACT_BINDINGS_MISSING")
            self.assertEqual(
                load_artifact_bindings(missing, allow_default=True)["schema_version"],
                "1.0",
            )


@unittest.skipUnless(shutil.which("git"), "git is not available")
class BindingWindowTests(unittest.TestCase):
    def initialize(self, root: Path) -> tuple[dict, Path]:
        run_git(root, "init")
        run_git(root, "config", "user.name", "IPD Test")
        run_git(root, "config", "user.email", "ipd@example.test")
        (root / "README.md").write_text("initial\n", encoding="utf-8")
        bindings_path = root / ".ipd" / "artifact_bindings.yaml"
        bindings_path.parent.mkdir()
        bindings_path.write_text(
            """schema_version: "1.0"
critical_roots:
  - src/**
ignore: []
bindings:
  - id: source-owner
    glob: src/**
    deliverable: D-A
    critical: true
""",
            encoding="utf-8",
        )
        run_git(root, "add", "README.md", ".ipd/artifact_bindings.yaml")
        run_git(root, "commit", "-m", "initial")
        return {"revision": 1, "deliverables": [{"id": "D-A"}]}, bindings_path

    def test_clean_claim_new_file_has_exact_window_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root)
            runtime = create_runtime_state()

            readiness = binding_readiness(
                root, state, runtime, target_deliverable="D-A"
            )
            self.assertTrue(readiness["eligible"], readiness["issues"])
            window = create_claim_binding_window(root, state, runtime, "D-A")
            self.assertEqual(window["opened_paths"], {})
            runtime = claim(
                runtime,
                "D-A",
                actor="agent-a",
                state_revision=1,
                binding_window=window,
            )

            (root / "src").mkdir()
            (root / "src" / "new.py").write_text("VALUE = 1\n", encoding="utf-8")
            report = reconcile_project(root, state, runtime=runtime, write=False)

            self.assertTrue(report["eligible"], report["issues"])
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["claim_provenance"], ["D-A"])

    def test_legacy_claim_is_history_not_v032_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root)
            baseline = artifact_baseline_snapshot(root, state)
            runtime = create_runtime_state()
            runtime["events"] = [
                {
                    "action": "verify",
                    "at": "2026-10-01T00:00:00Z",
                    "status": "passed",
                    "state_revision": 1,
                    "artifact_baseline": baseline,
                },
                {
                    "action": "claim",
                    "deliverable": "D-A",
                    "actor": "legacy-agent",
                    "at": "2026-10-01T00:01:00Z",
                    "state_revision": 1,
                },
            ]
            (root / "src").mkdir()
            (root / "src" / "new.py").write_text("VALUE = 1\n", encoding="utf-8")

            report = reconcile_project(root, state, runtime=runtime, write=False)
            issue = next(
                item
                for item in report["issues"]
                if item["code"] == "BINDING_UNCLAIMED_DELIVERABLE"
            )
            self.assertEqual(issue["reason_code"], "CLAIM_WINDOW_MISSING")

    def test_successful_snapshot_survives_failed_verify_and_needs_no_new_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root)
            runtime = create_runtime_state()
            window = create_claim_binding_window(root, state, runtime, "D-A")
            runtime = claim(
                runtime,
                "D-A",
                actor="agent-a",
                state_revision=1,
                binding_window=window,
            )
            (root / "src").mkdir()
            (root / "src" / "new.py").write_text("VALUE = 1\n", encoding="utf-8")
            verified = artifact_baseline_snapshot(root, state)
            runtime["events"].extend(
                [
                    {
                        "action": "verify",
                        "at": "2026-10-01T00:02:00Z",
                        "status": "passed",
                        "state_revision": 1,
                        "artifact_baseline": verified,
                    },
                    {
                        "action": "verify",
                        "at": "2026-10-01T00:03:00Z",
                        "status": "failed",
                        "state_revision": 1,
                    },
                ]
            )
            runtime["last_verification"] = {
                "status": "failed",
                "state_revision": 1,
                "input_fingerprint": "failed",
                "artifact_baseline": verified,
            }

            report = reconcile_project(root, state, runtime=runtime, write=False)
            self.assertTrue(report["eligible"], report["issues"])
            self.assertEqual(report["summary"]["window_paths"], 0)
            self.assertEqual(report["claim_provenance"], [])

    def test_critical_conflict_blocks_but_noncritical_multi_owner_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, path = self.initialize(root)
            (root / "src").mkdir()
            (root / "src" / "new.py").write_text("VALUE = 1\n", encoding="utf-8")
            path.write_text(
                """schema_version: "1.0"
critical_roots: [src/**]
ignore: []
bindings:
  - {id: a, glob: src/**, deliverable: D-A, critical: true}
  - {id: b, glob: src/**, deliverable: D-B, critical: true}
""",
                encoding="utf-8",
            )
            state["deliverables"].append({"id": "D-B"})
            blocked = preview_artifact_baseline(root, state)
            self.assertFalse(blocked["eligible"])
            self.assertTrue(
                any(
                    issue["code"] == "BINDING_CRITICAL_OWNER_CONFLICT"
                    for issue in blocked["issues"]
                )
            )

            path.write_text(
                """schema_version: "1.0"
critical_roots: []
ignore: []
bindings:
  - id: trace
    glob: src/**
    deliverables: [D-A, D-B]
    critical: false
""",
                encoding="utf-8",
            )
            warning = preview_artifact_baseline(root, state)
            self.assertTrue(warning["eligible"], warning["issues"])
            self.assertEqual(warning["status"], "warning")


if __name__ == "__main__":
    unittest.main()

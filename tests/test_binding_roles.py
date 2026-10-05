from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from ipdctl.reconcile import (
    ReconcileError,
    artifact_bindings_digest,
    create_claim_binding_window,
    map_paths_to_deliverables,
    preview_artifact_baseline,
    reconcile_project,
    sync_evidence_bindings,
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


def contract(*rules: dict, critical_roots: list[str] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "ignore": [],
        "critical_roots": critical_roots or [],
        "bindings": list(rules),
    }


class ArtifactBindingRoleValidationTests(unittest.TestCase):
    def test_explicit_owner_is_digest_equivalent_to_legacy_owner(self) -> None:
        legacy = contract(
            {
                "id": "source-owner",
                "glob": "src/**",
                "deliverable": "D-A",
                "critical": True,
            },
            critical_roots=["src/**"],
        )
        explicit_owner = contract(
            {
                "id": "source-owner",
                "glob": "src/**",
                "deliverable": "D-A",
                "role": "owner",
                "critical": True,
            },
            critical_roots=["src/**"],
        )

        self.assertEqual(
            artifact_bindings_digest(legacy),
            artifact_bindings_digest(explicit_owner),
        )

    def test_shared_evidence_changes_digest_and_has_strict_shape(self) -> None:
        legacy_trace = contract(
            {
                "id": "research",
                "glob": "research/**",
                "deliverables": ["D-A", "D-B"],
                "critical": False,
            }
        )
        shared = contract(
            {
                "id": "research",
                "glob": "research/**",
                "deliverables": ["D-A", "D-B"],
                "role": "shared_evidence",
                "critical": False,
            }
        )

        self.assertNotEqual(
            artifact_bindings_digest(legacy_trace),
            artifact_bindings_digest(shared),
        )
        validate_artifact_bindings(shared, known_deliverables={"D-A", "D-B"})

        invalid_rules = [
            {
                "id": "owner-array",
                "glob": "src/**",
                "deliverables": ["D-A"],
                "role": "owner",
                "critical": True,
            },
            {
                "id": "shared-singular",
                "glob": "research/**",
                "deliverable": "D-A",
                "role": "shared_evidence",
                "critical": False,
            },
            {
                "id": "shared-default-critical",
                "glob": "research/**",
                "deliverables": ["D-A"],
                "role": "shared_evidence",
            },
            {
                "id": "shared-critical",
                "glob": "research/**",
                "deliverables": ["D-A"],
                "role": "shared_evidence",
                "critical": True,
            },
        ]
        for rule in invalid_rules:
            with self.subTest(rule=rule["id"]), self.assertRaises(ReconcileError):
                validate_artifact_bindings(contract(rule))

    def test_roleless_rules_keep_v032_semantics_and_managed_rules_stay_roleless(
        self,
    ) -> None:
        legacy = contract(
            {
                "id": "legacy-trace",
                "glob": "notes/**",
                "deliverables": ["D-A", "D-B"],
                "critical": False,
            }
        )
        validated = validate_artifact_bindings(legacy)
        self.assertNotIn("role", validated["bindings"][0])

        synchronized = sync_evidence_bindings(
            validated,
            {"deliverables": [{"id": "D-A"}, {"id": "D-B"}]},
        )
        managed = [
            rule for rule in synchronized["bindings"] if rule.get("managed_by")
        ]
        self.assertTrue(managed)
        self.assertTrue(all("role" not in rule for rule in managed))

    def test_mapping_separates_owner_from_shared_evidence(self) -> None:
        bindings = validate_artifact_bindings(
            contract(
                {
                    "id": "owner",
                    "glob": "src/**",
                    "deliverable": "D-A",
                    "role": "owner",
                    "critical": True,
                },
                {
                    "id": "shared",
                    "glob": "src/**",
                    "deliverables": ["D-A", "D-B"],
                    "role": "shared_evidence",
                    "critical": False,
                },
            )
        )
        mapping = map_paths_to_deliverables(["src/model.py"], bindings)

        self.assertEqual(mapping["deliverables"]["D-B"], ["src/model.py"])
        self.assertNotIn("D-B", mapping["owner_deliverables"])
        self.assertEqual(
            mapping["shared_evidence_deliverables"]["D-B"], ["src/model.py"]
        )
        matches = mapping["paths"]["src/model.py"]
        self.assertEqual(matches[0]["owner_deliverable_id"], "D-A")
        self.assertEqual(matches[1]["shared_evidence_deliverable_ids"], ["D-A", "D-B"])


@unittest.skipUnless(shutil.which("git"), "git is not available")
class ArtifactBindingRoleIntegrationTests(unittest.TestCase):
    def initialize(self, root: Path, bindings: dict) -> tuple[dict, Path]:
        run_git(root, "init")
        run_git(root, "config", "user.name", "IPD Test")
        run_git(root, "config", "user.email", "ipd@example.test")
        (root / "README.md").write_text("initial\n", encoding="utf-8")
        bindings_path = root / ".ipd" / "artifact_bindings.yaml"
        bindings_path.parent.mkdir()
        bindings_path.write_text(
            yaml.safe_dump(bindings, sort_keys=False),
            encoding="utf-8",
        )
        run_git(root, "add", "README.md", ".ipd/artifact_bindings.yaml")
        run_git(root, "commit", "-m", "initial")
        state = {
            "revision": 1,
            "deliverables": [{"id": "D-A"}, {"id": "D-B"}],
        }
        return state, bindings_path

    def test_owner_and_shared_evidence_coexist_without_conflict(self) -> None:
        bindings = contract(
            {
                "id": "source-owner",
                "glob": "src/**",
                "deliverable": "D-A",
                "role": "owner",
                "critical": True,
            },
            {
                "id": "research-reference",
                "glob": "src/**",
                "deliverables": ["D-B"],
                "role": "shared_evidence",
                "critical": False,
            },
            critical_roots=["src/**"],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root, bindings)
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
            (root / "src" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")

            report = reconcile_project(root, state, runtime=runtime, write=False)

        self.assertTrue(report["eligible"], report["issues"])
        self.assertEqual(report["claim_provenance"], ["D-A"])
        path = report["paths"]["src/model.py"]
        self.assertEqual(path["owner_deliverable_id"], "D-A")
        self.assertEqual(path["shared_evidence_deliverable_ids"], ["D-B"])
        self.assertEqual(path["owner_rule_ids"], ["source-owner"])
        self.assertEqual(
            path["shared_evidence_rule_ids"], ["research-reference"]
        )
        self.assertNotIn(
            "BINDING_CRITICAL_OWNER_CONFLICT", path["issue_codes"]
        )
        self.assertTrue(report["deliverables"]["D-A"]["binding_ready"])
        self.assertFalse(report["deliverables"]["D-B"]["binding_ready"])
        self.assertEqual(
            report["deliverables"]["D-B"]["shared_evidence_rule_ids"],
            ["research-reference"],
        )

    def test_shared_evidence_does_not_authorize_claim(self) -> None:
        bindings = contract(
            {
                "id": "shared-only",
                "glob": "research/**",
                "deliverables": ["D-B"],
                "role": "shared_evidence",
                "critical": False,
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root, bindings)
            with self.assertRaises(ReconcileError) as raised:
                create_claim_binding_window(root, state, create_runtime_state(), "D-B")

        self.assertEqual(raised.exception.code, "BINDING_WINDOW_MISMATCH")
        self.assertEqual(raised.exception.details["reason_code"], "TARGET_HAS_NO_BINDING")

    def test_critical_path_with_only_shared_evidence_fails_closed(self) -> None:
        bindings = contract(
            {
                "id": "shared-only",
                "glob": "src/**",
                "deliverables": ["D-A", "D-B"],
                "role": "shared_evidence",
                "critical": False,
            },
            critical_roots=["src/**"],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root, bindings)
            (root / "src").mkdir()
            (root / "src" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
            report = preview_artifact_baseline(root, state)

        self.assertFalse(report["eligible"])
        issue = next(
            item
            for item in report["issues"]
            if item["code"] == "BINDING_CRITICAL_OWNER_MISSING"
        )
        self.assertEqual(issue["path"], "src/model.py")
        path = report["paths"]["src/model.py"]
        self.assertIsNone(path["owner_deliverable_id"])
        self.assertFalse(path["binding_ready"])
        self.assertEqual(path["shared_evidence_rule_ids"], ["shared-only"])

    def test_two_explicit_owners_still_conflict(self) -> None:
        bindings = contract(
            {
                "id": "owner-a",
                "glob": "src/**",
                "deliverable": "D-A",
                "role": "owner",
                "critical": True,
            },
            {
                "id": "owner-b",
                "glob": "src/**",
                "deliverable": "D-B",
                "role": "owner",
                "critical": True,
            },
            critical_roots=["src/**"],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, _ = self.initialize(root, bindings)
            (root / "src").mkdir()
            (root / "src" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
            report = preview_artifact_baseline(root, state)

        conflict = next(
            item
            for item in report["issues"]
            if item["code"] == "BINDING_CRITICAL_OWNER_CONFLICT"
        )
        self.assertEqual(conflict["rule_ids"], ["owner-a", "owner-b"])
        self.assertFalse(report["eligible"])


if __name__ == "__main__":
    unittest.main()

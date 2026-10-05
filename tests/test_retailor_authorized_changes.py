from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from ipdctl.cli import main
from ipdctl.process_extensions import ProcessExtensionError, load_process_extension
from ipdctl.runtime import load_runtime
from ipdctl.state import load_state, write_state
from ipdctl.tailoring import tailor_profile


class AuthorizedRetailorTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def init(self, root: Path) -> None:
        code, output, error = self.invoke(
            ["init", str(root), "--name", "authorized-retailor"]
        )
        self.assertEqual(code, 0, output + error)

    @staticmethod
    def extension() -> dict:
        return {
            "schema_version": "1.0",
            "extension_id": "project",
            "activities": [],
            "deliverables": [],
            "gates": [],
            "dependencies": [],
            "checkpoint_criteria": [],
            "migrations": [],
            "gate_migrations": [],
            "dependency_corrections": [],
            "refinement_requirements": [],
            "refinements": [],
        }

    @staticmethod
    def authority_args(root: Path) -> list[str]:
        return [
            "tailor",
            str(root),
            "--apply-migrations",
            "--actor",
            "project-owner",
            "--actor-type",
            "human",
            "--authorized",
            "--reason",
            "Approve the reviewed project contract correction.",
            "--json",
        ]

    def test_authorized_dependency_correction_preserves_history_and_requires_reapproval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = self.extension()
            prerequisite_id = "project.problem_input"
            extension["deliverables"] = [
                {
                    "id": prerequisite_id,
                    "title": "Project problem input",
                    "phase": "concept",
                    "activity_id": "concept.scope",
                    "review_required": True,
                    "depends_on": [],
                }
            ]
            write_state(extension_path, extension)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            governed = next(
                item
                for item in state["deliverables"]
                if item["id"] == "concept.problem_definition"
            )
            governed["status"] = "accepted"
            governed["evidence"] = ["docs/problem-definition.md"]
            governed["reviews"] = [
                {
                    "reviewer": "project-owner",
                    "reviewer_type": "human",
                    "authorized": True,
                    "decision": "approve",
                    "evidence": "docs/problem-definition-review.md",
                }
            ]
            write_state(state_path, state)

            correction = {
                "deliverable": "concept.problem_definition",
                "before": [],
                "after": [prerequisite_id],
                "reason": "Restore the omitted project input dependency.",
                "preserve_history": True,
                "require_reapproval": True,
            }
            extension["dependency_corrections"] = [correction]
            write_state(extension_path, extension)
            before = {
                path: path.read_bytes()
                for path in (
                    state_path,
                    root / ".ipd" / "tailored_process.yaml",
                    root / ".ipd" / "agent_runtime.yaml",
                )
            }

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            preview = json.loads(output)
            self.assertEqual(
                set(preview), {"added", "removed", "changed", "migrations", "ambiguous"}
            )
            self.assertTrue(
                any(
                    item.get("entity_type") == "deliverable_dependency"
                    and item.get("deliverable") == "concept.problem_definition"
                    for item in preview["migrations"]
                )
            )
            self.assertTrue(
                any(
                    item.get("collection") == "state.traceability"
                    and item.get("id")
                    == "concept.problem_definition|depends_on|project.problem_input"
                    for item in preview["added"]
                )
            )
            self.assertEqual(
                {path: path.read_bytes() for path in before}, before
            )

            code, _, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("--apply-migrations", error)
            self.assertEqual({path: path.read_bytes() for path in before}, before)

            code, output, error = self.invoke(self.authority_args(root))
            self.assertEqual(code, 0, output + error)
            updated = load_state(state_path)
            corrected = next(
                item
                for item in updated["deliverables"]
                if item["id"] == "concept.problem_definition"
            )
            self.assertEqual(corrected["depends_on"], [prerequisite_id])
            self.assertEqual(corrected["status"], "blocked")
            self.assertEqual(corrected["blocked_reason"], "DEPENDENCY_CONTRACT_CHANGED")
            self.assertEqual(corrected["evidence"], ["docs/problem-definition.md"])
            self.assertEqual(len(corrected["reviews"]), 1)
            affected_gates = [
                gate
                for gate in updated["gates"]
                if "concept.problem_definition" in gate["required_deliverables"]
            ]
            self.assertTrue(affected_gates)
            self.assertTrue(all(gate["status"] == "planned" for gate in affected_gates))
            self.assertTrue(
                all(gate["stale_reason"] == "DEPENDENCY_CONTRACT_CHANGED" for gate in affected_gates)
            )
            runtime = load_runtime(root)
            events = [
                event
                for event in runtime["events"]
                if event.get("action") == "process_migration"
            ]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["dependency_corrections"], [correction])

            state_after = state_path.read_bytes()
            runtime_after = (root / ".ipd" / "agent_runtime.yaml").read_bytes()
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 0, output + error)
            self.assertEqual(state_path.read_bytes(), state_after)
            self.assertEqual(
                (root / ".ipd" / "agent_runtime.yaml").read_bytes(), runtime_after
            )

    def test_explicit_gate_migration_redirects_claim_trace_and_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            canonical = next(
                gate for gate in state["gates"] if gate["id"] == "gate.tr.concept"
            )
            legacy = deepcopy(canonical)
            legacy.update(
                {
                    "id": "gate.legacy.replay_readiness",
                    "title": "Legacy Replay Readiness",
                    "kind": "Gate",
                }
            )
            state["gates"].append(legacy)
            state["claims"].append(
                {
                    "id": "claim.replay_ready",
                    "statement": "Replay baseline is ready.",
                    "status": "open",
                    "evidence": [],
                }
            )
            state["traceability"].append(
                {
                    "source": "claim.replay_ready",
                    "target": legacy["id"],
                    "relation": "supports",
                }
            )
            write_state(state_path, state)

            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = load_state(extension_path)
            migration = {
                "from": legacy["id"],
                "to": canonical["id"],
                "reason": "Map the legacy replay gate to the canonical concept TR gate.",
                "preserve_history": True,
            }
            extension["gate_migrations"] = [migration]
            write_state(extension_path, extension)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            preview = json.loads(output)
            redirect = next(
                item
                for item in preview["changed"]
                if item.get("collection") == "state.traceability"
            )
            self.assertEqual(redirect["before"]["target"], legacy["id"])
            self.assertEqual(redirect["after"]["target"], canonical["id"])
            self.assertTrue(
                any(item.get("entity_type") == "gate" for item in preview["migrations"])
            )

            code, _, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("--apply-migrations", error)

            code, output, error = self.invoke(self.authority_args(root))
            self.assertEqual(code, 0, output + error)
            updated = load_state(state_path)
            self.assertNotIn(legacy["id"], {gate["id"] for gate in updated["gates"]})
            self.assertIn(
                {
                    "source": "claim.replay_ready",
                    "target": canonical["id"],
                    "relation": "supports",
                },
                updated["traceability"],
            )
            runtime = load_runtime(root)
            event = next(
                event
                for event in runtime["events"]
                if event.get("action") == "process_migration"
            )
            self.assertEqual(event["gate_migrations"], [migration])

    def test_dependency_correction_before_must_match_state_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = load_state(extension_path)
            valid_after = "project.problem_input"
            extension["deliverables"] = [
                {
                    "id": valid_after,
                    "title": "Project problem input",
                    "phase": "concept",
                    "activity_id": "concept.scope",
                    "review_required": True,
                    "depends_on": [],
                }
            ]
            extension["dependency_corrections"] = [
                {
                    "deliverable": "concept.problem_definition",
                    "before": ["concept.nonexistent_prior"],
                    "after": [valid_after],
                    "reason": "A stale correction declaration.",
                    "preserve_history": True,
                    "require_reapproval": True,
                }
            ]
            write_state(extension_path, extension)
            code, _, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertIn("expected before", error)

    def test_restored_candidate_process_cannot_bypass_migration_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

            state_path = root / ".ipd" / "project_state.yaml"
            process_path = root / ".ipd" / "tailored_process.yaml"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            extension_path = root / ".ipd" / "process_extensions.yaml"
            profile_path = root / ".ipd" / "task_profile.yaml"

            state = load_state(state_path)
            governed = next(
                item
                for item in state["deliverables"]
                if item["id"] == "concept.problem_definition"
            )
            governed["status"] = "accepted"
            governed["evidence"] = ["docs/problem-definition.md"]
            governed["reviews"] = [
                {
                    "reviewer": "project-owner",
                    "reviewer_type": "human",
                    "authorized": True,
                    "decision": "approve",
                    "evidence": "docs/problem-definition-review.md",
                }
            ]
            write_state(state_path, state)

            prerequisite_id = "project.problem_input"
            extension = self.extension()
            extension["deliverables"] = [
                {
                    "id": prerequisite_id,
                    "title": "Project problem input",
                    "phase": "concept",
                    "activity_id": "concept.scope",
                    "review_required": True,
                    "depends_on": [],
                }
            ]
            correction = {
                "deliverable": "concept.problem_definition",
                "before": [],
                "after": [prerequisite_id],
                "reason": "Restore the omitted project input dependency.",
                "preserve_history": True,
                "require_reapproval": True,
            }
            extension["dependency_corrections"] = [correction]
            write_state(extension_path, extension)

            # Simulate a restored/partially upgraded bundle whose compiled
            # process already contains ``after`` while state still contains
            # the governed ``before`` facts.
            candidate = tailor_profile(load_state(profile_path), extension)
            write_state(process_path, candidate)
            before = {
                path: path.read_bytes()
                for path in (state_path, process_path, runtime_path)
            }

            code, _, error = self.invoke(
                ["tailor", str(root), "--apply-migrations"]
            )
            self.assertEqual(code, 1)
            self.assertIn("actor", error.lower())
            self.assertEqual({path: path.read_bytes() for path in before}, before)

            code, output, error = self.invoke(self.authority_args(root))
            self.assertEqual(code, 0, output + error)
            updated = load_state(state_path)
            corrected = next(
                item
                for item in updated["deliverables"]
                if item["id"] == "concept.problem_definition"
            )
            self.assertEqual(corrected["status"], "blocked")
            self.assertEqual(corrected["depends_on"], [prerequisite_id])
            events = [
                event
                for event in load_runtime(root)["events"]
                if event.get("action") == "process_migration"
            ]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["dependency_corrections"], [correction])

    def test_gate_migration_self_map_is_rejected_at_input_boundary(self) -> None:
        with self.assertRaisesRegex(ProcessExtensionError, "source and target must differ"):
            load_process_extension(
                {
                    "schema_version": "1.0",
                    "extension_id": "project",
                    "gate_migrations": [
                        {
                            "from": "gate.tr.concept",
                            "to": "gate.tr.concept",
                            "reason": "No-op migration.",
                            "preserve_history": True,
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()

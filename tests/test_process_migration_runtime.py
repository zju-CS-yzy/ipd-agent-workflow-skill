from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.governance import apply_phase_pointers, phase_history_issues
from ipdctl.project import (
    _legacy_process_projection,
    project_consistency_issues,
    verification_input_fingerprint,
)
from ipdctl.runtime import (
    create_runtime_state,
    load_runtime,
    record_event,
    save_runtime,
    validate_runtime,
)
from ipdctl.state import load_state, write_state


class ProcessMigrationRuntimeTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def snapshot(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def init(self, root: Path) -> None:
        code, output, error = self.invoke(["init", str(root), "--name", "migration"])
        self.assertEqual(code, 0, output + error)

    @staticmethod
    def extension(deliverables: list[dict], migrations: list[dict] | None = None) -> dict:
        return {
            "schema_version": "1.0",
            "extension_id": "project",
            "activities": [],
            "deliverables": deliverables,
            "dependencies": [],
            "checkpoint_criteria": [],
            "migrations": list(migrations or []),
            "refinement_requirements": [],
            "refinements": [],
        }

    @staticmethod
    def deliverable(identifier: str) -> dict:
        return {
            "id": identifier,
            "title": identifier.replace(".", " ").title(),
            "phase": "concept",
            "activity_id": "concept.scope",
            "review_required": True,
            "depends_on": [],
        }

    def test_init_writes_empty_project_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            extension = load_state(root / ".ipd" / "process_extensions.yaml")
            self.assertEqual(
                extension,
                self.extension([]),
            )
            profile = load_state(root / ".ipd" / "task_profile.yaml")
            self.assertEqual(profile["capability_patterns"], [])

    def test_runtime_validates_authorized_process_migration_events(self) -> None:
        event = {
            "action": "process_migration",
            "at": "2026-10-03T00:00:00Z",
            "actor": "release-owner",
            "actor_type": "human",
            "authorized": True,
            "reason": "Approve the reviewed process replacement.",
            "state_revision": 4,
            "previous_process_schema_version": "1.0",
            "process_schema_version": "2.0",
            "migrations": [
                {
                    "from": "legacy.baseline",
                    "to": "project.integration_baseline",
                    "strategy": "replace",
                    "reason": "Replace the historical baseline.",
                    "preserve_history": True,
                }
            ],
        }
        runtime = create_runtime_state()
        runtime["events"].append(event)
        self.assertEqual(validate_runtime(runtime), [])

        runtime["events"][0]["authorized"] = False
        issues = validate_runtime(runtime)
        self.assertTrue(any("authorized" in issue for issue in issues))

        runtime["events"][0]["authorized"] = True
        runtime["events"][0]["migrations"] = []
        issues = validate_runtime(runtime)
        self.assertTrue(any("migrations" in issue for issue in issues))

    def test_tailor_preview_is_deterministic_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            before = self.snapshot(root)
            first = self.invoke(["tailor", str(root), "--preview", "--json"])
            second = self.invoke(["tailor", str(root), "--preview", "--json"])
            self.assertEqual(first[0], 0, first[2])
            self.assertEqual(second[0], 0, second[2])
            self.assertEqual(json.loads(first[1]), json.loads(second[1]))
            self.assertEqual(self.snapshot(root), before)

    def test_retailor_materializes_missing_legacy_extension_after_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension_path.unlink()

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertFalse(extension_path.exists())

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 0, output + error)
            self.assertEqual(load_state(extension_path), self.extension([]))

    def test_process_extension_is_part_of_verification_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            before = verification_input_fingerprint(root)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = load_state(extension_path)
            extension["extension_id"] = "project_overlay"
            write_state(extension_path, extension)
            self.assertNotEqual(verification_input_fingerprint(root), before)

    def test_active_claim_blocks_retailor_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"]["concept.problem_definition"] = {
                "deliverable": "concept.problem_definition",
                "actor": "agent-a",
                "started_at": "2026-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            }
            write_state(runtime_path, runtime)
            before = self.snapshot(root)
            code, _, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("active Claim", error)
            self.assertEqual(self.snapshot(root), before)

    def test_retailor_cannot_rewrite_a_governed_deliverable_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            deliverable = self.deliverable("project.reviewed_baseline")
            write_state(extension_path, self.extension([deliverable]))
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            governed = next(
                item
                for item in state["deliverables"]
                if item["id"] == deliverable["id"]
            )
            governed["status"] = "accepted"
            governed["evidence"] = ["evidence/project/reviewed-baseline.md"]
            governed["reviews"] = [
                {
                    "reviewer": "design-authority",
                    "reviewer_type": "human",
                    "authorized": True,
                    "decision": "approve",
                    "evidence": "evidence/project/reviewed-baseline-review.md",
                }
            ]
            write_state(state_path, state)

            changed = self.extension([dict(deliverable)])
            changed["deliverables"][0]["title"] = "Reinterpreted baseline"
            write_state(extension_path, changed)
            before = self.snapshot(root)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertTrue(
                any(
                    item.get("collection") == "deliverables"
                    and item.get("id") == deliverable["id"]
                    and "title" in item.get("fields", [])
                    for item in json.loads(output)["changed"]
                )
            )
            self.assertEqual(self.snapshot(root), before)

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("governed history", error)
            self.assertIn("title", error)
            self.assertEqual(self.snapshot(root), before)

    def test_retailor_cannot_rewrite_governed_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            prerequisite = self.deliverable("project.new_prerequisite")
            write_state(extension_path, self.extension([prerequisite]))
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            governed = next(
                item
                for item in state["deliverables"]
                if item["id"] == "concept.problem_definition"
            )
            governed["status"] = "accepted"
            governed["evidence"] = ["evidence/concept/problem-definition.md"]
            write_state(state_path, state)

            changed = self.extension([prerequisite])
            changed["dependencies"] = [
                {
                    "source": "concept.problem_definition",
                    "target": prerequisite["id"],
                    "relation": "depends_on",
                }
            ]
            write_state(extension_path, changed)
            before = self.snapshot(root)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertTrue(
                any(
                    item.get("collection") == "deliverables"
                    and item.get("id") == "concept.problem_definition"
                    and "depends_on" in item.get("fields", [])
                    for item in json.loads(output)["changed"]
                )
            )
            self.assertEqual(self.snapshot(root), before)

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("governed history", error)
            self.assertIn("depends_on", error)
            self.assertEqual(self.snapshot(root), before)

    def test_retailor_cannot_invalidate_a_closed_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            process = load_state(root / ".ipd" / "tailored_process.yaml")
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            for gate in state["gates"]:
                if gate.get("phase") == "concept":
                    gate["status"] = "approved"
                    gate["reviews"] = [
                        {
                            "reviewer": "legacy-authority",
                            "reviewer_type": "human",
                            "authorized": True,
                            "decision": "approve",
                            "evidence": f"evidence/legacy/{gate['id']}-review.md",
                            "gate_epoch": gate.get("review_epoch", 0),
                        }
                    ]
                    gate["approval"] = "legacy-authority"
            state["project"]["phase"] = "plan"
            apply_phase_pointers(state, process)
            write_state(state_path, state)

            runtime = load_runtime(root)
            runtime = record_event(
                runtime,
                "advance_phase",
                details={
                    "from_phase": "concept",
                    "to_phase": "plan",
                    "state_revision": state["revision"],
                },
            )
            save_runtime(root, runtime)
            self.assertEqual(phase_history_issues(state, process, runtime), [])

            extension_path = root / ".ipd" / "process_extensions.yaml"
            late_deliverable = self.deliverable("project.late_concept_baseline")
            write_state(extension_path, self.extension([late_deliverable]))
            before = self.snapshot(root)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertTrue(
                any(
                    item.get("collection") == "deliverables"
                    and item.get("id") == late_deliverable["id"]
                    for item in json.loads(output)["added"]
                )
            )
            self.assertEqual(self.snapshot(root), before)

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("closed Phase history", error)
            self.assertIn("deliverables:project.late_concept_baseline", error)
            self.assertEqual(self.snapshot(root), before)

    def test_retailor_cannot_add_criteria_to_a_closed_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            process = load_state(root / ".ipd" / "tailored_process.yaml")
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            for gate in state["gates"]:
                if gate.get("phase") == "concept":
                    gate["status"] = "approved"
            state["project"]["phase"] = "plan"
            apply_phase_pointers(state, process)
            write_state(state_path, state)

            runtime = record_event(
                load_runtime(root),
                "advance_phase",
                details={
                    "from_phase": "concept",
                    "to_phase": "plan",
                    "state_revision": state["revision"],
                },
            )
            save_runtime(root, runtime)
            self.assertEqual(phase_history_issues(state, process, runtime), [])

            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = self.extension([])
            extension["checkpoint_criteria"] = [
                {
                    "id": "criterion.tr.concept.project_evidence",
                    "checkpoint_id": "tr.concept",
                    "description": "Project evidence confirms the concept baseline.",
                    "evidence_required": True,
                }
            ]
            write_state(extension_path, extension)
            before = self.snapshot(root)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertTrue(
                any(
                    item.get("collection") == "technical_reviews"
                    and item.get("id") == "tr.concept"
                    and "criteria" in item.get("fields", [])
                    for item in json.loads(output)["changed"]
                )
            )
            self.assertEqual(self.snapshot(root), before)

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("closed Phase history", error)
            self.assertIn("technical_reviews:tr.concept", error)
            self.assertEqual(self.snapshot(root), before)

    def test_retailor_cannot_change_current_phase_after_gate_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            approved_gate = next(
                gate for gate in state["gates"]
                if gate["id"] == "gate.tr.concept"
            )
            approved_gate["status"] = "approved"
            write_state(state_path, state)

            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = self.extension([])
            extension["checkpoint_criteria"] = [
                {
                    "id": "criterion.tr.concept.post_approval",
                    "checkpoint_id": "tr.concept",
                    "description": "A criterion added after technical approval.",
                    "evidence_required": True,
                }
            ]
            write_state(extension_path, extension)
            before = self.snapshot(root)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertEqual(self.snapshot(root), before)
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("approved or closed Phase history", error)
            self.assertIn("technical_reviews:tr.concept", error)
            self.assertEqual(self.snapshot(root), before)

    def test_explicit_split_migration_preserves_history_without_spreading_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            legacy_id = "project.legacy_baseline"
            first_id = "project.integration_baseline"
            second_id = "project.assurance_baseline"
            write_state(extension_path, self.extension([self.deliverable(legacy_id)]))
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            legacy = next(item for item in state["deliverables"] if item["id"] == legacy_id)
            legacy["status"] = "accepted"
            legacy["evidence"] = ["evidence/legacy/result.md"]
            legacy["reviews"] = [
                {
                    "reviewer": "design-authority",
                    "reviewer_type": "human",
                    "authorized": True,
                    "decision": "approve",
                    "evidence": "evidence/legacy/approval.md",
                }
            ]
            write_state(state_path, state)

            migrations = [
                {
                    "from": legacy_id,
                    "to": first_id,
                    "strategy": "split",
                    "reason": "Separate integration and assurance evidence.",
                    "preserve_history": True,
                },
                {
                    "from": legacy_id,
                    "to": second_id,
                    "strategy": "split",
                    "reason": "Separate integration and assurance evidence.",
                    "preserve_history": True,
                },
            ]
            write_state(
                extension_path,
                self.extension(
                    [self.deliverable(first_id), self.deliverable(second_id)],
                    migrations,
                ),
            )
            before = self.snapshot(root)
            code, _, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("--apply-migrations", error)
            self.assertEqual(self.snapshot(root), before)

            code, _, error = self.invoke(
                ["tailor", str(root), "--apply-migrations"]
            )
            self.assertEqual(code, 1)
            self.assertIn("--actor", error)
            self.assertEqual(self.snapshot(root), before)

            code, output, error = self.invoke(
                [
                    "tailor",
                    str(root),
                    "--apply-migrations",
                    "--actor",
                    "release-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    "Approve reviewed split migration.",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, output + error)
            self.assertEqual(json.loads(output)["ambiguous"], [])
            migrated_state = load_state(state_path)
            records = {item["id"]: item for item in migrated_state["deliverables"]}
            historical = records[legacy_id]
            self.assertEqual(historical["status"], "superseded")
            self.assertEqual(historical["replacement"], first_id)
            self.assertEqual(historical["replacements"], [first_id, second_id])
            self.assertEqual(historical["evidence"], ["evidence/legacy/result.md"])
            self.assertEqual(len(historical["reviews"]), 1)
            for identifier in (first_id, second_id):
                self.assertEqual(records[identifier]["status"], "planned")
                self.assertEqual(records[identifier]["evidence"], [])
                self.assertEqual(records[identifier]["reviews"], [])

            runtime = load_runtime(root)
            events = [
                event
                for event in runtime["events"]
                if event.get("action") == "process_migration"
            ]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["migrations"], migrations)
            self.assertEqual(events[0]["actor"], "release-owner")
            self.assertEqual(events[0]["actor_type"], "human")
            self.assertTrue(events[0]["authorized"])
            self.assertEqual(
                events[0]["reason"], "Approve reviewed split migration."
            )
            process = load_state(root / ".ipd" / "tailored_process.yaml")
            self.assertEqual(
                project_consistency_issues(migrated_state, process, runtime), []
            )

            state_after_migration = state_path.read_bytes()
            runtime_after_migration = (
                root / ".ipd" / "agent_runtime.yaml"
            ).read_bytes()
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 0, output + error)
            self.assertEqual(state_path.read_bytes(), state_after_migration)
            self.assertEqual(
                (root / ".ipd" / "agent_runtime.yaml").read_bytes(),
                runtime_after_migration,
            )
            repeated_runtime = load_runtime(root)
            self.assertEqual(
                len(
                    [
                        event
                        for event in repeated_runtime["events"]
                        if event.get("action") == "process_migration"
                    ]
                ),
                1,
            )

    def test_unmapped_historical_removal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            legacy_id = "project.unmapped_history"
            write_state(extension_path, self.extension([self.deliverable(legacy_id)]))
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            legacy = next(item for item in state["deliverables"] if item["id"] == legacy_id)
            legacy["status"] = "blocked"
            legacy["blocked_reason"] = "Preserve this historical decision."
            write_state(state_path, state)
            write_state(extension_path, self.extension([]))
            before = self.snapshot(root)
            code, _, error = self.invoke(
                ["tailor", str(root), "--apply-migrations"]
            )
            self.assertEqual(code, 1)
            self.assertIn("unmapped historical", error)
            self.assertEqual(self.snapshot(root), before)

    def test_verify_accepts_matching_legacy_process_and_detects_stale_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            process_path = root / ".ipd" / "tailored_process.yaml"
            state_path = root / ".ipd" / "project_state.yaml"
            process = _legacy_process_projection(load_state(process_path))
            write_state(process_path, process)
            state = load_state(state_path)
            for deliverable in state["deliverables"]:
                deliverable.pop("provenance", None)
                deliverable.pop("maturity", None)
                deliverable.pop("replacements", None)
            write_state(state_path, state)
            (root / ".ipd" / "process_extensions.yaml").unlink()

            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, error + output)

            profile_path = root / ".ipd" / "task_profile.yaml"
            profile = load_state(profile_path)
            profile["project_name"] = "renamed-project"
            write_state(profile_path, profile)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 1, error)
            report = json.loads(output)
            self.assertTrue(
                any(
                    issue.get("code") == "tailored_process_stale"
                    for issue in report["issues"]
                )
            )

    def test_advanced_legacy_project_accepts_only_derived_schema_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.init(root)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            process_path = root / ".ipd" / "tailored_process.yaml"
            process = _legacy_process_projection(load_state(process_path))
            write_state(process_path, process)

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            for deliverable in state["deliverables"]:
                deliverable.pop("provenance", None)
                deliverable.pop("maturity", None)
                deliverable.pop("replacements", None)
                if deliverable.get("phase") == "concept":
                    deliverable["status"] = "accepted"
                    deliverable["evidence"] = [
                        f"evidence/legacy/{deliverable['id']}.md"
                    ]
                    deliverable["reviews"] = [
                        {
                            "reviewer": "legacy-authority",
                            "reviewer_type": "human",
                            "authorized": True,
                            "decision": "approve",
                            "evidence": f"evidence/legacy/{deliverable['id']}-review.md",
                        }
                    ]
            for gate in state["gates"]:
                if gate.get("phase") == "concept":
                    gate["status"] = "approved"
                    gate["reviews"] = [
                        {
                            "reviewer": "legacy-authority",
                            "reviewer_type": "human",
                            "authorized": True,
                            "decision": "approve",
                            "evidence": f"evidence/legacy/{gate['id']}-review.md",
                            "gate_epoch": gate.get("review_epoch", 0),
                        }
                    ]
                    gate["approval"] = "legacy-authority"
            state["project"]["phase"] = "plan"
            apply_phase_pointers(state, process)
            write_state(state_path, state)

            runtime = record_event(
                load_runtime(root),
                "advance_phase",
                details={
                    "from_phase": "concept",
                    "to_phase": "plan",
                    "state_revision": state["revision"],
                },
            )
            save_runtime(root, runtime)
            self.assertEqual(phase_history_issues(state, process, runtime), [])

            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension_path.unlink()
            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            preview = json.loads(output)
            self.assertTrue(
                any(
                    set(item.get("fields", [])) <= {"provenance", "maturity"}
                    for item in preview["changed"]
                )
            )
            self.assertFalse(extension_path.exists())

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 0, output + error)
            self.assertTrue(extension_path.is_file())
            upgraded_process = load_state(process_path)
            upgraded_state = load_state(state_path)
            self.assertEqual(upgraded_process["schema_version"], "2.0")
            self.assertEqual(upgraded_state["project"]["phase"], "plan")
            self.assertTrue(
                all(
                    gate["status"] == "approved"
                    for gate in upgraded_state["gates"]
                    if gate.get("phase") == "concept"
                )
            )


if __name__ == "__main__":
    unittest.main()

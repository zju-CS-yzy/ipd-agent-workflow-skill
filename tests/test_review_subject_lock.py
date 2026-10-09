from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.engine import (
    TransitionError,
    approve_deliverable,
    approve_gate,
    assert_current_iteration_subject,
    bind_current_iteration_subject,
    clear_current_iteration_subject,
    record_deliverable_review,
    record_gate_review,
    recover_current_iteration_subject,
    start_deliverable_review,
    transition_workflow,
)
from ipdctl.state import create_initial_state, load_state, write_state
from ipdctl.refinement import process_fingerprint
from ipdctl.validation import validate_state


def deliverable(identifier: str, status: str = "ready_for_review") -> dict[str, object]:
    return {
        "id": identifier,
        "title": identifier.replace(".", " ").title(),
        "phase": "concept",
        "status": status,
        "review_required": True,
        "depends_on": [],
        "evidence": [f"docs/{identifier}.md"],
        "reviews": [],
    }


def gate(identifier: str, status: str = "ready") -> dict[str, object]:
    return {
        "id": identifier,
        "title": identifier.upper(),
        "kind": "Gate",
        "phase": "concept",
        "status": status,
        "required_deliverables": [],
        "reviews": [],
    }


class ReviewSubjectLockTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def initialize_review(
        self, root: Path, *, deliverable_id: str = "concept.problem_definition",
        refinement_required: bool = False,
    ) -> tuple[Path, Path]:
        self.assertEqual(
            self.invoke(["init", str(root), "--name", "review-lock-demo"])[0],
            0,
        )
        if refinement_required:
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = load_state(extension_path)
            extension["refinement_requirements"].append({
                "root": deliverable_id, "definition_state": "concrete", "refinement_required": True,
                "trigger": {"all_of": [{"subject": deliverable_id, "condition": "accepted"}]},
                "completion_policy": "all_children_accepted",
            })
            write_state(extension_path, extension)
        self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
        self.assertEqual(
            self.invoke(
                [
                    "claim",
                    deliverable_id,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )[0],
            0,
        )
        evidence = root / "docs" / "problem-definition.md"
        evidence.write_text("completed problem definition\n", encoding="utf-8")
        code, output, error = self.invoke(
            [
                "close",
                deliverable_id,
                "--project-root",
                str(root),
                "--actor",
                "agent-a",
                "--evidence",
                "docs/problem-definition.md",
            ]
        )
        self.assertEqual(code, 0, output + error)
        return (
            root / ".ipd" / "project_state.yaml",
            root / ".ipd" / "agent_runtime.yaml",
        )

    def test_new_state_writes_explicit_null_lock(self) -> None:
        state = create_initial_state("demo")

        self.assertIsNone(state["project"]["current_iteration_subject"])
        self.assertEqual(validate_state(state), [])

    def test_legacy_non_review_state_can_omit_lock(self) -> None:
        state = create_initial_state("demo")
        state["project"].pop("current_iteration_subject")

        self.assertEqual(validate_state(state), [])

    def test_legacy_mid_review_state_is_not_guessed(self) -> None:
        state = create_initial_state("demo")
        state["project"].pop("current_iteration_subject")
        state["project"]["workflow_step"] = "review"
        state["deliverables"] = [deliverable("concept.problem-definition")]

        issues = validate_state(state)
        self.assertTrue(
            any(
                issue.path == "$.project.current_iteration_subject"
                and "globally locked" in issue.message
                for issue in issues
            )
        )
        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_REQUIRED"):
            bind_current_iteration_subject(state, "concept.problem-definition")

    def test_legacy_mid_review_recovery_requires_an_explicit_existing_id(self) -> None:
        state = create_initial_state("demo")
        state["project"].pop("current_iteration_subject")
        state["project"]["workflow_step"] = "review"
        state["deliverables"] = [
            deliverable("concept.problem-definition"),
            deliverable("dlv-ipd-governance"),
        ]

        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_NOT_FOUND"):
            recover_current_iteration_subject(state, "missing")
        recovered = recover_current_iteration_subject(
            state, "dlv-ipd-governance"
        )
        self.assertEqual(
            recovered["project"]["current_iteration_subject"],
            "dlv-ipd-governance",
        )
        self.assertEqual(recovered["revision"], state["revision"] + 1)
        self.assertEqual(validate_state(recovered), [])
        self.assertNotIn("current_iteration_subject", state["project"])

        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_ACTIVE"):
            recover_current_iteration_subject(recovered, "concept.problem-definition")

    def test_recovery_rejects_other_invalid_state(self) -> None:
        state = create_initial_state("demo")
        state["project"].pop("current_iteration_subject")
        state["project"]["workflow_step"] = "review"
        state["deliverables"] = [deliverable("spec")]
        state["revision"] = -1

        with self.assertRaisesRegex(TransitionError, "revision"):
            recover_current_iteration_subject(state, "spec")

    def test_review_subject_must_reference_existing_canonical_entity(self) -> None:
        state = create_initial_state("demo")
        state["project"]["workflow_step"] = "review"
        state["project"]["current_iteration_subject"] = "missing"

        issues = validate_state(state)
        self.assertTrue(
            any(
                issue.path == "$.project.current_iteration_subject"
                and "references unknown" in issue.message
                for issue in issues
            )
        )

    def test_deliverable_lock_rejects_other_review_subjects(self) -> None:
        state = create_initial_state("demo")
        state["project"]["workflow_step"] = "work"
        state["deliverables"] = [
            deliverable("concept.problem-definition"),
            deliverable("dlv-ipd-governance"),
        ]

        bound = bind_current_iteration_subject(state, "concept.problem-definition")
        self.assertEqual(bound["project"]["workflow_step"], "review")
        self.assertEqual(
            bound["project"]["current_iteration_subject"],
            "concept.problem-definition",
        )
        self.assertEqual(
            assert_current_iteration_subject(
                bound,
                "concept.problem-definition",
                expected_kind="deliverable",
            ),
            "deliverable",
        )
        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_MISMATCH"):
            start_deliverable_review(bound, "dlv-ipd-governance")
        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_MISMATCH"):
            record_deliverable_review(
                bound,
                "dlv-ipd-governance",
                reviewer="reviewer",
                reviewer_type="human",
                authorized=True,
                decision="approve",
                evidence="reviews/governance.md",
            )

        reviewed = start_deliverable_review(bound, "concept.problem-definition")
        approved = approve_deliverable(
            reviewed,
            "concept.problem-definition",
            reviewer="design-authority",
            reviewer_type="human",
            authorized=True,
            evidence="reviews/problem-definition.md",
        )
        cleared = clear_current_iteration_subject(
            approved, "concept.problem-definition"
        )
        self.assertEqual(cleared["project"]["workflow_step"], "refresh")
        self.assertIsNone(cleared["project"]["current_iteration_subject"])
        self.assertEqual(validate_state(cleared), [])

    def test_gate_record_and_approval_require_same_lock(self) -> None:
        state = create_initial_state("demo")
        state["project"]["workflow_step"] = "verify"
        state["gates"] = [gate("concept-exit"), gate("plan-exit")]
        bound = bind_current_iteration_subject(state, "concept-exit")

        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_MISMATCH"):
            record_gate_review(
                bound,
                "plan-exit",
                reviewer="product-director",
                reviewer_type="human",
                authorized=True,
                decision="approve",
                evidence="reviews/plan-exit.md",
            )
        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_MISMATCH"):
            approve_gate(bound, "plan-exit")

        reviewed = record_gate_review(
            bound,
            "concept-exit",
            reviewer="product-director",
            reviewer_type="human",
            authorized=True,
            decision="approve",
            evidence="reviews/concept-exit.md",
        )
        approved = approve_gate(reviewed, "concept-exit")
        cleared = clear_current_iteration_subject(approved, "concept-exit")
        self.assertEqual(cleared["gates"][0]["status"], "approved")
        self.assertIsNone(cleared["project"]["current_iteration_subject"])

    def test_transition_workflow_binds_and_clears_atomically(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [deliverable("spec")]
        for step in ("claim", "work", "close"):
            state = transition_workflow(state, step)

        with self.assertRaisesRegex(TransitionError, "REVIEW_SUBJECT_REQUIRED"):
            transition_workflow(state, "review")
        state = transition_workflow(state, "review", subject="spec")
        self.assertEqual(state["project"]["current_iteration_subject"], "spec")
        state = transition_workflow(state, "refresh")
        self.assertIsNone(state["project"]["current_iteration_subject"])

    def test_cli_locks_one_subject_rejects_others_and_clears_after_approval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            subject = "concept.problem_definition"
            state_path, runtime_path = self.initialize_review(root)
            state = load_state(state_path)
            other = next(
                item["id"]
                for item in state["deliverables"]
                if item["id"] != subject
            )
            self.assertEqual(state["project"]["workflow_step"], "review")
            self.assertEqual(
                state["project"]["current_iteration_subject"], subject
            )

            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()
            code, output, error = self.invoke(
                [
                    "review",
                    other,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ]
            )
            self.assertEqual(code, 1, output + error)
            self.assertIn("REVIEW_SUBJECT_MISMATCH", output + error)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)

            wrong_review = root / "docs" / "wrong-review.md"
            wrong_review.write_text("must not be applied\n", encoding="utf-8")
            code, output, error = self.invoke(
                [
                    "approve",
                    other,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    "docs/wrong-review.md",
                ]
            )
            self.assertEqual(code, 1, output + error)
            self.assertIn("REVIEW_SUBJECT_MISMATCH", output + error)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)

            code, output, error = self.invoke(
                [
                    "review",
                    subject,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ]
            )
            self.assertEqual(code, 0, output + error)
            review_evidence = root / "docs" / "problem-definition-review.md"
            review_evidence.write_text("approved by design authority\n", encoding="utf-8")
            code, output, error = self.invoke(
                [
                    "approve",
                    subject,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    "docs/problem-definition-review.md",
                ]
            )
            self.assertEqual(code, 0, output + error)
            state = load_state(state_path)
            reviewed = next(
                item for item in state["deliverables"] if item["id"] == subject
            )
            self.assertEqual(reviewed["status"], "accepted")
            self.assertEqual(state["project"]["workflow_step"], "refresh")
            self.assertIsNone(state["project"]["current_iteration_subject"])

    def test_cli_legacy_review_requires_authorized_explicit_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            subject = "concept.problem_definition"
            state_path, runtime_path = self.initialize_review(root)
            legacy_state = load_state(state_path)
            legacy_state["project"].pop("current_iteration_subject")
            write_state(state_path, legacy_state)

            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()
            for command in (
                [
                    "review",
                    subject,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ],
                [
                    "approve",
                    subject,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    "docs/problem-definition.md",
                ],
            ):
                with self.subTest(command=command[0]):
                    code, output, error = self.invoke(command)
                    self.assertEqual(code, 1, output + error)
                    self.assertIn("REVIEW_SUBJECT_REQUIRED", output + error)
                    self.assertEqual(state_path.read_bytes(), before_state)
                    self.assertEqual(runtime_path.read_bytes(), before_runtime)

            unauthorized_recoveries = (
                [
                    "--reviewer",
                    "migration-agent",
                    "--actor-type",
                    "agent",
                    "--authorized",
                    "--reason",
                    "Restore the legacy review subject",
                ],
                [
                    "--reviewer",
                    "migration-authority",
                    "--actor-type",
                    "human",
                    "--reason",
                    "Restore the legacy review subject",
                ],
                [
                    "--reviewer",
                    "migration-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                ],
            )
            for options in unauthorized_recoveries:
                with self.subTest(options=options):
                    code, output, error = self.invoke(
                        [
                            "review",
                            subject,
                            "--project-root",
                            str(root),
                            "--recover-subject",
                            *options,
                        ]
                    )
                    self.assertEqual(code, 1, output + error)
                    self.assertEqual(state_path.read_bytes(), before_state)
                    self.assertEqual(runtime_path.read_bytes(), before_runtime)

            reason = "Restore the explicit v0.5 review subject"
            code, output, error = self.invoke(
                [
                    "review",
                    subject,
                    "--project-root",
                    str(root),
                    "--recover-subject",
                    "--reviewer",
                    "migration-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    reason,
                ]
            )
            self.assertEqual(code, 0, output + error)
            recovered = load_state(state_path)
            self.assertEqual(recovered["project"]["workflow_step"], "review")
            self.assertEqual(
                recovered["project"]["current_iteration_subject"], subject
            )
            runtime = load_state(runtime_path)
            event = runtime["events"][-1]
            self.assertEqual(
                set(event),
                {
                    "action",
                    "at",
                    "subject",
                    "subject_type",
                    "actor",
                    "actor_type",
                    "authorized",
                    "reason",
                    "state_revision",
                },
            )
            self.assertEqual(event["action"], "review_subject_recovered")
            self.assertEqual(event["subject"], subject)
            self.assertEqual(event["subject_type"], "deliverable")
            self.assertEqual(event["actor"], "migration-authority")
            self.assertEqual(event["actor_type"], "human")
            self.assertIs(event["authorized"], True)
            self.assertEqual(event["reason"], reason)
            self.assertEqual(event["state_revision"], recovered["revision"])

            self.assertEqual(
                self.invoke(
                    [
                        "review",
                        subject,
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "review-agent",
                    ]
                )[0],
                0,
            )
            review_evidence = root / "docs" / "legacy-review.md"
            review_evidence.write_text("authorized approval\n", encoding="utf-8")
            code, output, error = self.invoke(
                [
                    "approve",
                    subject,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    "docs/legacy-review.md",
                ]
            )
            self.assertEqual(code, 0, output + error)
            final_state = load_state(state_path)
            self.assertEqual(final_state["project"]["workflow_step"], "refresh")
            self.assertIsNone(final_state["project"]["current_iteration_subject"])

    def test_cli_legacy_gate_recovery_and_cross_kind_lock_in_both_locales(self) -> None:
        for locale in ("en", "zh-CN"):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                self.assertEqual(self.invoke(["init", str(root), "--name", "gate-recovery", "--locale", locale])[0], 0)
                self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
                state_path = root / ".ipd" / "project_state.yaml"
                runtime_path = root / ".ipd" / "agent_runtime.yaml"
                state = load_state(state_path)
                subject = state["project"]["current_gate"]
                for item in state["deliverables"]:
                    if item.get("phase") == "concept":
                        item["status"] = "accepted"
                        item["evidence"] = ["docs/approval.md"]
                        item["reviews"] = [{"reviewer": "fixture-human", "reviewer_type": "human", "authorized": True,
                                            "decision": "approve", "evidence": "docs/approval.md"}]
                next(item for item in state["gates"] if item["id"] == subject)["status"] = "ready"
                state["project"]["workflow_step"] = "review"
                state["project"].pop("current_iteration_subject")
                write_state(state_path, state)
                (root / "docs" / "approval.md").write_text("fixture human review\n", encoding="utf-8")
                code, output, error = self.invoke(["review", "tr.concept", "--project-root", str(root),
                                                  "--reviewer", "fixture-human", "--actor-type", "human", "--authorized",
                                                  "--recover-subject", "--reason", "Recover fixture legacy Gate"])
                self.assertEqual(code, 0, output + error)
                self.assertEqual(load_state(state_path)["project"]["current_iteration_subject"], subject)
                before = (state_path.read_bytes(), runtime_path.read_bytes())
                for command in ("review", "approve", "reject"):
                    arguments = [command, "concept.problem_definition", "--project-root", str(root), "--reviewer", "fixture-human"]
                    if command != "review":
                        arguments += ["--actor-type", "human", "--authorized", "--evidence", "docs/approval.md"]
                    code, output, error = self.invoke(arguments)
                    self.assertEqual(code, 1, output + error)
                    self.assertIn("REVIEW_SUBJECT_MISMATCH", output + error)
                    self.assertEqual(before, (state_path.read_bytes(), runtime_path.read_bytes()))
                self.assertEqual(self.invoke(["review", "tr.concept", "--project-root", str(root), "--reviewer", "fixture-agent"])[0], 0)
                code, output, error = self.invoke(["reject", "tr.concept", "--project-root", str(root), "--reviewer", "fixture-human",
                                                  "--actor-type", "human", "--authorized", "--evidence", "docs/approval.md"])
                self.assertEqual(code, 0, output + error)
                after = load_state(state_path)
                self.assertEqual(after["project"]["workflow_step"], "refresh")
                self.assertIsNone(after["project"]["current_iteration_subject"])
                self.assertEqual(next(item for item in after["gates"] if item["id"] == subject)["status"], "rejected")

    def test_tailor_cannot_rewrite_an_active_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize_review(root)
            before = {path: path.read_bytes() for path in (root / ".ipd").glob("*.yaml")}
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_refinement_preview_exposes_active_review_and_apply_is_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize_review(root, refinement_required=True)
            process = load_state(root / ".ipd" / "tailored_process.yaml")
            plan_path = root / "plan.yaml"
            write_state(plan_path, {
                "schema_version": "1.0", "id": "refinement.problem.fixture", "root": "concept.problem_definition",
                "mode": "expand", "base_process_fingerprint": process_fingerprint(process),
                "reason": "Fixture expansion during an active review must fail closed",
                "basis": ["docs/problem-definition.md"],
                "activities": [{"id": "concept.child_activity", "title": "Child", "phase": "concept", "sequence": 2}],
                "deliverables": [{"id": "concept.child", "title": "Child", "phase": "concept", "activity_id": "concept.child_activity",
                                  "review_required": True, "depends_on": [], "refines": "concept.problem_definition"}],
                "dependencies": [],
            })
            before = {path: path.read_bytes() for path in (root / ".ipd").glob("*.yaml")}
            command = ["refine", str(root), "--plan", str(plan_path)]
            code, output, error = self.invoke([*command, "--preview", "--json"])
            self.assertEqual(code, 0, output + error)
            self.assertIn("ACTIVE_REVIEW", {item["code"] for item in json.loads(output)["blockers"]})
            code, output, error = self.invoke([*command, "--apply", "--actor", "fixture-human", "--actor-type", "human",
                                              "--authorized", "--reason", "Fixture authorization does not override active review"])
            self.assertEqual(code, 1, output + error)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_runtime_schema_declares_recovery_subjects_only_on_events(self) -> None:
        schema = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "schemas"
                / "agent_runtime.schema.json"
            ).read_text(encoding="utf-8")
        )
        active_claim_properties = schema["properties"]["active_claims"][
            "additionalProperties"
        ]["properties"]
        event_properties = schema["properties"]["events"]["items"]["properties"]

        self.assertNotIn("subject", active_claim_properties)
        self.assertNotIn("subject_type", active_claim_properties)
        self.assertIn("subject", event_properties)
        self.assertIn("subject_type", event_properties)


if __name__ == "__main__":
    unittest.main()

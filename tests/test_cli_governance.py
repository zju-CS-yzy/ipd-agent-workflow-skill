from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.state import load_state, write_state


class CliGovernanceTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def initialize(self, root: Path, *, locale: str = "en") -> None:
        self.assertEqual(
            self.invoke(
                [
                    "init",
                    str(root),
                    "--name",
                    "governed-project",
                    "--locale",
                    locale,
                ]
            )[0],
            0,
        )
        self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

    def accept_deliverable(self, root: Path, identifier: str) -> None:
        evidence = root / "evidence" / f"{identifier}.md"
        review = root / "evidence" / f"{identifier}.review.md"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("completed work\n", encoding="utf-8")
        review.write_text("authorized approval\n", encoding="utf-8")
        relative_evidence = evidence.relative_to(root).as_posix()
        relative_review = review.relative_to(root).as_posix()
        commands = (
            ["claim", identifier, "--project-root", str(root), "--actor", "agent-a"],
            [
                "close",
                identifier,
                "--project-root",
                str(root),
                "--actor",
                "agent-a",
                "--evidence",
                relative_evidence,
            ],
            [
                "review",
                identifier,
                "--project-root",
                str(root),
                "--reviewer",
                "review-agent",
            ],
            [
                "approve",
                identifier,
                "--project-root",
                str(root),
                "--reviewer",
                "design-authority",
                "--actor-type",
                "human",
                "--authorized",
                "--evidence",
                relative_review,
            ],
        )
        for command in commands:
            code, output, error = self.invoke(command)
            self.assertEqual(code, 0, output + error)

    def refresh_verify(self, root: Path) -> None:
        code, output, error = self.invoke(["refresh", str(root)])
        self.assertEqual(code, 0, output + error)
        code, output, error = self.invoke(["verify", str(root), "--json"])
        self.assertEqual(code, 0, output + error)

    def approve_gate(
        self, root: Path, subject: str, *, synchronize: bool = True
    ) -> None:
        evidence = root / "evidence" / f"{subject}.md"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("authorized gate decision\n", encoding="utf-8")
        relative = evidence.relative_to(root).as_posix()
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
        code, _, error = self.invoke(
            [
                "approve",
                subject,
                "--project-root",
                str(root),
                "--reviewer",
                "review-agent",
                "--actor-type",
                "agent",
                "--authorized",
                "--evidence",
                relative,
            ]
        )
        self.assertEqual(code, 1)
        profile = load_state(root / ".ipd" / "task_profile.yaml")
        if profile.get("presentation", {}).get("locale") == "zh-CN":
            self.assertIn("经授权的人类批准记录", error)
            self.assertNotIn("authorized human", error)
        else:
            self.assertIn("authorized human", error)
        code, output, error = self.invoke(
            [
                "approve",
                subject,
                "--project-root",
                str(root),
                "--reviewer",
                "governance-board",
                "--actor-type",
                "human",
                "--authorized",
                "--evidence",
                relative,
            ]
        )
        self.assertEqual(code, 0, output + error)
        if synchronize:
            self.refresh_verify(root)

    def test_tr_dcp_aliases_approve_canonical_gates_and_advance_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            state = load_state(root / ".ipd" / "project_state.yaml")
            self.assertEqual(len(state["gates"]), 12)
            self.assertEqual({gate["kind"] for gate in state["gates"]}, {"TR", "DCP"})

            code, _, error = self.invoke(
                [
                    "review",
                    "tr.concept",
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("workflow step", error)

            self.accept_deliverable(root, "concept.problem_definition")
            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            self.assertEqual(json.loads(output)["available_tasks"], [])
            self.refresh_verify(root)
            self.approve_gate(root, "tr.concept")
            state = load_state(root / ".ipd" / "project_state.yaml")
            self.assertEqual(state["project"]["current_gate"], "gate.dcp.concept")
            self.approve_gate(root, "dcp.concept", synchronize=False)

            state = load_state(root / ".ipd" / "project_state.yaml")
            statuses = {gate["id"]: gate["status"] for gate in state["gates"]}
            self.assertEqual(statuses["gate.tr.concept"], "approved")
            self.assertEqual(statuses["gate.dcp.concept"], "approved")

            code, _, _ = self.invoke(["advance-phase", str(root)])
            self.assertEqual(code, 1)
            self.refresh_verify(root)

            verified_state = load_state(root / ".ipd" / "project_state.yaml")
            skipped_state = load_state(root / ".ipd" / "project_state.yaml")
            skipped_state["project"].update(
                {
                    "phase": "plan",
                    "current_tr": "tr.plan",
                    "current_dcp": "dcp.plan",
                    "current_gate": "gate.tr.plan",
                }
            )
            write_state(root / ".ipd" / "project_state.yaml", skipped_state)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertIn("phase advancement history", output + error)
            write_state(root / ".ipd" / "project_state.yaml", verified_state)
            self.refresh_verify(root)

            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            original_runtime = load_state(runtime_path)
            tampered_runtime = load_state(runtime_path)
            claim_event = next(
                event
                for event in tampered_runtime["events"]
                if event.get("action") == "claim"
            )
            claim_event["actor"] = "tampered-agent"
            write_state(runtime_path, tampered_runtime)
            code, _, error = self.invoke(["advance-phase", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("changed after verification", error)
            write_state(runtime_path, original_runtime)

            process_path = root / ".ipd" / "tailored_process.yaml"
            original_process = load_state(process_path)
            tampered_process = load_state(process_path)
            tampered_process["phases"][1]["sequence"] = 99
            write_state(process_path, tampered_process)
            code, _, error = self.invoke(["advance-phase", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("changed after verification", error)
            self.assertEqual(
                load_state(root / ".ipd" / "project_state.yaml")["project"]["phase"],
                "concept",
            )
            write_state(process_path, original_process)

            dcp_evidence = root / "evidence" / "dcp.concept.md"
            dcp_text = dcp_evidence.read_text(encoding="utf-8")
            dcp_evidence.unlink()
            code, _, error = self.invoke(["advance-phase", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("changed after verification", error)
            dcp_evidence.write_text(dcp_text, encoding="utf-8")

            code, output, error = self.invoke(["advance-phase", str(root)])
            self.assertEqual(code, 0, output + error)
            state = load_state(root / ".ipd" / "project_state.yaml")
            self.assertEqual(state["project"]["phase"], "plan")
            self.assertEqual(state["project"]["workflow_step"], "refresh")
            self.assertEqual(state["project"]["current_tr"], "tr.plan")
            self.assertEqual(state["project"]["current_dcp"], "dcp.plan")
            self.assertEqual(state["project"]["current_gate"], "gate.tr.plan")
            code, _, _ = self.invoke(
                ["claim", "plan.integrated_plan", "--project-root", str(root)]
            )
            self.assertEqual(code, 1)

    def test_claim_cannot_follow_a_hand_edited_phase_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            state["project"].update(
                {
                    "phase": "plan",
                    "current_tr": "tr.plan",
                    "current_dcp": "dcp.plan",
                    "current_gate": "gate.tr.plan",
                }
            )
            write_state(state_path, state)
            before = state_path.read_bytes()
            code, _, error = self.invoke(
                [
                    "claim",
                    "plan.integrated_plan",
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("phase advancement history", error)
            self.assertEqual(state_path.read_bytes(), before)

    def test_gate_review_cannot_skip_current_tr_or_cross_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            self.accept_deliverable(root, "concept.problem_definition")
            self.refresh_verify(root)

            state_path = root / ".ipd" / "project_state.yaml"
            before = state_path.read_bytes()
            for subject in ("dcp.concept", "tr.plan"):
                code, _, error = self.invoke(
                    [
                        "review",
                        subject,
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "review-agent",
                    ]
                )
                self.assertEqual(code, 1)
                self.assertIn("is not the current gate", error)
                self.assertEqual(state_path.read_bytes(), before)

            self.assertEqual(
                load_state(state_path)["project"]["current_gate"],
                "gate.tr.concept",
            )

            code, output, error = self.invoke(
                [
                    "review",
                    "tr.concept",
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ]
            )
            self.assertEqual(code, 0, output + error)

            tampered = load_state(state_path)
            tampered["project"]["current_gate"] = "gate.dcp.concept"
            write_state(state_path, tampered)
            tampered_bytes = state_path.read_bytes()
            evidence = root / "evidence" / "tampered-gate.md"
            evidence.write_text("tampered gate attempt\n", encoding="utf-8")
            code, _, error = self.invoke(
                [
                    "approve",
                    "dcp.concept",
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "governance-board",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    evidence.relative_to(root).as_posix(),
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("current_gate", error)
            self.assertIn("stale", error)
            self.assertEqual(state_path.read_bytes(), tampered_bytes)

    def test_rejected_gate_and_deliverable_preserve_history_through_rework(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root, locale="zh-CN")
            deliverable = "concept.problem_definition"
            self.accept_deliverable(root, deliverable)
            self.refresh_verify(root)

            # Rejection/rework is exercised on a gate because accepted deliverables are terminal.
            gate_evidence = root / "evidence" / "gate-rejected.md"
            gate_evidence.write_text("rejected gate decision\n", encoding="utf-8")
            relative = gate_evidence.relative_to(root).as_posix()
            self.assertEqual(
                self.invoke(
                    [
                        "review",
                        "gate.tr.concept",
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "review-agent",
                    ]
                )[0],
                0,
            )
            code, output, error = self.invoke(
                [
                    "reject",
                    "gate.tr.concept",
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "governance-board",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    relative,
                ]
            )
            self.assertEqual(code, 0, output + error)
            self.refresh_verify(root)
            self.approve_gate(root, "gate.tr.concept")
            state = load_state(root / ".ipd" / "project_state.yaml")
            gate = next(item for item in state["gates"] if item["id"] == "gate.tr.concept")
            self.assertEqual(gate["status"], "approved")
            self.assertEqual(
                [review["decision"] for review in gate["reviews"]],
                ["reject", "approve"],
            )

    def test_active_claim_cannot_be_taken_over_but_expired_claim_can_recover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            self.assertEqual(
                self.invoke(
                    [
                        "claim",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-a",
                    ]
                )[0],
                0,
            )

            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-b",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("already claimed", error)

            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"][deliverable]["started_at"] = "1999-01-01T00:00:00Z"
            runtime["active_claims"][deliverable]["expires_at"] = "2000-01-01T00:00:00Z"
            write_state(runtime_path, runtime)

            code, output, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-b",
                ]
            )
            self.assertEqual(code, 0, output + error)
            runtime = load_state(runtime_path)
            self.assertEqual(runtime["active_claims"][deliverable]["actor"], "agent-b")
            self.assertIn(
                "claim_expired", [event["action"] for event in runtime["events"]]
            )
            state = load_state(root / ".ipd" / "project_state.yaml")
            item = next(row for row in state["deliverables"] if row["id"] == deliverable)
            self.assertEqual(item["status"], "in_progress")

    def test_context_exposes_orphaned_claim_and_close_requires_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            self.assertEqual(
                self.invoke(
                    [
                        "claim",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-a",
                    ]
                )[0],
                0,
            )
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"].pop(deliverable)
            write_state(runtime_path, runtime)

            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            snapshot = json.loads(output)
            self.assertEqual(snapshot["recoverable_claims"], [deliverable])
            self.assertTrue(
                next(
                    item for item in snapshot["blocked_items"] if item["id"] == deliverable
                )["recoverable"]
            )

            evidence = root / "evidence" / "orphan.md"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text("orphan work\n", encoding="utf-8")
            code, _, error = self.invoke(
                [
                    "close",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                    "--evidence",
                    "evidence/orphan.md",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("no active claim lease", error)
            state = load_state(root / ".ipd" / "project_state.yaml")
            item = next(row for row in state["deliverables"] if row["id"] == deliverable)
            self.assertEqual(item["status"], "in_progress")

    def test_invalid_claim_expiry_is_rejected_instead_of_becoming_permanent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            self.assertEqual(
                self.invoke(
                    ["claim", deliverable, "--project-root", str(root), "--actor", "agent-a"]
                )[0],
                0,
            )
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"][deliverable]["expires_at"] = "not-a-timestamp"
            write_state(runtime_path, runtime)

            code, _, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertIn("invalid runtime timestamp", error)

    def test_failed_retailor_preserves_canonical_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            code, output, error = self.invoke(
                [
                    "init",
                    str(root),
                    "--name",
                    "retailor-project",
                    "--task-type",
                    "software",
                    "--task-type",
                    "embedded",
                ]
            )
            self.assertEqual(code, 0, output + error)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            process_path = root / ".ipd" / "tailored_process.yaml"
            before = process_path.read_bytes()

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            embedded = next(
                item
                for item in state["deliverables"]
                if item["id"] == "embedded.partition_specification"
            )
            embedded["status"] = "blocked"
            embedded["blocked_reason"] = "historical work must be preserved"
            write_state(state_path, state)
            profile_path = root / ".ipd" / "task_profile.yaml"
            profile = load_state(profile_path)
            profile["task_types"] = ["software"]
            write_state(profile_path, profile)

            code, _, _ = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1)
            self.assertEqual(process_path.read_bytes(), before)

    def test_rejected_work_cannot_skip_refresh_and_verify_before_reclaim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            evidence_dir = root / "evidence"
            evidence_dir.mkdir(parents=True)
            (evidence_dir / "work.md").write_text("work\n", encoding="utf-8")
            (evidence_dir / "reject.md").write_text("reject\n", encoding="utf-8")
            for command in (
                ["claim", deliverable, "--project-root", str(root)],
                [
                    "close",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--evidence",
                    "evidence/work.md",
                ],
                [
                    "review",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ],
                [
                    "reject",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    "evidence/reject.md",
                ],
            ):
                code, output, error = self.invoke(command)
                self.assertEqual(code, 0, output + error)

            code, _, _ = self.invoke(
                ["claim", deliverable, "--project-root", str(root)]
            )
            self.assertEqual(code, 1)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            code, _, _ = self.invoke(
                ["claim", deliverable, "--project-root", str(root)]
            )
            self.assertEqual(code, 1)
            self.assertEqual(self.invoke(["verify", str(root), "--json"])[0], 0)
            self.assertEqual(
                self.invoke(["claim", deliverable, "--project-root", str(root)])[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.i18n import get_translator, localized_exception_message
from ipdctl.state import load_state, write_state


class CliChineseErrorLocalizationTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def initialize(self, root: Path) -> None:
        code, output, error = self.invoke(
            ["init", str(root), "--name", "中文错误回归", "--locale", "zh-CN"]
        )
        self.assertEqual(code, 0, output + error)
        code, output, error = self.invoke(["tailor", str(root)])
        self.assertEqual(code, 0, output + error)

    def assert_chinese_error(
        self,
        result: tuple[int, str, str],
        *,
        contains: tuple[str, ...],
        excludes: tuple[str, ...],
    ) -> str:
        code, output, error = result
        self.assertEqual(code, 1, output + error)
        self.assertTrue(error.startswith("错误: "), error)
        for fragment in contains:
            self.assertIn(fragment, error)
        for fragment in excludes:
            self.assertNotIn(fragment, error)
        return error

    def set_workflow_step(self, root: Path, step: str) -> None:
        state_path = root / ".ipd" / "project_state.yaml"
        state = load_state(state_path)
        state["project"]["workflow_step"] = step
        write_state(state_path, state)

    def test_exception_adapter_preserves_english_and_unknown_diagnostics(self) -> None:
        english = get_translator("en")
        messages = (
            "deliverable 'plan.integrated_plan' belongs to phase 'plan'; "
            "current phase is 'concept'",
            "deliverable 'concept.problem_definition' has unmet dependencies: "
            "concept.prerequisite",
            "deliverable 'concept.problem_definition' has no active claim lease; "
            "claim or recover it before close",
            "closing a deliverable requires evidence",
            "only a ready gate can be approved",
            "current phase gates are not approved: gate.tr.concept, gate.dcp.concept",
            "current state revision must pass verification before phase advancement",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(
                    localized_exception_message(ValueError(message), english),
                    message,
                )

        unknown = "unexpected lower-level diagnostic"
        self.assertEqual(
            localized_exception_message(ValueError(unknown), get_translator("zh-CN")),
            unknown,
        )

    def test_claim_failures_translate_narrative_and_preserve_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)

            self.assert_chinese_error(
                self.invoke(
                    [
                        "claim",
                        "plan.integrated_plan",
                        "--project-root",
                        str(root),
                    ]
                ),
                contains=(
                    "交付件 'plan.integrated_plan' 属于阶段 'plan'",
                    "当前阶段为 'concept'",
                ),
                excludes=("belongs to phase", "current phase is"),
            )

            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            deliverable = next(
                item
                for item in state["deliverables"]
                if item["id"] == "concept.problem_definition"
            )
            prerequisite = copy.deepcopy(deliverable)
            prerequisite.update(
                {
                    "id": "concept.prerequisite",
                    "title": "Synthetic prerequisite",
                    "status": "planned",
                    "depends_on": [],
                    "evidence": [],
                    "reviews": [],
                    "blocked_reason": None,
                    "replacement": None,
                }
            )
            deliverable["depends_on"] = [prerequisite["id"]]
            state["deliverables"].append(prerequisite)
            write_state(state_path, state)

            self.assert_chinese_error(
                self.invoke(
                    [
                        "claim",
                        "concept.problem_definition",
                        "--project-root",
                        str(root),
                    ]
                ),
                contains=(
                    "交付件 'concept.problem_definition' 存在尚未验收的依赖",
                    "concept.prerequisite",
                ),
                excludes=("has unmet dependencies",),
            )

    def test_close_failures_translate_missing_evidence_and_claim_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "expired"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            self.assertEqual(
                self.invoke(
                    ["claim", deliverable, "--project-root", str(root)]
                )[0],
                0,
            )

            self.assert_chinese_error(
                self.invoke(
                    ["close", deliverable, "--project-root", str(root)]
                ),
                contains=("关闭交付件时必须提供 evidence",),
                excludes=("closing a deliverable requires evidence",),
            )

            evidence = root / "docs" / "work.md"
            evidence.write_text("work\n", encoding="utf-8")
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"][deliverable]["started_at"] = (
                "1999-01-01T00:00:00Z"
            )
            runtime["active_claims"][deliverable]["expires_at"] = (
                "2000-01-01T00:00:00Z"
            )
            write_state(runtime_path, runtime)
            self.assert_chinese_error(
                self.invoke(
                    [
                        "close",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--evidence",
                        "docs/work.md",
                    ]
                ),
                contains=(
                    "交付件 'concept.problem_definition' 没有活动领取租约",
                    "close",
                ),
                excludes=("has no active claim lease",),
            )

            orphan_root = Path(directory) / "orphan"
            self.initialize(orphan_root)
            self.assertEqual(
                self.invoke(
                    ["claim", deliverable, "--project-root", str(orphan_root)]
                )[0],
                0,
            )
            orphan_runtime_path = orphan_root / ".ipd" / "agent_runtime.yaml"
            orphan_runtime = load_state(orphan_runtime_path)
            orphan_runtime["active_claims"].pop(deliverable)
            write_state(orphan_runtime_path, orphan_runtime)
            orphan_evidence = orphan_root / "docs" / "work.md"
            orphan_evidence.write_text("work\n", encoding="utf-8")
            self.assert_chinese_error(
                self.invoke(
                    [
                        "close",
                        deliverable,
                        "--project-root",
                        str(orphan_root),
                        "--evidence",
                        "docs/work.md",
                    ]
                ),
                contains=("没有活动领取租约",),
                excludes=("has no active claim lease",),
            )

    def test_gate_failures_translate_not_ready_and_unaccepted_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            self.set_workflow_step(root, "review")
            evidence = root / "docs" / "gate-review.md"
            evidence.write_text("review\n", encoding="utf-8")

            self.assert_chinese_error(
                self.invoke(
                    [
                        "approve",
                        "gate.tr.concept",
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "governance-board",
                        "--actor-type",
                        "human",
                        "--authorized",
                        "--evidence",
                        "docs/gate-review.md",
                    ]
                ),
                contains=("只有 status 为 ready 的 Gate 才能批准",),
                excludes=("only a ready gate can be approved",),
            )

            self.assert_chinese_error(
                self.invoke(
                    [
                        "review",
                        "gate.tr.concept",
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "review-agent",
                    ]
                ),
                contains=(
                    "$.gates[0].required_deliverables",
                    "Gate 前置交付件尚未验收",
                    "concept.problem_definition",
                ),
                excludes=("gate prerequisites are not accepted",),
            )

    def test_phase_and_stale_verification_failures_are_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            self.set_workflow_step(root, "refresh")
            code, output, error = self.invoke(["refresh", str(root)])
            self.assertEqual(code, 0, output + error)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, output + error)

            self.assert_chinese_error(
                self.invoke(["advance-phase", str(root)]),
                contains=(
                    "当前阶段的 Gate 尚未批准",
                    "gate.tr.concept",
                    "gate.dcp.concept",
                ),
                excludes=("current phase gates are not approved",),
            )

            process_path = root / ".ipd" / "tailored_process.yaml"
            process = load_state(process_path)
            process["phases"][1]["sequence"] = 99
            write_state(process_path, process)
            self.assert_chinese_error(
                self.invoke(["advance-phase", str(root)]),
                contains=(
                    "项目输入在验证后发生变化",
                    "refresh",
                    "verify",
                    "advance-phase",
                ),
                excludes=("project inputs changed after verification",),
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.state import load_state, write_state


class CliLifecycleTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_required_temporary_project_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "test-project"
            self.assertEqual(
                self.invoke(
                    ["init", str(root), "--name", "test-project", "--task-type", "software"]
                )[0],
                0,
            )
            for relative in (".ipd", "docs", "src", "tests", "dashboard", "state"):
                self.assertTrue((root / relative).is_dir(), relative)
            self.assertTrue((root / ".ipd" / "project_state.yaml").is_file())
            self.assertTrue((root / ".ipd" / "task_profile.yaml").is_file())
            profile = load_state(root / ".ipd" / "task_profile.yaml")
            self.assertEqual(profile["presentation"]["locale"], "en")

            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            bindings = load_state(root / ".ipd" / "artifact_bindings.yaml")
            self.assertTrue(
                any(
                    rule.get("glob") == "evidence/concept.problem_definition/**"
                    for rule in bindings["bindings"]
                )
            )
            context_code, context_output, _ = self.invoke(["context", str(root), "--json"])
            self.assertEqual(context_code, 0)
            context = json.loads(context_output)
            self.assertEqual(context["phase"], "concept")
            self.assertTrue(context["available_tasks"])

            refresh_code, refresh_output, refresh_error = self.invoke(
                ["refresh", str(root)]
            )
            self.assertEqual(refresh_code, 0, refresh_error)
            self.assertIn("15 files including manifest", refresh_output)
            verify_code, verify_output, _ = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(verify_code, 0, verify_output)
            self.assertEqual(json.loads(verify_output)["status"], "passed")

            dashboard = root / ".ipd" / "dashboard"
            self.assertTrue((dashboard / "index.html").is_file())
            self.assertTrue((dashboard / "assets" / "ipd_flow.svg").is_file())
            self.assertTrue((dashboard / "assets" / "current_status_flow.svg").is_file())
            self.assertTrue((dashboard / "assets" / "deliverable_dependency.svg").is_file())
            self.assertTrue((dashboard / "phases" / "concept.svg").is_file())
            self.assertTrue((dashboard / "matrices" / "deliverable_matrix.html").is_file())
            self.assertTrue((dashboard / "matrices" / "gate_matrix.html").is_file())
            self.assertTrue((dashboard / "data" / "state.json").is_file())
            self.assertTrue((dashboard / "data" / "graph.json").is_file())
            self.assertTrue((dashboard / "manifest.json").is_file())

            unexpected = dashboard / "stale-output.svg"
            unexpected.write_text("<svg/>", encoding="utf-8")
            verify_code, verify_output, _ = self.invoke(
                ["verify", str(root), "--json"]
            )
            self.assertEqual(verify_code, 1)
            self.assertTrue(
                any(
                    "unexpected dashboard file" in issue["message"]
                    for issue in json.loads(verify_output)["issues"]
                )
            )

    def test_claim_close_review_and_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            deliverable = "concept.problem_definition"
            self.assertEqual(
                self.invoke(
                    ["claim", deliverable, "--project-root", str(root), "--actor", "agent-a"]
                )[0],
                0,
            )
            evidence = root / "docs" / "problem.md"
            evidence.write_text("problem evidence\n", encoding="utf-8")
            self.assertEqual(
                self.invoke(
                    [
                        "close",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-a",
                        "--evidence",
                        "docs/problem.md",
                    ]
                )[0],
                0,
            )
            self.assertEqual(
                self.invoke(
                    [
                        "review",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "review-agent",
                    ]
                )[0],
                0,
            )
            review = root / "docs" / "problem-review.md"
            review.write_text("approved by design authority\n", encoding="utf-8")
            self.assertEqual(
                self.invoke(
                    [
                        "approve",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--reviewer",
                        "design-authority",
                        "--actor-type",
                        "human",
                        "--authorized",
                        "--evidence",
                        "docs/problem-review.md",
                    ]
                )[0],
                0,
            )
            state = load_state(root / ".ipd" / "project_state.yaml")
            accepted = next(item for item in state["deliverables"] if item["id"] == deliverable)
            self.assertEqual(accepted["status"], "accepted")
            self.assertTrue(accepted["reviews"])

    def test_verify_rejects_ghost_runtime_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)

            deliverable = "concept.problem_definition"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"][deliverable] = {
                "deliverable": deliverable,
                "actor": "ghost-agent",
                "started_at": "2099-01-01T00:00:00Z",
                "expires_at": "2099-01-02T00:00:00Z",
            }
            write_state(runtime_path, runtime)

            code, output, _ = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 1)
            report = json.loads(output)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(
                any(
                    issue.get("code") == "project_bundle_inconsistent"
                    for issue in report["issues"]
                )
            )
            self.assertTrue(
                any("ghost active claim" in issue["message"] for issue in report["issues"])
            )

    def test_force_init_cannot_reuse_stale_process_as_a_valid_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "before"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root), "--json"])[0], 0)

            code, output, error = self.invoke(
                ["init", str(root), "--name", "after", "--force"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertEqual(self.invoke(["context", str(root), "--json"])[0], 1)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 1)
            code, output, _ = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output)["status"], "failed")

            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root), "--json"])[0], 0)

    def test_agent_final_approval_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            deliverable = "concept.problem_definition"
            self.assertEqual(
                self.invoke(["claim", deliverable, "--project-root", str(root)])[0], 0
            )
            (root / "docs" / "evidence.md").write_text("evidence\n", encoding="utf-8")
            self.assertEqual(
                self.invoke(
                    [
                        "close",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--evidence",
                        "docs/evidence.md",
                    ]
                )[0],
                0,
            )
            self.assertEqual(
                self.invoke(
                    ["review", deliverable, "--project-root", str(root), "--reviewer", "agent"]
                )[0],
                0,
            )
            code, _, error = self.invoke(
                [
                    "approve",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "agent",
                    "--actor-type",
                    "agent",
                    "--authorized",
                    "--evidence",
                    "docs/evidence.md",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("authorized human", error)

    def test_chinese_project_localizes_lifecycle_output_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            code, output, error = self.invoke(
                ["init", str(root), "--name", "演示项目", "--locale", "zh-CN"]
            )
            self.assertEqual(code, 0, error)
            self.assertIn("已初始化", output)

            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 0, error)
            self.assertIn("已生成裁剪流程", output)

            deliverable = "concept.problem_definition"
            code, output, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertIn("已由 agent-a 领取", output)

            evidence = root / "docs" / "problem.md"
            evidence.write_text("problem evidence\n", encoding="utf-8")
            code, output, error = self.invoke(
                [
                    "close",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                    "--evidence",
                    "docs/problem.md",
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertIn("待评审", output)

            code, output, error = self.invoke(
                [
                    "review",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertIn("已开始评审", output)

            review = root / "docs" / "problem-review.md"
            review.write_text("approved\n", encoding="utf-8")
            code, output, error = self.invoke(
                [
                    "approve",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    "docs/problem-review.md",
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertIn("已验收", output)
            state = load_state(root / ".ipd" / "project_state.yaml")
            accepted = next(item for item in state["deliverables"] if item["id"] == deliverable)
            self.assertEqual(accepted["status"], "accepted")


if __name__ == "__main__":
    unittest.main()

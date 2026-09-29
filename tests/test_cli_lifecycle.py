from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.state import load_state


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

            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            context_code, context_output, _ = self.invoke(["context", str(root), "--json"])
            self.assertEqual(context_code, 0)
            context = json.loads(context_output)
            self.assertEqual(context["phase"], "concept")
            self.assertTrue(context["available_tasks"])

            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            verify_code, verify_output, _ = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(verify_code, 0, verify_output)
            self.assertEqual(json.loads(verify_output)["status"], "passed")

            dashboard = root / ".ipd" / "dashboard"
            self.assertTrue((dashboard / "index.html").is_file())
            self.assertTrue((dashboard / "deliverable_dependency_graph.json").is_file())
            self.assertTrue((dashboard / "deliverable_matrix.html").is_file())
            self.assertTrue((dashboard / "deliverable_matrix.json").is_file())
            self.assertTrue((dashboard / "deliverable_matrix.md").is_file())
            self.assertTrue((dashboard / "gate_matrix.html").is_file())

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


if __name__ == "__main__":
    unittest.main()

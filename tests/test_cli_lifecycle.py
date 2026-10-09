from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from ipdctl.cli import main
from ipdctl.project import sync_state_with_process
from ipdctl.refinement import merge_refinement_plan, process_fingerprint
from ipdctl.state import load_state, write_state
from ipdctl.tailoring import tailor_profile


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
            self.assertEqual(profile["capability_patterns"], [])

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
            self.assertIn("16 files including manifest", refresh_output)
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

    def test_tailor_cannot_apply_hand_written_refinement_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = load_state(extension_path)
            extension["refinement_requirements"].append(
                {
                    "root": "concept.problem_definition",
                    "definition_state": "concrete",
                    "refinement_required": True,
                    "trigger": {
                        "all_of": [
                            {
                                "subject": "concept.problem_definition",
                                "condition": "accepted",
                            }
                        ]
                    },
                    "completion_policy": "all_children_accepted",
                }
            )
            write_state(extension_path, extension)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            process_path = root / ".ipd" / "tailored_process.yaml"
            process = load_state(process_path)
            plan = {
                "schema_version": "1.0",
                "id": "refinement.problem.v1",
                "root": "concept.problem_definition",
                "mode": "expand",
                "base_process_fingerprint": process_fingerprint(process),
                "reason": "Unauthorized direct extension edit used for a negative test.",
                "basis": ["evidence/concept.problem_definition/approval.md"],
                "activities": [
                    {
                        "id": "concept.define_problem_subsystem",
                        "title": "Define problem subsystem",
                        "phase": "concept",
                        "sequence": 2,
                    }
                ],
                "deliverables": [
                    {
                        "id": "concept.problem_subsystem",
                        "title": "Problem subsystem definition",
                        "phase": "concept",
                        "activity_id": "concept.define_problem_subsystem",
                        "review_required": True,
                        "depends_on": [],
                        "refines": "concept.problem_definition",
                    }
                ],
                "dependencies": [],
            }
            unauthorized, applied = merge_refinement_plan(
                extension, plan, process=process
            )
            self.assertTrue(applied)
            write_state(extension_path, unauthorized)

            code, output, error = self.invoke(
                ["tailor", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, output + error)
            self.assertTrue(
                any(
                    item.get("collection") == "refinements"
                    for item in json.loads(output)["added"]
                )
            )
            protected = {
                path.name: path.read_bytes()
                for path in (
                    process_path,
                    root / ".ipd" / "project_state.yaml",
                    root / ".ipd" / "agent_runtime.yaml",
                )
            }
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("ipdctl refine --apply", error)
            self.assertEqual(
                protected,
                {
                    path.name: path.read_bytes()
                    for path in (
                        process_path,
                        root / ".ipd" / "project_state.yaml",
                        root / ".ipd" / "agent_runtime.yaml",
                    )
                },
            )

            # Materialize the authorized shape, then prove changing a child
            # while keeping the recorded plan unchanged cannot use tailor as a
            # lineage bypass.
            authorized_process = tailor_profile(
                load_state(root / ".ipd" / "task_profile.yaml"),
                process_extension=unauthorized,
            )
            write_state(process_path, authorized_process)
            write_state(
                root / ".ipd" / "project_state.yaml",
                sync_state_with_process(
                    load_state(root / ".ipd" / "project_state.yaml"),
                    authorized_process,
                ),
            )
            drifted = deepcopy(unauthorized)
            next(
                item
                for item in drifted["deliverables"]
                if item["id"] == "concept.problem_subsystem"
            )["title"] = "Drifted problem subsystem definition"
            write_state(extension_path, drifted)
            protected = {
                path.name: path.read_bytes()
                for path in (
                    process_path,
                    root / ".ipd" / "project_state.yaml",
                    root / ".ipd" / "agent_runtime.yaml",
                )
            }
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("ipdctl refine --apply", error)
            self.assertEqual(
                protected,
                {
                    path.name: path.read_bytes()
                    for path in (
                        process_path,
                        root / ".ipd" / "project_state.yaml",
                        root / ".ipd" / "agent_runtime.yaml",
                    )
                },
            )

    def test_unapplied_requirement_can_be_corrected_but_not_preexpanded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            extension_path = root / ".ipd" / "process_extensions.yaml"
            extension = load_state(extension_path)
            extension["refinement_requirements"].append(
                {
                    "root": "software.architecture",
                    "definition_state": "placeholder",
                    "refinement_required": True,
                    "trigger": {
                        "all_of": [
                            {"subject": "plan.integrated_plan", "condition": "accepted"}
                        ]
                    },
                    "completion_policy": "all_children_accepted",
                }
            )
            write_state(extension_path, extension)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

            corrected = load_state(extension_path)
            corrected["refinement_requirements"][0]["trigger"] = {
                "all_of": [{"subject": "gate.dcp.concept", "condition": "approved"}]
            }
            write_state(extension_path, corrected)
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 0, output + error)

            preexpanded = load_state(extension_path)
            preexpanded["activities"].append(
                {
                    "id": "plan.hidden_module_design",
                    "title": "Define hidden module",
                    "phase": "plan",
                    "sequence": 99,
                }
            )
            preexpanded["deliverables"].append(
                {
                    "id": "software.hidden_module",
                    "title": "Hidden module",
                    "phase": "plan",
                    "activity_id": "plan.hidden_module_design",
                    "review_required": True,
                    "depends_on": ["plan.integrated_plan"],
                    "refines": "software.architecture",
                }
            )
            write_state(extension_path, preexpanded)
            process_path = root / ".ipd" / "tailored_process.yaml"
            protected = process_path.read_bytes()
            code, output, error = self.invoke(["tailor", str(root)])
            self.assertEqual(code, 1, output + error)
            self.assertIn("ipdctl refine --apply", error)
            self.assertEqual(process_path.read_bytes(), protected)


if __name__ == "__main__":
    unittest.main()

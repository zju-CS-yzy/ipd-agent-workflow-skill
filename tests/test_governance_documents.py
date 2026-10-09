from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path

from ipdctl.cli import main
from ipdctl.governance_documents import (
    governance_document_issues,
    render_governance_document,
)
from ipdctl.state import load_state, write_state


def facts() -> tuple[dict, dict]:
    process = {
        "schema_version": "2.0",
        "gates": [
            {
                "id": "gate.tr.concept",
                "title": "Concept technical review",
                "kind": "TR",
                "phase": "concept",
                "required_deliverables": ["concept.problem_definition"],
            }
        ],
    }
    state = {
        "schema_version": "2.0",
        "revision": 7,
        "project": {
            "name": "governed-project",
            "phase": "concept",
            "workflow_step": "review",
            "current_tr": "tr.concept",
            "current_dcp": "dcp.concept",
            "current_gate": "gate.tr.concept",
            "current_iteration_subject": "concept.problem_definition",
        },
        "claims": [],
        "deliverables": [
            {
                "id": "concept.problem_definition",
                "title": "Problem definition",
                "phase": "concept",
                "status": "in_review",
                "evidence": ["docs/problem.md"],
                "reviews": [],
            }
        ],
        "gates": [
            {
                "id": "gate.tr.concept",
                "title": "Concept technical review",
                "kind": "TR",
                "phase": "concept",
                "status": "planned",
                "required_deliverables": ["concept.problem_definition"],
                "reviews": [],
            }
        ],
        "traceability": [],
    }
    return process, state


class GovernanceDocumentTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_render_is_deterministic_and_preserves_machine_values(self) -> None:
        process, state = facts()
        before_process = deepcopy(process)
        before_state = deepcopy(state)
        first = render_governance_document(process, state, locale="en")
        second = render_governance_document(process, state, locale="en")
        chinese = render_governance_document(process, state, locale="zh-CN")

        self.assertEqual(first, second)
        self.assertEqual(process, before_process)
        self.assertEqual(state, before_state)
        for text in (first, chinese):
            self.assertIn('framework_version: 0.5.1-beta', text)
            self.assertIn('gate.tr.concept', text)
            self.assertIn('planned', text)
            self.assertIn('concept.problem_definition', text)
        self.assertNotEqual(first, chinese)
        self.assertIn("| ID | 标题 | 阶段 | 状态 | 证据 | 评审记录 | 人类决定 |", chinese)
        self.assertIn("| ID | 类型 | 阶段 | 状态 | 所需交付件 | 评审记录 | 人类决定 |", chinese)
        self.assertNotIn("Human decision", chinese)

    def test_new_project_requires_render_before_governance_validation(self) -> None:
        for locale in ("en", "zh-CN"):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                self.assertEqual(self.invoke(["init", str(root), "--name", "demo", "--locale", locale])[0], 0)
                self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
                code, output, error = self.invoke(["validate", str(root), "--json"])
                self.assertEqual(code, 1, error)
                self.assertIn("governance_document_missing", {item["code"] for item in json.loads(output)["issues"]})
                before = {path: path.read_bytes() for path in (root / ".ipd").glob("*.yaml")}
                self.assertEqual(self.invoke(["render-dashboard", str(root)])[0], 0)
                self.assertEqual(before, {path: path.read_bytes() for path in before})
                code, output, error = self.invoke(["validate", str(root), "--json"])
                self.assertEqual(code, 0, output + error)

    def test_semantic_drift_has_stable_diagnostics(self) -> None:
        process, state = facts()
        canonical = render_governance_document(process, state)
        cases = {
            "governance_document_version_stale": canonical.replace(
                "framework_version: 0.5.1-beta",
                "framework_version: 0.5.0-beta",
                1,
            ),
            "governance_document_gate_ids_stale": canonical.replace(
                "- gate.tr.concept", "- gate.tr.legacy", 1
            ),
            "governance_document_gate_status_stale": canonical.replace(
                "gate.tr.concept: planned", "gate.tr.concept: approved", 1
            ),
            "governance_document_content_stale": canonical.replace(
                "Problem definition", "Outdated problem statement", 1
            ),
        }
        for expected_code, document in cases.items():
            with self.subTest(expected_code=expected_code):
                issues = governance_document_issues(document, process, state)
                self.assertEqual([item["code"] for item in issues], [expected_code])

    def test_render_projects_expired_claim_without_rewriting_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "expiry-view"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            subject = "concept.problem_definition"
            self.assertEqual(self.invoke(["claim", subject, "--project-root", str(root), "--actor", "fixture-agent"])[0], 0)
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            runtime["active_claims"][subject]["started_at"] = "1999-01-01T00:00:00Z"
            runtime["active_claims"][subject]["expires_at"] = "2000-01-01T00:00:00Z"
            write_state(runtime_path, runtime)
            before = {path: path.read_bytes() for path in (root / ".ipd").glob("*.yaml")}
            code, output, error = self.invoke(["render-dashboard", str(root)])
            self.assertEqual(code, 0, output + error)
            data = json.loads((root / ".ipd" / "dashboard" / "data" / "state.json").read_text(encoding="utf-8"))
            item = next(item for item in data["deliverables"] if item["id"] == subject)
            self.assertTrue(item["recoverable_claim"])
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            # Context records the expired lease. Pure rendering must still
            # explain its recoverable orphan without further authoritative writes.
            self.assertEqual(self.invoke(["context", str(root), "--json"])[0], 0)
            after_context = {path: path.read_bytes() for path in before}
            code, output, error = self.invoke(["render-dashboard", str(root)])
            self.assertEqual(code, 0, output + error)
            self.assertEqual(after_context, {path: path.read_bytes() for path in before})

    def test_render_dashboard_is_fact_preserving_and_refresh_rejects_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
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
            state_path = root / ".ipd" / "project_state.yaml"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()

            code, output, error = self.invoke(["render-dashboard", str(root)])
            self.assertEqual(code, 0, output + error)
            self.assertIn("without changing project state", output)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)
            manifest = json.loads(
                (root / ".ipd" / "dashboard" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            state = load_state(state_path)
            self.assertEqual(manifest["state_revision"], state["revision"])
            self.assertTrue((root / ".ipd" / "dashboard" / "governance.md").is_file())

            dashboard_before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in (root / ".ipd" / "dashboard").rglob("*")
                if path.is_file()
            }
            code, _, error = self.invoke(["refresh", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("render-dashboard", error)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)
            self.assertEqual(
                dashboard_before,
                {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in (root / ".ipd" / "dashboard").rglob("*")
                    if path.is_file()
                },
            )

    def test_formal_refresh_changes_state_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            state_path = root / ".ipd" / "project_state.yaml"
            before = load_state(state_path)
            code, output, error = self.invoke(["refresh", str(root)])
            self.assertEqual(code, 0, output + error)
            after = load_state(state_path)
            self.assertEqual(after["revision"], before["revision"] + 1)
            self.assertEqual(after["project"]["workflow_step"], "verify")

    def test_project_validate_detects_governance_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            governance = root / ".ipd" / "dashboard" / "governance.md"
            governance.write_text(
                governance.read_text(encoding="utf-8").replace(
                    "framework_version: 0.5.1-beta",
                    "framework_version: 0.5.0-beta",
                    1,
                ),
                encoding="utf-8",
            )
            code, output, error = self.invoke(["validate", str(root), "--json"])
            self.assertEqual(code, 1, error)
            report = json.loads(output)
            self.assertEqual(report["checks"]["governance_document"], "failed")
            self.assertIn(
                "governance_document_version_stale",
                {item["code"] for item in report["issues"]},
            )


if __name__ == "__main__":
    unittest.main()

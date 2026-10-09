from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "simulate_project_lifecycle.py"
)
SPEC = importlib.util.spec_from_file_location(
    "simulate_project_lifecycle", SCRIPT_PATH
)
assert SPEC and SPEC.loader
simulation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = simulation
SPEC.loader.exec_module(simulation)


class FullLifecycleSimulationTests(unittest.TestCase):
    def test_cli_accepts_each_supported_locale(self) -> None:
        parser = simulation._build_parser()
        self.assertEqual(parser.parse_args(["--locale", "en"]).locale, "en")
        self.assertEqual(parser.parse_args(["--locale", "zh-CN"]).locale, "zh-CN")

    def test_realistic_project_completes_without_missing_outputs_or_severe_issues(self) -> None:
        locale = os.environ.get("IPD_TEST_LOCALE", "zh-CN")
        report = simulation.run_simulation(locale=locale)

        self.assertTrue(report["passed"], report["severe_issues"])
        self.assertEqual(report["missing_outputs"], [])
        self.assertEqual(report["severe_issues"], [])
        self.assertTrue(report["cleanup_confirmed"])

        checks = report["checks"]
        self.assertEqual(checks["phases"], 6)
        self.assertEqual(checks["deliverables"], 22)
        self.assertEqual(checks["accepted_deliverables"], 22)
        self.assertEqual(checks["gates"], 12)
        self.assertEqual(checks["approved_gates"], 12)
        self.assertEqual(checks["current_phase"], "lifecycle")
        self.assertTrue(checks["lifecycle_complete"])
        self.assertEqual(checks["active_claims"], 0)

        self.assertEqual(checks["dashboard_files"], 16)
        self.assertEqual(checks["dashboard_locale"], locale)
        self.assertEqual(
            checks["dashboard_state_revision"], checks["state_revision"]
        )
        self.assertEqual(checks["reconciliation_status"], "passed")
        self.assertEqual(checks["repository_kind"], "git")
        self.assertEqual(checks["repository_branch"], "main")
        self.assertEqual(checks["capability_deliverables"], 3)
        self.assertEqual(checks["project_extension_deliverables"], 1)
        self.assertTrue(checks["binding_owner_role"])
        self.assertTrue(checks["binding_shared_evidence_role"])

        self.assertEqual(checks["blocked_iterations"], 1)
        self.assertEqual(checks["deliverable_rejections"], 1)
        self.assertEqual(checks["gate_rejections"], 1)
        self.assertEqual(checks["expired_claim_recoveries"], 1)
        self.assertGreaterEqual(checks["agent_approval_denials"], 2)
        self.assertEqual(checks["phase_advances"], 5)

        self.assertGreaterEqual(len(report["iterations"]), 39)
        for iteration in report["iterations"]:
            self.assertEqual(iteration["verification"], "passed")
            self.assertEqual(
                iteration["manifest_revision"], iteration["revision_after"]
            )
            self.assertGreater(
                iteration["revision_after"], iteration["revision_before"]
            )

        markdown = simulation.render_markdown(report)
        self.assertIn("**Result:** PASS", markdown)
        self.assertIn("Missing outputs: 0", markdown)
        self.assertIn("Severe issues: 0", markdown)


if __name__ == "__main__":
    unittest.main()

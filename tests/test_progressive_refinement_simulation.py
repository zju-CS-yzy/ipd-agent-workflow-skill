from __future__ import annotations

import unittest

from scripts.simulate_progressive_refinement import (
    INTERMEDIATE,
    LEAF_CAPTURE,
    LEAF_FUSION,
    SIBLING,
    run_simulation,
)


class ProgressiveRefinementSimulationTests(unittest.TestCase):
    def test_two_round_public_cli_simulation(self) -> None:
        report = run_simulation()

        self.assertTrue(report["passed"], report.get("severe_issues"))
        self.assertTrue(report["cleanup_confirmed"])
        self.assertEqual(report["severe_issues"], [])

        checks = report["checks"]
        self.assertEqual(checks["refinement_events"], 2)
        self.assertEqual(
            checks["root_leaf_closure"],
            [SIBLING, LEAF_CAPTURE, LEAF_FUSION],
        )
        self.assertEqual(
            checks["intermediate_leaf_closure"],
            [LEAF_CAPTURE, LEAF_FUSION],
        )
        self.assertEqual(checks["dashboard_files"], 16)
        self.assertEqual(checks["concept_gate_epoch"], 2)
        self.assertTrue(checks["history_preserved"])
        self.assertTrue(checks["owner_preflight_exercised"])
        self.assertTrue(checks["idempotent_replay"])
        self.assertEqual(checks["fail_closed_preflight_cases"], 4)
        self.assertTrue(checks["plan_conflict_rejected"])
        self.assertTrue(checks["verification_invalidated"])
        self.assertTrue(checks["input_drift_rejected"])
        self.assertTrue(checks["runtime_replay_tamper_rejected"])
        self.assertTrue(checks["runtime_result_fingerprint_tamper_rejected"])
        self.assertTrue(checks["runtime_invalidated_gates_tamper_rejected"])
        self.assertTrue(checks["duplicate_runtime_event_rejected"])
        self.assertTrue(checks["due_requirement_removal_rejected"])
        self.assertTrue(checks["downstream_claim_blocked_until_refined"])

        labels = [item["label"] for item in report["iterations"]]
        self.assertIn("root-accepted-and-due", labels)
        self.assertIn("intermediate-accepted-and-due", labels)
        self.assertIn("second-refinement-owner-ready", labels)
        self.assertGreaterEqual(len(report["commands"]), 25)


if __name__ == "__main__":
    unittest.main()

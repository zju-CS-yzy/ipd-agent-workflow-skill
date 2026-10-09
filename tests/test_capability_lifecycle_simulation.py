from __future__ import annotations

import unittest

from scripts.simulate_capability_lifecycle import (
    FINAL_CONCRETE_DELIVERABLES,
    FINAL_DELIVERABLES,
    REFINEMENT_CHILDREN,
    run_simulation,
)


class CapabilityLifecycleSimulationTests(unittest.TestCase):
    def test_all_v05_capabilities_complete_one_refined_lifecycle(self) -> None:
        report = run_simulation()

        self.assertTrue(report["passed"], report.get("severe_issues"))
        self.assertEqual(report["severe_issues"], [])
        self.assertEqual(report["missing_outputs"], [])
        self.assertTrue(report["cleanup_confirmed"])

        checks = report["checks"]
        self.assertEqual(checks["phases"], 6)
        self.assertEqual(checks["capability_patterns"], 3)
        self.assertEqual(checks["initial_deliverables"], 20)
        self.assertEqual(checks["final_deliverables"], FINAL_DELIVERABLES)
        self.assertEqual(
            checks["concrete_deliverables"], FINAL_CONCRETE_DELIVERABLES
        )
        self.assertEqual(
            checks["accepted_concrete_deliverables"],
            FINAL_CONCRETE_DELIVERABLES,
        )
        self.assertEqual(checks["approved_gates"], 12)
        self.assertEqual(checks["current_phase"], "lifecycle")
        self.assertEqual(checks["refinement_events"], 1)
        self.assertEqual(checks["refinement_children"], list(REFINEMENT_CHILDREN))
        self.assertEqual(checks["refinement_preview_missing_owners"], 2)
        self.assertTrue(checks["refined_binding_baseline_adopted"])
        self.assertTrue(checks["history_preserved"])
        self.assertEqual(
            checks["actionability"],
            {
                "waiting_items": True,
                "explicit_blockers": True,
                "governance_blockers": True,
            },
        )
        self.assertEqual(checks["dashboard_files"], 16)
        self.assertEqual(checks["final_verify"], "passed")
        self.assertEqual(checks["active_claims"], 0)
        self.assertEqual(checks["phase_advances"], 5)
        self.assertGreaterEqual(len(report["iterations"]), 35)
        self.assertGreaterEqual(len(report["commands"]), 150)


if __name__ == "__main__":
    unittest.main()

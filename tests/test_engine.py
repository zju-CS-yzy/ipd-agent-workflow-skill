from __future__ import annotations

import unittest

from ipdctl.engine import (
    TransitionError,
    approve_gate,
    record_gate_review,
    set_deliverable_status,
    set_gate_ready,
    transition_workflow,
)
from ipdctl.state import create_initial_state


class EngineTests(unittest.TestCase):
    def test_workflow_advances_in_one_canonical_order(self) -> None:
        state = create_initial_state("demo")
        state = transition_workflow(state, "claim")
        state = transition_workflow(state, "work")
        self.assertEqual(state["project"]["workflow_step"], "work")
        self.assertEqual(state["revision"], 2)
        with self.assertRaises(TransitionError):
            transition_workflow(state, "verify")

    def test_deliverable_transition_requires_evidence(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "spec",
                "title": "Specification",
                "status": "planned",
                "depends_on": [],
                "evidence": [],
            }
        ]
        state = set_deliverable_status(state, "spec", "in_progress")
        state = set_deliverable_status(state, "spec", "ready_for_review")
        with self.assertRaises(TransitionError):
            set_deliverable_status(state, "spec", "accepted")
        state = set_deliverable_status(
            state, "spec", "accepted", evidence=["docs/specification.md"]
        )
        self.assertEqual(state["deliverables"][0]["status"], "accepted")

    def test_agent_review_cannot_finalize_gate(self) -> None:
        state = create_initial_state("demo")
        state["gates"] = [
            {
                "id": "dcp-1",
                "title": "Concept decision",
                "kind": "DCP",
                "status": "planned",
                "required_deliverables": [],
                "reviews": [],
            }
        ]
        state = set_gate_ready(state, "dcp-1")
        state = record_gate_review(
            state,
            "dcp-1",
            reviewer="review-agent",
            reviewer_type="agent",
            authorized=True,
            decision="approve",
            evidence="reviews/dcp-1-agent.md",
        )
        with self.assertRaises(TransitionError):
            approve_gate(state, "dcp-1")

        state = record_gate_review(
            state,
            "dcp-1",
            reviewer="product-director",
            reviewer_type="human",
            authorized=True,
            decision="approve",
            evidence="reviews/dcp-1-human.md",
        )
        state = approve_gate(state, "dcp-1")
        self.assertEqual(state["gates"][0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()

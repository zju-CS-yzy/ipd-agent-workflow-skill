from __future__ import annotations

import unittest

from ipdctl.engine import (
    TransitionError,
    approve_deliverable,
    approve_gate,
    claim_deliverable,
    record_deliverable_review,
    record_gate_review,
    reject_deliverable,
    reject_gate,
    set_deliverable_status,
    set_gate_ready,
    start_deliverable_review,
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

        for step in ("close", "review", "refresh", "verify", "context"):
            state = transition_workflow(state, step)
        self.assertEqual(state["project"]["workflow_step"], "context")

    def test_deliverable_transition_requires_evidence(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "spec",
                "title": "Specification",
                "status": "planned",
                "review_required": True,
                "depends_on": [],
                "evidence": [],
                "reviews": [],
            }
        ]
        state = set_deliverable_status(state, "spec", "in_progress")
        state = set_deliverable_status(state, "spec", "ready_for_review")
        state = start_deliverable_review(state, "spec")
        with self.assertRaises(TransitionError):
            set_deliverable_status(state, "spec", "accepted")
        state = record_deliverable_review(
            state,
            "spec",
            reviewer="design-authority",
            reviewer_type="human",
            authorized=True,
            decision="approve",
            evidence="reviews/specification.md",
        )
        state = set_deliverable_status(
            state, "spec", "accepted", evidence=["docs/specification.md"]
        )
        self.assertEqual(state["deliverables"][0]["status"], "accepted")

    def test_claim_cannot_bypass_the_current_product_phase(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "plan.spec",
                "title": "Plan specification",
                "phase": "plan",
                "status": "planned",
                "review_required": True,
                "depends_on": [],
                "evidence": [],
                "reviews": [],
            }
        ]
        with self.assertRaises(TransitionError):
            claim_deliverable(state, "plan.spec")

    def test_claim_requires_accepted_predecessors(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "concept.input",
                "title": "Input",
                "phase": "concept",
                "status": "planned",
                "review_required": True,
                "depends_on": [],
                "evidence": [],
                "reviews": [],
            },
            {
                "id": "concept.output",
                "title": "Output",
                "phase": "concept",
                "status": "planned",
                "review_required": True,
                "depends_on": ["concept.input"],
                "evidence": [],
                "reviews": [],
            },
        ]
        with self.assertRaises(TransitionError):
            claim_deliverable(state, "concept.output")

    def test_agent_cannot_approve_deliverable_and_rejected_work_can_be_reclaimed(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "spec",
                "title": "Specification",
                "status": "in_review",
                "review_required": True,
                "depends_on": [],
                "evidence": ["docs/specification.md"],
                "reviews": [],
            }
        ]
        with self.assertRaises(TransitionError):
            approve_deliverable(
                state,
                "spec",
                reviewer="review-agent",
                reviewer_type="agent",
                authorized=True,
                evidence="reviews/agent.md",
            )
        state = reject_deliverable(
            state,
            "spec",
            reviewer="design-authority",
            reviewer_type="human",
            authorized=True,
            evidence="reviews/rejected.md",
        )
        self.assertEqual(state["deliverables"][0]["status"], "rejected")
        state = claim_deliverable(state, "spec")
        self.assertEqual(state["deliverables"][0]["status"], "in_progress")

        state = set_deliverable_status(
            state, "spec", "ready_for_review", evidence=["docs/specification-v2.md"]
        )
        state = start_deliverable_review(state, "spec")
        state = approve_deliverable(
            state,
            "spec",
            reviewer="design-authority",
            reviewer_type="human",
            authorized=True,
            evidence="reviews/approved-v2.md",
        )
        self.assertEqual(state["deliverables"][0]["status"], "accepted")
        self.assertEqual(len(state["deliverables"][0]["reviews"]), 2)

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
        self.assertEqual(state["gates"][0]["approval"], "product-director")

    def test_rejected_gate_can_be_reviewed_and_approved_in_a_later_iteration(self) -> None:
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
            reviewer="product-director",
            reviewer_type="human",
            authorized=True,
            decision="reject",
            evidence="reviews/dcp-1-rejected.md",
        )
        state = reject_gate(state, "dcp-1")
        state = set_gate_ready(state, "dcp-1")
        state = record_gate_review(
            state,
            "dcp-1",
            reviewer="product-director",
            reviewer_type="human",
            authorized=True,
            decision="approve",
            evidence="reviews/dcp-1-approved.md",
        )
        state = approve_gate(state, "dcp-1")
        self.assertEqual(state["gates"][0]["status"], "approved")
        self.assertEqual(len(state["gates"][0]["reviews"]), 2)

    def test_gate_ready_clears_process_contract_staleness_blockers(self) -> None:
        state = create_initial_state("demo")
        state["gates"] = [
            {
                "id": "dcp-1",
                "title": "Concept decision",
                "kind": "DCP",
                "status": "planned",
                "required_deliverables": [],
                "reviews": [],
                "blockers": [
                    "GATE_REQUIREMENTS_CHANGED",
                    "DEPENDENCY_CONTRACT_CHANGED",
                    "EXTERNAL_DECISION_PENDING",
                ],
                "stale": True,
                "stale_reason": "DEPENDENCY_CONTRACT_CHANGED",
            }
        ]

        state = set_gate_ready(state, "dcp-1")

        gate = state["gates"][0]
        self.assertEqual(gate["status"], "ready")
        self.assertFalse(gate["stale"])
        self.assertIsNone(gate["stale_reason"])
        self.assertEqual(gate["blockers"], ["EXTERNAL_DECISION_PENDING"])


if __name__ == "__main__":
    unittest.main()

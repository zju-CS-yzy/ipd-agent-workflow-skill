from __future__ import annotations

import unittest

from ipdctl.state import create_initial_state
from ipdctl.validation import validate_state


class ValidationTests(unittest.TestCase):
    def test_initial_state_is_valid(self) -> None:
        self.assertEqual(validate_state(create_initial_state("demo")), [])

    def test_dependency_cycle_and_unknown_dependency_are_rejected(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "a",
                "title": "A",
                "status": "planned",
                "depends_on": ["b"],
                "evidence": [],
            },
            {
                "id": "b",
                "title": "B",
                "status": "planned",
                "depends_on": ["a", "missing"],
                "evidence": [],
            },
        ]
        messages = [str(issue) for issue in validate_state(state)]
        self.assertTrue(any("dependency cycle detected" in item for item in messages))
        self.assertTrue(any("unknown deliverable 'missing'" in item for item in messages))

    def test_accepted_deliverable_requires_evidence_and_closed_dependencies(self) -> None:
        state = create_initial_state("demo")
        state["deliverables"] = [
            {
                "id": "input",
                "title": "Input",
                "status": "in_progress",
                "depends_on": [],
                "evidence": [],
            },
            {
                "id": "output",
                "title": "Output",
                "status": "accepted",
                "depends_on": ["input"],
                "evidence": [],
            },
        ]
        messages = [str(issue) for issue in validate_state(state)]
        self.assertTrue(any("requires evidence" in item for item in messages))
        self.assertTrue(any("dependencies must be accepted" in item for item in messages))

    def test_supported_claim_requires_evidence(self) -> None:
        state = create_initial_state("demo")
        state["claims"] = [
            {
                "id": "claim-1",
                "statement": "The design meets its target.",
                "status": "supported",
                "evidence": [],
            }
        ]
        self.assertTrue(
            any("supported claim requires evidence" in str(issue) for issue in validate_state(state))
        )

    def test_approved_gate_requires_authorized_human(self) -> None:
        state = create_initial_state("demo")
        state["gates"] = [
            {
                "id": "tr-1",
                "title": "Architecture review",
                "kind": "TR",
                "status": "approved",
                "required_deliverables": [],
                "reviews": [
                    {
                        "reviewer": "review-agent",
                        "reviewer_type": "agent",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": "reviews/tr-1.md",
                    }
                ],
            }
        ]
        self.assertTrue(
            any("authorized human approval" in str(issue) for issue in validate_state(state))
        )

    def test_traceability_must_reference_known_entities(self) -> None:
        state = create_initial_state("demo")
        state["claims"] = [
            {
                "id": "claim-1",
                "statement": "A claim",
                "status": "open",
                "evidence": [],
            }
        ]
        state["traceability"] = [
            {"source": "claim-1", "target": "unknown", "relation": "supports"}
        ]
        self.assertTrue(
            any("references unknown entity 'unknown'" in str(issue) for issue in validate_state(state))
        )


if __name__ == "__main__":
    unittest.main()

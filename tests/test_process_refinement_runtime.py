from __future__ import annotations

import unittest

from ipdctl.eligibility import (
    deliverable_refinement_status,
    normalize_eligibility,
    requirements_fingerprint,
)
from ipdctl.engine import (
    TransitionError,
    approve_gate,
    claim_deliverable,
    record_gate_review,
    set_gate_ready,
)
from ipdctl.runtime import (
    RuntimeError,
    create_runtime_state,
    record_process_refinement,
    validate_runtime,
)
from ipdctl.state import create_initial_state
from ipdctl.validation import validate_state


def deliverable(
    identifier: str,
    *,
    status: str = "planned",
    phase: str = "concept",
    **extra: object,
) -> dict[str, object]:
    record: dict[str, object] = {
        "id": identifier,
        "title": identifier,
        "phase": phase,
        "status": status,
        "review_required": True,
        "depends_on": [],
        "evidence": [],
        "reviews": [],
    }
    if status == "accepted":
        record["evidence"] = [f"evidence/{identifier}.md"]
        record["reviews"] = [
            {
                "reviewer": "design-authority",
                "reviewer_type": "human",
                "authorized": True,
                "decision": "approve",
                "evidence": f"reviews/{identifier}.md",
            }
        ]
    record.update(extra)
    return record


class ProcessRefinementStateTests(unittest.TestCase):
    def state(self) -> dict:
        return create_initial_state("refinement")

    def test_refines_is_same_phase_acyclic_and_not_an_execution_dependency(self) -> None:
        state = self.state()
        state["deliverables"] = [
            deliverable(
                "concept.parent",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger={
                    "all_of": [
                        {"subject": "concept.parent", "condition": "accepted"}
                    ]
                },
            ),
            deliverable("concept.child", refines="concept.parent"),
        ]
        state["traceability"] = [
            {
                "source": "concept.child",
                "target": "concept.parent",
                "relation": "refines",
            }
        ]
        self.assertEqual(validate_state(state), [])
        claimed = claim_deliverable(state, "concept.child")
        self.assertEqual(claimed["deliverables"][1]["status"], "in_progress")

        state["deliverables"][1]["phase"] = "plan"
        messages = [str(issue) for issue in validate_state(state)]
        self.assertTrue(any("same phase" in item for item in messages), messages)

        state["deliverables"][1]["phase"] = "concept"
        state["deliverables"][0]["refines"] = "concept.child"
        messages = [str(issue) for issue in validate_state(state)]
        self.assertTrue(any("refinement cycle" in item for item in messages), messages)

    def test_refinement_status_and_claim_block_are_shared(self) -> None:
        state = self.state()
        state["deliverables"] = [
            deliverable("concept.input"),
            deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger={
                    "all_of": [
                        {"subject": "concept.input", "condition": "accepted"}
                    ]
                },
                requires_artifact_owner=False,
            ),
        ]
        pending = deliverable_refinement_status(state, "concept.architecture")
        self.assertEqual(pending["refinement_status"], "pending")
        with self.assertRaisesRegex(TransitionError, "REFINEMENT_REQUIRED"):
            claim_deliverable(state, "concept.architecture")

        state["deliverables"][0] = deliverable("concept.input", status="accepted")
        due = deliverable_refinement_status(state, "concept.architecture")
        self.assertEqual(due["refinement_status"], "due")
        normalized = normalize_eligibility(
            {
                "status": "passed",
                "eligible": True,
                "issues": [],
                "paths": {},
                "deliverables": {},
            },
            state,
        )
        row = normalized["deliverables"]["concept.architecture"]
        self.assertFalse(row["eligible"])
        self.assertIn("REFINEMENT_REQUIRED", row["issue_codes"])

        state["deliverables"].append(
            deliverable("concept.mobility", refines="concept.architecture")
        )
        resolved = deliverable_refinement_status(state, "concept.architecture")
        self.assertEqual(resolved["refinement_status"], "resolved")
        self.assertEqual(resolved["leaf_deliverables"], ["concept.mobility"])

    def test_downstream_claim_waits_for_dependency_refinement(self) -> None:
        state = self.state()
        state["deliverables"] = [
            deliverable(
                "concept.architecture",
                status="accepted",
                definition_state="concrete",
                refinement_required=True,
                refinement_trigger={
                    "all_of": [
                        {
                            "subject": "concept.architecture",
                            "condition": "accepted",
                        }
                    ]
                },
            ),
            deliverable(
                "concept.integration",
                depends_on=["concept.architecture"],
            ),
        ]
        with self.assertRaisesRegex(
            TransitionError, "REFINEMENT_DEPENDENCY_REQUIRED"
        ):
            claim_deliverable(state, "concept.integration")

        normalized = normalize_eligibility(
            {
                "status": "passed",
                "eligible": True,
                "issues": [],
                "paths": {},
                "deliverables": {},
            },
            state,
        )
        row = normalized["deliverables"]["concept.integration"]
        self.assertFalse(row["eligible"])
        self.assertIn("REFINEMENT_DEPENDENCY_REQUIRED", row["issue_codes"])

        state["deliverables"][0]["definition_state"] = "abstract"
        state["deliverables"].append(
            deliverable(
                "concept.architecture_leaf",
                status="accepted",
                refines="concept.architecture",
            )
        )
        state["deliverables"][1]["depends_on"] = ["concept.architecture_leaf"]
        claimed = claim_deliverable(state, "concept.integration")
        self.assertEqual(claimed["deliverables"][1]["status"], "in_progress")

    def test_gate_uses_leaf_closure_and_only_current_review_epoch(self) -> None:
        state = self.state()
        state["deliverables"] = [
            deliverable(
                "concept.architecture",
                status="accepted",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger={
                    "all_of": [
                        {
                            "subject": "concept.architecture",
                            "condition": "accepted",
                        }
                    ]
                },
            ),
            deliverable("concept.mobility", refines="concept.architecture"),
        ]
        state["gates"] = [
            {
                "id": "tr-concept",
                "title": "Concept review",
                "kind": "TR",
                "phase": "concept",
                "status": "planned",
                "required_deliverables": ["concept.architecture"],
                "reviews": [
                    {
                        "reviewer": "old-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": "reviews/old.md",
                        "gate_epoch": 0,
                    }
                ],
                "review_epoch": 1,
                "stale": True,
                "stale_reason": "The concrete leaf closure changed.",
            }
        ]
        with self.assertRaisesRegex(TransitionError, "not accepted"):
            set_gate_ready(state, "tr-concept")

        state["deliverables"][1] = deliverable(
            "concept.mobility", status="accepted", refines="concept.architecture"
        )
        ready = set_gate_ready(state, "tr-concept")
        gate = ready["gates"][0]
        self.assertFalse(gate["stale"])
        self.assertIsNone(gate["stale_reason"])
        self.assertEqual(
            gate["requirements_fingerprint"],
            requirements_fingerprint(["concept.architecture"], ready),
        )
        with self.assertRaisesRegex(TransitionError, "review epoch 1"):
            approve_gate(ready, "tr-concept")

        reviewed = record_gate_review(
            ready,
            "tr-concept",
            reviewer="current-authority",
            reviewer_type="human",
            authorized=True,
            decision="approve",
            evidence="reviews/current.md",
            gate_epoch=1,
        )
        approved = approve_gate(reviewed, "tr-concept")
        self.assertEqual(approved["gates"][0]["status"], "approved")
        self.assertEqual(approved["gates"][0]["approval"], "current-authority")

    def test_gate_fails_closed_while_refinement_is_due(self) -> None:
        state = self.state()
        state["deliverables"] = [
            deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger={
                    "all_of": [
                        {
                            "subject": "concept.architecture",
                            "condition": "accepted",
                        }
                    ]
                },
            )
        ]
        state["gates"] = [
            {
                "id": "tr-concept",
                "title": "Concept review",
                "kind": "TR",
                "status": "planned",
                "required_deliverables": ["concept.architecture"],
                "reviews": [],
            }
        ]
        with self.assertRaisesRegex(TransitionError, "REFINEMENT_REQUIRED"):
            set_gate_ready(state, "tr-concept")


class ProcessRefinementRuntimeEventTests(unittest.TestCase):
    @staticmethod
    def event(**overrides: object) -> dict[str, object]:
        event: dict[str, object] = {
            "action": "process_refinement_applied",
            "at": "2026-10-05T00:00:00Z",
            "plan_id": "refinement.architecture.v1",
            "plan_digest": "sha256:" + "1" * 64,
            "base_process_fingerprint": "sha256:" + "2" * 64,
            "result_process_fingerprint": "sha256:" + "3" * 64,
            "actor": "project-owner",
            "actor_type": "human",
            "authorized": True,
            "reason": "Approve the reviewed subsystem decomposition.",
            "state_revision": 12,
            "root": "concept.architecture",
            "children": ["concept.mobility", "concept.perception"],
            "invalidated_gates": ["tr-concept"],
        }
        event.update(overrides)
        return event

    def test_event_is_strict_authorized_and_idempotent(self) -> None:
        runtime = create_runtime_state()
        updated, changed = record_process_refinement(runtime, self.event())
        self.assertTrue(changed)
        self.assertEqual(validate_runtime(updated), [])
        replayed, changed = record_process_refinement(updated, self.event())
        self.assertFalse(changed)
        self.assertIs(replayed, updated)
        self.assertEqual(replayed["revision"], 1)

        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            record_process_refinement(
                updated, self.event(plan_digest="sha256:" + "4" * 64)
            )
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            record_process_refinement(
                updated,
                self.event(result_process_fingerprint="sha256:" + "5" * 64),
            )
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            record_process_refinement(
                updated, self.event(invalidated_gates=["gate.dcp.concept"])
            )

    def test_event_rejects_non_human_or_unknown_fields(self) -> None:
        runtime = create_runtime_state()
        invalid = self.event(actor_type="agent")
        with self.assertRaisesRegex(RuntimeError, "actor_type"):
            record_process_refinement(runtime, invalid)
        invalid = self.event(unexpected=True)
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            record_process_refinement(runtime, invalid)
        invalid = self.event(result_process_fingerprint="sha256:not-a-digest")
        with self.assertRaisesRegex(RuntimeError, "64 lowercase hex"):
            record_process_refinement(runtime, invalid)


if __name__ == "__main__":
    unittest.main()

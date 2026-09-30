from __future__ import annotations

import unittest
from copy import deepcopy

from ipdctl.engine import TransitionError
from ipdctl.lifecycle import advance_phase, phase_completion
from ipdctl.project import sync_state_with_process
from ipdctl.state import create_initial_state
from ipdctl.tailoring import tailor_profile


def _process() -> dict:
    return {
        "phases": [
            {"id": "concept", "sequence": 1},
            {"id": "plan", "sequence": 2},
        ],
        "technical_reviews": [
            {"id": "tr.concept", "phase": "concept"},
            {"id": "tr.plan", "phase": "plan"},
        ],
        "decision_checkpoints": [
            {"id": "dcp.concept", "phase": "concept"},
            {"id": "dcp.plan", "phase": "plan"},
        ],
        "gates": [
            {"id": "gate.tr.concept", "phase": "concept"},
            {"id": "gate.dcp.concept", "phase": "concept"},
            {"id": "gate.tr.plan", "phase": "plan"},
            {"id": "gate.dcp.plan", "phase": "plan"},
        ],
    }


def _state() -> dict:
    state = create_initial_state("demo")
    state["project"].update(
        {
            "current_tr": "tr.concept",
            "current_dcp": "dcp.concept",
            "current_gate": "gate.tr.concept",
        }
    )
    state["gates"] = [
        {
            "id": identifier,
            "title": identifier,
            "kind": "TR" if ".tr." in identifier else "DCP",
            "status": status,
            "phase": phase,
            "required_deliverables": [],
            "reviews": (
                [
                    {
                        "reviewer": "authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": f"reviews/{identifier}.md",
                    }
                ]
                if status == "approved"
                else []
            ),
        }
        for identifier, phase, status in (
            ("gate.tr.concept", "concept", "approved"),
            ("gate.dcp.concept", "concept", "approved"),
            ("gate.tr.plan", "plan", "planned"),
            ("gate.dcp.plan", "plan", "planned"),
        )
    ]
    return state


class LifecycleTests(unittest.TestCase):
    def test_state_sync_keeps_only_canonical_gates_and_migrates_legacy_checkpoint_history(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "demo",
                "task_types": ["software"],
            }
        )
        state = sync_state_with_process(create_initial_state("demo"), process)
        self.assertEqual(len(state["gates"]), 12)
        self.assertEqual({item["kind"] for item in state["gates"]}, {"TR", "DCP"})

        canonical = next(item for item in state["gates"] if item["id"] == "gate.tr.concept")
        legacy = deepcopy(canonical)
        legacy.update(
            {
                "id": "tr.concept",
                "status": "rejected",
                "reviews": [
                    {
                        "reviewer": "authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "reject",
                        "evidence": "reviews/legacy-rejection.md",
                    }
                ],
            }
        )
        state["gates"].append(legacy)
        migrated = sync_state_with_process(state, process)
        self.assertEqual(len(migrated["gates"]), 12)
        self.assertNotIn("tr.concept", {item["id"] for item in migrated["gates"]})
        canonical = next(
            item for item in migrated["gates"] if item["id"] == "gate.tr.concept"
        )
        self.assertEqual(canonical["status"], "rejected")
        self.assertEqual(canonical["reviews"][0]["decision"], "reject")

    def test_advance_phase_requires_all_current_phase_gates(self) -> None:
        state = _state()
        state["gates"][1]["status"] = "ready"
        state["gates"][1]["reviews"] = []
        completion = phase_completion(state, _process())
        self.assertFalse(completion["complete"])
        self.assertEqual(completion["pending_gates"], ["gate.dcp.concept"])
        with self.assertRaises(TransitionError):
            advance_phase(
                state, _process(), verified_state_revision=state["revision"]
            )

    def test_advance_phase_requires_new_phase_refresh_and_updates_checkpoints(self) -> None:
        state = _state()
        state["project"]["workflow_step"] = "verify"
        with self.assertRaises(TransitionError):
            advance_phase(state, _process())
        updated = advance_phase(
            state, _process(), verified_state_revision=state["revision"]
        )
        self.assertEqual(updated["project"]["phase"], "plan")
        self.assertEqual(updated["project"]["workflow_step"], "refresh")
        self.assertEqual(updated["project"]["current_tr"], "tr.plan")
        self.assertEqual(updated["project"]["current_dcp"], "dcp.plan")
        self.assertEqual(updated["project"]["current_gate"], "gate.tr.plan")

    def test_final_phase_completion_is_reported_but_cannot_advance(self) -> None:
        state = _state()
        state["project"].update(
            {
                "phase": "plan",
                "current_tr": "tr.plan",
                "current_dcp": "dcp.plan",
                "current_gate": "gate.tr.plan",
            }
        )
        for gate in state["gates"]:
            if gate["phase"] == "plan":
                gate["status"] = "approved"
                gate["reviews"] = [
                    {
                        "reviewer": "authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": f"reviews/{gate['id']}.md",
                    }
                ]
        self.assertTrue(phase_completion(state, _process())["complete"])
        with self.assertRaises(TransitionError):
            advance_phase(
                state, _process(), verified_state_revision=state["revision"]
            )


if __name__ == "__main__":
    unittest.main()

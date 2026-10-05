from __future__ import annotations

import unittest
from copy import deepcopy

from ipdctl.project import (
    ProjectError,
    project_traceability_projection,
    sync_state_with_process,
)
from ipdctl.state import create_initial_state
from ipdctl.tailoring import tailor_profile


def _process() -> dict:
    process = tailor_profile(
        {
            "schema_version": "1.0",
            "project_name": "traceability-demo",
            "task_types": ["software"],
        }
    )
    process.setdefault("gate_migrations", [])
    return process


def _claim(identifier: str) -> dict:
    return {
        "id": identifier,
        "statement": f"Evidence supports {identifier}.",
        "status": "open",
        "evidence": [],
    }


def _edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"source": source, "target": target, "relation": relation}


def _deliverable(identifier: str) -> dict:
    return {
        "id": identifier,
        "title": identifier,
        "phase": "concept",
        "activity_id": "concept.scope",
        "review_required": True,
        "depends_on": [],
        "provenance": {"layer": "project", "source_id": "traceability-test"},
        "maturity": "defined",
    }


class RetailorTraceabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.process = _process()
        self.state = sync_state_with_process(
            create_initial_state("traceability-demo", ["software"]), self.process
        )

    def test_claim_links_survive_while_process_edges_remain_authoritative(self) -> None:
        self.state["claims"] = [_claim("claim.alpha"), _claim("claim.beta")]
        claim_links = [
            _edge("claim.alpha", "concept.problem_definition", "supports"),
            _edge("plan.integrated_plan", "claim.alpha", "verifies"),
            _edge("claim.alpha", "claim.beta", "supports"),
            _edge("claim.beta", "gate.tr.concept", "verifies"),
        ]
        stale_state_only_edge = _edge(
            "concept.problem_definition", "gate.tr.concept", "supports"
        )
        self.state["traceability"].extend(claim_links + [stale_state_only_edge])

        projected, impact = project_traceability_projection(self.state, self.process)
        for link in claim_links:
            self.assertIn(link, projected)
        self.assertNotIn(stale_state_only_edge, projected)
        self.assertEqual(impact["blocked"], [])
        self.assertIn(stale_state_only_edge, impact["removed"])

        updated = sync_state_with_process(self.state, self.process)
        for link in claim_links:
            self.assertIn(link, updated["traceability"])
        self.assertNotIn(stale_state_only_edge, updated["traceability"])
        revision = updated["revision"]
        replayed = sync_state_with_process(updated, self.process)
        self.assertEqual(replayed, updated)
        self.assertEqual(replayed["revision"], revision)

    def test_gate_migration_rejects_conflicting_target_history(self) -> None:
        canonical = next(
            gate for gate in self.state["gates"] if gate["id"] == "gate.tr.concept"
        )
        canonical.update(
            {
                "status": "approved",
                "approval": "canonical-authority",
                "reviews": [
                    {
                        "reviewer": "canonical-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": "reviews/canonical-approval.md",
                    }
                ],
            }
        )
        legacy = deepcopy(canonical)
        legacy.update(
            {
                "id": "legacy.concept_gate",
                "status": "rejected",
                "approval": None,
                "reviews": [
                    {
                        "reviewer": "legacy-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "reject",
                        "evidence": "reviews/legacy-rejection.md",
                    }
                ],
            }
        )
        self.state["gates"].append(legacy)
        self.process["gate_migrations"] = [
            {
                "from": "legacy.concept_gate",
                "to": "gate.tr.concept",
                "reason": "Attempt to merge conflicting decisions.",
                "preserve_history": True,
            }
        ]

        with self.assertRaisesRegex(
            ProjectError, "conflicting historical status or approval"
        ):
            sync_state_with_process(
                self.state, self.process, apply_migrations=True
            )

        legacy["status"] = "approved"
        legacy["approval"] = "different-authority"
        legacy["reviews"] = [
            {
                "reviewer": "different-authority",
                "reviewer_type": "human",
                "authorized": True,
                "decision": "approve",
                "evidence": "reviews/different-approval.md",
            }
        ]
        with self.assertRaisesRegex(
            ProjectError, "conflicting historical status or approval"
        ):
            sync_state_with_process(
                self.state, self.process, apply_migrations=True
            )
    def test_explicit_gate_migration_redirects_claim_endpoint(self) -> None:
        legacy = deepcopy(
            next(gate for gate in self.state["gates"] if gate["id"] == "gate.tr.concept")
        )
        legacy.update(
            {
                "id": "legacy.concept_gate",
                "status": "rejected",
                "reviews": [
                    {
                        "reviewer": "gate-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "reject",
                        "evidence": "reviews/legacy-gate-rejection.md",
                    }
                ],
            }
        )
        self.state["gates"].append(legacy)
        self.state["claims"] = [_claim("claim.gate")]
        old_link = _edge("claim.gate", "legacy.concept_gate", "verifies")
        new_link = _edge("claim.gate", "gate.tr.concept", "verifies")
        self.state["traceability"].append(old_link)
        self.process["gate_migrations"] = [
            {
                "from": "legacy.concept_gate",
                "to": "gate.tr.concept",
                "reason": "Map the reviewed legacy checkpoint to canonical TR.",
                "preserve_history": True,
            }
        ]

        projected, impact = project_traceability_projection(self.state, self.process)
        self.assertIn(new_link, projected)
        self.assertNotIn(old_link, projected)
        self.assertEqual(impact["blocked"], [])
        self.assertEqual(
            impact["redirected"],
            [{"before": old_link, "after": new_link, "fields": ["target"]}],
        )

        with self.assertRaisesRegex(ProjectError, "explicit --apply-migrations"):
            sync_state_with_process(self.state, self.process)
        updated = sync_state_with_process(
            self.state, self.process, apply_migrations=True
        )
        self.assertIn(new_link, updated["traceability"])
        self.assertNotIn(old_link, updated["traceability"])
        self.assertNotIn(
            "legacy.concept_gate", {gate["id"] for gate in updated["gates"]}
        )
        canonical = next(
            gate for gate in updated["gates"] if gate["id"] == "gate.tr.concept"
        )
        self.assertEqual(canonical["status"], "rejected")
        self.assertEqual(canonical["reviews"][0]["decision"], "reject")
        replayed = sync_state_with_process(updated, self.process)
        self.assertEqual(replayed, updated)

    def test_unknown_gate_target_blocks_projection_and_sync(self) -> None:
        self.state["claims"] = [_claim("claim.gate")]
        self.state["traceability"].append(
            _edge("claim.gate", "gate.tr.concept", "verifies")
        )
        self.process["gate_migrations"] = [
            {
                "from": "legacy.concept_gate",
                "to": "gate.unknown",
                "reason": "Invalid target used to prove fail-closed behavior.",
                "preserve_history": True,
            }
        ]

        _, impact = project_traceability_projection(self.state, self.process)
        self.assertEqual(impact["blocked"][0]["kind"], "unknown_gate_migration_target")
        with self.assertRaisesRegex(ProjectError, "invalid or ambiguous gate migration"):
            sync_state_with_process(self.state, self.process)

    def test_project_gate_does_not_duplicate_implicit_checkpoint_history(self) -> None:
        legacy = deepcopy(
            next(gate for gate in self.state["gates"] if gate["id"] == "gate.tr.concept")
        )
        legacy.update(
            {
                "id": "tr.concept",
                "status": "rejected",
                "reviews": [
                    {
                        "reviewer": "legacy-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "reject",
                        "evidence": "reviews/legacy-tr.md",
                    }
                ],
            }
        )
        self.state["gates"] = [
            gate for gate in self.state["gates"] if gate["id"] != "gate.tr.concept"
        ] + [legacy]
        self.process["gates"].append(
            {
                **deepcopy(
                    next(
                        gate
                        for gate in self.process["gates"]
                        if gate["id"] == "gate.tr.concept"
                    )
                ),
                "id": "gate.concept.project_readiness",
                "title": "Project readiness",
                "kind": "Gate",
            }
        )

        updated = sync_state_with_process(self.state, self.process)

        canonical = next(
            gate for gate in updated["gates"] if gate["id"] == "gate.tr.concept"
        )
        project_gate = next(
            gate
            for gate in updated["gates"]
            if gate["id"] == "gate.concept.project_readiness"
        )
        self.assertEqual(canonical["status"], "rejected")
        self.assertEqual(len(canonical["reviews"]), 1)
        self.assertEqual(project_gate["status"], "planned")
        self.assertEqual(project_gate["reviews"], [])

    def test_explicit_checkpoint_redirect_is_consumed_by_only_its_target(self) -> None:
        legacy = deepcopy(
            next(gate for gate in self.state["gates"] if gate["id"] == "gate.tr.concept")
        )
        legacy.update(
            {
                "id": "tr.concept",
                "status": "rejected",
                "reviews": [
                    {
                        "reviewer": "legacy-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "reject",
                        "evidence": "reviews/legacy-tr.md",
                    }
                ],
            }
        )
        self.state["gates"] = [
            gate for gate in self.state["gates"] if gate["id"] != "gate.tr.concept"
        ] + [legacy]
        project_gate = {
            **deepcopy(
                next(
                    gate
                    for gate in self.process["gates"]
                    if gate["id"] == "gate.tr.concept"
                )
            ),
            "id": "gate.concept.project_readiness",
            "title": "Project readiness",
            "kind": "Gate",
        }
        self.process["gates"].append(project_gate)
        self.process["gate_migrations"] = [
            {
                "from": "tr.concept",
                "to": project_gate["id"],
                "reason": "Preserve the project-specific legacy decision.",
                "preserve_history": True,
            }
        ]

        updated = sync_state_with_process(
            self.state, self.process, apply_migrations=True
        )

        canonical = next(
            gate for gate in updated["gates"] if gate["id"] == "gate.tr.concept"
        )
        migrated = next(
            gate for gate in updated["gates"] if gate["id"] == project_gate["id"]
        )
        self.assertEqual(canonical["status"], "planned")
        self.assertEqual(canonical["reviews"], [])
        self.assertEqual(migrated["status"], "rejected")
        self.assertEqual(len(migrated["reviews"]), 1)

    def test_planned_stale_gate_history_is_preserved_or_fails_closed(self) -> None:
        canonical = next(
            gate for gate in self.state["gates"] if gate["id"] == "gate.tr.concept"
        )
        legacy = deepcopy(canonical)
        legacy.update(
            {
                "id": "gate.legacy.stale_readiness",
                "status": "planned",
                "reviews": [
                    {
                        "reviewer": "legacy-authority",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": "reviews/stale-gate.md",
                        "gate_epoch": 1,
                    }
                ],
                "evidence": ["evidence/stale-gate.md"],
                "blockers": ["GATE_REQUIREMENTS_CHANGED"],
                "approval": None,
                "review_epoch": 1,
                "stale": True,
                "stale_reason": "GATE_REQUIREMENTS_CHANGED",
            }
        )
        self.state["gates"].append(legacy)

        with self.assertRaisesRegex(ProjectError, "active or historical gates"):
            sync_state_with_process(self.state, self.process)

        self.process["gate_migrations"] = [
            {
                "from": legacy["id"],
                "to": canonical["id"],
                "reason": "Preserve the stale legacy Gate review history.",
                "preserve_history": True,
            }
        ]
        updated = sync_state_with_process(
            self.state, self.process, apply_migrations=True
        )
        migrated = next(
            gate for gate in updated["gates"] if gate["id"] == canonical["id"]
        )
        self.assertEqual(migrated["reviews"], legacy["reviews"])
        self.assertEqual(migrated["evidence"], legacy["evidence"])
        self.assertEqual(migrated["review_epoch"], legacy["review_epoch"])
        self.assertTrue(migrated["stale"])
        self.assertEqual(migrated["stale_reason"], legacy["stale_reason"])

    def test_claim_linked_deliverable_requires_migration_and_keeps_history(self) -> None:
        old_process = deepcopy(self.process)
        old_process["deliverables"].append(_deliverable("project.legacy_baseline"))
        state = sync_state_with_process(self.state, old_process)
        state["claims"] = [_claim("claim.baseline")]
        claim_link = _edge(
            "claim.baseline", "project.legacy_baseline", "supports"
        )
        state["traceability"].append(claim_link)

        candidate = deepcopy(self.process)
        _, impact = project_traceability_projection(state, candidate)
        self.assertEqual(impact["blocked"][0]["kind"], "claim_traceability_removal")
        with self.assertRaisesRegex(ProjectError, "unmapped historical deliverables"):
            sync_state_with_process(state, candidate)

        candidate["deliverables"].append(_deliverable("project.current_baseline"))
        candidate["migrations"].append(
            {
                "from": "project.legacy_baseline",
                "to": "project.current_baseline",
                "strategy": "replace",
                "reason": "Replace the legacy project baseline.",
                "preserve_history": True,
            }
        )
        with self.assertRaisesRegex(ProjectError, "explicit --apply-migrations"):
            sync_state_with_process(state, candidate)
        migrated = sync_state_with_process(state, candidate, apply_migrations=True)
        legacy = next(
            item
            for item in migrated["deliverables"]
            if item["id"] == "project.legacy_baseline"
        )
        self.assertEqual(legacy["status"], "superseded")
        self.assertEqual(legacy["replacement"], "project.current_baseline")
        self.assertIn(claim_link, migrated["traceability"])
        self.assertIn(
            _edge(
                "project.legacy_baseline",
                "project.current_baseline",
                "supersedes",
            ),
            migrated["traceability"],
        )

    def test_unexplained_gate_removal_and_dangling_input_fail_closed(self) -> None:
        legacy = deepcopy(
            next(gate for gate in self.state["gates"] if gate["id"] == "gate.tr.concept")
        )
        legacy.update({"id": "legacy.unmapped_gate", "status": "planned"})
        self.state["gates"].append(legacy)
        self.state["claims"] = [_claim("claim.gate")]
        claim_link = _edge("claim.gate", "legacy.unmapped_gate", "verifies")
        self.state["traceability"].append(claim_link)

        _, impact = project_traceability_projection(self.state, self.process)
        self.assertIn(claim_link, impact["removed"])
        self.assertEqual(impact["blocked"][0]["kind"], "claim_traceability_removal")
        with self.assertRaisesRegex(ProjectError, "active or historical gates"):
            sync_state_with_process(self.state, self.process)

        dangling = deepcopy(self.state)
        dangling["gates"] = [
            gate for gate in dangling["gates"] if gate["id"] != "legacy.unmapped_gate"
        ]
        _, impact = project_traceability_projection(dangling, self.process)
        self.assertEqual(impact["blocked"][0]["kind"], "dangling_existing_traceability")
        with self.assertRaisesRegex(ProjectError, "Claim traceability"):
            sync_state_with_process(dangling, self.process)


if __name__ == "__main__":
    unittest.main()

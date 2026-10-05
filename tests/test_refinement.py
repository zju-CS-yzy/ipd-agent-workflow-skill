from __future__ import annotations

import unittest
from copy import deepcopy

from ipdctl.process_extensions import preview_process_diff
from ipdctl.refinement import (
    RefinementPlanError,
    effective_gate_requirements,
    finalize_refinement_record,
    historical_deliverable_id_reuse,
    historical_dependency_rewrites,
    load_refinement_plan,
    merge_refinement_plan,
    process_fingerprint,
    refinement_authority_projection,
    refinement_leaf_closure,
    refinement_status,
    trigger_satisfied,
)
from ipdctl.tailoring import TailoringError, tailor_profile, validate_process


def requirement_extension() -> dict:
    return {
        "schema_version": "1.0",
        "extension_id": "project.refinement",
        "refinement_requirements": [
            {
                "root": "software.architecture",
                "definition_state": "placeholder",
                "refinement_required": True,
                "trigger": {
                    "all_of": [
                        {"subject": "plan.integrated_plan", "condition": "accepted"}
                    ]
                },
                "completion_policy": "all_children_accepted",
            }
        ],
    }


def expansion_plan(process: dict) -> dict:
    return {
        "schema_version": "1.0",
        "id": "refinement.software_architecture.v1",
        "root": "software.architecture",
        "mode": "expand",
        "base_process_fingerprint": process_fingerprint(process),
        "reason": "The accepted integrated plan identifies separate runtime and perception modules.",
        "basis": ["evidence/plan.integrated_plan/approval.md"],
        "activities": [
            {
                "id": "plan.module_architecture",
                "title": "Define module architecture",
                "phase": "plan",
                "sequence": 22,
                "refines": "plan.software_architecture",
            }
        ],
        "deliverables": [
            {
                "id": "software.runtime_architecture",
                "title": "Runtime architecture aggregate",
                "phase": "plan",
                "activity_id": "plan.module_architecture",
                "review_required": True,
                "depends_on": ["plan.integrated_plan"],
                "definition_state": "abstract",
                "refines": "software.architecture",
            },
            {
                "id": "software.motion_architecture",
                "title": "Motion architecture",
                "phase": "plan",
                "activity_id": "plan.module_architecture",
                "review_required": True,
                "depends_on": ["plan.integrated_plan"],
                "refines": "software.runtime_architecture",
            },
            {
                "id": "software.perception_architecture",
                "title": "Perception architecture",
                "phase": "plan",
                "activity_id": "plan.module_architecture",
                "review_required": True,
                "depends_on": ["plan.integrated_plan"],
                "refines": "software.architecture",
            },
        ],
        "dependencies": [
            {
                "source": "software.perception_architecture",
                "target": "concept.problem_definition",
                "relation": "supports",
            }
        ],
    }


class RefinementContractTests(unittest.TestCase):
    def test_requirement_annotates_root_and_placeholder_remains_a_gate_requirement(self) -> None:
        process = tailor_profile(
            {"task_type": "software"},
            process_extension=requirement_extension(),
        )
        root = next(
            item for item in process["deliverables"]
            if item["id"] == "software.architecture"
        )
        self.assertEqual(root["definition_state"], "placeholder")
        self.assertTrue(root["refinement_required"])
        self.assertEqual(root["completion_policy"], "all_children_accepted")
        plan_tr = next(
            item for item in process["technical_reviews"]
            if item["id"] == "tr.plan"
        )
        self.assertIn("software.architecture", plan_tr["required_deliverables"])
        self.assertEqual(process["refinements"], [])
        self.assertEqual(validate_process(process), [])

    def test_plan_merge_is_idempotent_and_rejects_changed_content(self) -> None:
        extension = requirement_extension()
        process = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(process)
        merged, applied = merge_refinement_plan(extension, plan, process=process)
        self.assertTrue(applied)
        self.assertEqual(len(merged["refinements"]), 1)
        merged_by_id = {
            item["id"]: item for item in merged["deliverables"]
        }
        self.assertFalse(
            merged_by_id["software.runtime_architecture"][
                "requires_artifact_owner"
            ]
        )
        self.assertTrue(
            merged_by_id["software.motion_architecture"][
                "requires_artifact_owner"
            ]
        )
        self.assertTrue(
            merged_by_id["software.perception_architecture"][
                "requires_artifact_owner"
            ]
        )

        compiled = tailor_profile(
            {"task_type": "software"}, process_extension=merged
        )
        replayed, applied = merge_refinement_plan(merged, plan, process=compiled)
        self.assertFalse(applied)
        self.assertEqual(replayed, merged)

        changed = deepcopy(plan)
        changed["reason"] = "A different expansion using the same plan id."
        with self.assertRaisesRegex(RefinementPlanError, "different digest"):
            merge_refinement_plan(merged, changed, process=compiled)

    def test_result_audit_fields_are_bound_without_self_referential_digest(self) -> None:
        extension = requirement_extension()
        process = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        merged, applied = merge_refinement_plan(
            extension, expansion_plan(process), process=process
        )
        self.assertTrue(applied)
        candidate = tailor_profile(
            {"task_type": "software"}, process_extension=merged
        )
        result_fingerprint = process_fingerprint(candidate)
        finalized = finalize_refinement_record(
            merged,
            plan_id="refinement.software_architecture.v1",
            result_process_fingerprint=result_fingerprint,
            invalidated_gates=["gate.tr.plan"],
        )
        finalized_process = tailor_profile(
            {"task_type": "software"}, process_extension=finalized
        )
        self.assertEqual(process_fingerprint(finalized_process), result_fingerprint)
        record = finalized_process["refinements"][0]
        self.assertEqual(record["result_process_fingerprint"], result_fingerprint)
        self.assertEqual(record["invalidated_gates"], ["gate.tr.plan"])
        with self.assertRaisesRegex(RefinementPlanError, "conflicts"):
            finalize_refinement_record(
                finalized,
                plan_id="refinement.software_architecture.v1",
                result_process_fingerprint="sha256:" + "f" * 64,
                invalidated_gates=["gate.tr.plan"],
            )

    def test_owner_default_follows_normalized_definition_state(self) -> None:
        process = tailor_profile(
            {"task_type": "software"},
            process_extension=requirement_extension(),
        )
        plan = expansion_plan(process)
        invalid = deepcopy(plan)
        invalid["deliverables"][1]["requires_artifact_owner"] = False
        with self.assertRaisesRegex(
            RefinementPlanError, "concrete Deliverables must require"
        ):
            load_refinement_plan(invalid)
        placeholder = plan["deliverables"][2]
        placeholder["definition_state"] = "placeholder"
        placeholder["refinement_required"] = True
        placeholder["refinement_trigger"] = {
            "all_of": [
                {"subject": "plan.integrated_plan", "condition": "accepted"}
            ]
        }
        placeholder["requires_artifact_owner"] = False

        normalized = load_refinement_plan(plan)
        by_id = {item["id"]: item for item in normalized["deliverables"]}

        self.assertFalse(
            by_id["software.runtime_architecture"]["requires_artifact_owner"]
        )
        self.assertTrue(
            by_id["software.motion_architecture"]["requires_artifact_owner"]
        )
        self.assertFalse(
            by_id["software.perception_architecture"]["requires_artifact_owner"]
        )

        merged, applied = merge_refinement_plan(
            requirement_extension(), normalized, process=process
        )
        self.assertTrue(applied)
        merged_by_id = {
            item["id"]: item for item in merged["deliverables"]
        }
        self.assertFalse(
            merged_by_id["software.perception_architecture"][
                "requires_artifact_owner"
            ]
        )

    def test_nested_requirement_must_remain_a_leaf_until_a_later_plan(self) -> None:
        extension = requirement_extension()
        process = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(process)
        aggregate = plan["deliverables"][0]
        aggregate["definition_state"] = "placeholder"
        aggregate["refinement_required"] = True
        aggregate["refinement_trigger"] = {
            "all_of": [
                {"subject": "plan.integrated_plan", "condition": "accepted"}
            ]
        }
        with self.assertRaisesRegex(
            RefinementPlanError, "must remain a leaf in this plan"
        ):
            merge_refinement_plan(extension, plan, process=process)

    def test_plan_cannot_reuse_a_state_only_historical_deliverable_id(self) -> None:
        process = tailor_profile({"task_type": "software"})
        plan = expansion_plan(process)
        plan["deliverables"][0]["id"] = "software.retired_architecture"
        state = {
            "deliverables": [
                *deepcopy(process["deliverables"]),
                {
                    "id": "software.retired_architecture",
                    "status": "superseded",
                    "replacement": "software.architecture",
                    "replacements": ["software.architecture"],
                },
            ]
        }
        self.assertEqual(
            historical_deliverable_id_reuse(plan, state, process),
            ["software.retired_architecture"],
        )

    def test_refinement_cannot_rewrite_dependencies_of_accepted_history(self) -> None:
        diff = {
            "changed": [
                {
                    "collection": "deliverables",
                    "id": "software.release_candidate",
                    "fields": ["depends_on"],
                }
            ]
        }
        accepted = {
            "deliverables": [
                {
                    "id": "software.release_candidate",
                    "status": "accepted",
                    "evidence": ["evidence/release.md"],
                    "reviews": [],
                }
            ]
        }
        self.assertEqual(
            historical_dependency_rewrites(diff, accepted),
            ["software.release_candidate"],
        )
        accepted["deliverables"][0] = {
            "id": "software.release_candidate",
            "status": "planned",
            "evidence": [],
            "reviews": [],
        }
        self.assertEqual(historical_dependency_rewrites(diff, accepted), [])

    def test_applied_expand_compiles_leaf_gates_and_execution_dependencies(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        merged, _ = merge_refinement_plan(
            extension, expansion_plan(before), process=before
        )
        after = tailor_profile(
            {"task_type": "software"}, process_extension=merged
        )

        by_id = {item["id"]: item for item in after["deliverables"]}
        root = by_id["software.architecture"]
        self.assertEqual(root["definition_state"], "abstract")
        self.assertEqual(
            refinement_leaf_closure(after, root["id"]),
            ["software.motion_architecture", "software.perception_architecture"],
        )
        self.assertEqual(
            effective_gate_requirements([root["id"]], after),
            ["software.motion_architecture", "software.perception_architecture"],
        )

        downstream = by_id["software.release_candidate"]
        self.assertNotIn(root["id"], downstream["depends_on"])
        self.assertIn("software.motion_architecture", downstream["depends_on"])
        self.assertIn("software.perception_architecture", downstream["depends_on"])

        plan_tr = next(
            item for item in after["technical_reviews"]
            if item["id"] == "tr.plan"
        )
        self.assertNotIn(root["id"], plan_tr["required_deliverables"])
        self.assertIn("software.motion_architecture", plan_tr["required_deliverables"])
        self.assertIn("software.perception_architecture", plan_tr["required_deliverables"])
        self.assertNotIn("software.runtime_architecture", plan_tr["required_deliverables"])

        missing_record = deepcopy(after)
        missing_record["refinements"] = []
        self.assertTrue(
            any(
                "pre-expanded without an applied refinement record" in issue
                for issue in validate_process(missing_record)
            )
        )

        typed_edges = {
            (item["source"], item["target"], item["relation"])
            for item in after["dependencies"]
        }
        self.assertIn(
            ("software.motion_architecture", "software.runtime_architecture", "refines"),
            typed_edges,
        )
        self.assertNotIn(
            ("software.motion_architecture", "software.runtime_architecture", "depends_on"),
            typed_edges,
        )
        self.assertEqual(validate_process(after), [])

    def test_refinement_authority_projection_blocks_lineage_drift_only(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        merged, _ = merge_refinement_plan(
            extension, expansion_plan(before), process=before
        )
        protected = tailor_profile(
            {"task_type": "software"}, process_extension=merged
        )
        baseline = refinement_authority_projection(protected)
        roots = baseline["roots"]

        variants: dict[str, dict] = {}
        changed_dependency = deepcopy(protected)
        next(
            item
            for item in changed_dependency["deliverables"]
            if item["id"] == "software.motion_architecture"
        )["depends_on"] = ["concept.problem_definition"]
        variants["child dependency"] = changed_dependency

        changed_parent = deepcopy(protected)
        next(
            item
            for item in changed_parent["deliverables"]
            if item["id"] == "software.motion_architecture"
        )["refines"] = "software.architecture"
        variants["child parent"] = changed_parent

        added_descendant = deepcopy(protected)
        added_descendant["deliverables"].append(
            {
                "id": "software.hidden_descendant",
                "title": "Hidden descendant",
                "phase": "plan",
                "activity_id": "plan.module_architecture",
                "review_required": True,
                "depends_on": ["plan.integrated_plan"],
                "refines": "software.architecture",
            }
        )
        variants["new descendant"] = added_descendant

        changed_root = deepcopy(protected)
        next(
            item
            for item in changed_root["deliverables"]
            if item["id"] == "software.architecture"
        )["definition_state"] = "concrete"
        variants["root definition"] = changed_root

        for label, candidate in variants.items():
            with self.subTest(label=label):
                self.assertNotEqual(
                    baseline,
                    refinement_authority_projection(
                        candidate, protected_roots=roots
                    ),
                )

        unrelated_extension = deepcopy(merged)
        unrelated_extension.setdefault("activities", []).append(
            {
                "id": "plan.unrelated_assurance",
                "title": "Plan unrelated assurance",
                "phase": "plan",
                "sequence": 90,
            }
        )
        unrelated_extension.setdefault("deliverables", []).append(
            {
                "id": "project.unrelated_assurance",
                "title": "Unrelated assurance",
                "phase": "plan",
                "activity_id": "plan.unrelated_assurance",
                "review_required": True,
                "depends_on": ["plan.integrated_plan"],
            }
        )
        unrelated = tailor_profile(
            {"task_type": "software"}, process_extension=unrelated_extension
        )
        self.assertEqual(
            baseline,
            refinement_authority_projection(unrelated, protected_roots=roots),
        )

    def test_trigger_and_refinement_status_are_pure_and_fail_closed(self) -> None:
        requirement = requirement_extension()["refinement_requirements"][0]
        self.assertFalse(trigger_satisfied(requirement["trigger"], {}))
        self.assertEqual(
            refinement_status(requirement, statuses={}), "pending"
        )
        statuses = {"plan.integrated_plan": {"status": "accepted"}}
        self.assertTrue(trigger_satisfied(requirement["trigger"], statuses))
        self.assertEqual(
            refinement_status(requirement, statuses=statuses), "due"
        )
        self.assertEqual(
            refinement_status(
                requirement,
                statuses=statuses,
                refinements=[{"root": "software.architecture"}],
            ),
            "resolved",
        )

    def test_plan_requires_declared_existing_root_and_current_fingerprint(self) -> None:
        empty_extension = {
            "schema_version": "1.0",
            "extension_id": "project",
        }
        process = tailor_profile({"task_type": "software"})
        plan = expansion_plan(process)
        with self.assertRaisesRegex(RefinementPlanError, "no declared"):
            merge_refinement_plan(empty_extension, plan, process=process)

        extension = requirement_extension()
        declared_process = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        stale = expansion_plan(declared_process)
        stale["base_process_fingerprint"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(RefinementPlanError, "does not match"):
            merge_refinement_plan(extension, stale, process=declared_process)

    def test_preview_reports_refinement_and_inert_migration_source(self) -> None:
        before = tailor_profile({"task_type": "software"})
        candidate = deepcopy(before)
        candidate["refinements"] = [
            {
                "id": "refinement.example",
                "root": "software.architecture",
                "mode": "expand",
                "base_process_fingerprint": "sha256:" + "1" * 64,
                "reason": "Example.",
                "basis": ["evidence/example.md"],
                "plan_digest": "sha256:" + "2" * 64,
                "children": ["software.release_candidate"],
            }
        ]
        candidate["migrations"] = [
            {
                "from": "software.architecture",
                "to": "software.release_candidate",
                "strategy": "replace",
                "reason": "Inert while the source remains.",
                "preserve_history": True,
            }
        ]
        preview = preview_process_diff(before, candidate)
        self.assertIn(
            {"collection": "refinements", "id": "refinement.example"},
            preview["added"],
        )
        self.assertTrue(
            any(item["kind"] == "source_still_present" for item in preview["ambiguous"])
        )

    def test_compiler_rejects_unknown_requirement_root(self) -> None:
        extension = requirement_extension()
        extension["refinement_requirements"][0]["root"] = "missing.root"
        with self.assertRaisesRegex(TailoringError, "existing Deliverable"):
            tailor_profile({"task_type": "software"}, process_extension=extension)

    def test_additive_relation_cannot_reparent_an_earlier_layer_node(self) -> None:
        extension = {
            "schema_version": "1.0",
            "extension_id": "project.unsafe_reparent",
            "dependencies": [
                {
                    "source": "software.release_candidate",
                    "target": "software.architecture",
                    "relation": "refines",
                }
            ],
        }
        with self.assertRaisesRegex(TailoringError, "earlier-layer entity"):
            tailor_profile({"task_type": "software"}, process_extension=extension)

    def test_refinement_children_cannot_move_the_parent_across_phases(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(before)
        plan["deliverables"][0]["phase"] = "develop"
        plan["deliverables"][0]["activity_id"] = "develop.software_implementation"
        with self.assertRaisesRegex(RefinementPlanError, "must remain in parent phase"):
            merge_refinement_plan(extension, plan, process=before)

    def test_nested_requirement_is_materialized_for_a_second_refinement_round(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        first = {
            "schema_version": "1.0",
            "id": "refinement.software_modules.v1",
            "root": "software.architecture",
            "mode": "expand",
            "base_process_fingerprint": process_fingerprint(before),
            "reason": "The integrated plan identifies runtime and perception modules.",
            "basis": ["evidence/plan.integrated_plan/approval.md"],
            "activities": [
                {
                    "id": "plan.software_modules",
                    "title": "Define software modules",
                    "phase": "plan",
                    "sequence": 22,
                    "refines": "plan.software_architecture",
                }
            ],
            "deliverables": [
                {
                    "id": "software.runtime_architecture",
                    "title": "Runtime architecture",
                    "phase": "plan",
                    "activity_id": "plan.software_modules",
                    "review_required": True,
                    "depends_on": ["plan.integrated_plan"],
                    "refines": "software.architecture",
                },
                {
                    "id": "software.perception_architecture",
                    "title": "Perception architecture placeholder",
                    "phase": "plan",
                    "activity_id": "plan.software_modules",
                    "review_required": True,
                    "depends_on": ["plan.integrated_plan"],
                    "definition_state": "placeholder",
                    "refinement_required": True,
                    "refinement_trigger": {
                        "all_of": [
                            {
                                "subject": "plan.integrated_plan",
                                "condition": "accepted",
                            }
                        ]
                    },
                    "refines": "software.architecture",
                },
            ],
            "dependencies": [],
        }
        first_extension, applied = merge_refinement_plan(
            extension, first, process=before
        )
        self.assertTrue(applied)
        nested_requirement = next(
            item
            for item in first_extension["refinement_requirements"]
            if item["root"] == "software.perception_architecture"
        )
        self.assertEqual(nested_requirement["definition_state"], "placeholder")
        after_first = tailor_profile(
            {"task_type": "software"}, process_extension=first_extension
        )

        second = {
            "schema_version": "1.0",
            "id": "refinement.perception_components.v1",
            "root": "software.perception_architecture",
            "mode": "expand",
            "base_process_fingerprint": process_fingerprint(after_first),
            "reason": "The perception baseline identifies vision and ranging components.",
            "basis": ["evidence/software.perception_architecture/design.md"],
            "activities": [
                {
                    "id": "plan.perception_components",
                    "title": "Define perception components",
                    "phase": "plan",
                    "sequence": 23,
                    "refines": "plan.software_modules",
                }
            ],
            "deliverables": [
                {
                    "id": "software.vision_architecture",
                    "title": "Vision architecture",
                    "phase": "plan",
                    "activity_id": "plan.perception_components",
                    "review_required": True,
                    "depends_on": ["plan.integrated_plan"],
                    "refines": "software.perception_architecture",
                },
                {
                    "id": "software.ranging_architecture",
                    "title": "Ranging architecture",
                    "phase": "plan",
                    "activity_id": "plan.perception_components",
                    "review_required": True,
                    "depends_on": ["plan.integrated_plan"],
                    "refines": "software.perception_architecture",
                },
            ],
            "dependencies": [],
        }
        second_extension, applied = merge_refinement_plan(
            first_extension, second, process=after_first
        )
        self.assertTrue(applied)
        after_second = tailor_profile(
            {"task_type": "software"}, process_extension=second_extension
        )
        self.assertEqual(
            refinement_leaf_closure(after_second, "software.architecture"),
            [
                "software.ranging_architecture",
                "software.runtime_architecture",
                "software.vision_architecture",
            ],
        )
        perception = next(
            item
            for item in after_second["deliverables"]
            if item["id"] == "software.perception_architecture"
        )
        self.assertEqual(perception["definition_state"], "abstract")
        self.assertEqual(len(after_second["refinements"]), 2)
        self.assertEqual(validate_process(after_second), [])

    def test_nested_requirement_requires_a_trigger(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(before)
        plan["deliverables"][1]["refinement_required"] = True
        with self.assertRaisesRegex(RefinementPlanError, "refinement_trigger"):
            merge_refinement_plan(extension, plan, process=before)

    def test_placeholder_children_require_an_executable_refinement_requirement(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(before)
        plan["deliverables"][1]["definition_state"] = "placeholder"
        with self.assertRaisesRegex(
            RefinementPlanError,
            "must be true when definition_state is placeholder",
        ):
            merge_refinement_plan(extension, plan, process=before)

    def test_activity_hierarchy_is_structural_and_cannot_declare_a_requirement(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(before)
        plan["activities"][0]["definition_state"] = "placeholder"

        merged, applied = merge_refinement_plan(extension, plan, process=before)
        self.assertTrue(applied)
        compiled = tailor_profile(
            {"task_type": "software"}, process_extension=merged
        )
        activity = next(
            item
            for item in compiled["activities"]
            if item["id"] == "plan.module_architecture"
        )
        self.assertEqual(activity["definition_state"], "placeholder")
        self.assertEqual(activity["refines"], "plan.software_architecture")
        self.assertNotIn("refinement_required", activity)
        self.assertNotIn("refinement_trigger", activity)
        self.assertEqual(validate_process(compiled), [])

        for forbidden_field, forbidden_value in (
            ("refinement_required", True),
            (
                "refinement_trigger",
                {
                    "all_of": [
                        {
                            "subject": "plan.integrated_plan",
                            "condition": "accepted",
                        }
                    ]
                },
            ),
        ):
            with self.subTest(field=forbidden_field):
                invalid = expansion_plan(before)
                invalid["activities"][0][forbidden_field] = forbidden_value
                with self.assertRaisesRegex(
                    RefinementPlanError,
                    "only Deliverables may declare refinement requirements",
                ):
                    merge_refinement_plan(extension, invalid, process=before)

        invalid_process = deepcopy(before)
        invalid_process["activities"][0]["refinement_required"] = True
        invalid_process["activities"][0]["refinement_trigger"] = {
            "all_of": [
                {"subject": "plan.integrated_plan", "condition": "accepted"}
            ]
        }
        process_issues = validate_process(invalid_process)
        self.assertTrue(
            any(
                "$.activities[0].refinement_required: only Deliverables"
                in issue
                for issue in process_issues
            )
        )
        self.assertTrue(
            any(
                "$.activities[0].refinement_trigger: only Deliverables" in issue
                for issue in process_issues
            )
        )

    def test_refinement_triggers_must_be_reachable_before_the_root_gate(self) -> None:
        self_trigger = requirement_extension()
        self_trigger["refinement_requirements"][0]["trigger"] = {
            "all_of": [
                {"subject": "software.architecture", "condition": "accepted"}
            ]
        }
        with self.assertRaisesRegex(TailoringError, "placeholder refinement root"):
            tailor_profile(
                {"task_type": "software"}, process_extension=self_trigger
            )

        later_phase = requirement_extension()
        later_phase["refinement_requirements"][0]["trigger"] = {
            "all_of": [
                {"subject": "software.release_candidate", "condition": "accepted"}
            ]
        }
        with self.assertRaisesRegex(TailoringError, "later-phase Deliverable"):
            tailor_profile(
                {"task_type": "software"}, process_extension=later_phase
            )

        same_phase_gate = requirement_extension()
        same_phase_gate["refinement_requirements"][0]["trigger"] = {
            "all_of": [{"subject": "gate.tr.plan", "condition": "approved"}]
        }
        with self.assertRaisesRegex(TailoringError, "phase before refinement root"):
            tailor_profile(
                {"task_type": "software"}, process_extension=same_phase_gate
            )

        earlier_gate = requirement_extension()
        earlier_gate["refinement_requirements"][0]["trigger"] = {
            "all_of": [{"subject": "gate.dcp.concept", "condition": "approved"}]
        }
        self.assertEqual(
            validate_process(
                tailor_profile(
                    {"task_type": "software"}, process_extension=earlier_gate
                )
            ),
            [],
        )

    def test_nested_requirement_cannot_overwrite_an_existing_root_declaration(self) -> None:
        extension = requirement_extension()
        before = tailor_profile(
            {"task_type": "software"}, process_extension=extension
        )
        plan = expansion_plan(before)
        plan["deliverables"][1].update(
            definition_state="placeholder",
            refinement_required=True,
            refinement_trigger={
                "all_of": [
                    {"subject": "plan.integrated_plan", "condition": "accepted"}
                ]
            },
        )
        conflicting = deepcopy(extension)
        conflicting["refinement_requirements"].append(
            {
                "root": "software.motion_architecture",
                "definition_state": "concrete",
                "refinement_required": True,
                "trigger": {
                    "all_of": [
                        {"subject": "plan.integrated_plan", "condition": "accepted"}
                    ]
                },
                "completion_policy": "all_children_accepted",
            }
        )
        with self.assertRaisesRegex(RefinementPlanError, "already declared"):
            merge_refinement_plan(conflicting, plan, process=before)


if __name__ == "__main__":
    unittest.main()

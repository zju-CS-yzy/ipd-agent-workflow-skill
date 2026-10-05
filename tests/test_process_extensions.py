from __future__ import annotations

import unittest
from copy import deepcopy

from ipdctl.process_extensions import (
    ProcessExtensionError,
    load_process_extension,
    preview_process_diff,
)
from ipdctl.tailoring import tailor_profile, validate_process


class ProcessExtensionTests(unittest.TestCase):
    def test_empty_extension_is_normalized_without_io(self) -> None:
        extension = load_process_extension(None)
        self.assertEqual(extension["schema_version"], "1.0")
        self.assertEqual(extension["extension_id"], "project")
        for field in (
            "activities",
            "deliverables",
            "dependencies",
            "checkpoint_criteria",
            "migrations",
        ):
            self.assertEqual(extension[field], [])

    def test_extension_cannot_weaken_review_or_history(self) -> None:
        with self.assertRaisesRegex(ProcessExtensionError, "review_required"):
            load_process_extension(
                {
                    "schema_version": "1.0",
                    "extension_id": "unsafe.extension",
                    "deliverables": [
                        {
                            "id": "unsafe.record",
                            "title": "Unsafe record",
                            "phase": "plan",
                            "activity_id": "plan.integrated_planning",
                            "review_required": False,
                            "depends_on": [],
                        }
                    ],
                }
            )
        with self.assertRaisesRegex(ProcessExtensionError, "preserve_history"):
            load_process_extension(
                {
                    "schema_version": "1.0",
                    "extension_id": "unsafe.extension",
                    "migrations": [
                        {
                            "from": "old.record",
                            "to": "plan.integrated_plan",
                            "strategy": "replace",
                            "reason": "Unsafe history removal",
                            "preserve_history": False,
                        }
                    ],
                }
            )

    def test_activity_refinement_metadata_is_structural_only(self) -> None:
        structural = {
            "schema_version": "1.0",
            "extension_id": "activity.hierarchy",
            "activities": [
                {
                    "id": "plan.module_architecture",
                    "title": "Define module architecture",
                    "phase": "plan",
                    "sequence": 22,
                    "definition_state": "placeholder",
                    "refines": "plan.software_architecture",
                }
            ],
        }
        normalized = load_process_extension(structural)
        self.assertEqual(
            normalized["activities"][0]["definition_state"], "placeholder"
        )
        process = tailor_profile(
            {"task_type": "software"}, process_extension=normalized
        )
        self.assertEqual(validate_process(process), [])

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
                invalid = deepcopy(structural)
                invalid["activities"][0][forbidden_field] = forbidden_value
                with self.assertRaisesRegex(
                    ProcessExtensionError,
                    "only Deliverables may declare refinement requirements",
                ):
                    load_process_extension(invalid)

    def test_requirement_cannot_be_preexpanded_without_an_applied_record(self) -> None:
        extension = {
            "schema_version": "1.0",
            "extension_id": "preexpanded.requirement",
            "activities": [
                {
                    "id": "plan.hidden_module_design",
                    "title": "Define hidden module",
                    "phase": "plan",
                    "sequence": 99,
                }
            ],
            "deliverables": [
                {
                    "id": "software.hidden_module",
                    "title": "Hidden module",
                    "phase": "plan",
                    "activity_id": "plan.hidden_module_design",
                    "review_required": True,
                    "depends_on": ["plan.integrated_plan"],
                    "refines": "software.architecture",
                }
            ],
            "refinement_requirements": [
                {
                    "root": "software.architecture",
                    "definition_state": "placeholder",
                    "refinement_required": True,
                    "trigger": {
                        "all_of": [
                            {
                                "subject": "plan.integrated_plan",
                                "condition": "accepted",
                            }
                        ]
                    },
                    "completion_policy": "all_children_accepted",
                }
            ],
        }
        with self.assertRaisesRegex(
            ProcessExtensionError,
            "pre-expanded without an applied refinement record",
        ):
            load_process_extension(extension)

    def test_project_dependency_between_existing_nodes_keeps_project_provenance(
        self,
    ) -> None:
        process = tailor_profile(
            {"task_type": "software"},
            process_extension={
                "schema_version": "1.0",
                "extension_id": "project.integration",
                "dependencies": [
                    {
                        "source": "develop.solution_baseline",
                        "target": "concept.problem_definition",
                        "relation": "depends_on",
                    }
                ],
            },
        )

        edge = next(
            item
            for item in process["dependencies"]
            if item["source"] == "develop.solution_baseline"
            and item["target"] == "concept.problem_definition"
            and item["relation"] == "depends_on"
        )
        self.assertEqual(
            edge["provenance"],
            {"layer": "project", "source_id": "project.integration"},
        )
        source = next(
            item
            for item in process["deliverables"]
            if item["id"] == "develop.solution_baseline"
        )
        self.assertIn("concept.problem_definition", source["depends_on"])
        self.assertEqual(validate_process(process), [])

    def test_preview_is_deterministic_and_accepts_explicit_split(self) -> None:
        current = tailor_profile({"task_type": "software"})
        candidate = deepcopy(current)
        candidate["migrations"] = [
            {
                "from": "legacy.record",
                "to": "software.architecture",
                "strategy": "split",
                "reason": "Separate architecture history.",
                "preserve_history": True,
            },
            {
                "from": "legacy.record",
                "to": "software.release_candidate",
                "strategy": "split",
                "reason": "Separate implementation history.",
                "preserve_history": True,
            },
        ]
        first = preview_process_diff(current, candidate)
        second = preview_process_diff(deepcopy(current), deepcopy(candidate))
        self.assertEqual(first, second)
        self.assertEqual(
            list(first),
            ["added", "removed", "changed", "migrations", "ambiguous"],
        )
        self.assertEqual(first["ambiguous"], [])
        self.assertEqual(first["migrations"], sorted(first["migrations"], key=str))

    def test_many_to_one_migration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ProcessExtensionError, "merge is unsupported"):
            load_process_extension(
                {
                    "schema_version": "1.0",
                    "extension_id": "unsupported.merge",
                    "migrations": [
                        {
                            "from": "legacy.a",
                            "to": "project.record",
                            "strategy": "replace",
                            "reason": "First source.",
                            "preserve_history": True,
                        },
                        {
                            "from": "legacy.b",
                            "to": "project.record",
                            "strategy": "replace",
                            "reason": "Second source.",
                            "preserve_history": True,
                        },
                    ],
                }
            )

    def test_duplicate_pair_and_mixed_source_strategy_fail_closed(self) -> None:
        duplicate_pair = {
            "schema_version": "1.0",
            "extension_id": "invalid.migration",
            "migrations": [
                {
                    "from": "legacy.record",
                    "to": "project.record",
                    "strategy": "replace",
                    "reason": "Replace the record.",
                    "preserve_history": True,
                },
                {
                    "from": "legacy.record",
                    "to": "project.record",
                    "strategy": "split",
                    "reason": "Conflicting strategy.",
                    "preserve_history": True,
                },
            ],
        }
        with self.assertRaisesRegex(ProcessExtensionError, "duplicate migration mapping"):
            load_process_extension(duplicate_pair)

        process = tailor_profile({"task_type": "software"})
        process["migrations"] = [
            {
                "from": "legacy.record",
                "to": "software.architecture",
                "strategy": "replace",
                "reason": "First mapping.",
                "preserve_history": True,
            },
            {
                "from": "legacy.record",
                "to": "software.release_candidate",
                "strategy": "split",
                "reason": "Mixed strategy.",
                "preserve_history": True,
            },
        ]
        issues = validate_process(process)
        self.assertTrue(any("must use exactly one strategy" in item for item in issues))

    def test_preview_flags_unmapped_removal_and_inconsistent_mapping(self) -> None:
        current = tailor_profile({"task_type": "software"})
        candidate = deepcopy(current)
        candidate["deliverables"] = [
            item
            for item in candidate["deliverables"]
            if item["id"] != "software.architecture"
        ]
        candidate["migrations"] = [
            {
                "from": "legacy.record",
                "to": "software.release_candidate",
                "strategy": "replace",
                "reason": "First target.",
                "preserve_history": True,
            },
            {
                "from": "legacy.record",
                "to": "software.verification_report",
                "strategy": "replace",
                "reason": "Second target.",
                "preserve_history": True,
            },
        ]
        ambiguous = preview_process_diff(current, candidate)["ambiguous"]
        self.assertTrue(any(item["kind"] == "unmapped_removal" for item in ambiguous))
        self.assertTrue(any(item["kind"] == "one_to_many" for item in ambiguous))


if __name__ == "__main__":
    unittest.main()

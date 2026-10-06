from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ipdctl.i18n import get_translator
from ipdctl.process_extensions import load_process_extension
from ipdctl.process_model import (
    CAPABILITY_PATTERNS,
    ProcessModelError,
    _require_capability_policy_assets,
    capability_policy_directory,
    load_capability_policy,
    validate_capability_policy,
)
from ipdctl.refinement import (
    merge_refinement_plan,
    process_fingerprint,
    refinement_leaf_closure,
)
from ipdctl.tailoring import tailor_profile, validate_process


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_DELIVERABLES = {
    "sourced_component_integration": {
        "sourced_component.candidate_validation",
        "sourced_component.selection_decision",
        "sourced_component.integration_baseline",
    },
    "module_decomposition_and_verification": {
        "module.decomposition_baseline",
        "module.implementation_baseline",
        "module.verification_report",
    },
    "interface_contract_and_integration": {
        "interface.contract_baseline",
        "interface.integration_evidence",
        "interface.conformance_report",
    },
    "release_and_lifecycle_assurance": {
        "release.strategy",
        "release.candidate",
        "release.verification_report",
        "release.handover_package",
        "release.lifecycle_assurance_record",
    },
}

EXPECTED_SEMANTIC_RELATIONS = {
    "module_decomposition_and_verification": {
        (
            "module.decomposition_baseline",
            "module.implementation_baseline",
            "supports",
        ),
        (
            "module.verification_report",
            "module.implementation_baseline",
            "verifies",
        ),
    },
    "interface_contract_and_integration": {
        (
            "interface.contract_baseline",
            "interface.integration_evidence",
            "supports",
        ),
        (
            "interface.conformance_report",
            "interface.contract_baseline",
            "verifies",
        ),
    },
    "release_and_lifecycle_assurance": {
        ("release.strategy", "release.candidate", "supports"),
        ("release.verification_report", "release.candidate", "verifies"),
        (
            "release.handover_package",
            "release.lifecycle_assurance_record",
            "supports",
        ),
    },
}


def profile(*patterns: str) -> dict:
    return {
        "schema_version": "1.0",
        "project_name": "capability-catalog-test",
        "task_type": "software",
        "capability_patterns": list(patterns),
    }


class CapabilityCatalogTests(unittest.TestCase):
    def test_registry_assets_and_schema_enums_are_synchronized(self) -> None:
        directory = capability_policy_directory()
        self.assertEqual(
            {path.stem for path in directory.glob("*.yaml")},
            set(CAPABILITY_PATTERNS),
        )
        for pattern in CAPABILITY_PATTERNS:
            policy = load_capability_policy(pattern)
            self.assertEqual(validate_capability_policy(policy, pattern), [])

        task_schema = json.loads(
            (ROOT / "schemas" / "task_profile.schema.json").read_text(
                encoding="utf-8"
            )
        )
        capability_schema = json.loads(
            (ROOT / "schemas" / "capability_policy.schema.json").read_text(
                encoding="utf-8"
            )
        )
        process_schema = json.loads(
            (ROOT / "schemas" / "tailored_process.schema.json").read_text(
                encoding="utf-8"
            )
        )
        enums = (
            task_schema["$defs"]["capabilityPattern"]["enum"],
            capability_schema["properties"]["capability_pattern"]["enum"],
            process_schema["properties"]["profile"]["properties"]
            ["capability_patterns"]["items"]["enum"],
        )
        for values in enums:
            self.assertEqual(values, list(CAPABILITY_PATTERNS))

        activity_state = capability_schema["$defs"]["activity"]["properties"][
            "definition_state"
        ]
        self.assertEqual(activity_state["enum"], ["concrete", "abstract"])
        self.assertTrue(capability_schema["$defs"]["deliverable"]["allOf"])

        invalid_placeholder_activity = load_capability_policy(
            "interface_contract_and_integration"
        )
        invalid_placeholder_activity["activities"][0][
            "definition_state"
        ] = "placeholder"
        self.assertTrue(
            any(
                "placeholder nodes must require refinement" in issue
                for issue in validate_capability_policy(
                    invalid_placeholder_activity,
                    "interface_contract_and_integration",
                )
            )
        )

    def test_capabilities_are_explicit_opt_in(self) -> None:
        absent = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "capability-catalog-test",
                "task_type": "software",
            }
        )
        empty = tailor_profile(profile())
        self.assertEqual(absent, empty)
        self.assertEqual(empty["profile"]["capability_patterns"], [])
        capability_ids = set().union(*EXPECTED_DELIVERABLES.values())
        self.assertFalse(
            capability_ids & {item["id"] for item in empty["deliverables"]}
        )

    def test_project_concrete_deliverable_can_retain_v041_owner_opt_out(self) -> None:
        extension = load_process_extension(None)
        extension["activities"].append(
            {
                "id": "plan.compatibility_activity",
                "title": "Compatibility activity",
                "phase": "plan",
                "sequence": 90,
            }
        )
        extension["deliverables"].append(
            {
                "id": "compatibility.owner_optional",
                "title": "Owner-optional compatibility deliverable",
                "phase": "plan",
                "activity_id": "plan.compatibility_activity",
                "review_required": True,
                "depends_on": ["plan.integrated_plan"],
                "requires_artifact_owner": False,
            }
        )

        process = tailor_profile(profile(), extension)
        deliverable = next(
            item
            for item in process["deliverables"]
            if item["id"] == "compatibility.owner_optional"
        )
        self.assertFalse(deliverable["requires_artifact_owner"])
        self.assertEqual(validate_process(process), [])

    def test_each_catalog_entry_compiles_with_exact_provenance(self) -> None:
        for pattern in CAPABILITY_PATTERNS:
            with self.subTest(pattern=pattern):
                process = tailor_profile(profile(pattern))
                selected = {
                    item["id"]: item
                    for item in process["deliverables"]
                    if item.get("provenance")
                    == {"layer": "capability", "source_id": pattern}
                }
                self.assertEqual(set(selected), EXPECTED_DELIVERABLES[pattern])
                self.assertTrue(
                    all(item.get("maturity") for item in selected.values())
                )
                if pattern != "sourced_component_integration":
                    for item in selected.values():
                        expected_owner = (
                            item.get("definition_state", "concrete") == "concrete"
                        )
                        self.assertIs(
                            item.get("requires_artifact_owner"),
                            expected_owner,
                            item["id"],
                        )
                self.assertEqual(validate_process(process), [])

                if pattern in EXPECTED_SEMANTIC_RELATIONS:
                    relations = {
                        (item["source"], item["target"], item["relation"])
                        for item in process["dependencies"]
                        if item.get("provenance")
                        == {"layer": "capability", "source_id": pattern}
                        and item["relation"] != "depends_on"
                    }
                    self.assertEqual(
                        relations, EXPECTED_SEMANTIC_RELATIONS[pattern]
                    )

    def test_catalog_nodes_have_bilingual_display_messages(self) -> None:
        translators = (get_translator("en"), get_translator("zh-CN"))
        for pattern in CAPABILITY_PATTERNS:
            policy = load_capability_policy(pattern)
            keys = [
                *(f"workflow.activity.{item['id']}" for item in policy["activities"]),
                *(
                    f"workflow.deliverable.{item['id']}"
                    for item in policy["deliverables"]
                ),
                *(
                    f"workflow.criterion.{item['id']}"
                    for item in policy["checkpoint_criteria"]
                ),
            ]
            for translator in translators:
                for key in keys:
                    with self.subTest(pattern=pattern, locale=translator.locale, key=key):
                        self.assertTrue(translator.has_key(key), key)

    def test_all_capabilities_compile_in_canonical_order(self) -> None:
        forward = tailor_profile(profile(*CAPABILITY_PATTERNS))
        reverse = tailor_profile(profile(*reversed(CAPABILITY_PATTERNS)))
        self.assertEqual(forward, reverse)
        self.assertEqual(
            forward["profile"]["capability_patterns"],
            list(CAPABILITY_PATTERNS),
        )
        identifiers = [item["id"] for item in forward["deliverables"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(validate_process(forward), [])

    def test_missing_registry_asset_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                ProcessModelError, "capability policy resources do not match"
            ):
                _require_capability_policy_assets(Path(directory))

    def test_unregistered_policy_asset_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pattern in CAPABILITY_PATTERNS:
                (root / f"{pattern}.yaml").touch()
            (root / "unregistered_pattern.yaml").touch()
            with self.assertRaisesRegex(ProcessModelError, "unregistered"):
                _require_capability_policy_assets(root)

    def test_module_capability_root_can_be_refined_without_duplicate_config(self) -> None:
        selected_profile = profile("module_decomposition_and_verification")
        before = tailor_profile(selected_profile)
        root = next(
            item
            for item in before["deliverables"]
            if item["id"] == "module.implementation_baseline"
        )
        self.assertEqual(root["definition_state"], "placeholder")
        self.assertTrue(root["refinement_required"])
        self.assertFalse(root["requires_artifact_owner"])
        self.assertEqual(root["completion_policy"], "all_children_accepted")

        plan = {
            "schema_version": "1.0",
            "id": "refinement.module_implementation.v1",
            "root": "module.implementation_baseline",
            "mode": "expand",
            "base_process_fingerprint": process_fingerprint(before),
            "reason": "The approved decomposition identifies independently owned motion and perception modules.",
            "basis": ["evidence/module.decomposition_baseline/approval.md"],
            "activities": [],
            "deliverables": [
                {
                    "id": "module.motion_implementation",
                    "title": "Motion module implementation baseline",
                    "phase": "develop",
                    "activity_id": "develop.module_realization",
                    "review_required": True,
                    "depends_on": [
                        "module.decomposition_baseline",
                        "develop.solution_baseline",
                    ],
                    "refines": "module.implementation_baseline",
                },
                {
                    "id": "module.perception_implementation",
                    "title": "Perception module implementation baseline",
                    "phase": "develop",
                    "activity_id": "develop.module_realization",
                    "review_required": True,
                    "depends_on": [
                        "module.decomposition_baseline",
                        "develop.solution_baseline",
                    ],
                    "refines": "module.implementation_baseline",
                },
            ],
            "dependencies": [],
        }
        extension, applied = merge_refinement_plan(
            load_process_extension(None), plan, process=before
        )
        self.assertTrue(applied)
        materialized = next(
            item
            for item in extension["refinement_requirements"]
            if item["root"] == "module.implementation_baseline"
        )
        self.assertEqual(materialized["definition_state"], "placeholder")

        after = tailor_profile(selected_profile, extension)
        self.assertEqual(
            refinement_leaf_closure(after, "module.implementation_baseline"),
            ["module.motion_implementation", "module.perception_implementation"],
        )
        expanded_root = next(
            item
            for item in after["deliverables"]
            if item["id"] == "module.implementation_baseline"
        )
        self.assertEqual(expanded_root["definition_state"], "abstract")
        report = next(
            item
            for item in after["deliverables"]
            if item["id"] == "module.verification_report"
        )
        self.assertNotIn("module.implementation_baseline", report["depends_on"])
        self.assertTrue(
            {
                "module.motion_implementation",
                "module.perception_implementation",
            }.issubset(report["depends_on"])
        )
        self.assertEqual(validate_process(after), [])


if __name__ == "__main__":
    unittest.main()

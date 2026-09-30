from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from ipdctl.process_model import TASK_TYPES, normalize_task_type
from ipdctl.tailoring import (
    TailoringError,
    load_process,
    tailor_file,
    tailor_profile,
    validate_tailored_process,
)


ROOT = Path(__file__).resolve().parents[1]


class TailoringTests(unittest.TestCase):
    def test_all_six_task_types_produce_distinct_domain_extensions(self) -> None:
        expected_deliverables = {
            "software": "software.architecture",
            "hardware": "hardware.architecture",
            "embedded": "embedded.partition_specification",
            "robotics": "robotics.system_design",
            "ai_system": "ai_system.assurance_plan",
            "material_change": "material_change.impact_assessment",
        }
        signatures: set[tuple[str, ...]] = set()
        for task_type in TASK_TYPES:
            with self.subTest(task_type=task_type):
                result = tailor_profile(
                    {
                        "schema_version": "1.0",
                        "project_name": "demo",
                        "task_type": task_type,
                    }
                )
                self.assertEqual(result["profile"]["task_types"], [task_type])
                self.assertEqual(
                    [phase["id"] for phase in result["phases"]],
                    ["concept", "plan", "develop", "qualify", "launch", "lifecycle"],
                )
                deliverable_ids = tuple(item["id"] for item in result["deliverables"])
                self.assertIn(expected_deliverables[task_type], deliverable_ids)
                self.assertEqual(validate_tailored_process(result), [])
                signatures.add(deliverable_ids)
        self.assertEqual(len(signatures), len(TASK_TYPES))

    def test_space_and_hyphen_aliases_are_canonicalized_and_deduplicated(self) -> None:
        result = tailor_profile(
            {
                "schema_version": "1.0",
                "project": {"name": "hybrid"},
                "task_type": "AI system",
                "task_types": ["ai-system", "material change", "material-change"],
            }
        )
        self.assertEqual(result["profile"]["name"], "hybrid")
        self.assertEqual(
            result["profile"]["task_types"], ["ai_system", "material_change"]
        )
        self.assertEqual(normalize_task_type("material-change"), "material_change")

    def test_generation_and_file_serialization_are_deterministic(self) -> None:
        profile = {
            "schema_version": "1.0",
            "project_name": "deterministic",
            "task_types": ["robotics", "software"],
        }
        first = tailor_profile(profile)
        second = tailor_profile(deepcopy(profile))
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "task_profile.yaml"
            profile_path.write_text(
                "schema_version: '1.0'\n"
                "project_name: deterministic\n"
                "task_types: [robotics, software]\n",
                encoding="utf-8",
            )
            first_path = root / "first.yaml"
            second_path = root / "second.yaml"
            self.assertEqual(tailor_file(profile_path, first_path), first)
            tailor_file(profile_path, second_path)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(load_process(first_path), first)

    def test_unknown_task_type_and_unsafe_yaml_are_rejected(self) -> None:
        with self.assertRaisesRegex(TailoringError, "unknown task type"):
            tailor_profile({"task_type": "spacecraft"})

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "unsafe.yaml"
            source.write_text(
                "!!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(TailoringError, "invalid YAML"):
                tailor_file(source, Path(directory) / "out.yaml")

    def test_canonical_phase_order_cannot_be_resequenced(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "phase-order",
                "task_type": "software",
            }
        )
        process["phases"][1]["sequence"] = 99
        self.assertTrue(
            any(
                "canonical concept-to-lifecycle order" in issue
                for issue in validate_tailored_process(process)
            )
        )

    def test_every_phase_requires_its_canonical_tr_dcp_and_gates(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "governance-controls",
                "task_type": "software",
            }
        )
        mutations = {
            "technical review": lambda value: value["technical_reviews"].pop(0),
            "decision checkpoint": lambda value: value[
                "decision_checkpoints"
            ].pop(0),
            "TR gate": lambda value: value["gates"].pop(0),
            "DCP gate": lambda value: value["gates"].pop(1),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                broken = deepcopy(process)
                mutate(broken)
                issues = validate_tailored_process(broken)
                self.assertTrue(
                    any("missing canonical" in issue for issue in issues),
                    issues,
                )

    def test_canonical_checkpoint_links_and_phase_deliverable_sets_are_fixed(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "checkpoint-contract",
                "task_type": "software",
            }
        )
        mutations = {
            "TR phase": (
                lambda value: value["technical_reviews"][0].update(phase="plan"),
                ".phase: must equal 'concept'",
            ),
            "DCP gate link": (
                lambda value: value["decision_checkpoints"][0].update(
                    gate_id="gate.dcp.plan"
                ),
                ".gate_id: must equal 'gate.dcp.concept'",
            ),
            "TR required set": (
                lambda value: value["technical_reviews"][0][
                    "required_deliverables"
                ].pop(),
                "complete deliverable set",
            ),
            "DCP required set": (
                lambda value: value["decision_checkpoints"][0][
                    "required_deliverables"
                ].append("plan.integrated_plan"),
                "complete deliverable set",
            ),
        }
        for label, (mutate, expected) in mutations.items():
            with self.subTest(label=label):
                broken = deepcopy(process)
                mutate(broken)
                issues = validate_tailored_process(broken)
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_canonical_gate_contract_cannot_be_weakened_or_relinked(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "gate-contract",
                "task_type": "software",
            }
        )
        mutations = {
            "phase": (
                lambda gate: gate.update(phase="plan"),
                ".phase: must equal 'concept'",
            ),
            "checkpoint link": (
                lambda gate: gate.update(checkpoint_id="tr.plan"),
                ".checkpoint_id: must equal 'tr.concept'",
            ),
            "kind": (lambda gate: gate.update(kind="Gate"), ".kind: must equal 'TR'"),
            "required set": (
                lambda gate: gate["required_deliverables"].pop(),
                "complete deliverable set",
            ),
            "review": (
                lambda gate: gate.update(review_required=False),
                ".review_required: must equal true",
            ),
            "approval": (
                lambda gate: gate.update(final_approval="agent"),
                ".final_approval: must equal 'authorized_human'",
            ),
        }
        for label, (mutate, expected) in mutations.items():
            with self.subTest(label=label):
                broken = deepcopy(process)
                mutate(broken["gates"][0])
                issues = validate_tailored_process(broken)
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_canonical_gate_order_cannot_be_reversed(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "gate-order",
                "task_type": "software",
            }
        )
        process["gates"][0], process["gates"][1] = (
            process["gates"][1],
            process["gates"][0],
        )
        issues = validate_tailored_process(process)
        self.assertTrue(
            any("TR before DCP" in issue for issue in issues),
            issues,
        )

    def test_additional_generic_gate_cannot_replace_canonical_controls(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "generic-gate",
                "task_type": "software",
            }
        )
        process["gates"].append(
            {
                "id": "gate.concept.security",
                "title": "Concept Security Gate",
                "kind": "Gate",
                "phase": "concept",
                "checkpoint_id": "tr.concept",
                "required_deliverables": [
                    item["id"]
                    for item in process["deliverables"]
                    if item["phase"] == "concept"
                ],
                "review_required": True,
                "final_approval": "authorized_human",
            }
        )
        self.assertEqual(validate_tailored_process(process), [])

        without_tr = deepcopy(process)
        without_tr["gates"] = [
            gate for gate in without_tr["gates"] if gate["id"] != "gate.tr.concept"
        ]
        self.assertTrue(
            any(
                "missing canonical gate 'gate.tr.concept'" in issue
                for issue in validate_tailored_process(without_tr)
            )
        )

    def test_dependency_edges_match_deliverables_and_invalid_graphs_are_reported(self) -> None:
        process = tailor_profile(
            {
                "schema_version": "1.0",
                "project_name": "dependency-check",
                "task_types": list(TASK_TYPES),
            }
        )
        expected = {
            (deliverable["id"], prerequisite, "depends_on")
            for deliverable in process["deliverables"]
            for prerequisite in deliverable["depends_on"]
        }
        actual = {
            (edge["source"], edge["target"], edge["relation"])
            for edge in process["dependencies"]
        }
        self.assertEqual(actual, expected)

        broken = deepcopy(process)
        broken["deliverables"][0]["depends_on"] = ["missing"]
        broken["dependencies"].append(
            {
                "source": broken["deliverables"][0]["id"],
                "target": "missing",
                "relation": "depends_on",
            }
        )
        issues = validate_tailored_process(broken)
        self.assertTrue(any("unknown deliverable 'missing'" in issue for issue in issues))

        cyclic = deepcopy(process)
        first = cyclic["deliverables"][0]["id"]
        second = cyclic["deliverables"][1]["id"]
        cyclic["deliverables"][0]["depends_on"] = [second]
        cyclic["deliverables"][1]["depends_on"] = [first]
        cyclic["dependencies"] = [
            edge
            for edge in cyclic["dependencies"]
            if edge["source"] not in {first, second}
        ] + [
            {"source": first, "target": second, "relation": "depends_on"},
            {"source": second, "target": first, "relation": "depends_on"},
        ]
        self.assertTrue(
            any("dependency cycle detected" in issue for issue in validate_tailored_process(cyclic))
        )

    def test_validator_reports_malformed_ids_without_crashing(self) -> None:
        process = tailor_profile({"task_type": "software"})
        del process["deliverables"][0]["id"]
        process["profile"]["task_types"] = {"software": True}
        issues = validate_tailored_process(process)
        self.assertTrue(any("deliverables[0].id" in issue for issue in issues))
        self.assertTrue(any("profile.task_types: must be an array" in issue for issue in issues))

    def test_schema_files_are_valid_json_and_cover_required_collections(self) -> None:
        task_schema = json.loads(
            (ROOT / "schemas" / "task_profile.schema.json").read_text(encoding="utf-8")
        )
        process_schema = json.loads(
            (ROOT / "schemas" / "tailored_process.schema.json").read_text(
                encoding="utf-8"
            )
        )
        runtime_schema = json.loads(
            (ROOT / "schemas" / "agent_runtime.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("task_types", task_schema["properties"])
        self.assertEqual(
            set(process_schema["required"]),
            {
                "schema_version",
                "profile",
                "phases",
                "technical_reviews",
                "decision_checkpoints",
                "gates",
                "activities",
                "deliverables",
                "dependencies",
                "review_requirements",
            },
        )
        claim_schema = runtime_schema["properties"]["events"]["items"]
        self.assertEqual(claim_schema["properties"]["at"]["format"], "date-time")
        self.assertEqual(
            set(claim_schema["allOf"][0]["then"]["required"]),
            {"deliverable", "actor", "state_revision"},
        )
        self.assertEqual(
            set(claim_schema["allOf"][1]["then"]["required"]),
            {"from_phase", "to_phase", "state_revision"},
        )


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

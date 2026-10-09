from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dashboard_golden_test.py"
SPEC = importlib.util.spec_from_file_location("dashboard_golden_test", SCRIPT_PATH)
assert SPEC and SPEC.loader
golden = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(golden)


def _legacy_payload() -> dict:
    return {
        "schema_version": "1.4",
        "stages": {
            "concept": {
                "name": "Concept",
                "nodes": [
                    {"id": "D-001", "title": "Problem Definition", "status": "accepted"},
                    {"id": "D-002", "title": "Concept Architecture", "status": "in_progress"},
                ],
                "edges": [{"from": "D-001", "to": "D-002"}],
                "external_prerequisites": [{"id": "EXT-1"}],
            },
            "plan": {
                "name": "Plan",
                "nodes": {"D-003": {"title": "Delivery Plan", "status": "planned"}},
                "edges": [],
                "external_prerequisites": {},
            },
        },
    }


class DashboardGoldenHarnessTests(unittest.TestCase):
    def test_locate_and_normalize_legacy_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            example = Path(directory) / "quadruped_perception_fusion"
            generated = example / "generated"
            generated.mkdir(parents=True)
            graph_path = generated / "deliverable_dependency_graph.json"
            graph_path.write_text(json.dumps(_legacy_payload()), encoding="utf-8")

            self.assertEqual(golden.locate_legacy_graph(example), graph_path.resolve())
            self.assertEqual(golden.locate_legacy_graph(generated), graph_path.resolve())
            self.assertEqual(golden.locate_legacy_graph(graph_path), graph_path.resolve())

        graph, statistics = golden.normalize_legacy_graph(_legacy_payload())
        self.assertEqual(
            statistics,
            {
                "nodes": 3,
                "internal_edges": 1,
                "external_prerequisites": 1,
                "stages": 2,
            },
        )
        self.assertEqual(
            {node["id"] for node in graph["nodes"]},
            {"concept:D-001", "concept:D-002", "plan:D-003"},
        )
        self.assertEqual(graph["edges"][0]["source"], "concept:D-001")
        self.assertEqual(graph["edges"][0]["target"], "concept:D-002")
        self.assertEqual(graph["nodes"][0]["title"], "Problem Definition")

    def test_render_is_output_only_and_reports_bbox_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "legacy" / "generated" / "deliverable_dependency_graph.json"
            source.parent.mkdir(parents=True)
            original = json.dumps(_legacy_payload())
            source.write_text(original, encoding="utf-8")
            graph, _ = golden.normalize_legacy_graph(_legacy_payload())
            destination = root / "current" / "golden.svg"

            def fake_renderer(graph_data, **kwargs):
                self.assertEqual(len(graph_data["nodes"]), 3)
                self.assertIsNone(kwargs["phase"])
                return """<svg xmlns="http://www.w3.org/2000/svg">
                  <g data-node-id="concept:D-001" data-phase="concept" data-x="0" data-y="0" data-width="80" data-height="40" />
                  <g data-node-id="concept:D-002" data-phase="concept" data-x="100" data-y="0" data-width="80" data-height="40" />
                </svg>"""

            result = golden.render_legacy_svg(graph, destination, renderer=fake_renderer)
            self.assertTrue(result["xml_valid"])
            self.assertFalse(result["graphviz_signature"])
            self.assertEqual(result["bbox_nodes"], 2)
            self.assertEqual(result["same_lane_overlaps"], [])
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertEqual(list(source.parent.iterdir()), [source])
            self.assertTrue(destination.exists())

    def test_inventory_dashboard_inspection_and_english_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dashboard = root / "dashboard"
            for relative in golden.REQUIRED_DASHBOARD_FILES:
                path = dashboard / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".svg":
                    if relative in {
                        "assets/deliverable_dependency.svg",
                        "phases/concept.svg",
                    }:
                        path.write_text(
                            '''<svg xmlns="http://www.w3.org/2000/svg">
                              <g data-node-id="D-0" data-phase="concept" data-x="100" data-y="0" data-width="80" data-height="40" />
                              <g data-node-id="D-1" data-phase="plan" data-x="0" data-y="0" data-width="80" data-height="40" />
                              <path data-source="D-0" data-target="D-1" data-relation="depends_on" data-visual-source="D-1" data-visual-target="D-0" />
                              <text>Legend</text><text>Prerequisite → Dependent</text>
                            </svg>''',
                            encoding="utf-8",
                        )
                    elif relative == "phases/plan.svg":
                        path.write_text(
                            '''<svg xmlns="http://www.w3.org/2000/svg">
                              <g data-node-id="D-1" data-phase="plan" data-x="0" data-y="0" data-width="80" data-height="40" />
                            </svg>''',
                            encoding="utf-8",
                        )
                    else:
                        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
                elif relative == "data/graph.json":
                    path.write_text(
                        json.dumps(
                            {
                                "relation_types": [
                                    "depends_on",
                                    "supports",
                                    "verifies",
                                    "supersedes",
                                    "refines",
                                ],
                                "nodes": [
                                    {"id": "D-0", "type": "Deliverable", "phase": "concept", "status": "planned"},
                                    {"id": "D-1", "type": "Deliverable", "phase": "plan", "status": "planned"},
                                ],
                                "edges": [{"source": "D-0", "target": "D-1", "relation": "depends_on"}],
                            }
                        ),
                        encoding="utf-8",
                    )
                elif relative == "data/state.json":
                    path.write_text(
                        json.dumps(
                            {
                                "project": {"current": {"phase": "concept"}},
                                "deliverables": [
                                    {"id": "D-0", "phase": "concept", "depends_on": ["D-1"]},
                                    {"id": "D-1", "phase": "plan", "depends_on": []},
                                ]
                            }
                        ),
                        encoding="utf-8",
                    )
                elif path.suffix == ".json":
                    path.write_text("{}", encoding="utf-8")
                elif relative == "index.html":
                    path.write_text(
                        "<html><script>location.hash; addEventListener('hashchange', openDetail);</script>"
                        "<a href='#node=Deliverable:D-1'>Detail</a> Dependencies Evidence Review History "
                        "Current Phase Waiting on Prerequisites Actionability Unmet Prerequisites"
                        "<aside id=\"details\"><div id=\"detail-body\"></div></aside></html>",
                        encoding="utf-8",
                    )
                else:
                    path.write_text("<html>Back to dashboard Matrix</html>", encoding="utf-8")

            inspected = golden.inspect_dashboard(dashboard)
            self.assertTrue(inspected["required_files_present"])
            self.assertEqual(inspected["svg_count"], 8)
            self.assertEqual(inspected["html_count"], 3)
            self.assertEqual(inspected["xml_errors"], [])
            self.assertEqual(inspected["language_violations"], [])
            self.assertEqual(
                inspected["declared_relations"],
                ["depends_on", "refines", "supersedes", "supports", "verifies"],
            )
            self.assertTrue(all(inspected["interactions"].values()))
            self.assertTrue(inspected["locale_markers_present"])
            self.assertTrue(inspected["dependency_contract"]["only_depends_on"])
            self.assertTrue(
                inspected["dependency_contract"]["canonical_endpoints_match_graph"]
            )
            self.assertTrue(
                inspected["dependency_contract"]["projection_preserves_contract"]
            )
            self.assertTrue(inspected["dependency_contract"]["execution_order"])
            self.assertTrue(inspected["dependency_contract"]["graph_matches_state"])
            self.assertTrue(inspected["dependency_contract"]["svg_covers_state"])
            self.assertTrue(inspected["dependency_contract"]["per_view_complete"])

            results = [
                {"name": f"Synthetic check {index:02d}", "passed": True, "evidence": "complete"}
                for index in range(1, 28)
            ]
            locale_run = {
                "golden_render": {},
                "profiles": {},
                "current": inspected,
                "results": results,
            }
            report = golden.build_report(
                root / "legacy" / "generated" / "deliverable_dependency_graph.json",
                {"files": 6, "html": 1, "json": 1, "markdown": 1, "svg": 3, "png": 0},
                {"nodes": 286, "internal_edges": 144, "external_prerequisites": 31},
                {
                    "dependency_graph_sha256": "a" * 64,
                    "inventory_sha256": "b" * 64,
                    "inventory_entries": 6,
                },
                {"en": locale_run, "zh-CN": locale_run},
            )
            self.assertIn("output-derived structural renderer test", report)
            self.assertIn("same-source end-to-end reproduction", report)
            self.assertIn("Dependency graph SHA-256: `" + "a" * 64 + "`", report)
            self.assertIn("Generated inventory SHA-256: `" + "b" * 64 + "`", report)
            self.assertIn("en: 27/27; zh-CN: 27/27", report)
            self.assertEqual(report.count("**PASS — 27 of 27 checks passed.**"), 2)
            self.assertEqual(report.count("| PASS | Synthetic check"), 54)
            self.assertIsNone(golden._CJK_RE.search(report))

            graph_path = dashboard / "data" / "graph.json"
            graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
            graph_payload["edges"] = [
                {"source": "D-1", "target": "D-0", "relation": "depends_on"}
            ]
            graph_path.write_text(json.dumps(graph_payload), encoding="utf-8")
            reversed_graph = golden.inspect_dashboard(dashboard)
            self.assertFalse(
                reversed_graph["dependency_contract"]["graph_matches_state"]
            )

            graph_payload["edges"] = [
                {"source": "D-0", "target": "D-1", "relation": "depends_on"}
            ]
            graph_path.write_text(json.dumps(graph_payload), encoding="utf-8")
            dependency_svg = dashboard / "phases" / "concept.svg"
            dependency_svg.write_text(
                '''<svg xmlns="http://www.w3.org/2000/svg">
                  <g data-node-id="D-0" data-phase="concept" data-x="100" data-y="0" data-width="80" data-height="40" />
                  <text>Legend</text><text>Prerequisite → Dependent</text>
                </svg>''',
                encoding="utf-8",
            )
            missing_svg_edge = golden.inspect_dashboard(dashboard)
            self.assertTrue(missing_svg_edge["dependency_contract"]["svg_covers_state"])
            self.assertFalse(
                missing_svg_edge["dependency_contract"]["per_view_complete"]
            )

    def test_fixture_fingerprints_identify_graph_and_full_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "generated"
            generated.mkdir()
            graph_path = generated / "deliverable_dependency_graph.json"
            graph_bytes = b'{"stages": {}}\n'
            graph_path.write_bytes(graph_bytes)
            nested = generated / "deliverable_graphs" / "plan.svg"
            nested.parent.mkdir()
            nested.write_text("<svg/>", encoding="utf-8")

            first = golden.legacy_fixture_fingerprints(generated, graph_path)
            second = golden.legacy_fixture_fingerprints(generated, graph_path)
            self.assertEqual(first, second)
            self.assertEqual(
                first["dependency_graph_sha256"],
                hashlib.sha256(graph_bytes).hexdigest(),
            )
            self.assertEqual(first["inventory_entries"], 2)

            nested.write_text("<svg><title>changed</title></svg>", encoding="utf-8")
            changed_inventory = golden.legacy_fixture_fingerprints(generated, graph_path)
            self.assertEqual(
                changed_inventory["dependency_graph_sha256"],
                first["dependency_graph_sha256"],
            )
            self.assertNotEqual(changed_inventory["inventory_sha256"], first["inventory_sha256"])

    def test_default_run_is_bilingual_and_aggregates_27_checks_per_locale(self) -> None:
        self.assertEqual(
            golden.parse_args(["--legacy-root", "legacy"]).locale,
            "both",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "legacy" / "generated"
            generated.mkdir(parents=True)
            graph_path = generated / "deliverable_dependency_graph.json"
            graph_path.write_text(json.dumps(_legacy_payload()), encoding="utf-8")
            report_path = root / "report.md"
            profile = {
                "software": {
                    "dashboard_root": root / "dashboard",
                    "commands": [],
                    "passed": True,
                }
            }

            def inspection(_dashboard_root, locale="en"):
                return {"locale": locale, "structure_fingerprint": f"fingerprint-{locale}"}

            def checks(*_args, **_kwargs):
                return [
                    {"name": f"Check {index:02d}", "passed": True, "evidence": "ok"}
                    for index in range(1, 28)
                ]

            with (
                mock.patch.object(
                    golden,
                    "render_legacy_svg",
                    return_value={"xml_valid": True},
                ) as render,
                mock.patch.object(golden, "run_cli_profiles", return_value=profile) as profiles,
                mock.patch.object(golden, "inspect_dashboard", side_effect=inspection),
                mock.patch.object(golden, "evaluate", side_effect=checks),
            ):
                passed, report = golden.run(
                    root / "legacy",
                    root / "output",
                    report_path,
                )

            self.assertTrue(passed)
            self.assertEqual([call.kwargs["locale"] for call in render.call_args_list], ["en", "zh-CN"])
            self.assertEqual([call.kwargs["locale"] for call in profiles.call_args_list], ["en", "zh-CN"])
            self.assertIn("en: 27/27; zh-CN: 27/27", report)
            self.assertEqual(report_path.read_text(encoding="utf-8"), report)

    def test_evaluate_contract_is_27_checks_including_all_task_types(self) -> None:
        profiles = {
            task_type: {"passed": True, "commands": []}
            for task_type in golden.TASK_TYPES
        }
        current = {
            "required_files_present": True,
            "file_count": 16,
            "svg_count": 9,
            "html_count": 3,
            "xml_errors": [],
            "graphviz_files": [],
            "same_lane_overlaps": {},
            "language_violations": [],
            "unresolved_message_keys": [],
            "locale": "en",
            "manifest_locale": "en",
            "locale_markers_present": True,
            "interactions": {
                "node_links": True,
                "hash_navigation": True,
                "detail_panel": True,
                "dependencies": True,
                "evidence": True,
                "review_history": True,
            },
            "node_types": ["Phase", "TR", "DCP", "Gate", "Activity", "Deliverable"],
            "declared_relations": [
                "depends_on",
                "supports",
                "verifies",
                "supersedes",
                "refines",
            ],
            "relations": ["depends_on"],
            "dependency_contract": {
                "rendered_relations": ["depends_on"],
                "dependency_edges": [
                    {
                        "source": "D-1",
                        "target": "D-0",
                        "relation": "depends_on",
                        "visual_source": "D-0",
                        "visual_target": "D-1",
                    }
                ],
                "only_depends_on": True,
                "canonical_endpoints_match_graph": True,
                "graph_matches_state": True,
                "svg_covers_state": True,
                "per_view_complete": True,
                "view_mismatches": [],
                "projection_preserves_contract": True,
                "execution_order": True,
            },
            "statuses": ["planned"],
        }
        results = golden.evaluate(
            {"files": 6, "html": 1, "json": 1, "markdown": 1, "svg": 3, "png": 0},
            {"nodes": 286, "internal_edges": 144, "external_prerequisites": 31},
            {
                "xml_valid": True,
                "graphviz_signature": False,
                "bbox_nodes": 286,
                "same_lane_overlaps": [],
            },
            profiles,
            current,
        )
        self.assertEqual(len(results), 27)
        self.assertTrue(all(result["passed"] for result in results))
        self.assertEqual(
            [result["name"] for result in results if result["name"].startswith("CLI lifecycle:")],
            [f"CLI lifecycle: {task_type}" for task_type in golden.TASK_TYPES],
        )

        reversed_graph = json.loads(json.dumps(current))
        reversed_graph["dependency_contract"]["graph_matches_state"] = False
        reversed_results = golden.evaluate(
            {"files": 6, "html": 1, "json": 1, "markdown": 1, "svg": 3, "png": 0},
            {"nodes": 286, "internal_edges": 144, "external_prerequisites": 31},
            {
                "xml_valid": True,
                "graphviz_signature": False,
                "bbox_nodes": 286,
                "same_lane_overlaps": [],
            },
            profiles,
            reversed_graph,
        )
        self.assertFalse(
            next(
                result["passed"]
                for result in reversed_results
                if result["name"]
                == "Dependency projection is prerequisite to dependent"
            )
        )

        missing_svg_edge = json.loads(json.dumps(current))
        missing_svg_edge["dependency_contract"]["svg_covers_state"] = False
        missing_results = golden.evaluate(
            {"files": 6, "html": 1, "json": 1, "markdown": 1, "svg": 3, "png": 0},
            {"nodes": 286, "internal_edges": 144, "external_prerequisites": 31},
            {
                "xml_valid": True,
                "graphviz_signature": False,
                "bbox_nodes": 286,
                "same_lane_overlaps": [],
            },
            profiles,
            missing_svg_edge,
        )
        self.assertFalse(
            next(
                result["passed"]
                for result in missing_results
                if result["name"] == "Dependency view isolates dependency facts"
            )
        )


if __name__ == "__main__":
    unittest.main()

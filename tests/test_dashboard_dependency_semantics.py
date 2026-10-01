from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
import tempfile
from pathlib import Path

from ipdctl.dashboard import render_dashboard
from ipdctl.dashboard_svg import render_dependency_svg, render_svg


SVG = "{http://www.w3.org/2000/svg}"


def _graph(edges: list[dict[str, str]], *node_ids: str) -> dict[str, object]:
    return {
        "nodes": [
            {
                "id": node_id,
                "type": "Deliverable",
                "title": node_id,
                "phase": "develop",
                "status": "planned",
            }
            for node_id in node_ids
        ],
        "edges": edges,
    }


def _parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _node_x(root: ET.Element) -> dict[str, float]:
    return {
        node.attrib["data-node-id"]: float(node.attrib["data-x"])
        for node in root.findall(f".//{SVG}g[@data-node-id]")
    }


class DashboardDependencySemanticsTests(unittest.TestCase):
    def test_dependency_keeps_canonical_endpoints_and_draws_prerequisite_first(self) -> None:
        root = _parse(
            render_dependency_svg(
                _graph(
                    [
                        {
                            "source": "dependent",
                            "target": "prerequisite",
                            "relation": "depends_on",
                        }
                    ],
                    "dependent",
                    "prerequisite",
                )
            )
        )

        edge = root.find(f".//{SVG}path[@data-relation='depends_on']")
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertEqual(edge.attrib["data-source"], "dependent")
        self.assertEqual(edge.attrib["data-target"], "prerequisite")
        self.assertEqual(edge.attrib["data-visual-source"], "prerequisite")
        self.assertEqual(edge.attrib["data-visual-target"], "dependent")

        positions = _node_x(root)
        self.assertLess(positions["prerequisite"], positions["dependent"])
        self.assertIn("Prerequisite → Dependent", "".join(root.itertext()))

    def test_three_node_chain_is_laid_out_in_execution_order(self) -> None:
        root = _parse(
            render_dependency_svg(
                _graph(
                    [
                        {"source": "A", "target": "B", "relation": "depends_on"},
                        {"source": "B", "target": "C", "relation": "depends_on"},
                    ],
                    "A",
                    "B",
                    "C",
                )
            )
        )

        positions = _node_x(root)
        self.assertLess(positions["C"], positions["B"])
        self.assertLess(positions["B"], positions["A"])

    def test_traceability_relations_do_not_change_dependency_rank(self) -> None:
        dependency = {"source": "A", "target": "B", "relation": "depends_on"}
        base_graph = _graph([dependency], "A", "B", "C")
        mixed_graph = _graph(
            [
                dependency,
                {"source": "A", "target": "C", "relation": "supports"},
                {"source": "C", "target": "B", "relation": "verifies"},
                {"source": "B", "target": "C", "relation": "supersedes"},
            ],
            "A",
            "B",
            "C",
        )

        base = _node_x(_parse(render_svg(base_graph, title="base", layout="dependency")))
        mixed = _node_x(_parse(render_svg(mixed_graph, title="mixed", layout="dependency")))
        self.assertEqual(base, mixed)

    def test_dependency_view_filters_non_dependency_relations_by_default(self) -> None:
        root = _parse(
            render_dependency_svg(
                _graph(
                    [
                        {"source": "A", "target": "B", "relation": "depends_on"},
                        {"source": "A", "target": "C", "relation": "supports"},
                        {"source": "C", "target": "B", "relation": "verifies"},
                        {"source": "B", "target": "C", "relation": "supersedes"},
                    ],
                    "A",
                    "B",
                    "C",
                )
            )
        )

        self.assertEqual(root.attrib["data-edge-count"], "1")
        rendered_relations = {
            edge.attrib["data-relation"]
            for edge in root.findall(f".//{SVG}path[@data-relation]")
        }
        self.assertEqual(rendered_relations, {"depends_on"})

    def test_dependency_view_excludes_activity_nodes(self) -> None:
        graph = _graph(
            [
                {
                    "source": "dependent",
                    "target": "prerequisite",
                    "relation": "depends_on",
                },
                {
                    "source": "activity",
                    "target": "dependent",
                    "relation": "supports",
                },
            ],
            "dependent",
            "prerequisite",
        )
        graph["nodes"].append(
            {
                "id": "activity",
                "type": "Activity",
                "title": "Activity",
                "phase": "develop",
                "status": "planned",
            }
        )

        root = _parse(render_dependency_svg(graph))
        self.assertEqual(set(_node_x(root)), {"dependent", "prerequisite"})

    def test_dashboard_preserves_recursive_cross_phase_prerequisites(self) -> None:
        deliverables = [
            {
                "id": "concept.input",
                "title": "Concept input",
                "phase": "concept",
                "status": "planned",
                "depends_on": [],
                "evidence": [],
                "reviews": [],
            },
            {
                "id": "plan.design",
                "title": "Plan design",
                "phase": "plan",
                "status": "planned",
                "depends_on": ["concept.input"],
                "evidence": [],
                "reviews": [],
            },
            {
                "id": "develop.build",
                "title": "Develop build",
                "phase": "develop",
                "status": "planned",
                "depends_on": ["plan.design"],
                "evidence": [],
                "reviews": [],
            },
        ]
        process = {
            "schema_version": "1.0",
            "profile": {"name": "Recursive dependencies"},
            "phases": [
                {"id": "concept", "title": "Concept", "sequence": 1},
                {"id": "plan", "title": "Plan", "sequence": 2},
                {"id": "develop", "title": "Develop", "sequence": 3},
            ],
            "deliverables": deliverables,
        }
        state = {
            "schema_version": "2.0",
            "revision": 1,
            "project": {
                "name": "Recursive dependencies",
                "phase": "develop",
                "workflow_step": "context",
            },
            "deliverables": deliverables,
            "gates": [],
        }

        with tempfile.TemporaryDirectory() as directory:
            render_dashboard(Path(directory), process, state)
            dashboard = Path(directory) / ".ipd" / "dashboard"
            for relative in (
                "assets/current_status_flow.svg",
                "assets/deliverable_dependency.svg",
                "phases/develop.svg",
            ):
                root = _parse((dashboard / relative).read_text(encoding="utf-8"))
                self.assertTrue(
                    {"concept.input", "plan.design", "develop.build"}.issubset(
                        set(_node_x(root))
                    ),
                    relative,
                )
                edges = {
                    (
                        edge.attrib["data-source"],
                        edge.attrib["data-target"],
                        edge.attrib["data-relation"],
                    )
                    for edge in root.findall(f".//{SVG}path[@data-relation]")
                }
                self.assertTrue(
                    {
                        ("develop.build", "plan.design", "depends_on"),
                        ("plan.design", "concept.input", "depends_on"),
                    }.issubset(edges),
                    relative,
                )


if __name__ == "__main__":
    unittest.main()

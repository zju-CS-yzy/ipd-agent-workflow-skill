import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from ipdctl.dashboard_html import render_index
from ipdctl.dashboard_model import build_dashboard_model
from ipdctl.i18n import get_translator


class DashboardProvenanceTests(unittest.TestCase):
    def _documents(self, locale="en"):
        process = {
            "schema_version": "2.0",
            "profile": {"name": "Capability project"},
            "phases": [
                {
                    "id": "concept",
                    "title": "Concept",
                    "sequence": 1,
                    "maturity": "defined",
                    "provenance": {"layer": "core", "source_id": "ipd-core"},
                }
            ],
            "activities": [
                {
                    "id": "concept.source_selection",
                    "title": "Source selection",
                    "phase": "concept",
                    "maturity": "selected",
                    "provenance": {
                        "layer": "capability",
                        "source_id": "sourced_component_integration",
                    },
                }
            ],
            "deliverables": [
                {
                    "id": "concept.candidate_evidence",
                    "title": "Candidate evidence",
                    "phase": "concept",
                    "activity_id": "concept.source_selection",
                    "depends_on": [],
                    "review_required": True,
                    "maturity": "selected",
                    "provenance": {
                        "layer": "capability",
                        "source_id": "sourced_component_integration",
                    },
                }
            ],
            "technical_reviews": [
                {
                    "id": "tr.concept",
                    "title": "Concept technical review",
                    "phase": "concept",
                    "required_deliverables": ["concept.candidate_evidence"],
                    "maturity": "defined",
                    "provenance": {"layer": "core", "source_id": "ipd-core"},
                    "criteria": [
                        {
                            "id": "criterion.sourced_component.candidate_validation",
                            "description": "Candidate validation evidence covers requirements, interfaces, constraints, and known risks.",
                            "evidence_required": True,
                        }
                    ],
                }
            ],
        }
        state = {
            "schema_version": "2.0",
            "revision": 3,
            "project": {
                "name": "Capability project",
                "phase": "concept",
                "current_tr": "tr.concept",
                "current_dcp": None,
                "current_gate": None,
                "workflow_step": "context",
            },
            "deliverables": [
                {
                    "id": "concept.candidate_evidence",
                    "title": "Candidate evidence",
                    "phase": "concept",
                    "status": "planned",
                    "depends_on": [],
                    "evidence": [],
                    "reviews": [],
                    "review_required": True,
                }
            ],
            "gates": [],
            "traceability": [],
        }
        return build_dashboard_model(
            process,
            state,
            {"active_claims": {}},
            translator=get_translator(locale),
            locale=locale,
        )

    def test_machine_documents_expose_provenance_maturity_and_criteria(self):
        state, graph = self._documents()

        deliverable = state["deliverables"][0]
        self.assertEqual(
            deliverable["provenance"],
            {
                "layer": "capability",
                "source_id": "sourced_component_integration",
            },
        )
        self.assertEqual(deliverable["maturity"], "selected")

        checkpoint = state["checkpoints"][0]
        self.assertEqual(checkpoint["provenance"]["layer"], "core")
        self.assertEqual(
            checkpoint["criteria"],
            [
                {
                    "id": "criterion.sourced_component.candidate_validation",
                    "description": "Candidate validation evidence covers requirements, interfaces, constraints, and known risks.",
                    "evidence_required": True,
                }
            ],
        )

        graph_deliverable = next(
            item for item in graph["nodes"] if item["type"] == "Deliverable"
        )
        self.assertEqual(graph_deliverable["provenance"], deliverable["provenance"])

    def test_interactive_details_render_provenance_and_criteria_bilingually(self):
        state, graph = self._documents()
        chinese_state, chinese_graph = self._documents("zh-CN")
        phase_files = {"concept": "phases/concept.svg"}

        english = render_index(
            state,
            graph,
            phase_files,
            translator=get_translator("en"),
        )
        chinese = render_index(
            chinese_state,
            chinese_graph,
            phase_files,
            translator=get_translator("zh-CN"),
        )

        self.assertIn("Provenance Layer", english)
        self.assertIn("Review Criteria", english)
        self.assertIn("sourced_component_integration", english)
        i18n = json.loads(
            re.search(
                r'<script id="ipd-i18n" type="application/json">(.*?)</script>',
                chinese,
                flags=re.S,
            ).group(1)
        )
        self.assertEqual(i18n["ui"]["provenance_layer"], "来源层")
        self.assertEqual(i18n["ui"]["criteria"], "评审准则")
        self.assertTrue(
            chinese_state["checkpoints"][0]["criteria"][0]["description"].startswith(
                "候选验证证据覆盖需求"
            )
        )
        self.assertIn("function showDetails", chinese)
        self.assertIn("label('nodeTypes'", chinese)
        self.assertIn("(phase|activity|tr|dcp|gate|deliverable)", chinese)
        self.assertEqual(i18n["nodeTypes"]["activity"], "活动")

    def test_legacy_nodes_without_provenance_remain_renderable(self):
        state, graph = build_dashboard_model(
            {
                "schema_version": "1.0",
                "profile": {"name": "Legacy"},
                "phases": [{"id": "concept", "title": "Concept", "sequence": 1}],
                "deliverables": [],
            },
            {
                "schema_version": "2.0",
                "revision": 0,
                "project": {"name": "Legacy", "phase": "concept"},
                "deliverables": [],
                "gates": [],
                "traceability": [],
            },
        )

        self.assertIsNone(state["phases"][0]["provenance"])
        self.assertIsNone(graph["nodes"][0]["provenance"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is not available")
    def test_interactive_javascript_is_valid_in_both_locales(self):
        phase_files = {"concept": "phases/concept.svg"}
        for locale in ("en", "zh-CN"):
            with self.subTest(locale=locale):
                state, graph = self._documents(locale)
                html = render_index(
                    state,
                    graph,
                    phase_files,
                    translator=get_translator(locale),
                )
                scripts = [
                    body
                    for attributes, body in re.findall(
                        r"<script([^>]*)>(.*?)</script>", html, flags=re.I | re.S
                    )
                    if "application/json" not in attributes
                ]
                self.assertTrue(scripts)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / f"dashboard-{locale}.js"
                    path.write_text("\n".join(scripts), encoding="utf-8")
                    result = subprocess.run(
                        [shutil.which("node"), "--check", str(path)],
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

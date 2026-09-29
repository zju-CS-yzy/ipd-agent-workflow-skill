from __future__ import annotations

import hashlib
import html
import json
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from ipdctl.dashboard import render_dashboard


STATUSES = (
    "planned",
    "in_progress",
    "ready_for_review",
    "in_review",
    "accepted",
    "rejected",
    "blocked",
    "superseded",
)


def process_fixture() -> dict:
    return {
        "schema_version": "1.0",
        "profile": {"name": "Demo <unsafe>", "task_types": ["software"]},
        "phases": [
            {"id": "concept", "title": "Concept", "sequence": 1},
            {"id": "develop", "title": "Develop", "sequence": 2},
        ],
        "technical_reviews": [
            {
                "id": "tr-design",
                "title": "Design TR",
                "phase": "concept",
                "sequence": 1,
                "gate_id": "gate-tr-design",
                "required_deliverables": ["accepted"],
            }
        ],
        "decision_checkpoints": [
            {
                "id": "dcp-concept",
                "title": "Concept DCP",
                "phase": "concept",
                "sequence": 2,
                "gate_id": "gate-dcp-concept",
                "required_deliverables": ["accepted"],
            }
        ],
        "gates": [
            {
                "id": "gate-tr-design",
                "title": "Design review gate",
                "kind": "TR",
                "phase": "concept",
                "checkpoint_id": "tr-design",
                "required_deliverables": ["accepted"],
                "review_required": True,
                "final_approval": "authorized_human",
            },
            {
                "id": "gate-dcp-concept",
                "title": "Concept decision gate",
                "kind": "DCP",
                "phase": "concept",
                "checkpoint_id": "dcp-concept",
                "required_deliverables": ["blocked"],
                "review_required": True,
                "final_approval": "authorized_human",
            },
            {
                "id": "gate-release",
                "title": "Release gate",
                "kind": "Gate",
                "phase": "concept",
                "required_deliverables": ["accepted"],
                "review_required": True,
                "final_approval": "authorized_human",
            },
        ],
        "activities": [
            {"id": "design", "title": "Design", "phase": "concept", "sequence": 1}
        ],
        "deliverables": [
            {
                "id": status,
                "title": (
                    '<script>alert("dashboard")</script>' if status == "planned" else status
                ),
                "phase": "concept",
                "activity_id": "design",
                "review_required": status in {"accepted", "ready_for_review", "in_review"},
                "depends_on": ["accepted"] if status == "in_progress" else [],
            }
            for status in STATUSES
        ]
        + [
            {
                "id": "future",
                "title": "Future deliverable",
                "phase": "develop",
                "activity_id": "implementation",
                "review_required": False,
                "depends_on": ["accepted"],
            }
        ],
        "dependencies": [
            {"source": "in_progress", "target": "accepted", "relation": "depends_on"},
            {"source": "planned", "target": "accepted", "relation": "supports"},
        ],
        "review_requirements": [
            {
                "id": "review-accepted",
                "subject_type": "deliverable",
                "subject_id": "accepted",
                "reviewer_type": "human",
                "authorization_required": True,
                "decision_required": True,
            }
        ],
    }


def state_fixture() -> dict:
    deliverables = []
    for status in STATUSES:
        item = {
            "id": status,
            "title": (
                '<script>alert("dashboard")</script>' if status == "planned" else status
            ),
            "status": status,
            "depends_on": ["accepted"] if status == "in_progress" else [],
            "evidence": ["evidence/accepted.md"] if status == "accepted" else [],
            "reviews": [],
        }
        if status == "blocked":
            item["blocked_reason"] = "missing prototype"
        if status == "superseded":
            item["replacement"] = "accepted"
        if status == "accepted":
            item["reviews"] = [
                {
                    "reviewer": "lead",
                    "reviewer_type": "human",
                    "authorized": True,
                    "decision": "approve",
                    "evidence": "reviews/accepted.md",
                }
            ]
        deliverables.append(item)
    deliverables.append(
        {
            "id": "future",
            "title": "Future deliverable",
            "status": "planned",
            "depends_on": ["accepted"],
            "evidence": [],
            "reviews": [],
        }
    )
    return {
        "schema_version": "2.0",
        "revision": 7,
        "project": {
            "name": "Demo <unsafe>",
            "phase": "concept",
            "workflow_step": "work",
            "current_tr": "tr-design",
            "current_dcp": "dcp-concept",
            "current_gate": "gate-release",
        },
        "claims": [],
        "deliverables": deliverables,
        "gates": [
            {
                "id": "gate-tr-design",
                "title": "Design review gate",
                "kind": "TR",
                "status": "approved",
                "required_deliverables": ["accepted"],
                "reviews": [
                    {
                        "reviewer": "chief engineer",
                        "reviewer_type": "human",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": "reviews/gate-tr-design.md",
                    }
                ],
            },
            {
                "id": "gate-dcp-concept",
                "title": "Concept decision gate",
                "kind": "DCP",
                "status": "planned",
                "required_deliverables": ["blocked"],
                "reviews": [
                    {
                        "reviewer": "review-agent",
                        "reviewer_type": "agent",
                        "authorized": True,
                        "decision": "approve",
                        "evidence": "reviews/agent-only.md",
                    }
                ],
            },
            {
                "id": "gate-release",
                "title": "Release gate",
                "kind": "Gate",
                "status": "ready",
                "required_deliverables": ["accepted"],
                "reviews": [],
            },
        ],
        "traceability": [
            {"source": "ready_for_review", "target": "accepted", "relation": "verifies"},
            {"source": "superseded", "target": "accepted", "relation": "supersedes"},
        ],
    }


class DashboardTests(unittest.TestCase):
    def test_renders_complete_manifest_and_consistent_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = render_dashboard(root, process_fixture(), state_fixture())
            dashboard = root / ".ipd" / "dashboard"

            expected = {"index.html", "manifest.json"}
            for view in (
                "ipd_process",
                "deliverable_dependency_graph",
                "deliverable_matrix",
                "gate_matrix",
            ):
                expected.update(f"{view}.{extension}" for extension in ("html", "json", "md"))
            self.assertEqual({item.name for item in dashboard.iterdir()}, expected)
            self.assertEqual(manifest["state_revision"], 7)
            self.assertEqual(manifest["process_schema_version"], "1.0")
            self.assertEqual(set(manifest["files"]), expected)

            for output in manifest["outputs"]:
                path = root / output["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), output["sha256"])

            markers = {
                "ipd_process": ("concept", "tr-design", "dcp-concept", "gate-release"),
                "deliverable_dependency_graph": ("planned", "accepted", "supersedes"),
                "deliverable_matrix": ("blocked", "missing prototype", "accepted"),
                "gate_matrix": ("gate-tr-design", "reviews/gate-tr-design.md", "approved"),
            }
            for view, expected_markers in markers.items():
                json_data = json.loads((dashboard / f"{view}.json").read_text(encoding="utf-8"))
                html_text = (dashboard / f"{view}.html").read_text(encoding="utf-8")
                markdown_text = (dashboard / f"{view}.md").read_text(encoding="utf-8")
                embedded_match = re.search(r"<pre>(.*?)</pre>", html_text, re.DOTALL)
                self.assertIsNotNone(embedded_match)
                embedded = json.loads(html.unescape(embedded_match.group(1)))
                self.assertEqual(embedded, json_data)
                for marker in expected_markers:
                    self.assertIn(marker, json.dumps(json_data, ensure_ascii=False))
                    self.assertIn(marker, html_text)
                    self.assertIn(marker, markdown_text)

    def test_graph_preserves_canonical_statuses_and_maps_display_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            dashboard = root / ".ipd" / "dashboard"
            graph = json.loads(
                (dashboard / "deliverable_dependency_graph.json").read_text(encoding="utf-8")
            )
            nodes = {item["id"]: item for item in graph["nodes"]}
            self.assertEqual(set(nodes), set(STATUSES))
            self.assertEqual({item["status"] for item in nodes.values()}, set(STATUSES))
            self.assertEqual(nodes["planned"]["display_status"], "not_started")
            self.assertEqual(nodes["accepted"]["display_status"], "approved")
            self.assertEqual(nodes["blocked"]["display_status"], "blocked")
            relations = {item["relation"] for item in graph["edges"]}
            self.assertEqual(relations, {"depends_on", "supports", "verifies", "supersedes"})

            raw_payload = '<script>alert("dashboard")</script>'
            encoded_payload = html.escape(raw_payload, quote=True)
            for path in dashboard.glob("*.html"):
                contents = path.read_text(encoding="utf-8")
                self.assertNotIn(raw_payload, contents)
            self.assertIn(encoded_payload, (dashboard / "deliverable_matrix.html").read_text(encoding="utf-8"))
            self.assertNotIn("Demo <unsafe>", (dashboard / "index.html").read_text(encoding="utf-8"))

    def test_gate_readiness_and_human_approval_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            data = json.loads(
                (root / ".ipd" / "dashboard" / "gate_matrix.json").read_text(
                    encoding="utf-8"
                )
            )
            gates = {item["id"]: item for item in data["gates"]}
            approved = gates["gate-tr-design"]
            self.assertTrue(approved["readiness"]["ready"])
            self.assertEqual(approved["approval"]["status"], "approved")
            self.assertTrue(approved["approval"]["authorized_human"])

            agent_only = gates["gate-dcp-concept"]
            self.assertFalse(agent_only["readiness"]["ready"])
            self.assertEqual(agent_only["blockers"], [{"deliverable": "blocked", "status": "blocked"}])
            self.assertEqual(agent_only["approval"]["status"], "pending")
            self.assertFalse(agent_only["approval"]["authorized_human"])

    def test_current_phase_graph_keeps_upstream_prerequisites(self) -> None:
        process = process_fixture()
        state = state_fixture()
        state["project"]["phase"] = "develop"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process, state)
            graph = json.loads(
                (
                    root
                    / ".ipd"
                    / "dashboard"
                    / "deliverable_dependency_graph.json"
                ).read_text(encoding="utf-8")
            )
        nodes = {item["id"]: item for item in graph["nodes"]}
        self.assertEqual(set(nodes), {"future", "accepted"})
        self.assertTrue(nodes["future"]["in_current_phase"])
        self.assertFalse(nodes["accepted"]["in_current_phase"])
        self.assertIn(
            {"source": "future", "target": "accepted", "relation": "depends_on"},
            graph["edges"],
        )

    def test_rendering_is_deterministic_and_does_not_mutate_sources(self) -> None:
        process = process_fixture()
        state = state_fixture()
        original_process = deepcopy(process)
        original_state = deepcopy(state)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_manifest = render_dashboard(root, process, state)
            dashboard = root / ".ipd" / "dashboard"
            first = {item.name: item.read_bytes() for item in dashboard.iterdir()}
            second_manifest = render_dashboard(root, process, state)
            second = {item.name: item.read_bytes() for item in dashboard.iterdir()}
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first, second)
        self.assertEqual(process, original_process)
        self.assertEqual(state, original_state)


if __name__ == "__main__":
    unittest.main()

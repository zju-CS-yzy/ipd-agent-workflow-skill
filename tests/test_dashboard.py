from __future__ import annotations

import hashlib
import html
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

from ipdctl.dashboard import render_dashboard
from ipdctl.dashboard_svg import _display_width, _wrap_text
from ipdctl.eligibility import eligibility_fingerprint
from ipdctl.i18n import get_translator
from ipdctl.project import sync_state_with_process
from ipdctl.state import create_initial_state
from ipdctl.tailoring import tailor_profile


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
NODE_TYPES = {"Phase", "TR", "DCP", "Gate", "Activity", "Deliverable"}
RELATIONS = {"depends_on", "supports", "verifies", "supersedes", "refines"}
SVG_NAMESPACE = {"svg": "http://www.w3.org/2000/svg"}
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def canonical_fixture() -> tuple[dict, dict]:
    process = tailor_profile(
        {
            "schema_version": "1.0",
            "project_name": "Dashboard Demo",
            "task_types": ["software"],
        }
    )
    state = sync_state_with_process(
        create_initial_state("Dashboard Demo", ["software"]), process
    )
    return process, state


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
            {"id": "design", "title": "Design", "phase": "concept", "sequence": 1},
            {
                "id": "implementation",
                "title": "Implementation",
                "phase": "develop",
                "sequence": 2,
            },
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
            {"source": "planned", "target": "accepted", "relation": "refines"},
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
            "phase": "concept",
            "activity_id": "design",
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
            "phase": "develop",
            "activity_id": "implementation",
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
            "workflow_step": "context",
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


def generated_files(dashboard: Path) -> dict[str, bytes]:
    return {
        path.relative_to(dashboard).as_posix(): path.read_bytes()
        for path in sorted(dashboard.rglob("*"))
        if path.is_file()
    }


def value_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def node_boxes(svg_path: Path) -> list[tuple[str, float, float, float, float]]:
    root = ET.parse(svg_path).getroot()
    return [
        (
            node.attrib["data-node-id"],
            float(node.attrib["data-x"]),
            float(node.attrib["data-y"]),
            float(node.attrib["data-width"]),
            float(node.attrib["data-height"]),
        )
        for node in root.findall(".//svg:g[@data-node-id]", SVG_NAMESPACE)
    ]


class DashboardTests(unittest.TestCase):
    def test_eligibility_fingerprint_ignores_derived_summary_counts(self) -> None:
        first = {
            "status": "passed",
            "eligible": True,
            "issues": [],
            "paths": {},
            "deliverables": {"concept.problem_definition": {"eligible": True}},
            "summary": {"changed_paths": 4, "ignored_paths": 4},
        }
        second = deepcopy(first)
        second["summary"] = {"changed_paths": 20, "ignored_paths": 20}

        self.assertEqual(
            eligibility_fingerprint(first), eligibility_fingerprint(second)
        )

    def assert_no_node_overlap(self, svg_path: Path) -> None:
        boxes = node_boxes(svg_path)
        self.assertTrue(boxes, svg_path)
        for index, (left_id, left_x, left_y, left_w, left_h) in enumerate(boxes):
            for right_id, right_x, right_y, right_w, right_h in boxes[index + 1 :]:
                separated = (
                    left_x + left_w <= right_x
                    or right_x + right_w <= left_x
                    or left_y + left_h <= right_y
                    or right_y + right_h <= left_y
                )
                self.assertTrue(
                    separated,
                    f"overlapping SVG nodes: {left_id} and {right_id} in {svg_path.name}",
                )

    def test_renders_complete_manifest_and_consistent_formats(self) -> None:
        process, state = canonical_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = render_dashboard(
                root,
                process,
                state,
                runtime={"active_claims": {}, "events": []},
            )
            dashboard = root / ".ipd" / "dashboard"
            required = {
                "index.html",
                "assets/ipd_flow.svg",
                "assets/current_status_flow.svg",
                "assets/deliverable_dependency.svg",
                "phases/concept.svg",
                "phases/plan.svg",
                "phases/develop.svg",
                "phases/qualify.svg",
                "phases/launch.svg",
                "matrices/deliverable_matrix.html",
                "matrices/gate_matrix.html",
                "data/state.json",
                "data/graph.json",
                "manifest.json",
            }
            expected = required | {"phases/lifecycle.svg"}
            self.assertEqual(set(generated_files(dashboard)), expected)
            self.assertEqual(set(manifest["files"]), expected)
            self.assertEqual(len(expected), 15)
            self.assertEqual(manifest["schema_version"], "2.1")
            self.assertEqual(manifest["locale"], "en")
            self.assertEqual(manifest["state_revision"], state["revision"])
            self.assertIsNone(manifest["bindings_sha256"])
            self.assertEqual(
                manifest["eligibility_sha256"], eligibility_fingerprint({})
            )
            self.assertEqual(len(manifest["outputs"]), len(expected) - 1)

            for output in manifest["outputs"]:
                path = root / output["path"]
                self.assertTrue(path.is_file(), output["path"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), output["sha256"])

    def test_graph_preserves_canonical_statuses_and_maps_display_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            dashboard = root / ".ipd" / "dashboard"
            graph = json.loads(
                (dashboard / "data" / "graph.json").read_text(encoding="utf-8")
            )
            self.assertEqual(set(graph["node_types"]), NODE_TYPES)
            self.assertEqual(set(graph["relation_types"]), RELATIONS)
            self.assertEqual({item["type"] for item in graph["nodes"]}, NODE_TYPES)
            nodes = {
                item["id"]: item
                for item in graph["nodes"]
                if item["type"] == "Deliverable"
            }
            self.assertEqual(set(STATUSES), set(nodes) - {"future"})
            self.assertEqual({nodes[status]["status"] for status in STATUSES}, set(STATUSES))
            self.assertEqual(nodes["planned"]["display_status"], "not_started")
            self.assertEqual(nodes["accepted"]["display_status"], "approved")
            self.assertEqual(nodes["blocked"]["display_status"], "blocked")
            relations = {item["relation"] for item in graph["edges"]}
            self.assertEqual(relations, RELATIONS)

            raw_payload = '<script>alert("dashboard")</script>'
            encoded_payload = html.escape(raw_payload, quote=True)
            for path in dashboard.rglob("*.html"):
                contents = path.read_text(encoding="utf-8")
                self.assertNotIn(raw_payload, contents)
            self.assertIn(
                encoded_payload,
                (dashboard / "matrices" / "deliverable_matrix.html").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertNotIn("Demo <unsafe>", (dashboard / "index.html").read_text(encoding="utf-8"))

    def test_svg_is_typed_hierarchical_parseable_and_non_overlapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            dashboard = root / ".ipd" / "dashboard"
            svg_paths = sorted((dashboard / "assets").glob("*.svg")) + sorted(
                (dashboard / "phases").glob("*.svg")
            )
            self.assertGreaterEqual(len(svg_paths), 8)
            for svg_path in svg_paths:
                root_element = ET.parse(svg_path).getroot()
                self.assertEqual(
                    root_element.attrib["data-layout"], "hierarchical-swimlane"
                )
                contents = svg_path.read_text(encoding="utf-8")
                self.assertNotIn("Generated by graphviz", contents)
                self.assertIn("Legend", contents)
                self.assertIn("phase-lane", contents)

            overview = (dashboard / "assets" / "ipd_flow.svg").read_text(
                encoding="utf-8"
            )
            translator = get_translator("en")
            for node_type in NODE_TYPES:
                label = translator.text(f"node_type.{node_type.lower()}")
                self.assertIn(f">{label}<", overview)
            for relation in RELATIONS:
                expected = (
                    translator.text("svg.dependency_direction")
                    if relation == "depends_on"
                    else translator.text(f"relation.{relation}")
                )
                self.assertIn(expected, overview)
            for status in STATUSES:
                self.assertIn(translator.text(f"status.{status}"), overview)

            self.assert_no_node_overlap(
                dashboard / "assets" / "current_status_flow.svg"
            )
            self.assert_no_node_overlap(dashboard / "phases" / "concept.svg")
            self.assertIn(
                "<tspan",
                (dashboard / "phases" / "develop.svg").read_text(encoding="utf-8"),
            )

    def test_current_phase_blocker_and_next_task_are_visually_prioritized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            dashboard = root / ".ipd" / "dashboard"
            index = (dashboard / "index.html").read_text(encoding="utf-8")
            current_svg = (dashboard / "assets" / "current_status_flow.svg").read_text(
                encoding="utf-8"
            )
            self.assertIn('class="phase-card active"', index)
            translator = get_translator("en")
            self.assertIn(translator.text("dashboard.current_phase"), index)
            self.assertIn(translator.text("dashboard.next_task"), index)
            self.assertIn(translator.text("dashboard.open_blockers"), index)
            self.assertIn("planned", index)
            self.assertIn(translator.text("svg.current"), current_svg)
            self.assertIn(translator.text("svg.blocked"), current_svg)
            self.assertIn('class="blocked-badge"', current_svg)

    def test_index_interactions_details_and_dynamic_html_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            dashboard = root / ".ipd" / "dashboard"
            index = (dashboard / "index.html").read_text(encoding="utf-8")
            translator = get_translator("en")
            for marker in (
                "hashchange",
                'id="details"',
                'id="detail-body"',
                translator.text("detail.input_evidence"),
                translator.text("detail.output_deliverables"),
                translator.text("detail.review_history"),
                'id="phase-view"',
                'data-zoom="in"',
                'data-zoom="out"',
                'id="gate-search"',
                'id="deliverable-search"',
                "#node=",
            ):
                self.assertIn(marker, index)
            matrix = (dashboard / "matrices" / "deliverable_matrix.html").read_text(
                encoding="utf-8"
            )
            self.assertIn('href="../index.html#node=', matrix)
            raw_payload = '<script>alert("dashboard")</script>'
            for path in dashboard.rglob("*.html"):
                self.assertNotIn(raw_payload, path.read_text(encoding="utf-8"))
            self.assertIn(html.escape(raw_payload, quote=True), index)
            self.assertNotIn('</script><script>alert("dashboard")</script>', index)
            self.assertIn("\\u003cscript\\u003e", index)

    def test_gate_readiness_and_human_approval_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process_fixture(), state_fixture())
            data = json.loads(
                (root / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
            gates = {item["id"]: item for item in data["checkpoints"]}
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
                    / "data"
                    / "graph.json"
                ).read_text(encoding="utf-8")
            )
        nodes = {
            item["id"]: item
            for item in graph["nodes"]
            if item["type"] == "Deliverable"
        }
        self.assertIn("future", nodes)
        self.assertIn("accepted", nodes)
        self.assertEqual(nodes["future"]["phase"], "develop")
        self.assertEqual(nodes["accepted"]["phase"], "concept")
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
            first = generated_files(dashboard)
            second_manifest = render_dashboard(root, process, state)
            second = generated_files(dashboard)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first, second)
        self.assertEqual(process, original_process)
        self.assertEqual(state, original_state)

    def test_rerender_removes_stale_flat_and_phase_files(self) -> None:
        canonical_process, canonical_state = canonical_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, canonical_process, canonical_state)
            dashboard = root / ".ipd" / "dashboard"
            stale_flat = dashboard / "deliverable_matrix.json"
            stale_phase = dashboard / "phases" / "retired.svg"
            stale_flat.write_text("stale\n", encoding="utf-8")
            stale_phase.write_text("stale\n", encoding="utf-8")

            render_dashboard(root, process_fixture(), state_fixture())
            self.assertFalse(stale_flat.exists())
            self.assertFalse(stale_phase.exists())
            self.assertFalse((dashboard / "phases" / "lifecycle.svg").exists())

    def test_generated_html_svg_and_json_use_english_fixture_text(self) -> None:
        process, state = canonical_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process, state)
            dashboard = root / ".ipd" / "dashboard"
            checked = 0
            for suffix in ("*.html", "*.svg", "*.json"):
                for path in dashboard.rglob(suffix):
                    self.assertIsNone(
                        HAN_RE.search(path.read_text(encoding="utf-8")), path
                    )
                    checked += 1
            self.assertGreaterEqual(checked, 14)

    def test_zh_cn_rendering_preserves_machine_contract_and_user_text(self) -> None:
        process, state = canonical_fixture()
        state["project"]["name"] = "四足机器人感知融合"
        process["profile"]["name"] = state["project"]["name"]
        state["deliverables"][0]["title"] = "用户自定义需求说明"
        process["deliverables"][0]["title"] = "用户自定义需求说明"
        state["deliverables"][0]["owner"] = "张工"
        state["deliverables"][0]["evidence"] = ["docs/验证证据.md"]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zh_manifest = render_dashboard(root, process, state, locale="zh-CN")
            dashboard = root / ".ipd" / "dashboard"
            zh_state = json.loads((dashboard / "data" / "state.json").read_text(encoding="utf-8"))
            zh_graph = json.loads((dashboard / "data" / "graph.json").read_text(encoding="utf-8"))
            zh_index = (dashboard / "index.html").read_text(encoding="utf-8")
            zh_svg = (dashboard / "assets" / "ipd_flow.svg").read_text(encoding="utf-8")

            english_root = root / "english"
            en_manifest = render_dashboard(english_root, process, state, locale="en")
            en_dashboard = english_root / ".ipd" / "dashboard"
            en_state = json.loads((en_dashboard / "data" / "state.json").read_text(encoding="utf-8"))
            en_graph = json.loads((en_dashboard / "data" / "graph.json").read_text(encoding="utf-8"))

        self.assertEqual(zh_manifest["locale"], "zh-CN")
        self.assertEqual(en_manifest["locale"], "en")
        self.assertEqual(zh_state["locale"], "zh-CN")
        self.assertEqual(zh_graph["locale"], "zh-CN")
        self.assertIn('<html lang="zh-CN">', zh_index)
        self.assertIn("当前阶段", zh_index)
        self.assertIn("四足机器人感知融合", zh_index)
        self.assertIn("用户自定义需求说明", zh_index)
        self.assertIn("张工", zh_index)
        self.assertIn("概念", zh_svg)
        built_in = next(
            item for item in zh_state["deliverables"] if item["id"] == "plan.integrated_plan"
        )
        self.assertEqual(
            built_in["display_label"],
            get_translator("zh-CN").text(
                "workflow.deliverable.plan.integrated_plan"
            ),
        )
        built_in_gate = next(
            item for item in zh_state["checkpoints"] if item["id"] == "gate.tr.concept"
        )
        self.assertEqual(
            built_in_gate["display_label"],
            get_translator("zh-CN").text("workflow.checkpoint.tr.concept"),
        )
        self.assertIn(
            get_translator("zh-CN").text("workflow.checkpoint.tr.concept"),
            zh_svg,
        )
        self.assertEqual(
            [(item["id"], item["status"]) for item in zh_state["deliverables"]],
            [(item["id"], item["status"]) for item in en_state["deliverables"]],
        )
        self.assertEqual(
            [(item["source"], item["target"], item["relation"]) for item in zh_graph["edges"]],
            [(item["source"], item["target"], item["relation"]) for item in en_graph["edges"]],
        )
        self.assertEqual(
            [(item["id"], item["type"], item["status"]) for item in zh_graph["nodes"]],
            [(item["id"], item["type"], item["status"]) for item in en_graph["nodes"]],
        )

    def test_east_asian_width_wrapping_respects_visual_columns(self) -> None:
        lines = _wrap_text("四足机器人感知融合系统验证", 10, 3)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(_display_width(line.rstrip("…")) <= 10 for line in lines))
        self.assertLessEqual(len(lines), 3)

    def test_checkpoint_uses_linked_gate_state_before_checkpoint_placeholder(self) -> None:
        process = process_fixture()
        state = state_fixture()
        state["gates"].append(
            {
                "id": "tr-design",
                "status": "planned",
                "required_deliverables": ["accepted"],
                "reviews": [],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process, state)
            data = json.loads(
                (root / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
        checkpoint = next(item for item in data["checkpoints"] if item["id"] == "tr-design")
        self.assertEqual(checkpoint["status"], "approved")
        self.assertEqual(checkpoint["approval"]["status"], "approved")

    def test_latest_authorized_human_gate_decision_controls_dashboard_approval(self) -> None:
        process = process_fixture()
        state = state_fixture()
        gate = next(item for item in state["gates"] if item["id"] == "gate-tr-design")
        gate["status"] = "approved"
        gate["reviews"] = [
            {
                "reviewer": "governance-board",
                "reviewer_type": "human",
                "authorized": True,
                "decision": "reject",
                "evidence": "reviews/rejected.md",
            },
            {
                "reviewer": "governance-board",
                "reviewer_type": "human",
                "authorized": True,
                "decision": "approve",
                "evidence": "reviews/rework-approved.md",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process, state)
            data = json.loads(
                (root / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
        checkpoint = next(item for item in data["checkpoints"] if item["id"] == "tr-design")
        self.assertEqual(checkpoint["approval"]["status"], "approved")
        self.assertEqual(
            checkpoint["approval"]["latest_authorized_human_decision"],
            "approve",
        )
        self.assertEqual(
            [review["decision"] for review in checkpoint["approval"]["reviews"]],
            ["reject", "approve"],
        )

    def test_actionable_and_blocked_projections_are_scoped_to_current_phase(self) -> None:
        process = process_fixture()
        state = state_fixture()
        state["project"]["phase"] = "concept"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process, state)
            data = json.loads(
                (root / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertTrue(data["available_tasks"])
        self.assertTrue(
            all(item.get("phase") in {None, "concept"} for item in data["available_tasks"])
        )
        self.assertTrue(
            all(
                next(
                    deliverable.get("phase")
                    for deliverable in data["deliverables"]
                    if deliverable["id"] == item["id"]
                )
                in {None, "concept"}
                for item in data["blocked_items"]
            )
        )
        self.assertNotIn("future", {item["id"] for item in data["available_tasks"]})

    def test_binding_readiness_blocks_actionability_without_changing_lifecycle(self) -> None:
        process = process_fixture()
        state = state_fixture()
        binding_hash = "a" * 64
        eligibility = {
            "schema_version": "1.0",
            "status": "failed",
            "eligible": False,
            "bindings_sha256": binding_hash,
            "baseline_id": "baseline-7",
            "issues": [
                {
                    "code": "MISSING_BINDING",
                    "severity": "error",
                    "deliverable_id": "planned",
                    "reason_code": "no_matching_rule",
                    "rule_ids": [],
                }
            ],
            "paths": {},
            "deliverables": {
                "planned": {
                    "eligible": False,
                    "binding_ready": False,
                    "issue_codes": ["MISSING_BINDING"],
                    "blockers": [
                        {
                            "code": "MISSING_BINDING",
                            "reason_code": "no_matching_rule",
                        }
                    ],
                },
                "accepted": {
                    "eligible": False,
                    "binding_ready": False,
                    "issue_codes": ["MISSING_BINDING"],
                    "blockers": [{"code": "MISSING_BINDING"}],
                },
            },
            "summary": {"errors": 1, "warnings": 0},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = render_dashboard(
                root,
                process,
                state,
                eligibility=eligibility,
            )
            dashboard = root / ".ipd" / "dashboard"
            projected = json.loads(
                (dashboard / "data" / "state.json").read_text(encoding="utf-8")
            )
            graph = json.loads(
                (dashboard / "data" / "graph.json").read_text(encoding="utf-8")
            )
            index = (dashboard / "index.html").read_text(encoding="utf-8")

            zh_root = root / "zh"
            render_dashboard(
                zh_root,
                process,
                state,
                eligibility=eligibility,
                locale="zh-CN",
            )
            zh_index = (
                zh_root / ".ipd" / "dashboard" / "index.html"
            ).read_text(encoding="utf-8")

        deliverable = next(
            item for item in projected["deliverables"] if item["id"] == "planned"
        )
        accepted = next(
            item for item in projected["deliverables"] if item["id"] == "accepted"
        )
        node = next(
            item
            for item in graph["nodes"]
            if item["type"] == "Deliverable" and item["id"] == "planned"
        )
        self.assertEqual(deliverable["status"], "planned")
        self.assertEqual(deliverable["display_status"], "not_started")
        self.assertEqual(deliverable["actionability"]["state"], "waiting_on_bindings")
        self.assertFalse(deliverable["actionability"]["actionable"])
        self.assertFalse(deliverable["actionability"]["binding_ready"])
        self.assertEqual(deliverable["attention"], "binding_blocked")
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["actionability"]["state"], "inactive")
        self.assertTrue(accepted["actionability"]["binding_blocked"])
        self.assertIsNone(accepted["attention"])
        self.assertNotIn("planned", {item["id"] for item in projected["available_tasks"]})
        self.assertIn("planned", {item["id"] for item in projected["blocked_items"]})
        self.assertNotIn("accepted", {item["id"] for item in projected["blocked_items"]})
        self.assertEqual(projected["summary"]["binding_blocked"], 1)
        self.assertEqual(projected["eligibility"]["deliverables"], eligibility["deliverables"])
        self.assertEqual(node["status"], "planned")
        self.assertFalse(node["blocked"])
        self.assertEqual(node["attention"], "binding_blocked")
        self.assertEqual(manifest["bindings_sha256"], binding_hash)
        self.assertEqual(
            manifest["eligibility_sha256"],
            eligibility_fingerprint(projected["eligibility"]),
        )
        self.assertIn("Binding readiness", index)
        self.assertIn("Waiting on bindings", index)
        self.assertIn("产物绑定就绪度", zh_index)
        self.assertIn("\\u7b49\\u5f85\\u4ea7\\u7269\\u7ed1\\u5b9a", zh_index)

    def test_binding_and_eligibility_changes_update_manifest_fingerprints(self) -> None:
        process, state = canonical_fixture()
        bindings = {"schema_version": "1.0", "bindings": []}
        eligibility = {
            "schema_version": "1.0",
            "status": "passed",
            "eligible": True,
            "bindings_sha256": value_sha256(bindings),
            "deliverables": {},
            "issues": [],
            "paths": {},
            "summary": {"errors": 0},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = render_dashboard(
                root,
                process,
                state,
                bindings=bindings,
                eligibility=eligibility,
            )
            changed_eligibility = deepcopy(eligibility)
            changed_eligibility["status"] = "warning"
            changed_eligibility["issues"] = [
                {"code": "TEST_WARNING", "severity": "warning"}
            ]
            changed_eligibility["summary"]["warnings"] = 1
            second = render_dashboard(
                root,
                process,
                state,
                bindings=bindings,
                eligibility=changed_eligibility,
            )
            changed_bindings = deepcopy(bindings)
            changed_bindings["bindings"].append(
                {"id": "source", "glob": "src/**", "deliverable": "concept.charter"}
            )
            changed_binding_eligibility = deepcopy(changed_eligibility)
            changed_binding_eligibility["bindings_sha256"] = value_sha256(
                changed_bindings
            )
            third = render_dashboard(
                root,
                process,
                state,
                bindings=changed_bindings,
                eligibility=changed_binding_eligibility,
            )
            files = generated_files(root / ".ipd" / "dashboard")

        self.assertEqual(first["bindings_sha256"], second["bindings_sha256"])
        self.assertNotEqual(first["eligibility_sha256"], second["eligibility_sha256"])
        self.assertNotEqual(second["bindings_sha256"], third["bindings_sha256"])
        self.assertNotEqual(second["eligibility_sha256"], third["eligibility_sha256"])
        self.assertEqual(len(files), 15)

    def test_phase_acceptance_requires_all_phase_gates_approved(self) -> None:
        process = process_fixture()
        state = state_fixture()
        for deliverable in state["deliverables"]:
            if deliverable.get("phase") == "concept":
                deliverable["status"] = "accepted"
                deliverable["depends_on"] = []
        state["project"]["phase"] = "concept"
        pending_gate = next(
            item for item in state["gates"] if item["id"] == "gate-dcp-concept"
        )
        pending_gate["status"] = "planned"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(root, process, state)
            data = json.loads(
                (root / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
        phase = next(item for item in data["phases"] if item["id"] == "concept")
        self.assertNotEqual(phase["status"], "accepted")
        self.assertEqual(phase["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()

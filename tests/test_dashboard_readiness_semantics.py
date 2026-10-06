from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from ipdctl.dashboard import render_dashboard
from ipdctl.dashboard_model import build_dashboard_model


SVG = "{http://www.w3.org/2000/svg}"


def _process(*deliverables: dict) -> dict:
    return {
        "schema_version": "1.0",
        "profile": {"name": "Readiness semantics"},
        "phases": [{"id": "concept", "title": "Concept", "sequence": 1}],
        "deliverables": list(deliverables),
    }


def _state(*deliverables: dict) -> dict:
    return {
        "schema_version": "2.0",
        "revision": 1,
        "project": {
            "name": "Readiness semantics",
            "phase": "concept",
            "workflow_step": "context",
        },
        "deliverables": list(deliverables),
        "gates": [],
    }


def _deliverable(identifier: str, status: str, **overrides: object) -> dict:
    item: dict = {
        "id": identifier,
        "title": identifier,
        "phase": "concept",
        "status": status,
        "depends_on": [],
        "evidence": [],
        "reviews": [],
    }
    item.update(overrides)
    return item


def _by_id(items: list[dict]) -> dict[str, dict]:
    return {item["id"]: item for item in items}


class DashboardReadinessSemanticsTests(unittest.TestCase):
    def test_dependency_wait_stays_in_compatibility_blocked_items_but_is_not_red(self) -> None:
        prerequisite = _deliverable("prerequisite", "planned")
        dependent = _deliverable(
            "dependent",
            "planned",
            depends_on=["prerequisite"],
        )
        state_data, graph = build_dashboard_model(
            _process(prerequisite, dependent),
            _state(prerequisite, dependent),
        )

        deliverables = _by_id(state_data["deliverables"])
        nodes = _by_id(graph["nodes"])
        blocked_items = _by_id(state_data["blocked_items"])
        waiting_items = _by_id(state_data["waiting_items"])

        self.assertEqual(
            deliverables["dependent"]["actionability"],
            {
                "state": "waiting_on_dependencies",
                "actionable": False,
                "in_current_scope": True,
                "unmet_dependencies": ["prerequisite"],
            },
        )
        self.assertIsNone(deliverables["dependent"]["attention"])
        self.assertIn("dependent", blocked_items)
        self.assertIn("dependent", waiting_items)
        self.assertEqual(state_data["explicit_blockers"], [])
        self.assertEqual(state_data["governance_blockers"], [])
        self.assertEqual(
            blocked_items["dependent"]["actionability"]["state"],
            "waiting_on_dependencies",
        )
        self.assertFalse(nodes["dependent"]["blocked"])
        self.assertEqual(
            nodes["dependent"]["actionability"]["state"],
            "waiting_on_dependencies",
        )
        self.assertEqual(state_data["summary"]["blocked_items"], 1)
        self.assertEqual(state_data["summary"]["waiting_items"], 1)
        self.assertEqual(state_data["summary"]["explicit_blockers"], 0)
        self.assertEqual(state_data["summary"]["governance_blockers"], 0)
        self.assertEqual(state_data["summary"]["waiting_on_dependencies"], 1)
        self.assertEqual(state_data["summary"]["explicitly_blocked"], 0)

        self.assertIn(
            {
                "source": "dependent",
                "target": "prerequisite",
                "relation": "depends_on",
            },
            graph["edges"],
        )

    def test_explicit_block_rework_and_orphan_claim_are_distinct_attention_states(self) -> None:
        blocked = _deliverable(
            "blocked",
            "blocked",
            blocked_reason="hardware unavailable",
        )
        rejected = _deliverable("rejected", "rejected")
        orphan = _deliverable("orphan", "in_progress")
        claimed = _deliverable("claimed", "in_progress")
        state_data, graph = build_dashboard_model(
            _process(blocked, rejected, orphan, claimed),
            _state(blocked, rejected, orphan, claimed),
            runtime={
                "active_claims": {
                    "claimed": {"actor": "agent-a"},
                }
            },
        )

        deliverables = _by_id(state_data["deliverables"])
        nodes = _by_id(graph["nodes"])
        blocked_items = _by_id(state_data["blocked_items"])
        explicit_blockers = _by_id(state_data["explicit_blockers"])
        governance_blockers = _by_id(state_data["governance_blockers"])

        self.assertEqual(blocked_items["blocked"]["attention"], "explicitly_blocked")
        self.assertIn("blocked", explicit_blockers)
        self.assertEqual(deliverables["blocked"]["actionability"]["state"], "actionable")
        self.assertTrue(nodes["blocked"]["blocked"])

        self.assertEqual(deliverables["rejected"]["attention"], "rework_required")
        self.assertEqual(deliverables["rejected"]["actionability"]["state"], "actionable")
        self.assertFalse(nodes["rejected"]["blocked"])

        self.assertEqual(deliverables["orphan"]["attention"], "orphan_claim")
        self.assertEqual(deliverables["orphan"]["actionability"]["state"], "inactive")
        self.assertTrue(blocked_items["orphan"]["recoverable"])
        self.assertIn("orphan", governance_blockers)
        self.assertFalse(nodes["orphan"]["blocked"])

        self.assertIsNone(deliverables["claimed"]["attention"])
        self.assertEqual(deliverables["claimed"]["actionability"]["state"], "claimed")
        self.assertNotIn("claimed", blocked_items)
        self.assertFalse(nodes["claimed"]["blocked"])

        self.assertEqual(
            {item["id"] for item in state_data["available_tasks"]},
            {"blocked", "rejected"},
        )
        self.assertEqual(state_data["summary"]["explicitly_blocked"], 1)
        self.assertEqual(state_data["summary"]["rework_required"], 1)
        self.assertEqual(state_data["summary"]["orphan_claims"], 1)
        self.assertEqual(state_data["summary"]["explicit_blockers"], 1)
        self.assertEqual(state_data["summary"]["governance_blockers"], 1)

    def test_out_of_phase_deliverable_is_inactive_without_losing_dependency_facts(self) -> None:
        prerequisite = _deliverable("prerequisite", "planned")
        future = _deliverable(
            "future",
            "planned",
            phase="develop",
            depends_on=["prerequisite"],
        )
        state_data, graph = build_dashboard_model(
            _process(prerequisite, future),
            _state(prerequisite, future),
        )

        deliverables = _by_id(state_data["deliverables"])
        nodes = _by_id(graph["nodes"])
        self.assertEqual(deliverables["future"]["actionability"]["state"], "inactive")
        self.assertEqual(
            deliverables["future"]["actionability"]["unmet_dependencies"],
            ["prerequisite"],
        )
        self.assertFalse(deliverables["future"]["actionability"]["in_current_scope"])
        self.assertNotIn("future", {item["id"] for item in state_data["blocked_items"]})
        self.assertFalse(nodes["future"]["blocked"])
        self.assertEqual(state_data["summary"]["waiting_on_dependencies"], 0)

    def test_binding_and_protocol_failures_are_governance_blockers(self) -> None:
        target = _deliverable("target", "planned")
        binding_state, _ = build_dashboard_model(
            _process(target),
            _state(target),
            eligibility={
                "schema_version": "1.0",
                "deliverables": {
                    "target": {
                        "eligible": False,
                        "binding_ready": False,
                        "issue_codes": ["BINDING_OWNER_MISSING"],
                        "blockers": [
                            {"reason_code": "BINDING_OWNER_MISSING"}
                        ],
                    }
                },
            },
        )
        self.assertEqual(
            _by_id(binding_state["deliverables"])["target"]["actionability"]["state"],
            "waiting_on_bindings",
        )
        self.assertEqual(
            {item["id"] for item in binding_state["governance_blockers"]},
            {"target"},
        )
        self.assertEqual(binding_state["summary"]["governance_blockers"], 1)

        protocol_state, _ = build_dashboard_model(
            _process(target),
            _state(target),
            claim_readiness={
                "schema_version": "1.0",
                "eligible": False,
                "reason_code": "VERIFICATION_REQUIRED",
                "required_action": "verify",
            },
        )
        self.assertEqual(
            _by_id(protocol_state["deliverables"])["target"]["actionability"]["state"],
            "waiting_on_protocol",
        )
        self.assertEqual(protocol_state["blocked_items"], [])
        self.assertEqual(
            protocol_state["governance_blockers"],
            [
                {
                    "id": "project.claim_readiness",
                    "scope": "project",
                    "code": "VERIFICATION_REQUIRED",
                    "reason": "VERIFICATION_REQUIRED",
                    "required_action": "verify",
                }
            ],
        )
        self.assertEqual(protocol_state["summary"]["governance_blockers"], 1)

    def test_superseded_deliverable_is_terminal_even_with_unmet_dependencies(self) -> None:
        prerequisite = _deliverable("prerequisite", "planned")
        superseded = _deliverable(
            "superseded",
            "superseded",
            depends_on=["prerequisite"],
        )
        state_data, graph = build_dashboard_model(
            _process(prerequisite, superseded),
            _state(prerequisite, superseded),
        )

        deliverables = _by_id(state_data["deliverables"])
        nodes = _by_id(graph["nodes"])
        self.assertEqual(deliverables["superseded"]["actionability"]["state"], "inactive")
        self.assertEqual(
            deliverables["superseded"]["actionability"]["unmet_dependencies"],
            ["prerequisite"],
        )
        self.assertNotIn("superseded", {item["id"] for item in state_data["blocked_items"]})
        self.assertEqual(state_data["summary"]["waiting_on_dependencies"], 0)
        self.assertFalse(nodes["superseded"]["blocked"])

    def test_rendered_dashboard_separates_waiting_from_explicit_blockers(self) -> None:
        prerequisite = _deliverable("prerequisite", "planned")
        dependent = _deliverable(
            "dependent",
            "planned",
            depends_on=["prerequisite"],
        )
        blocked = _deliverable(
            "blocked",
            "blocked",
            blocked_reason="test fixture blocker",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dashboard(
                root,
                _process(prerequisite, dependent, blocked),
                _state(prerequisite, dependent, blocked),
            )
            dashboard = root / ".ipd" / "dashboard"
            projected = json.loads(
                (dashboard / "data" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(projected["summary"]["waiting_on_dependencies"], 1)
            self.assertEqual(projected["summary"]["explicitly_blocked"], 1)
            self.assertEqual(projected["summary"]["waiting_items"], 1)
            self.assertEqual(projected["summary"]["explicit_blockers"], 1)
            self.assertEqual(projected["summary"]["governance_blockers"], 0)

            index = (dashboard / "index.html").read_text(encoding="utf-8")
            self.assertIn("Waiting on Prerequisites", index)
            self.assertIn("Actionability", index)
            self.assertIn(
                '<span class="metric-label">Waiting on Prerequisites</span>'
                '<strong class="metric-value">1</strong>',
                index,
            )
            self.assertIn(
                '<span class="metric-label">Explicit Blockers</span>'
                '<strong class="metric-value alert">1</strong>',
                index,
            )
            self.assertIn(
                '<span class="metric-label">Governance Blockers</span>'
                '<strong class="metric-value">0</strong>',
                index,
            )
            self.assertNotIn("__WAITING__", index)

            current_svg = ET.fromstring(
                (dashboard / "assets" / "current_status_flow.svg").read_text(
                    encoding="utf-8"
                )
            )
            groups = {
                group.attrib["data-node-id"]: group
                for group in current_svg.findall(f".//{SVG}g[@data-node-id]")
            }
            self.assertIsNone(
                groups["dependent"].find(f".//{SVG}g[@class='blocked-badge']")
            )
            self.assertIsNotNone(
                groups["blocked"].find(f".//{SVG}g[@class='blocked-badge']")
            )


if __name__ == "__main__":
    unittest.main()

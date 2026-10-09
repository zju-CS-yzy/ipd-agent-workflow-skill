from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from ipdctl.dashboard import render_dashboard
from ipdctl.dashboard_model import build_dashboard_model
from ipdctl.dashboard_svg import _normalise_graph, _topological_levels
from ipdctl.i18n import get_translator
from ipdctl.reconcile import (
    preview_artifact_baseline,
    preview_refinement_binding_impact,
)


PHASES = [
    {"id": phase, "title": phase.title(), "sequence": index}
    for index, phase in enumerate(
        ("concept", "plan", "develop", "qualify", "launch", "lifecycle"),
        start=1,
    )
]


def deliverable(identifier: str, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": identifier,
        "title": identifier,
        "phase": "concept",
        "activity_id": "concept.design",
        "review_required": True,
        "depends_on": [],
    }
    row.update(extra)
    return row


def state_deliverable(identifier: str, **extra: object) -> dict[str, object]:
    row = deliverable(identifier)
    row.update({"status": "planned", "evidence": [], "reviews": []})
    row.update(extra)
    return row


def process(*deliverables: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "profile": {"name": "Refinement Demo", "task_types": ["software"]},
        "phases": deepcopy(PHASES),
        "activities": [
            {
                "id": "concept.design",
                "title": "System design",
                "phase": "concept",
                "sequence": 1,
            }
        ],
        "technical_reviews": [],
        "decision_checkpoints": [],
        "gates": [],
        "deliverables": list(deliverables),
        "dependencies": [],
    }


def state(*deliverables: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "revision": 4,
        "project": {
            "name": "Refinement Demo",
            "phase": "concept",
            "workflow_step": "context",
            "current_tr": None,
            "current_dcp": None,
            "current_gate": None,
        },
        "deliverables": list(deliverables),
        "gates": [],
        "traceability": [],
    }


class DashboardRefinementProjectionTests(unittest.TestCase):
    def test_due_abstract_node_is_not_available_and_is_prominent(self) -> None:
        trigger = {
            "all_of": [{"subject": "concept.input", "condition": "accepted"}]
        }
        candidate = process(
            deliverable("concept.input"),
            deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger=trigger,
            ),
        )
        project_state = state(
            state_deliverable("concept.input", status="accepted"),
            state_deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger=trigger,
            ),
        )

        state_data, graph = build_dashboard_model(candidate, project_state)
        rows = {item["id"]: item for item in state_data["deliverables"]}
        architecture = rows["concept.architecture"]

        self.assertEqual(architecture["refinement_status"], "due")
        self.assertTrue(architecture["refinement_due"])
        self.assertEqual(
            architecture["actionability"]["state"], "waiting_on_refinement"
        )
        self.assertNotIn(
            "concept.architecture", {item["id"] for item in state_data["available_tasks"]}
        )
        self.assertEqual(state_data["summary"]["refinement_due"], 1)
        self.assertEqual(state_data["refinement_due"][0]["id"], "concept.architecture")
        graph_row = next(
            item for item in graph["nodes"] if item["id"] == "concept.architecture"
        )
        self.assertTrue(graph_row["refinement_due"])

    def test_refinement_lineage_and_concrete_leaf_closure_are_derived(self) -> None:
        candidate = process(
            deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
            ),
            deliverable(
                "concept.mobility",
                refines="concept.architecture",
                requires_artifact_owner=True,
            ),
        )
        candidate["activities"][0].update(
            {"definition_state": "abstract", "refinement_required": True}
        )
        candidate["activities"].append(
            {
                "id": "concept.mobility_design",
                "title": "Mobility design",
                "phase": "concept",
                "sequence": 2,
                "definition_state": "concrete",
                "refines": "concept.design",
            }
        )
        project_state = state(
            state_deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
            ),
            state_deliverable(
                "concept.mobility",
                refines="concept.architecture",
                requires_artifact_owner=True,
            ),
        )

        state_data, graph = build_dashboard_model(candidate, project_state)
        rows = {item["id"]: item for item in state_data["deliverables"]}
        self.assertEqual(rows["concept.architecture"]["refined_by"], ["concept.mobility"])
        self.assertEqual(
            rows["concept.architecture"]["concrete_leaf_closure"],
            ["concept.mobility"],
        )
        self.assertEqual(rows["concept.architecture"]["refinement_status"], "resolved")
        self.assertEqual(rows["concept.mobility"]["refines"], ["concept.architecture"])
        self.assertIn(
            {
                "source": "concept.mobility",
                "target": "concept.architecture",
                "relation": "refines",
            },
            graph["edges"],
        )
        activities = {item["id"]: item for item in state_data["activities"]}
        self.assertEqual(
            activities["concept.design"]["refined_by"],
            ["concept.mobility_design"],
        )
        self.assertEqual(
            activities["concept.mobility_design"]["refines"], ["concept.design"]
        )
        self.assertIn(
            {
                "source": "concept.mobility_design",
                "target": "concept.design",
                "relation": "refines",
            },
            graph["edges"],
        )

    def test_refines_never_changes_execution_topological_levels(self) -> None:
        graph = {
            "nodes": [
                {"id": "parent", "type": "Deliverable", "phase": "concept"},
                {"id": "child", "type": "Deliverable", "phase": "concept"},
                {"id": "downstream", "type": "Deliverable", "phase": "concept"},
            ],
            "edges": [
                {"source": "downstream", "target": "child", "relation": "depends_on"},
                {"source": "child", "target": "parent", "relation": "refines"},
            ],
        }
        nodes, edges = _normalise_graph(graph)
        with_refines = _topological_levels(nodes, edges)
        without_refines = _topological_levels(
            nodes, [edge for edge in edges if edge.relation != "refines"]
        )
        self.assertEqual(with_refines, without_refines)
        self.assertEqual(with_refines["downstream"], with_refines["child"] + 1)

    def test_html_svg_and_inventory_are_bilingual_and_stable(self) -> None:
        trigger = {
            "all_of": [{"subject": "concept.input", "condition": "accepted"}]
        }
        candidate = process(
            deliverable("concept.input"),
            deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger=trigger,
            ),
            deliverable("concept.mobility", refines="concept.architecture"),
        )
        project_state = state(
            state_deliverable("concept.input", status="accepted"),
            state_deliverable(
                "concept.architecture",
                definition_state="abstract",
                refinement_required=True,
                refinement_trigger=trigger,
            ),
            state_deliverable("concept.mobility", refines="concept.architecture"),
        )
        # Keep one separate unresolved root so the SVG has a due badge while
        # the first root demonstrates a visible refines edge.
        candidate["deliverables"].append(
            deliverable(
                "concept.pending_refinement",
                definition_state="placeholder",
                refinement_required=True,
            )
        )
        project_state["deliverables"].append(
            state_deliverable(
                "concept.pending_refinement",
                status="blocked",
                definition_state="placeholder",
                refinement_required=True,
            )
        )

        for locale in ("en", "zh-CN"):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = render_dashboard(
                    root, candidate, project_state, locale=locale
                )
                dashboard = root / ".ipd" / "dashboard"
                self.assertEqual(len(manifest["files"]), 16)
                index = (dashboard / "index.html").read_text(encoding="utf-8")
                svg = (dashboard / "assets" / "deliverable_dependency.svg").read_text(
                    encoding="utf-8"
                )
                translator = get_translator(locale)
                for key in (
                    "dashboard.refinement_due",
                    "detail.definition_state",
                    "detail.refinement_status",
                    "detail.binding_impact",
                ):
                    label = translator.text(key)
                    escaped_label = json.dumps(label, ensure_ascii=True)[1:-1]
                    self.assertTrue(
                        label in index or escaped_label in index,
                        (key, label),
                    )
                self.assertIn(translator.text("relation.refines"), svg)
                self.assertIn('data-relation="refines"', svg)
                self.assertIn('class="refinement-badge"', svg)
                self.assertIn('class="blocked-badge"', svg)
                self.assertEqual(
                    json.loads((dashboard / "data" / "state.json").read_text("utf-8"))[
                        "locale"
                    ],
                    locale,
                )


class RefinementBindingImpactTests(unittest.TestCase):
    @staticmethod
    def bindings(*rules: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "ignore": [],
            "critical_roots": ["src/**"],
            "bindings": list(rules),
        }

    def test_preview_lists_managed_only_missing_and_parent_candidates(self) -> None:
        current = process(deliverable("concept.architecture"))
        candidate = process(
            deliverable("concept.architecture"),
            deliverable(
                "concept.mobility",
                refines="concept.architecture",
                requires_artifact_owner=True,
            ),
        )
        bindings = self.bindings(
            {
                "id": "architecture-owner",
                "glob": "src/architecture/**",
                "deliverable": "concept.architecture",
                "role": "owner",
                "critical": True,
            },
            {
                "id": "ipd-evidence-concept.mobility",
                "glob": "evidence/concept.mobility/**",
                "deliverable": "concept.mobility",
                "critical": True,
                "managed_by": "ipdctl.tailor",
                "managed_kind": "deliverable_evidence",
            },
        )

        impact = preview_refinement_binding_impact(
            bindings,
            current,
            candidate,
            {"added_deliverables": ["concept.mobility"]},
        )
        self.assertFalse(impact["eligible"])
        row = impact["new_concrete_children"][0]
        self.assertTrue(row["managed_evidence_only"])
        self.assertTrue(row["missing_owner"])
        self.assertEqual(
            row["parent_owner_candidate_rule_ids"], ["architecture-owner"]
        )
        self.assertIn(
            "REFINEMENT_OWNER_REQUIRED",
            {item["code"] for item in impact["issues"]},
        )

    def test_user_owner_and_shared_evidence_are_reported_separately(self) -> None:
        current = process(deliverable("concept.architecture"))
        candidate = process(
            deliverable("concept.architecture"),
            deliverable(
                "concept.mobility",
                refines="concept.architecture",
                requires_artifact_owner=True,
            ),
        )
        bindings = self.bindings(
            {
                "id": "mobility-owner",
                "glob": "src/mobility/**",
                "deliverable": "concept.mobility",
                "role": "owner",
                "critical": True,
            },
            {
                "id": "shared-research",
                "glob": "research/**",
                "deliverables": ["concept.mobility"],
                "role": "shared_evidence",
                "critical": False,
            },
        )

        impact = preview_refinement_binding_impact(
            bindings, current, candidate, {"deliverables": {"added": ["concept.mobility"]}}
        )
        self.assertTrue(impact["eligible"], impact["issues"])
        row = impact["new_concrete_children"][0]
        self.assertEqual(row["owner_rule_ids"], ["mobility-owner"])
        self.assertEqual(row["shared_evidence_rule_ids"], ["shared-research"])
        self.assertTrue(row["binding_ready"])

    @unittest.skipUnless(shutil.which("git"), "git is not available")
    def test_managed_evidence_only_fails_closed_and_blocks_dashboard_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.name", "IPD Test"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "ipd@example.test"],
                cwd=root,
                check=True,
            )
            ipd = root / ".ipd"
            ipd.mkdir()
            binding_contract = self.bindings(
                {
                    "id": "ipd-evidence-concept.mobility",
                    "glob": "evidence/concept.mobility/**",
                    "deliverable": "concept.mobility",
                    "critical": True,
                    "managed_by": "ipdctl.tailor",
                    "managed_kind": "deliverable_evidence",
                }
            )
            (ipd / "artifact_bindings.yaml").write_text(
                yaml.safe_dump(binding_contract, sort_keys=False), encoding="utf-8"
            )
            project_state = state(
                state_deliverable(
                    "concept.mobility", requires_artifact_owner=True
                )
            )
            report = preview_artifact_baseline(root, project_state)

        row = report["deliverables"]["concept.mobility"]
        self.assertFalse(row["eligible"])
        self.assertIn("ARTIFACT_OWNER_REQUIRED", row["issue_codes"])
        candidate = process(
            deliverable("concept.mobility", requires_artifact_owner=True)
        )
        state_data, _ = build_dashboard_model(
            candidate, project_state, eligibility=report
        )
        projected = state_data["deliverables"][0]
        self.assertEqual(
            projected["actionability"]["state"], "waiting_on_bindings"
        )
        self.assertIn(
            "ARTIFACT_OWNER_REQUIRED",
            projected["actionability"]["issue_codes"],
        )
        self.assertFalse(state_data["available_tasks"])

    @unittest.skipUnless(shutil.which("git"), "git is not available")
    def test_non_concrete_deliverable_does_not_require_owner_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            ipd = root / ".ipd"
            ipd.mkdir()
            binding_contract = self.bindings(
                {
                    "id": "ipd-evidence-concept.placeholder",
                    "glob": "evidence/concept.placeholder/**",
                    "deliverable": "concept.placeholder",
                    "critical": True,
                    "managed_by": "ipdctl.tailor",
                    "managed_kind": "deliverable_evidence",
                }
            )
            (ipd / "artifact_bindings.yaml").write_text(
                yaml.safe_dump(binding_contract, sort_keys=False), encoding="utf-8"
            )
            project_state = state(
                state_deliverable(
                    "concept.placeholder",
                    definition_state="placeholder",
                    refinement_required=True,
                    refinement_trigger={
                        "all_of": [
                            {"subject": "concept.input", "condition": "accepted"}
                        ]
                    },
                    # Preserve compatibility with state written before the
                    # definition-state-aware refinement-plan normalization.
                    requires_artifact_owner=True,
                )
            )
            report = preview_artifact_baseline(root, project_state)

        row = report["deliverables"]["concept.placeholder"]
        self.assertNotIn("REFINEMENT_OWNER_REQUIRED", row["issue_codes"])
        self.assertFalse(row["binding_impact"]["requires_artifact_owner"])
        self.assertTrue(row["binding_ready"])


if __name__ == "__main__":
    unittest.main()

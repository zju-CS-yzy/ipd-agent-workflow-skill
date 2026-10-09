#!/usr/bin/env python3
"""Exercise the v0.5 capability catalog through one complete IPD lifecycle.

The scenario is intentionally black-box at the workflow boundary: project
mutations are driven through ``ipdctl`` while the stable state loaders are used
only to author project inputs and inspect generated contracts.  The temporary
project is removed after every run.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ipdctl.refinement import process_fingerprint, refinement_leaf_closure
from ipdctl.runtime import load_runtime
from ipdctl.state import load_state, write_state
from scripts.simulate_project_lifecycle import (
    EXPECTED_DASHBOARD_FILES,
    EXPECTED_PHASES,
    LifecycleScenario,
    SimulationFailure,
    _json_output,
    _require,
)


CAPABILITY_PATTERNS = (
    "module_decomposition_and_verification",
    "interface_contract_and_integration",
    "release_and_lifecycle_assurance",
)
CAPABILITY_DELIVERABLES = frozenset(
    {
        "module.decomposition_baseline",
        "module.implementation_baseline",
        "module.verification_report",
        "interface.contract_baseline",
        "interface.integration_evidence",
        "interface.conformance_report",
        "release.strategy",
        "release.candidate",
        "release.verification_report",
        "release.handover_package",
        "release.lifecycle_assurance_record",
    }
)
REFINEMENT_ROOT = "module.implementation_baseline"
REFINEMENT_CHILDREN = (
    "module.motion_control_implementation",
    "module.perception_implementation",
)
INITIAL_DELIVERABLES = 20
FINAL_DELIVERABLES = 22
FINAL_CONCRETE_DELIVERABLES = 21


class CapabilityLifecycleScenario(LifecycleScenario):
    """Drive all three v0.5 capabilities and their refinement contract."""

    def __init__(self, root: Path) -> None:
        super().__init__(root, locale="en")
        self.refinement_applied = False
        self.refinement_plan_path: Path | None = None
        self.refinement_preview_missing_owners = 0
        self.refined_binding_baseline_adopted = False
        self.actionability_checks = {
            "waiting_items": False,
            "explicit_blockers": False,
            "governance_blockers": False,
        }

    @property
    def bindings_path(self) -> Path:
        return self.root / ".ipd" / "artifact_bindings.yaml"

    @property
    def extension_path(self) -> Path:
        return self.root / ".ipd" / "process_extensions.yaml"

    def snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def refresh_and_verify(
        self,
        label: str,
        *,
        expected_deliverable: tuple[str, str] | None = None,
        expected_gate: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run the public protocol while keeping failures concise and actionable."""

        before = self._state()
        self.invoke(("refresh", str(self.root)))
        after_refresh = self._state()
        _require(
            after_refresh["revision"] > before["revision"],
            f"refresh did not advance state revision for {label}",
        )
        verification_result = self.invoke(
            ("verify", str(self.root), "--json"), expected=None
        )
        verification = _json_output(verification_result)
        if verification_result.code != 0 or verification.get("status") != "passed":
            raise SimulationFailure(
                f"verification failed for {label}: "
                + json.dumps(
                    verification.get("issues", []),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        after_verify = self._state()
        manifest, state_data, graph_data = self._dashboard_documents()
        _require(
            after_verify["revision"] == after_refresh["revision"],
            f"verify mutated project state for {label}",
        )
        _require(
            manifest.get("state_revision") == after_verify["revision"]
            and state_data.get("project", {}).get("state_revision")
            == after_verify["revision"],
            f"Dashboard state revision was stale for {label}",
        )
        if expected_deliverable is not None:
            identifier, status = expected_deliverable
            row = next(
                item
                for item in state_data.get("deliverables", [])
                if item.get("id") == identifier
            )
            _require(
                row.get("status") == status,
                f"Dashboard status for {identifier} was not {status}",
            )
        if expected_gate is not None:
            identifier, status = expected_gate
            rows = [
                item
                for item in state_data.get("checkpoints", [])
                if item.get("id") == identifier
            ]
            _require(
                rows and all(item.get("status") == status for item in rows),
                f"Dashboard Gate status for {identifier} was not {status}",
            )
        self.iterations.append(
            {
                "label": label,
                "phase": after_verify["project"]["phase"],
                "revision_before": before["revision"],
                "revision_after": after_verify["revision"],
                "manifest_revision": manifest.get("state_revision"),
                "verification": verification.get("status"),
            }
        )
        return {
            "state": after_verify,
            "manifest": manifest,
            "state_data": state_data,
            "graph_data": graph_data,
            "runtime": load_runtime(self.root),
        }

    def _add_capability_owner_bindings(self, process: dict[str, Any]) -> None:
        bindings = load_state(self.bindings_path)
        for item in process.get("deliverables", []):
            identifier = item.get("id")
            if (
                identifier not in CAPABILITY_DELIVERABLES
                or item.get("requires_artifact_owner") is not True
            ):
                continue
            bindings["bindings"].append(
                {
                    "id": f"owner.{identifier}",
                    "glob": "src/capabilities/" + identifier.replace(".", "/") + "/**",
                    "deliverable": identifier,
                    "role": "owner",
                    "critical": True,
                    "review_required": True,
                    "description": "Authorized Owner for a selected capability Deliverable.",
                }
            )
        write_state(self.bindings_path, bindings)

    def initialize_ipd(self) -> dict[str, Any]:
        self.invoke(
            (
                "init",
                str(self.root),
                "--name",
                "Capability lifecycle simulation",
                "--locale",
                "en",
                "--task-type",
                "software",
            )
        )
        profile_path = self.root / ".ipd" / "task_profile.yaml"
        profile = load_state(profile_path)
        profile["capability_patterns"] = list(CAPABILITY_PATTERNS)
        write_state(profile_path, profile)

        preview = _json_output(
            self.invoke(("tailor", str(self.root), "--preview", "--json"))
        )
        _require(not self.process_path.exists(), "tailor preview wrote the process file")
        preview_ids = {
            item.get("id")
            for item in preview.get("added", [])
            if item.get("collection") == "deliverables"
        }
        _require(
            CAPABILITY_DELIVERABLES <= preview_ids,
            "tailor preview omitted one or more selected capability Deliverables",
        )
        _require(not preview.get("ambiguous"), "capability tailoring was ambiguous")
        self.invoke(("tailor", str(self.root)))

        process = load_state(self.process_path)
        _require(
            process.get("profile", {}).get("capability_patterns")
            == list(CAPABILITY_PATTERNS),
            "tailored process did not preserve canonical capability order",
        )
        _require(
            len(process.get("deliverables", [])) == INITIAL_DELIVERABLES,
            "software capability process did not contain 20 initial Deliverables",
        )
        rows = {item["id"]: item for item in process.get("deliverables", [])}
        _require(
            all(
                rows[identifier].get("provenance", {}).get("layer") == "capability"
                for identifier in CAPABILITY_DELIVERABLES
            ),
            "capability Deliverables lost capability provenance",
        )
        root = rows[REFINEMENT_ROOT]
        _require(
            root.get("definition_state") == "placeholder"
            and root.get("refinement_required") is True
            and root.get("completion_policy") == "all_children_accepted",
            "module implementation root lost its progressive-refinement contract",
        )

        # Capability policies declare which concrete artifacts need explicit
        # project ownership.  The first verification must fail closed until the
        # project supplies those bindings, and context must classify that state
        # as governance rather than ordinary dependency waiting.
        self.invoke(("refresh", str(self.root)))
        unbound_verify = self.invoke(
            ("verify", str(self.root), "--json"), expected=None
        )
        unbound_report = _json_output(unbound_verify)
        _require(
            unbound_verify.code != 0
            and unbound_report.get("status") == "failed"
            and unbound_report.get("eligibility", {})
            .get("summary", {})
            .get("errors")
            == 10,
            "selected capabilities did not fail closed on ten required Owners",
        )
        self._add_capability_owner_bindings(process)
        return process

    def _exercise_blocked_iteration(self, identifier: str) -> None:
        super()._exercise_blocked_iteration(identifier)
        context = self._context()
        explicit_ids = {
            item.get("id") for item in context.get("explicit_blockers", [])
        }
        self.actionability_checks["explicit_blockers"] = identifier in explicit_ids
        _require(
            self.actionability_checks["explicit_blockers"],
            "context did not classify a lifecycle-blocked Deliverable explicitly",
        )

    def _assert_waiting_actionability(self) -> None:
        context = self._context()
        waiting_ids = {item.get("id") for item in context.get("waiting_items", [])}
        expected = {
            "module.decomposition_baseline",
            "interface.contract_baseline",
            "release.strategy",
        }
        if expected <= waiting_ids:
            self.actionability_checks["waiting_items"] = True
        _require(
            self.actionability_checks["waiting_items"],
            "context did not separate dependency waiting from blocking",
        )

    def _refinement_plan(self) -> Path:
        plan = {
            "schema_version": "1.0",
            "id": "refinement.module_implementation.v1",
            "root": REFINEMENT_ROOT,
            "mode": "expand",
            "base_process_fingerprint": process_fingerprint(
                load_state(self.process_path)
            ),
            "reason": (
                "The accepted module decomposition defines independently owned "
                "motion-control and perception implementation baselines."
            ),
            "basis": [
                "evidence/module.decomposition_baseline/human-approval-1.md"
            ],
            "activities": [],
            "deliverables": [
                {
                    "id": REFINEMENT_CHILDREN[0],
                    "title": "Motion-control module implementation baseline",
                    "phase": "develop",
                    "activity_id": "develop.module_realization",
                    "review_required": True,
                    "depends_on": [
                        "module.decomposition_baseline",
                        "develop.solution_baseline",
                    ],
                    "refines": REFINEMENT_ROOT,
                    "requires_artifact_owner": True,
                },
                {
                    "id": REFINEMENT_CHILDREN[1],
                    "title": "Perception module implementation baseline",
                    "phase": "develop",
                    "activity_id": "develop.module_realization",
                    "review_required": True,
                    "depends_on": [
                        "module.decomposition_baseline",
                        "develop.solution_baseline",
                    ],
                    "refines": REFINEMENT_ROOT,
                    "requires_artifact_owner": True,
                },
            ],
            "dependencies": [],
        }
        path = (
            self.root
            / ".ipd"
            / "refinement_plans"
            / "refinement.module_implementation.v1.yaml"
        )
        write_state(path, plan)
        return path

    def _add_refined_owner_bindings(self) -> None:
        bindings = load_state(self.bindings_path)
        for identifier, pattern in zip(
            REFINEMENT_CHILDREN,
            ("src/modules/motion_control/**", "src/modules/perception/**"),
            strict=True,
        ):
            bindings["bindings"].append(
                {
                    "id": f"owner.{identifier}",
                    "glob": pattern,
                    "deliverable": identifier,
                    "role": "owner",
                    "critical": True,
                    "review_required": True,
                    "description": "Authorized Owner for a refined module baseline.",
                }
            )
        write_state(self.bindings_path, bindings)

    def _adopt_refined_binding_baseline(self) -> None:
        preview = _json_output(
            self.invoke(
                ("adopt-baseline", str(self.root), "--preview", "--json")
            )
        )
        _require(
            preview.get("eligible") is True and preview.get("adopted") is False,
            "refined Owner binding baseline was not eligible for review",
        )
        adopted = _json_output(
            self.invoke(
                (
                    "adopt-baseline",
                    str(self.root),
                    "--actor",
                    "project-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    "Adopt the reviewed Owner contract for refined module baselines.",
                    "--json",
                )
            )
        )
        _require(
            adopted.get("adopted") is True,
            "authorized refined Owner binding baseline was not adopted",
        )
        self.refined_binding_baseline_adopted = True

    def preview_module_refinement(self) -> None:
        context = self._context()
        _require(
            REFINEMENT_ROOT in context.get("refinement_due", []),
            "accepted decomposition did not make module refinement due",
        )
        plan = self._refinement_plan()
        before = self.snapshot()
        preview = _json_output(
            self.invoke(
                (
                    "refine",
                    str(self.root),
                    "--plan",
                    str(plan),
                    "--preview",
                    "--json",
                )
            )
        )
        _require(before == self.snapshot(), "refinement preview mutated the project")
        _require(
            preview.get("refinement_status") == "due"
            and preview.get("applicable") is False
            and preview.get("applied") is False
            and {item.get("code") for item in preview.get("blockers", [])}
            == {"CLOSED_PHASE"},
            "plan-phase refinement preview did not expose the develop-phase boundary",
        )
        self.refinement_preview_missing_owners = int(
            preview.get("binding_impact", {})
            .get("summary", {})
            .get("missing_owner", 0)
        )
        _require(
            self.refinement_preview_missing_owners == len(REFINEMENT_CHILDREN),
            "refinement preview did not identify both missing Owner bindings",
        )
        self.refinement_plan_path = plan

    def apply_module_refinement(self) -> None:
        _require(
            self.refinement_plan_path is not None,
            "module refinement was not previewed from the accepted decomposition",
        )
        applied = _json_output(
            self.invoke(
                (
                    "refine",
                    str(self.root),
                    "--plan",
                    str(self.refinement_plan_path),
                    "--apply",
                    "--actor",
                    "project-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    "Authorize implementation baselines from the accepted decomposition.",
                    "--json",
                )
            )
        )
        _require(applied.get("applied") is True, "authorized refinement was not applied")

        process = load_state(self.process_path)
        root = next(
            item
            for item in process.get("deliverables", [])
            if item.get("id") == REFINEMENT_ROOT
        )
        _require(
            root.get("definition_state") == "abstract",
            "refined module root did not become abstract",
        )
        _require(
            refinement_leaf_closure(process, REFINEMENT_ROOT)
            == list(REFINEMENT_CHILDREN),
            "module root concrete leaf closure was incorrect",
        )
        records = {item["id"]: item for item in self._state()["deliverables"]}
        _require(
            all(
                records[identifier].get("status") == "planned"
                and not records[identifier].get("evidence")
                and not records[identifier].get("reviews")
                for identifier in REFINEMENT_CHILDREN
            ),
            "new module children did not start with clean planned history",
        )
        # An applied plan intentionally arrives before project-specific Owner
        # paths are known.  Refresh must expose the missing binding, verify must
        # fail closed, and context must classify that protocol state as
        # governance rather than dependency waiting or an explicit block.
        self.invoke(("refresh", str(self.root)))
        missing_owner_verify = self.invoke(
            ("verify", str(self.root), "--json"), expected=None
        )
        _require(
            missing_owner_verify.code != 0
            and _json_output(missing_owner_verify).get("status") == "failed",
            "missing refined Owner bindings did not fail verification",
        )
        governance_context = self._context()
        governance_ids = {
            item.get("id")
            for item in governance_context.get("governance_blockers", [])
        }
        self.actionability_checks["governance_blockers"] = set(
            REFINEMENT_CHILDREN
        ) <= governance_ids
        _require(
            self.actionability_checks["governance_blockers"],
            "context omitted refined Deliverable governance blockers after Owner validation failed",
        )

        self._add_refined_owner_bindings()
        self._adopt_refined_binding_baseline()
        refreshed = self.refresh_and_verify("module-refinement-applied")
        dashboard_rows = {
            item["id"]: item
            for item in refreshed["state_data"].get("deliverables", [])
        }
        _require(
            dashboard_rows[REFINEMENT_ROOT].get("concrete_leaf_closure")
            == list(REFINEMENT_CHILDREN),
            "Dashboard omitted the module concrete leaf closure",
        )
        refines_edges = {
            (edge.get("source"), edge.get("target"))
            for edge in refreshed["graph_data"].get("edges", [])
            if edge.get("relation") == "refines"
        }
        _require(
            {(identifier, REFINEMENT_ROOT) for identifier in REFINEMENT_CHILDREN}
            <= refines_edges,
            "graph.json omitted module refinement lineage",
        )
        self.refinement_applied = True

    def run_lifecycle(self) -> None:
        self.refresh_and_verify("initial")
        blocked_used = False

        for phase_index, phase in enumerate(EXPECTED_PHASES):
            _require(
                self._state()["project"]["phase"] == phase,
                f"project did not enter expected phase {phase}",
            )
            if phase == "plan":
                self._assert_waiting_actionability()
            if phase == "develop" and not self.refinement_applied:
                self.apply_module_refinement()

            process = load_state(self.process_path)
            phase_ids = {
                item["id"]
                for item in process.get("deliverables", [])
                if item.get("phase") == phase
                and item.get("definition_state", "concrete") == "concrete"
            }
            while phase_ids:
                context = self._context()
                available = sorted(
                    item["id"]
                    for item in context.get("available_tasks", [])
                    if item["id"] in phase_ids
                )
                _require(available, f"no available Deliverable could progress {phase}")
                identifier = available[0]
                self.process_deliverable(identifier, block_once=not blocked_used)
                blocked_used = True
                phase_ids.remove(identifier)

                if (
                    identifier == "module.decomposition_baseline"
                    and self.refinement_plan_path is None
                ):
                    self.preview_module_refinement()

            process = load_state(self.process_path)
            tr, dcp = self._checkpoint_aliases(process, phase)
            self.process_gate(tr[0], tr[1])
            self.process_gate(dcp[0], dcp[1])

            if phase_index + 1 < len(EXPECTED_PHASES):
                self.invoke(("advance-phase", str(self.root)))
                self.phase_advances += 1
                next_phase = EXPECTED_PHASES[phase_index + 1]
                _require(
                    self._state()["project"]["phase"] == next_phase,
                    f"advance-phase did not enter {next_phase}",
                )
                self.refresh_and_verify(f"phase-advanced:{phase}->{next_phase}")
            else:
                before = self._state()
                result = self.invoke(("advance-phase", str(self.root)), expected=None)
                _require(result.code != 0, "advance-phase moved beyond lifecycle")
                _require(self._state() == before, "final advance probe mutated state")

        _require(blocked_used, "explicit blocked/reclaim path was not exercised")
        _require(self.refinement_applied, "module refinement was not exercised")

    def final_checks(self) -> dict[str, Any]:
        final = self.refresh_and_verify("lifecycle-completion-idempotence")
        verification = _json_output(
            self.invoke(("verify", str(self.root), "--json"))
        )
        _require(verification.get("status") == "passed", "final verify did not pass")

        process = load_state(self.process_path)
        state = self._state()
        runtime = load_runtime(self.root)
        records = {item["id"]: item for item in state.get("deliverables", [])}
        process_rows = {
            item["id"]: item for item in process.get("deliverables", [])
        }
        concrete_ids = {
            identifier
            for identifier, item in process_rows.items()
            if item.get("definition_state", "concrete") == "concrete"
        }
        _require(
            len(records) == FINAL_DELIVERABLES
            and len(concrete_ids) == FINAL_CONCRETE_DELIVERABLES,
            "refined process inventory did not contain 22 total / 21 concrete Deliverables",
        )
        _require(
            all(records[identifier].get("status") == "accepted" for identifier in concrete_ids),
            "one or more concrete Deliverables did not reach accepted",
        )
        _require(
            all(
                records[identifier].get("evidence")
                and records[identifier].get("reviews")
                for identifier in concrete_ids
            ),
            "accepted Deliverable evidence or review history was lost",
        )
        _require(
            len(state.get("gates", [])) == 12
            and all(item.get("status") == "approved" for item in state["gates"]),
            "not all canonical TR/DCP Gates were approved",
        )
        _require(
            state.get("project", {}).get("phase") == "lifecycle",
            "project did not finish in lifecycle",
        )
        _require(not runtime.get("active_claims"), "active Claims remained")
        refinement_events = [
            item
            for item in runtime.get("events", [])
            if item.get("action") == "process_refinement_applied"
            and item.get("root") == REFINEMENT_ROOT
        ]
        _require(
            len(refinement_events) == 1,
            "module refinement runtime provenance was not recorded exactly once",
        )

        dashboard_files = {
            path.relative_to(self.dashboard).as_posix()
            for path in self.dashboard.rglob("*")
            if path.is_file()
        }
        _require(
            dashboard_files == EXPECTED_DASHBOARD_FILES,
            "Dashboard output inventory diverged from the 16-file contract",
        )
        graph_data = final["graph_data"]
        state_data = final["state_data"]
        graph_deliverables = {
            item.get("id")
            for item in graph_data.get("nodes", [])
            if item.get("type") == "Deliverable"
        }
        _require(
            graph_deliverables == set(records),
            "graph.json did not expose the complete refined Deliverable inventory",
        )
        _require(
            state_data.get("refinement_due") == [],
            "resolved module refinement remained due on the final Dashboard",
        )
        final_context = self._context()
        _require(
            not final_context.get("waiting_items")
            and not final_context.get("explicit_blockers")
            and not final_context.get("governance_blockers"),
            "final context retained stale waiting or blocker entries",
        )
        _require(
            all(self.actionability_checks.values()),
            "the three context actionability categories were not all exercised",
        )
        _require(
            set(CAPABILITY_DELIVERABLES) <= set(records),
            "final state omitted selected capability Deliverables",
        )

        return {
            "phases": len(process.get("phases", [])),
            "capability_patterns": len(CAPABILITY_PATTERNS),
            "initial_deliverables": INITIAL_DELIVERABLES,
            "final_deliverables": len(records),
            "concrete_deliverables": len(concrete_ids),
            "accepted_concrete_deliverables": sum(
                records[identifier].get("status") == "accepted"
                for identifier in concrete_ids
            ),
            "approved_gates": sum(
                item.get("status") == "approved" for item in state.get("gates", [])
            ),
            "current_phase": state.get("project", {}).get("phase"),
            "refinement_events": len(refinement_events),
            "refinement_children": list(
                refinement_leaf_closure(process, REFINEMENT_ROOT)
            ),
            "refinement_preview_missing_owners": self.refinement_preview_missing_owners,
            "refined_binding_baseline_adopted": self.refined_binding_baseline_adopted,
            "history_preserved": all(
                records[identifier].get("evidence")
                and records[identifier].get("reviews")
                for identifier in concrete_ids
            ),
            "actionability": dict(self.actionability_checks),
            "dashboard_files": len(dashboard_files),
            "graph_nodes": len(graph_data.get("nodes", [])),
            "graph_edges": len(graph_data.get("edges", [])),
            "final_verify": verification.get("status"),
            "active_claims": len(runtime.get("active_claims", {})),
            "phase_advances": self.phase_advances,
        }


def run_simulation() -> dict[str, Any]:
    """Run the isolated capability lifecycle and return its diagnostic report."""

    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "scenario": "v0.5-capability-lifecycle",
        "capability_patterns": list(CAPABILITY_PATTERNS),
        "passed": False,
        "checks": {},
        "iterations": [],
        "commands": [],
        "missing_outputs": [],
        "severe_issues": [],
        "cleanup_confirmed": False,
    }
    project_root: Path | None = None
    scenario: CapabilityLifecycleScenario | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="ipd-capability-lifecycle-") as directory:
            project_root = Path(directory) / "software-project"
            scenario = CapabilityLifecycleScenario(project_root)
            scenario.initialize_git()
            scenario.initialize_ipd()
            scenario.run_lifecycle()
            report["checks"] = scenario.final_checks()
            report["iterations"] = scenario.iterations
            report["commands"] = scenario.commands
            report["passed"] = True
        report["cleanup_confirmed"] = bool(
            project_root is not None and not project_root.exists()
        )
        if not report["cleanup_confirmed"]:
            report["passed"] = False
            report["severe_issues"].append("temporary project directory was not removed")
    except Exception as exc:
        report["severe_issues"].append(f"{type(exc).__name__}: {exc}")
        if scenario is not None:
            report["iterations"] = list(scenario.iterations)
            report["commands"] = list(scenario.commands)
        if project_root is not None:
            dashboard = project_root / ".ipd" / "dashboard"
            if dashboard.exists():
                actual = {
                    path.relative_to(dashboard).as_posix()
                    for path in dashboard.rglob("*")
                    if path.is_file()
                }
                report["missing_outputs"] = sorted(
                    EXPECTED_DASHBOARD_FILES - actual
                )
        report["cleanup_confirmed"] = project_root is None or not project_root.exists()
    report["duration_seconds"] = round(time.perf_counter() - started, 3)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    checks = report.get("checks", {})
    lines = [
        "# v0.5 Capability Lifecycle Simulation",
        "",
        f"**Result:** {'PASS' if report.get('passed') else 'FAIL'}",
        "",
        f"- Capability patterns: {checks.get('capability_patterns', 0)}",
        f"- Accepted concrete Deliverables: {checks.get('accepted_concrete_deliverables', 0)}",
        f"- Approved Gates: {checks.get('approved_gates', 0)}",
        f"- Refinement events: {checks.get('refinement_events', 0)}",
        f"- Dashboard files: {checks.get('dashboard_files', 0)}",
        f"- Final verify: {checks.get('final_verify', 'not run')}",
        f"- Temporary project cleaned: {report.get('cleanup_confirmed')}",
    ]
    if report.get("severe_issues"):
        lines.extend(("", "## Severe issues", ""))
        lines.extend(f"- {item}" for item in report["severe_issues"])
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated v0.5 capability lifecycle simulation."
    )
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_simulation()
    print(
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.json
        else render_markdown(report),
        end="\n" if args.json else "",
    )
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Simulate two governed progressive-refinement iterations through public CLI.

The scenario creates an isolated project, accepts a concrete project root,
expands it twice, and checks history, owner bindings, Gate epochs, runtime
events, and Dashboard projections. The temporary project is always removed.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ipdctl.cli import main as cli_main
from ipdctl.project import verification_input_fingerprint
from ipdctl.refinement import process_fingerprint, refinement_leaf_closure
from ipdctl.runtime import load_runtime
from ipdctl.state import load_state, write_state


ROOT = "concept.system_architecture"
INTERMEDIATE = "concept.perception_architecture"
SIBLING = "concept.mobility_contract"
DOWNSTREAM = "concept.architecture_readiness"
LEAF_CAPTURE = "concept.perception_capture"
LEAF_FUSION = "concept.perception_fusion"
ROOT_ACTIVITY = "concept.define_system_architecture"
INTERMEDIATE_ACTIVITY = "concept.define_perception_architecture"
SIBLING_ACTIVITY = "concept.define_mobility_contract"
DOWNSTREAM_ACTIVITY = "concept.assess_architecture_readiness"
LEAF_CAPTURE_ACTIVITY = "concept.define_perception_capture"
LEAF_FUSION_ACTIVITY = "concept.define_perception_fusion"

EXPECTED_DASHBOARD_FILES = frozenset(
    {
        "index.html",
        "governance.md",
        "assets/ipd_flow.svg",
        "assets/current_status_flow.svg",
        "assets/deliverable_dependency.svg",
        "phases/concept.svg",
        "phases/plan.svg",
        "phases/develop.svg",
        "phases/qualify.svg",
        "phases/launch.svg",
        "phases/lifecycle.svg",
        "matrices/deliverable_matrix.html",
        "matrices/gate_matrix.html",
        "data/state.json",
        "data/graph.json",
        "manifest.json",
    }
)


class SimulationFailure(RuntimeError):
    """Raised when an expected public contract is absent."""


@dataclass(frozen=True)
class CommandResult:
    arguments: tuple[str, ...]
    code: int
    stdout: str
    stderr: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SimulationFailure(message)


def _json(result: CommandResult) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SimulationFailure(
            f"command did not emit JSON: {' '.join(result.arguments)}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SimulationFailure("CLI JSON output must be an object")
    return value


class ProgressiveRefinementScenario:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.commands: list[dict[str, Any]] = []
        self.iterations: list[dict[str, Any]] = []

    @property
    def ipd(self) -> Path:
        return self.root / ".ipd"

    @property
    def state_path(self) -> Path:
        return self.ipd / "project_state.yaml"

    @property
    def process_path(self) -> Path:
        return self.ipd / "tailored_process.yaml"

    @property
    def extension_path(self) -> Path:
        return self.ipd / "process_extensions.yaml"

    @property
    def bindings_path(self) -> Path:
        return self.ipd / "artifact_bindings.yaml"

    @property
    def runtime_path(self) -> Path:
        return self.ipd / "agent_runtime.yaml"

    @property
    def dashboard(self) -> Path:
        return self.ipd / "dashboard"

    def invoke(
        self, arguments: Sequence[str], *, expected: int | None = 0
    ) -> CommandResult:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_main(list(arguments))
        result = CommandResult(
            tuple(str(item) for item in arguments),
            int(code),
            stdout.getvalue(),
            stderr.getvalue(),
        )
        self.commands.append(
            {
                "arguments": [
                    "<project>" if item == str(self.root) else item
                    for item in result.arguments
                ],
                "code": result.code,
            }
        )
        if expected is not None and result.code != expected:
            detail = (result.stderr or result.stdout).strip()
            raise SimulationFailure(
                f"command returned {result.code}, expected {expected}: "
                f"{' '.join(result.arguments)}: {detail}"
            )
        return result

    def snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def state(self) -> dict[str, Any]:
        return load_state(self.state_path)

    def process(self) -> dict[str, Any]:
        return load_state(self.process_path)

    def deliverable(self, identifier: str) -> dict[str, Any]:
        return next(
            item
            for item in self.state().get("deliverables", [])
            if item.get("id") == identifier
        )

    def initialize(self) -> None:
        self.invoke(("init", str(self.root), "--name", "progressive-refinement"))
        extension = load_state(self.extension_path)
        extension["extension_id"] = "simulation.progressive_refinement"
        extension["activities"].append(
            {
                "id": ROOT_ACTIVITY,
                "title": "Define the project system architecture",
                "phase": "concept",
                "sequence": 12,
            }
        )
        extension["activities"].append(
            {
                "id": DOWNSTREAM_ACTIVITY,
                "title": "Assess architecture readiness",
                "phase": "concept",
                "sequence": 19,
            }
        )
        extension["deliverables"].append(
            {
                "id": ROOT,
                "title": "Project system architecture baseline",
                "phase": "concept",
                "activity_id": ROOT_ACTIVITY,
                "review_required": True,
                "depends_on": ["concept.problem_definition"],
                "requires_artifact_owner": False,
            }
        )
        extension["deliverables"].append(
            {
                "id": DOWNSTREAM,
                "title": "Architecture readiness assessment",
                "phase": "concept",
                "activity_id": DOWNSTREAM_ACTIVITY,
                "review_required": True,
                "depends_on": [ROOT],
                "requires_artifact_owner": False,
            }
        )
        extension["refinement_requirements"].append(
            {
                "root": ROOT,
                "definition_state": "concrete",
                "refinement_required": True,
                "trigger": {
                    "all_of": [{"subject": ROOT, "condition": "accepted"}]
                },
                "completion_policy": "all_children_accepted",
            }
        )
        write_state(self.extension_path, extension)
        self.invoke(("tailor", str(self.root)))
        root = self.deliverable(ROOT)
        _require(root.get("definition_state") == "concrete", "root was not concrete")
        _require(root.get("refinement_required") is True, "root requirement was lost")

    def evidence(self, identifier: str, name: str, text: str) -> str:
        path = self.root / "evidence" / identifier / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        return path.relative_to(self.root).as_posix()

    def refresh_verify(self, label: str, *, expected_pass: bool = True) -> dict[str, Any]:
        self.invoke(("refresh", str(self.root)))
        verification_result = self.invoke(
            ("verify", str(self.root), "--json"), expected=0 if expected_pass else None
        )
        verification = _json(verification_result)
        expected_status = "passed" if expected_pass else "failed"
        _require(
            verification.get("status") == expected_status,
            f"verify status for {label} was not {expected_status}",
        )
        if not expected_pass:
            _require(verification_result.code != 0, f"failed verify passed for {label}")
        actual_files = {
            path.relative_to(self.dashboard).as_posix()
            for path in self.dashboard.rglob("*")
            if path.is_file()
        }
        _require(
            actual_files == EXPECTED_DASHBOARD_FILES,
            f"Dashboard inventory mismatch for {label}: "
            f"missing={sorted(EXPECTED_DASHBOARD_FILES - actual_files)}, "
            f"extra={sorted(actual_files - EXPECTED_DASHBOARD_FILES)}",
        )
        state_data = json.loads(
            (self.dashboard / "data" / "state.json").read_text(encoding="utf-8")
        )
        graph_data = json.loads(
            (self.dashboard / "data" / "graph.json").read_text(encoding="utf-8")
        )
        self.iterations.append(
            {
                "label": label,
                "verification": expected_status,
                "state_revision": self.state().get("revision"),
                "refinement_due": [
                    item.get("id") for item in state_data.get("refinement_due", [])
                ],
            }
        )
        return {
            "verification": verification,
            "state_data": state_data,
            "graph_data": graph_data,
        }

    def accept(self, identifier: str, *, actor: str) -> None:
        self.invoke(
            ("claim", identifier, "--project-root", str(self.root), "--actor", actor)
        )
        self.complete_active_claim(identifier, actor=actor)

    def complete_active_claim(self, identifier: str, *, actor: str) -> None:
        work = self.evidence(identifier, "work", f"Work evidence for {identifier}.")
        self.invoke(
            (
                "close",
                identifier,
                "--project-root",
                str(self.root),
                "--actor",
                actor,
                "--evidence",
                work,
            )
        )
        self.invoke(
            (
                "review",
                identifier,
                "--project-root",
                str(self.root),
                "--reviewer",
                "review-agent",
            )
        )
        approval = self.evidence(
            identifier, "approval", f"Human approval for {identifier}."
        )
        self.invoke(
            (
                "approve",
                identifier,
                "--project-root",
                str(self.root),
                "--reviewer",
                "design-authority",
                "--actor-type",
                "human",
                "--authorized",
                "--evidence",
                approval,
            )
        )

    def assert_refine_rejected(
        self,
        plan: Path,
        *,
        arguments: Sequence[str],
        expected_text: str,
    ) -> None:
        before = self.snapshot()
        result = self.invoke(
            ("refine", str(self.root), "--plan", str(plan), *arguments),
            expected=None,
        )
        _require(result.code != 0, f"refine rejection unexpectedly passed: {expected_text}")
        _require(
            expected_text in (result.stdout + result.stderr),
            f"refine rejection did not expose {expected_text!r}",
        )
        _require(self.snapshot() == before, f"failed refinement wrote files: {expected_text}")

    def assert_tailor_rejected(self, *, expected_text: str) -> None:
        before = self.snapshot()
        result = self.invoke(("tailor", str(self.root)), expected=None)
        _require(result.code != 0, "unauthorized re-tailor unexpectedly passed")
        _require(
            expected_text in (result.stdout + result.stderr),
            f"tailor rejection did not expose {expected_text!r}",
        )
        _require(self.snapshot() == before, "failed re-tailor wrote project files")

    def make_plan(
        self,
        *,
        plan_id: str,
        root: str,
        activities: list[dict[str, Any]],
        deliverables: list[dict[str, Any]],
    ) -> Path:
        plan = {
            "schema_version": "1.0",
            "id": plan_id,
            "root": root,
            "mode": "expand",
            "base_process_fingerprint": process_fingerprint(self.process()),
            "reason": f"Expand {root} from accepted architecture evidence.",
            "basis": [f"evidence/{root}/approval.md"],
            "activities": activities,
            "deliverables": deliverables,
            "dependencies": [],
        }
        path = self.ipd / "refinement_plans" / f"{plan_id}.yaml"
        write_state(path, plan)
        return path

    def preview_twice(self, plan: Path) -> dict[str, Any]:
        before = self.snapshot()
        first = _json(
            self.invoke(
                ("refine", str(self.root), "--plan", str(plan), "--preview", "--json")
            )
        )
        after_first = self.snapshot()
        second = _json(
            self.invoke(
                ("refine", str(self.root), "--plan", str(plan), "--preview", "--json")
            )
        )
        _require(first == second, "refinement preview was not deterministic")
        _require(before == after_first == self.snapshot(), "preview wrote project files")
        _require(first.get("applicable") is True, "due refinement was not applicable")
        _require(first.get("applied") is False, "preview reported itself as applied")
        return first

    def apply(self, plan: Path, *, reason: str) -> dict[str, Any]:
        result = _json(
            self.invoke(
                (
                    "refine",
                    str(self.root),
                    "--plan",
                    str(plan),
                    "--apply",
                    "--actor",
                    "project-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    reason,
                    "--json",
                )
            )
        )
        _require(result.get("applied") is True, "authorized refinement was not applied")
        runtime = load_runtime(self.root)
        _require(
            runtime.get("last_verification", {}).get("input_fingerprint")
            != verification_input_fingerprint(self.root),
            "refinement did not invalidate the previous verification fingerprint",
        )
        return result

    def assert_new_children(self, identifiers: Sequence[str]) -> None:
        records = {item["id"]: item for item in self.state()["deliverables"]}
        for identifier in identifiers:
            item = records[identifier]
            _require(item.get("status") == "planned", f"{identifier} was not planned")
            _require(item.get("evidence") == [], f"{identifier} inherited evidence")
            _require(item.get("reviews") == [], f"{identifier} inherited reviews")

    def assert_missing_owner_claim(self, identifier: str) -> None:
        before_state = self.state()
        before_runtime = load_runtime(self.root)
        result = self.invoke(
            (
                "claim",
                identifier,
                "--project-root",
                str(self.root),
                "--actor",
                "agent-owner-probe",
            ),
            expected=None,
        )
        _require(result.code != 0, "Claim without an explicit Owner unexpectedly passed")
        _require(
            "REFINEMENT_OWNER_REQUIRED" in (result.stderr + result.stdout),
            "Claim failure did not expose REFINEMENT_OWNER_REQUIRED",
        )
        _require(self.state() == before_state, "failed Owner Claim mutated project state")
        _require(
            load_runtime(self.root) == before_runtime,
            "failed Owner Claim mutated Agent runtime",
        )

    def assert_refinement_dependency_claim_blocked(self, identifier: str) -> None:
        before = self.snapshot()
        result = self.invoke(
            (
                "claim",
                identifier,
                "--project-root",
                str(self.root),
                "--actor",
                "agent-downstream-probe",
            ),
            expected=None,
        )
        _require(result.code != 0, "downstream Claim passed before refinement")
        _require(
            "REFINEMENT_DEPENDENCY_REQUIRED" in (result.stdout + result.stderr),
            "downstream Claim did not expose REFINEMENT_DEPENDENCY_REQUIRED",
        )
        _require(self.snapshot() == before, "failed downstream Claim wrote files")

    def add_owner_bindings(self, mapping: dict[str, str]) -> None:
        bindings = load_state(self.bindings_path)
        for identifier, pattern in mapping.items():
            bindings["bindings"].append(
                {
                    "id": f"owner.{identifier}",
                    "glob": pattern,
                    "deliverable": identifier,
                    "role": "owner",
                    "critical": True,
                    "review_required": True,
                    "description": "Explicit project Owner for a refined Deliverable.",
                }
            )
        write_state(self.bindings_path, bindings)

    def assert_due(self, identifier: str, dashboard: dict[str, Any]) -> None:
        context = _json(self.invoke(("context", str(self.root), "--json")))
        _require(identifier in context.get("refinement_due", []), f"{identifier} not due")
        dashboard_due = {
            item.get("id") for item in dashboard["state_data"].get("refinement_due", [])
        }
        _require(identifier in dashboard_due, f"Dashboard omitted due root {identifier}")

    def assert_gate_epoch(self, expected: int) -> None:
        concept_gates = [
            gate
            for gate in self.state().get("gates", [])
            if gate.get("phase") == "concept"
        ]
        _require(len(concept_gates) == 2, "Concept TR/DCP Gate pair was missing")
        _require(
            all(gate.get("review_epoch") == expected for gate in concept_gates),
            f"Concept Gate review epoch was not {expected}",
        )
        _require(
            all(gate.get("stale") is True for gate in concept_gates),
            "changed Gate requirements were not marked stale",
        )

    def replay_noop(self, plan: Path) -> None:
        before = self.snapshot()
        before_events = list(load_runtime(self.root).get("events", []))
        result = _json(
            self.invoke(
                (
                    "refine",
                    str(self.root),
                    "--plan",
                    str(plan),
                    "--apply",
                    "--actor",
                    "project-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    "Replay the same authorized plan.",
                    "--json",
                )
            )
        )
        _require(result.get("already_applied") is True, "plan replay was not a no-op")
        _require(result.get("applied") is False, "plan replay reported a new application")
        _require(self.snapshot() == before, "idempotent plan replay wrote project files")
        _require(
            load_runtime(self.root).get("events", []) == before_events,
            "idempotent plan replay appended a runtime event",
        )
        conflict = load_state(plan)
        conflict["reason"] = "Conflicting content for an already applied plan ID."
        conflict_path = plan.with_name(plan.stem + ".conflict.yaml")
        write_state(conflict_path, conflict)
        self.assert_refine_rejected(
            conflict_path,
            arguments=(
                "--apply",
                "--actor",
                "project-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Attempt conflicting replay.",
            ),
            expected_text="different digest",
        )
        runtime = load_runtime(self.root)
        tampered = dict(runtime)
        tampered["events"] = [
            item
            for item in runtime.get("events", [])
            if not (
                item.get("action") == "process_refinement_applied"
                and item.get("plan_id") == load_state(plan)["id"]
            )
        ]
        write_state(self.runtime_path, tampered)
        self.assert_refine_rejected(
            plan,
            arguments=(
                "--apply",
                "--actor",
                "project-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Reject replay with missing runtime provenance.",
            ),
            expected_text="project bundle is inconsistent",
        )
        write_state(self.runtime_path, runtime)
        for field, value in (
            ("result_process_fingerprint", "sha256:" + "f" * 64),
            ("invalidated_gates", ["gate.dcp.concept"]),
        ):
            field_tampered = deepcopy(runtime)
            target_event = next(
                item
                for item in field_tampered.get("events", [])
                if item.get("action") == "process_refinement_applied"
                and item.get("plan_id") == load_state(plan)["id"]
            )
            target_event[field] = value
            write_state(self.runtime_path, field_tampered)
            self.assert_refine_rejected(
                plan,
                arguments=(
                    "--apply",
                    "--actor",
                    "project-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    f"Reject replay with tampered {field}.",
                ),
                expected_text="project bundle is inconsistent",
            )
            write_state(self.runtime_path, runtime)
        duplicate = dict(runtime)
        duplicate_event = next(
            item
            for item in runtime.get("events", [])
            if item.get("action") == "process_refinement_applied"
            and item.get("plan_id") == load_state(plan)["id"]
        )
        duplicate["events"] = [*runtime.get("events", []), dict(duplicate_event)]
        write_state(self.runtime_path, duplicate)
        self.assert_refine_rejected(
            plan,
            arguments=(
                "--apply",
                "--actor",
                "project-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "Reject replay with duplicate runtime provenance.",
            ),
            expected_text="project bundle is inconsistent",
        )
        write_state(self.runtime_path, runtime)

    def final_checks(
        self,
        root_history: dict[str, Any],
        intermediate_history: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.state()
        process = self.process()
        records = {item["id"]: item for item in state["deliverables"]}
        _require(
            records[ROOT]["evidence"] == root_history["evidence"]
            and records[ROOT]["reviews"] == root_history["reviews"]
            and records[ROOT]["status"] == "accepted",
            "root history was not preserved across two refinements",
        )
        _require(
            records[INTERMEDIATE]["evidence"] == intermediate_history["evidence"]
            and records[INTERMEDIATE]["reviews"] == intermediate_history["reviews"]
            and records[INTERMEDIATE]["status"] == "accepted",
            "intermediate history was not preserved after second refinement",
        )
        expected_root_leaves = [SIBLING, LEAF_CAPTURE, LEAF_FUSION]
        root_leaves = refinement_leaf_closure(process, ROOT)
        intermediate_leaves = refinement_leaf_closure(process, INTERMEDIATE)
        _require(root_leaves == expected_root_leaves, "root leaf closure was incorrect")
        _require(
            intermediate_leaves == [LEAF_CAPTURE, LEAF_FUSION],
            "intermediate leaf closure was incorrect",
        )

        runtime = load_runtime(self.root)
        events = [
            event
            for event in runtime.get("events", [])
            if event.get("action") == "process_refinement_applied"
        ]
        _require(len(events) == 2, "runtime did not contain exactly two refinements")
        _require(
            [event.get("root") for event in events] == [ROOT, INTERMEDIATE],
            "runtime refinement root history was out of order",
        )

        state_data = json.loads(
            (self.dashboard / "data" / "state.json").read_text(encoding="utf-8")
        )
        graph_data = json.loads(
            (self.dashboard / "data" / "graph.json").read_text(encoding="utf-8")
        )
        dashboard_records = {
            item["id"]: item for item in state_data.get("deliverables", [])
        }
        _require(
            dashboard_records[ROOT]["concrete_leaf_closure"] == expected_root_leaves,
            "Dashboard root leaf closure diverged from process facts",
        )
        _require(
            dashboard_records[INTERMEDIATE]["concrete_leaf_closure"]
            == [LEAF_CAPTURE, LEAF_FUSION],
            "Dashboard intermediate leaf closure diverged from process facts",
        )
        _require(not state_data.get("refinement_due"), "resolved refinement stayed due")
        _require(
            records[DOWNSTREAM]["depends_on"]
            == [SIBLING, LEAF_CAPTURE, LEAF_FUSION],
            "downstream dependency closure did not follow both refinements",
        )
        expected_edges = {
            (INTERMEDIATE, ROOT),
            (SIBLING, ROOT),
            (LEAF_CAPTURE, INTERMEDIATE),
            (LEAF_FUSION, INTERMEDIATE),
        }
        actual_edges = {
            (edge.get("source"), edge.get("target"))
            for edge in graph_data.get("edges", [])
            if edge.get("relation") == "refines"
        }
        _require(expected_edges <= actual_edges, "graph.json omitted refines edges")
        _require("refines" in graph_data.get("relation_types", []), "refines type missing")
        return {
            "refinement_events": len(events),
            "root_leaf_closure": root_leaves,
            "intermediate_leaf_closure": intermediate_leaves,
            "dashboard_files": len(EXPECTED_DASHBOARD_FILES),
            "concept_gate_epoch": 2,
            "history_preserved": True,
            "owner_preflight_exercised": True,
            "idempotent_replay": True,
            "fail_closed_preflight_cases": 4,
            "plan_conflict_rejected": True,
            "verification_invalidated": True,
            "input_drift_rejected": True,
            "runtime_replay_tamper_rejected": True,
            "runtime_result_fingerprint_tamper_rejected": True,
            "runtime_invalidated_gates_tamper_rejected": True,
            "duplicate_runtime_event_rejected": True,
            "due_requirement_removal_rejected": True,
            "downstream_claim_blocked_until_refined": True,
        }

    def run(self) -> dict[str, Any]:
        self.initialize()
        self.accept("concept.problem_definition", actor="agent-foundation")
        self.refresh_verify("foundation-accepted")
        first_plan = self.make_plan(
            plan_id="refinement.system_architecture.v1",
            root=ROOT,
            activities=[
                {
                    "id": INTERMEDIATE_ACTIVITY,
                    "title": "Define perception architecture",
                    "phase": "concept",
                    "sequence": 13,
                },
                {
                    "id": SIBLING_ACTIVITY,
                    "title": "Define mobility interface contract",
                    "phase": "concept",
                    "sequence": 14,
                },
            ],
            deliverables=[
                {
                    "id": INTERMEDIATE,
                    "title": "Perception architecture baseline",
                    "phase": "concept",
                    "activity_id": INTERMEDIATE_ACTIVITY,
                    "review_required": True,
                    "depends_on": ["concept.problem_definition"],
                    "refines": ROOT,
                    "definition_state": "concrete",
                    "refinement_required": True,
                    "refinement_trigger": {
                        "all_of": [
                            {"subject": INTERMEDIATE, "condition": "accepted"}
                        ]
                    },
                    "requires_artifact_owner": True,
                },
                {
                    "id": SIBLING,
                    "title": "Mobility interface contract",
                    "phase": "concept",
                    "activity_id": SIBLING_ACTIVITY,
                    "review_required": True,
                    "depends_on": ["concept.problem_definition"],
                    "refines": ROOT,
                    "requires_artifact_owner": True,
                },
            ],
        )
        authority = (
            "--apply",
            "--actor",
            "project-owner",
            "--actor-type",
            "human",
            "--authorized",
            "--reason",
            "Exercise a fail-closed refinement preflight.",
        )
        self.assert_refine_rejected(
            first_plan,
            arguments=authority,
            expected_text="trigger is not yet satisfied",
        )
        self.invoke(
            (
                "claim",
                ROOT,
                "--project-root",
                str(self.root),
                "--actor",
                "agent-architecture",
            )
        )
        self.assert_refine_rejected(
            first_plan,
            arguments=authority,
            expected_text="Claims are active",
        )
        self.complete_active_claim(ROOT, actor="agent-architecture")
        due_root = self.refresh_verify("root-accepted-and-due")
        self.assert_due(ROOT, due_root)
        root_history = self.deliverable(ROOT)
        self.assert_refinement_dependency_claim_blocked(DOWNSTREAM)
        governed_extension = load_state(self.extension_path)
        removed_requirement = load_state(self.extension_path)
        removed_requirement["refinement_requirements"] = [
            item
            for item in removed_requirement.get("refinement_requirements", [])
            if item.get("root") != ROOT
        ]
        write_state(self.extension_path, removed_requirement)
        self.assert_tailor_rejected(expected_text="ipdctl refine --apply")
        write_state(self.extension_path, governed_extension)
        self.assert_refine_rejected(
            first_plan,
            arguments=("--apply",),
            expected_text="requires --actor",
        )
        stale_plan_data = load_state(first_plan)
        stale_plan_data["base_process_fingerprint"] = "sha256:" + "0" * 64
        stale_plan = first_plan.with_name(first_plan.stem + ".stale.yaml")
        write_state(stale_plan, stale_plan_data)
        self.assert_refine_rejected(
            stale_plan,
            arguments=authority,
            expected_text="base process fingerprint",
        )
        first_preview = self.preview_twice(first_plan)
        _require(
            first_preview.get("binding_impact", {}).get("summary", {}).get(
                "missing_owner"
            )
            == 2,
            "first preview did not report both missing Owners",
        )
        self.apply(first_plan, reason="Authorize first architecture expansion.")
        self.assert_new_children((INTERMEDIATE, SIBLING))
        self.assert_gate_epoch(1)
        self.refresh_verify("first-refinement-missing-owner", expected_pass=False)
        self.assert_missing_owner_claim(INTERMEDIATE)
        self.add_owner_bindings(
            {
                INTERMEDIATE: "src/perception/**",
                SIBLING: "src/mobility/**",
            }
        )
        self.refresh_verify("first-refinement-owner-ready")

        self.accept(INTERMEDIATE, actor="agent-perception")
        due_intermediate = self.refresh_verify("intermediate-accepted-and-due")
        self.assert_due(INTERMEDIATE, due_intermediate)
        intermediate_history = self.deliverable(INTERMEDIATE)

        second_plan = self.make_plan(
            plan_id="refinement.perception_architecture.v1",
            root=INTERMEDIATE,
            activities=[
                {
                    "id": LEAF_CAPTURE_ACTIVITY,
                    "title": "Define perception capture contract",
                    "phase": "concept",
                    "sequence": 15,
                },
                {
                    "id": LEAF_FUSION_ACTIVITY,
                    "title": "Define perception fusion contract",
                    "phase": "concept",
                    "sequence": 16,
                },
            ],
            deliverables=[
                {
                    "id": LEAF_CAPTURE,
                    "title": "Perception capture contract",
                    "phase": "concept",
                    "activity_id": LEAF_CAPTURE_ACTIVITY,
                    "review_required": True,
                    "depends_on": ["concept.problem_definition"],
                    "refines": INTERMEDIATE,
                    "requires_artifact_owner": True,
                },
                {
                    "id": LEAF_FUSION,
                    "title": "Perception fusion contract",
                    "phase": "concept",
                    "activity_id": LEAF_FUSION_ACTIVITY,
                    "review_required": True,
                    "depends_on": ["concept.problem_definition"],
                    "refines": INTERMEDIATE,
                    "requires_artifact_owner": True,
                },
            ],
        )
        governed_extension = load_state(self.extension_path)
        drifted_extension = load_state(self.extension_path)
        next(
            item
            for item in drifted_extension["deliverables"]
            if item["id"] == SIBLING
        )["title"] = "Unreviewed mobility contract title"
        write_state(self.extension_path, drifted_extension)
        self.assert_refine_rejected(
            second_plan,
            arguments=authority,
            expected_text="no longer compiles to the governed tailored process",
        )
        write_state(self.extension_path, governed_extension)
        second_preview = self.preview_twice(second_plan)
        _require(
            second_preview.get("binding_impact", {}).get("summary", {}).get(
                "missing_owner"
            )
            == 2,
            "second preview did not report both missing Owners",
        )
        self.apply(second_plan, reason="Authorize perception subsystem expansion.")
        self.assert_new_children((LEAF_CAPTURE, LEAF_FUSION))
        self.assert_gate_epoch(2)
        self.refresh_verify("second-refinement-missing-owner", expected_pass=False)
        self.assert_missing_owner_claim(LEAF_CAPTURE)
        self.add_owner_bindings(
            {
                LEAF_CAPTURE: "src/perception/capture/**",
                LEAF_FUSION: "src/perception/fusion/**",
            }
        )
        self.refresh_verify("second-refinement-owner-ready")
        self.replay_noop(second_plan)
        return self.final_checks(root_history, intermediate_history)


def run_simulation() -> dict[str, Any]:
    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "scenario": "two-round-progressive-refinement",
        "passed": False,
        "checks": {},
        "iterations": [],
        "commands": [],
        "severe_issues": [],
        "cleanup_confirmed": False,
    }
    project_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="ipd-progressive-refinement-") as directory:
            project_root = Path(directory) / "project"
            scenario = ProgressiveRefinementScenario(project_root)
            report["checks"] = scenario.run()
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
        report["cleanup_confirmed"] = project_root is None or not project_root.exists()
    report["duration_seconds"] = round(time.perf_counter() - started, 3)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    checks = report.get("checks", {})
    lines = [
        "# Progressive Refinement Simulation",
        "",
        f"**Result:** {'PASS' if report.get('passed') else 'FAIL'}",
        "",
        f"- Refinement events: {checks.get('refinement_events', 0)}",
        f"- Root leaf closure: {checks.get('root_leaf_closure', [])}",
        f"- Dashboard files: {checks.get('dashboard_files', 0)}",
        f"- Temporary project cleaned: {report.get('cleanup_confirmed')}",
    ]
    if report.get("severe_issues"):
        lines.extend(("", "## Severe issues", ""))
        lines.extend(f"- {item}" for item in report["severe_issues"])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the isolated two-round progressive-refinement simulation."
    )
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    args = parser.parse_args(argv)
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

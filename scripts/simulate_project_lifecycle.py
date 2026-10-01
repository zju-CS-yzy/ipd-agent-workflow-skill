#!/usr/bin/env python3
"""Exercise the public CLI through a complete, governed IPD lifecycle.

The scenario intentionally behaves like an Agent using the Skill in a real
project.  It creates an isolated Git repository, drives every deliverable and
gate through the public CLI, inspects every generated view, and removes the
temporary project before returning.  No generated project instance is ever
written into this repository.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    # Direct source-tree execution starts with scripts/ on sys.path.
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ipdctl.cli import main as cli_main
from ipdctl.runtime import load_runtime, save_runtime
from ipdctl.state import load_state, write_state


TASK_TYPES = ("software", "embedded", "robotics", "ai_system")
EXPECTED_PHASES = (
    "concept",
    "plan",
    "develop",
    "qualify",
    "launch",
    "lifecycle",
)
EXPECTED_DASHBOARD_FILES = frozenset(
    {
        "index.html",
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
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class SimulationFailure(RuntimeError):
    """Raised when a lifecycle invariant or expected CLI result is absent."""


@dataclass(frozen=True)
class CommandResult:
    arguments: tuple[str, ...]
    code: int
    stdout: str
    stderr: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SimulationFailure(message)


def _json_output(result: CommandResult) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SimulationFailure(
            f"command did not return JSON: {' '.join(result.arguments)}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SimulationFailure(
            f"command returned a non-object JSON value: {' '.join(result.arguments)}"
        )
    return value


class LifecycleScenario:
    """Mutable scenario driver whose observable actions all use the public CLI."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.commands: list[dict[str, Any]] = []
        self.iterations: list[dict[str, Any]] = []
        self.processed_deliverables: list[str] = []
        self.approved_gates: list[str] = []
        self.agent_approval_denials = 0
        self.blocked_iterations = 0
        self.deliverable_rejections = 0
        self.gate_rejections = 0
        self.expired_claim_recoveries = 0
        self.phase_advances = 0
        self.rejected_deliverable: str | None = None
        self.rejected_gate: str | None = None
        self.blocked_deliverable: str | None = None
        self.expired_claim_deliverable: str | None = None
        self.project_source_binding_exercised = False
        self.project_source_binding_deliverable: str | None = None

    @property
    def state_path(self) -> Path:
        return self.root / ".ipd" / "project_state.yaml"

    @property
    def process_path(self) -> Path:
        return self.root / ".ipd" / "tailored_process.yaml"

    @property
    def dashboard(self) -> Path:
        return self.root / ".ipd" / "dashboard"

    def invoke(
        self,
        arguments: Sequence[str],
        *,
        expected: int | None = 0,
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
        rendered = ["<project>" if item == str(self.root) else item for item in result.arguments]
        self.commands.append(
            {
                "arguments": rendered,
                "code": result.code,
                "stdout_nonempty": bool(result.stdout.strip()),
                "stderr_nonempty": bool(result.stderr.strip()),
            }
        )
        if expected is not None and result.code != expected:
            detail = (result.stderr or result.stdout).strip()
            raise SimulationFailure(
                f"command returned {result.code}, expected {expected}: "
                f"{' '.join(rendered)}{': ' + detail if detail else ''}"
            )
        return result

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if result.returncode != 0:
            raise SimulationFailure(
                f"git {' '.join(arguments)} failed: "
                f"{(result.stderr or result.stdout).strip()}"
            )
        return result

    def initialize_git(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        initialized = subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if initialized.returncode != 0:
            self._git("init")
            current = self._git("branch", "--show-current").stdout.strip()
            if current != "main":
                self._git("checkout", "-b", "main")
        self._git("config", "user.name", "IPD Simulation")
        self._git("config", "user.email", "ipd-simulation@example.invalid")
        (self.root / "README.md").write_text(
            "# Simulated Robotics Platform\n", encoding="utf-8", newline="\n"
        )
        self._git("add", "README.md")
        self._git("commit", "-m", "Create simulation baseline")
        self._git(
            "remote",
            "add",
            "origin",
            "https://example.invalid/acme/simulated-robotics-platform.git",
        )
        return {
            "branch": self._git("branch", "--show-current").stdout.strip(),
            "revision": self._git("rev-parse", "HEAD").stdout.strip(),
        }

    def initialize_ipd(self) -> tuple[dict[str, Any], dict[str, Any]]:
        arguments = [
            "init",
            str(self.root),
            "--name",
            "多模态机器人平台",
            "--locale",
            "zh-CN",
        ]
        for task_type in TASK_TYPES:
            arguments.extend(("--task-type", task_type))
        initialized = self.invoke(arguments)
        _require(
            _CJK.search(initialized.stdout) is not None,
            "zh-CN init output did not contain localized presentation text",
        )
        tailored = self.invoke(("tailor", str(self.root)))
        _require(
            _CJK.search(tailored.stdout) is not None,
            "zh-CN tailor output did not contain localized presentation text",
        )

        process = load_state(self.process_path)
        state = load_state(self.state_path)
        _require(
            tuple(item["id"] for item in process["phases"]) == EXPECTED_PHASES,
            "tailored process did not contain the six canonical phases",
        )
        _require(
            len(process.get("deliverables", [])) == 18,
            "four selected task types did not produce 18 deliverables",
        )
        _require(
            len(process.get("gates", [])) == 12,
            "six phases did not produce 12 governed TR/DCP gates",
        )
        self._assert_managed_evidence_bindings(process)

        localized_context = self.invoke(("context", str(self.root)))
        _require(
            _CJK.search(localized_context.stdout) is not None,
            "zh-CN context output did not contain localized presentation text",
        )
        context = _json_output(
            self.invoke(("context", str(self.root), "--json"))
        )
        _require(context.get("phase") == "concept", "initial context was not concept")
        return process, state

    def _assert_managed_evidence_bindings(self, process: dict[str, Any]) -> None:
        bindings = load_state(self.root / ".ipd" / "artifact_bindings.yaml")
        expected = {
            f"evidence/{item['id']}/**" for item in process.get("deliverables", [])
        }
        actual = {
            rule.get("glob")
            for rule in bindings.get("bindings", [])
            if rule.get("managed_by") == "ipdctl.tailor"
        }
        _require(
            actual == expected,
            "tailor did not create the public managed evidence-binding contract",
        )

    def _configure_project_source_binding(self, deliverable: str) -> None:
        bindings_path = self.root / ".ipd" / "artifact_bindings.yaml"
        bindings = load_state(bindings_path)
        bindings["bindings"].insert(
            0,
            {
                "id": "perception-source-owner",
                "glob": "src/perception/**",
                "deliverable": deliverable,
                "critical": True,
                "review_required": True,
                "description": "Explicit source ownership established before claim",
            },
        )
        write_state(bindings_path, bindings)
        self.project_source_binding_deliverable = deliverable

    def _change_project_source(self) -> None:
        source = self.root / "src" / "perception" / "fusion.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "\"\"\"Simulated project source bound to the claimed deliverable.\"\"\"\n",
            encoding="utf-8",
            newline="\n",
        )
        self.project_source_binding_exercised = True

    def _evidence(
        self,
        subject: str,
        name: str,
        text: str,
        *,
        gate: bool = False,
        create: bool = True,
    ) -> str:
        directory = self.root / "evidence" / ("gates" if gate else subject)
        path = directory / f"{name}.md"
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
        return path.relative_to(self.root).as_posix()

    def _context(self) -> dict[str, Any]:
        return _json_output(
            self.invoke(("context", str(self.root), "--json"))
        )

    def _state(self) -> dict[str, Any]:
        return load_state(self.state_path)

    def _deliverable(self, identifier: str) -> dict[str, Any]:
        return next(
            item
            for item in self._state().get("deliverables", [])
            if item.get("id") == identifier
        )

    def _gate(self, identifier: str) -> dict[str, Any]:
        return next(
            item
            for item in self._state().get("gates", [])
            if item.get("id") == identifier
        )

    def _assert_failed_without_mutation(
        self, arguments: Sequence[str], *, label: str
    ) -> CommandResult:
        state_before = self._state()
        runtime_before = load_runtime(self.root)
        result = self.invoke(arguments, expected=None)
        _require(result.code != 0, f"negative scenario unexpectedly succeeded: {label}")
        _require(self._state() == state_before, f"failed command mutated state: {label}")
        _require(
            load_runtime(self.root) == runtime_before,
            f"failed command mutated Agent runtime: {label}",
        )
        return result

    def _dashboard_documents(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        manifest = json.loads((self.dashboard / "manifest.json").read_text(encoding="utf-8"))
        state_data = json.loads(
            (self.dashboard / "data" / "state.json").read_text(encoding="utf-8")
        )
        graph_data = json.loads(
            (self.dashboard / "data" / "graph.json").read_text(encoding="utf-8")
        )
        return manifest, state_data, graph_data

    def refresh_and_verify(
        self,
        label: str,
        *,
        expected_deliverable: tuple[str, str] | None = None,
        expected_gate: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        before = self._state()
        runtime_before = load_runtime(self.root)
        self.invoke(("refresh", str(self.root)))
        after_refresh = self._state()
        _require(
            after_refresh["revision"] > before["revision"],
            f"refresh did not advance state revision for {label}",
        )
        manifest, state_data, graph_data = self._dashboard_documents()
        _require(
            manifest.get("state_revision") == after_refresh["revision"],
            f"manifest revision was stale immediately after refresh for {label}",
        )
        _require(
            state_data.get("project", {}).get("state_revision")
            == after_refresh["revision"],
            f"Dashboard state revision was stale after refresh for {label}",
        )

        verification = _json_output(
            self.invoke(("verify", str(self.root), "--json"))
        )
        _require(
            verification.get("status") == "passed",
            f"verification failed for {label}: {verification.get('issues')}",
        )
        after_verify = self._state()
        final_manifest, final_state_data, final_graph_data = self._dashboard_documents()
        _require(
            after_verify["revision"] == after_refresh["revision"],
            f"verify unexpectedly mutated project state for {label}",
        )
        _require(
            final_manifest.get("state_revision") == after_verify["revision"],
            f"manifest revision diverged from state after verify for {label}",
        )
        _require(
            final_state_data.get("project", {}).get("state_revision")
            == after_verify["revision"],
            f"Dashboard state revision diverged after verify for {label}",
        )
        _require(
            final_manifest.get("locale") == "zh-CN"
            and final_state_data.get("locale") == "zh-CN"
            and final_graph_data.get("locale") == "zh-CN",
            f"locale was not propagated through every Dashboard contract for {label}",
        )
        current_phase = after_verify["project"]["phase"]
        _require(
            final_graph_data.get("current_phase") == current_phase,
            f"graph current phase was stale for {label}",
        )
        _require(
            all(
                task.get("phase") in {None, current_phase}
                for task in final_state_data.get("available_tasks", [])
            ),
            f"Dashboard next tasks leaked outside current phase for {label}",
        )

        if expected_deliverable is not None:
            identifier, status = expected_deliverable
            dashboard_item = next(
                item
                for item in final_state_data.get("deliverables", [])
                if item.get("id") == identifier
            )
            _require(
                dashboard_item.get("status") == status,
                f"Dashboard status for {identifier} was not {status} after {label}",
            )
        if expected_gate is not None:
            identifier, status = expected_gate
            dashboard_items = [
                item
                for item in final_state_data.get("checkpoints", [])
                if item.get("id") == identifier
            ]
            _require(dashboard_items, f"Dashboard omitted checkpoint {identifier}")
            _require(
                all(item.get("status") == status for item in dashboard_items),
                f"Dashboard checkpoint status for {identifier} was not {status}",
            )

        runtime_after = load_runtime(self.root)
        new_events = runtime_after.get("events", [])[len(runtime_before.get("events", [])) :]
        _require(
            [event.get("action") for event in new_events[:2]] == ["refresh", "verify"],
            f"refresh/verify events were not recorded in order for {label}",
        )
        iteration = {
            "label": label,
            "phase": current_phase,
            "revision_before": before["revision"],
            "revision_after": after_verify["revision"],
            "runtime_events_added": len(new_events),
            "manifest_revision": final_manifest.get("state_revision"),
            "verification": verification.get("status"),
        }
        self.iterations.append(iteration)
        return {
            "state": after_verify,
            "manifest": final_manifest,
            "state_data": final_state_data,
            "graph_data": final_graph_data,
            "runtime": runtime_after,
        }

    def _claim(self, identifier: str, actor: str) -> None:
        context = self._context()
        available = {item["id"] for item in context.get("available_tasks", [])}
        _require(identifier in available, f"context did not offer available task {identifier}")
        self.invoke(
            (
                "claim",
                identifier,
                "--project-root",
                str(self.root),
                "--actor",
                actor,
            )
        )
        if (
            not self.project_source_binding_exercised
            and identifier == self.project_source_binding_deliverable
        ):
            self._change_project_source()

    def _close_ready(self, identifier: str, actor: str, attempt: str) -> None:
        work = self._evidence(
            identifier,
            f"work-{attempt}",
            f"Engineering evidence for {identifier}, iteration {attempt}.",
        )
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

    def _deny_agent_deliverable_approval(self, identifier: str) -> None:
        evidence = self._evidence(
            identifier,
            "agent-recommendation",
            "Agent recommendation; this is not final approval.",
        )
        self._assert_failed_without_mutation(
            (
                "approve",
                identifier,
                "--project-root",
                str(self.root),
                "--reviewer",
                "review-agent",
                "--actor-type",
                "agent",
                "--authorized",
                "--evidence",
                evidence,
            ),
            label="Agent attempted final deliverable approval",
        )
        self.agent_approval_denials += 1

    def _approve_deliverable(self, identifier: str, attempt: str) -> None:
        evidence = self._evidence(
            identifier,
            f"human-approval-{attempt}",
            f"Authorized human approval for {identifier}, iteration {attempt}.",
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
                evidence,
            )
        )

    def _assert_blocked_event_auditable(self, identifier: str, reason: str) -> None:
        matching = [
            event
            for event in load_runtime(self.root).get("events", [])
            if event.get("deliverable") == identifier
            and event.get("action") in {"close", "blocked"}
            and (
                event.get("status") == "blocked"
                or event.get("action") == "blocked"
            )
        ]
        _require(matching, "blocked iteration was not preserved in Agent runtime history")
        latest = matching[-1]
        recorded_reason = latest.get("note") or latest.get("blocked_reason") or latest.get("reason")
        _require(
            recorded_reason == reason,
            "blocked iteration runtime record omitted its reason",
        )

    def _exercise_blocked_iteration(self, identifier: str) -> None:
        actor = "agent-blocked"
        self._claim(identifier, actor)
        reason = "Awaiting calibrated sensor fixture"
        evidence = self._evidence(
            identifier,
            "blocked-diagnostic",
            "Diagnostic evidence captured before the fixture became available.",
        )
        self.invoke(
            (
                "close",
                identifier,
                "--project-root",
                str(self.root),
                "--actor",
                actor,
                "--status",
                "blocked",
                "--note",
                reason,
                "--evidence",
                evidence,
            )
        )
        self.refresh_and_verify(
            f"blocked:{identifier}", expected_deliverable=(identifier, "blocked")
        )
        self._assert_blocked_event_auditable(identifier, reason)
        self.blocked_iterations += 1
        self.blocked_deliverable = identifier

    def _exercise_expired_claim(self, identifier: str) -> str:
        stale_actor = "agent-stale"
        recovery_actor = "agent-recovery"
        self._claim(identifier, stale_actor)
        runtime = load_runtime(self.root)
        claim = runtime.get("active_claims", {}).get(identifier)
        _require(isinstance(claim, dict), "initial claim was not recorded in Agent runtime")
        claim["started_at"] = "1999-01-01T00:00:00Z"
        claim["expires_at"] = "2000-01-01T00:00:00Z"
        save_runtime(self.root, runtime)

        result = self.invoke(
            (
                "claim",
                identifier,
                "--project-root",
                str(self.root),
                "--actor",
                recovery_actor,
            ),
            expected=None,
        )
        _require(
            result.code == 0,
            "expired claim permanently blocked recovery by a new Agent",
        )
        recovered_runtime = load_runtime(self.root)
        _require(
            any(
                event.get("action") == "claim_expired"
                and event.get("deliverable") == identifier
                and event.get("actor") == stale_actor
                for event in recovered_runtime.get("events", [])
            ),
            "expired claim recovery did not preserve a claim_expired audit event",
        )
        active = recovered_runtime.get("active_claims", {}).get(identifier, {})
        _require(
            active.get("actor") == recovery_actor,
            "expired claim was not reassigned to the recovery Agent",
        )
        self.expired_claim_recoveries += 1
        self.expired_claim_deliverable = identifier
        return recovery_actor

    def process_deliverable(
        self,
        identifier: str,
        *,
        block_once: bool = False,
        reject_once: bool = False,
        expire_claim_once: bool = False,
    ) -> None:
        actor = "agent-primary"
        if block_once:
            self._exercise_blocked_iteration(identifier)
            actor = "agent-rework"
            self._claim(identifier, actor)
        elif expire_claim_once:
            actor = self._exercise_expired_claim(identifier)
        else:
            self._claim(identifier, actor)

        self._close_ready(identifier, actor, "1")
        if not self.agent_approval_denials:
            self._deny_agent_deliverable_approval(identifier)

        if reject_once:
            rejected_evidence = self._evidence(
                identifier,
                "human-rejection-1",
                "Authorized rejection requesting corrected assurance criteria.",
            )
            self.invoke(
                (
                    "reject",
                    identifier,
                    "--project-root",
                    str(self.root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    rejected_evidence,
                )
            )
            self._assert_failed_without_mutation(
                (
                    "claim",
                    identifier,
                    "--project-root",
                    str(self.root),
                    "--actor",
                    "agent-protocol-bypass",
                ),
                label="claim attempted before mandatory refresh and verify",
            )
            self.refresh_and_verify(
                f"rejected:{identifier}",
                expected_deliverable=(identifier, "rejected"),
            )
            self.deliverable_rejections += 1
            self.rejected_deliverable = identifier
            actor = "agent-rework"
            self._claim(identifier, actor)
            self._close_ready(identifier, actor, "2")
            self._approve_deliverable(identifier, "2")
        else:
            self._approve_deliverable(identifier, "1")

        self.refresh_and_verify(
            f"accepted:{identifier}",
            expected_deliverable=(identifier, "accepted"),
        )
        item = self._deliverable(identifier)
        _require(item.get("status") == "accepted", f"{identifier} was not accepted")
        self.processed_deliverables.append(identifier)

    def _review_gate(self, alias: str) -> None:
        self.invoke(
            (
                "review",
                alias,
                "--project-root",
                str(self.root),
                "--reviewer",
                "review-agent",
            )
        )

    def _deny_agent_gate_approval(self, alias: str) -> None:
        evidence = self._evidence(
            alias,
            "agent-gate-recommendation",
            "Agent recommendation; final gate authority remains human.",
            gate=True,
        )
        self._assert_failed_without_mutation(
            (
                "approve",
                alias,
                "--project-root",
                str(self.root),
                "--reviewer",
                "review-agent",
                "--actor-type",
                "agent",
                "--authorized",
                "--evidence",
                evidence,
            ),
            label="Agent attempted final Gate approval",
        )
        self.agent_approval_denials += 1

    def _decide_gate(
        self,
        alias: str,
        decision: str,
        name: str,
        *,
        create_evidence: bool = True,
    ) -> str:
        evidence = self._evidence(
            alias,
            name,
            f"Authorized governance decision ({decision}) for {alias}.",
            gate=True,
            create=create_evidence,
        )
        self.invoke(
            (
                decision,
                alias,
                "--project-root",
                str(self.root),
                "--reviewer",
                "governance-board",
                "--actor-type",
                "human",
                "--authorized",
                "--evidence",
                evidence,
            )
        )
        return evidence

    def process_gate(
        self,
        alias: str,
        canonical: str,
        *,
        reject_once: bool = False,
        missing_evidence_before_advance: bool = False,
    ) -> str | None:
        self._review_gate(alias)
        if self.agent_approval_denials < 2:
            self._deny_agent_gate_approval(alias)

        if reject_once:
            self._decide_gate(alias, "reject", "human-rejection-1")
            self.refresh_and_verify(
                f"gate-rejected:{canonical}",
                expected_gate=(canonical, "rejected"),
            )
            self.gate_rejections += 1
            self.rejected_gate = canonical
            self._review_gate(alias)
            self._decide_gate(alias, "approve", "human-approval-2")
        elif missing_evidence_before_advance:
            evidence = self._decide_gate(
                alias,
                "approve",
                "human-approval-created-late",
                create_evidence=False,
            )
            self.approved_gates.append(canonical)
            return evidence
        else:
            self._decide_gate(alias, "approve", "human-approval-1")

        self.refresh_and_verify(
            f"gate-approved:{canonical}",
            expected_gate=(canonical, "approved"),
        )
        self.approved_gates.append(canonical)
        return None

    def assert_missing_gate_evidence_blocks_advance(
        self, phase: str, relative_evidence: str
    ) -> None:
        before = self._state()
        result = self.invoke(("advance-phase", str(self.root)), expected=None)
        _require(
            result.code != 0,
            "advance-phase accepted a Gate whose review evidence path did not exist",
        )
        after = self._state()
        _require(
            after == before and after["project"]["phase"] == phase,
            "failed advance-phase changed project phase or state",
        )
        evidence_path = self.root / relative_evidence
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "Authorized governance evidence created before phase advancement.\n",
            encoding="utf-8",
            newline="\n",
        )

    def _checkpoint_aliases(
        self, process: dict[str, Any], phase: str
    ) -> tuple[tuple[str, str], tuple[str, str]]:
        tr = next(
            item
            for item in process.get("technical_reviews", [])
            if item.get("phase") == phase
        )
        dcp = next(
            item
            for item in process.get("decision_checkpoints", [])
            if item.get("phase") == phase
        )
        return (tr["id"], tr["gate_id"]), (dcp["id"], dcp["gate_id"])

    def run_lifecycle(self, process: dict[str, Any]) -> None:
        first_deliverable = next(iter(process.get("deliverables", [])), None)
        _require(
            isinstance(first_deliverable, dict)
            and isinstance(first_deliverable.get("id"), str),
            "tailored process did not provide a first Deliverable",
        )
        self._configure_project_source_binding(first_deliverable["id"])
        self.refresh_and_verify("initial")
        blocked_used = False
        rejection_used = False
        expiration_used = False
        gate_rejection_used = False
        missing_gate_evidence_used = False

        for phase_index, phase in enumerate(EXPECTED_PHASES):
            _require(
                self._state()["project"]["phase"] == phase,
                f"project did not enter expected phase {phase}",
            )
            phase_ids = {
                item["id"]
                for item in process.get("deliverables", [])
                if item.get("phase") == phase
            }
            while phase_ids:
                context = self._context()
                available = sorted(
                    item["id"]
                    for item in context.get("available_tasks", [])
                    if item["id"] in phase_ids
                )
                _require(available, f"no available deliverable could progress phase {phase}")
                identifier = available[0]
                use_block = not blocked_used
                use_rejection = phase == "plan" and not rejection_used
                use_expiration = (
                    phase == "plan"
                    and not use_rejection
                    and not expiration_used
                )
                self.process_deliverable(
                    identifier,
                    block_once=use_block,
                    reject_once=use_rejection,
                    expire_claim_once=use_expiration,
                )
                blocked_used = blocked_used or use_block
                rejection_used = rejection_used or use_rejection
                expiration_used = expiration_used or use_expiration
                phase_ids.remove(identifier)

            tr, dcp = self._checkpoint_aliases(process, phase)
            self.process_gate(
                tr[0],
                tr[1],
                reject_once=phase == "concept" and not gate_rejection_used,
            )
            gate_rejection_used = gate_rejection_used or phase == "concept"
            missing_path = self.process_gate(
                dcp[0],
                dcp[1],
                missing_evidence_before_advance=(
                    phase == "plan" and not missing_gate_evidence_used
                ),
            )
            if missing_path is not None:
                self.assert_missing_gate_evidence_blocks_advance(phase, missing_path)
                self.refresh_and_verify(
                    f"gate-approved:{dcp[1]}",
                    expected_gate=(dcp[1], "approved"),
                )
                missing_gate_evidence_used = True

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
                _require(
                    result.code != 0,
                    "advance-phase moved beyond the final lifecycle phase",
                )
                _require(
                    self._state() == before,
                    "final lifecycle completion probe mutated project state",
                )

        _require(blocked_used, "blocked/reclaim scenario was not exercised")
        _require(rejection_used, "deliverable rejection/rework scenario was not exercised")
        _require(expiration_used, "expired claim recovery scenario was not exercised")
        _require(gate_rejection_used, "Gate rejection/rework scenario was not exercised")
        _require(
            missing_gate_evidence_used,
            "missing Gate evidence phase-advance guard was not exercised",
        )

    def repository_read_only_check(self) -> dict[str, Any]:
        before = self._git("status", "--porcelain=v1", "--untracked-files=all").stdout
        info = _json_output(
            self.invoke(("repository", str(self.root), "--json"))
        )
        after = self._git("status", "--porcelain=v1", "--untracked-files=all").stdout
        _require(before == after, "repository inspection changed the Git working tree")
        _require(info.get("kind") == "git", "repository adapter did not detect Git")
        _require(info.get("branch") == "main", "repository adapter did not report main branch")
        _require(
            isinstance(info.get("revision"), str) and len(info["revision"]) >= 7,
            "repository adapter omitted the Git revision",
        )
        _require(info.get("dirty") is True, "repository adapter did not report dirty state")
        _require(
            info.get("remote")
            == "https://example.invalid/acme/simulated-robotics-platform.git",
            "repository adapter omitted or changed the configured remote",
        )
        return info

    def reconcile(self) -> dict[str, Any]:
        report = _json_output(
            self.invoke(("reconcile", str(self.root), "--json"))
        )
        _require(report.get("status") == "passed", "repository reconciliation did not pass")
        _require(
            report.get("summary", {}).get("errors") == 0,
            "repository reconciliation reported blocking errors",
        )
        persisted = json.loads(
            (self.root / ".ipd" / "reconcile_report.json").read_text(encoding="utf-8")
        )
        _require(
            persisted.get("status") == report.get("status"),
            "persisted reconciliation report diverged from CLI output",
        )
        return report

    def final_checks(
        self, process: dict[str, Any], repository: dict[str, Any], reconciliation: dict[str, Any]
    ) -> dict[str, Any]:
        state = self._state()
        runtime = load_runtime(self.root)
        manifest, state_data, graph_data = self._dashboard_documents()
        actual_files = {
            path.relative_to(self.dashboard).as_posix()
            for path in self.dashboard.rglob("*")
            if path.is_file()
        }
        missing_outputs = sorted(EXPECTED_DASHBOARD_FILES - actual_files)
        unexpected_outputs = sorted(actual_files - EXPECTED_DASHBOARD_FILES)
        _require(not missing_outputs, f"Dashboard outputs were missing: {missing_outputs}")
        _require(
            not unexpected_outputs,
            f"Dashboard generated unexpected files: {unexpected_outputs}",
        )
        _require(
            set(manifest.get("files", [])) == EXPECTED_DASHBOARD_FILES,
            "Dashboard manifest file inventory did not match the 15-output contract",
        )
        _require(
            {item.get("path", "").removeprefix(".ipd/dashboard/") for item in manifest.get("outputs", [])}
            == EXPECTED_DASHBOARD_FILES - {"manifest.json"},
            "Dashboard manifest hash inventory did not cover its 14 non-manifest outputs",
        )

        _require(
            len(state.get("deliverables", [])) == 18
            and all(item.get("status") == "accepted" for item in state["deliverables"]),
            "not all 18 deliverables reached accepted",
        )
        _require(
            len(state.get("gates", [])) == 12
            and all(item.get("status") == "approved" for item in state["gates"]),
            "not all 12 TR/DCP gates reached approved",
        )
        _require(
            state.get("project", {}).get("phase") == "lifecycle",
            "project did not finish in lifecycle phase",
        )
        _require(not runtime.get("active_claims"), "active claims remained after lifecycle completion")
        _require(
            runtime.get("last_refresh", {}).get("state_revision") == state.get("revision")
            and runtime.get("last_verification", {}).get("state_revision")
            == state.get("revision"),
            "runtime refresh/verification pointers were not current",
        )
        lifecycle_events = [
            event
            for event in runtime.get("events", [])
            if event.get("action") == "lifecycle_complete"
        ]
        _require(
            len(lifecycle_events) == 1
            and lifecycle_events[0].get("phase") == "lifecycle",
            "final lifecycle completion was not recorded exactly once",
        )

        if self.rejected_deliverable:
            decisions = [
                review.get("decision")
                for review in self._deliverable(self.rejected_deliverable).get("reviews", [])
                if review.get("reviewer_type") == "human" and review.get("authorized") is True
            ]
            _require(
                decisions == ["reject", "approve"],
                "deliverable rejection/rework history was not preserved",
            )
        if self.rejected_gate:
            gate = self._gate(self.rejected_gate)
            decisions = [
                review.get("decision")
                for review in gate.get("reviews", [])
                if review.get("reviewer_type") == "human" and review.get("authorized") is True
            ]
            _require(
                decisions == ["reject", "approve"],
                "Gate rejection/rework history was not preserved",
            )
            checkpoint_rows = [
                row
                for row in state_data.get("checkpoints", [])
                if row.get("id") in {"tr.concept", self.rejected_gate}
            ]
            _require(
                checkpoint_rows
                and all(
                    row.get("status") == "approved"
                    and row.get("approval", {}).get("status") == "approved"
                    for row in checkpoint_rows
                ),
                "Dashboard retained a stale rejected approval after Gate rework",
            )

        dashboard_deliverables = [
            node for node in graph_data.get("nodes", []) if node.get("type") == "Deliverable"
        ]
        _require(
            len(dashboard_deliverables) == 18
            and all(node.get("status") == "accepted" for node in dashboard_deliverables),
            "final graph did not expose all accepted deliverables",
        )
        _require(
            state_data.get("summary", {}).get("accepted_deliverables") == 18
            and state_data.get("summary", {}).get("progress_percent") == 100,
            "Dashboard summary did not report complete delivery",
        )
        _require(
            all(
                task.get("phase") in {None, "lifecycle"}
                for task in state_data.get("available_tasks", [])
            ),
            "final next-task list leaked work from a non-current phase",
        )

        localized_files = (
            "index.html",
            "matrices/deliverable_matrix.html",
            "matrices/gate_matrix.html",
            "assets/ipd_flow.svg",
            "assets/current_status_flow.svg",
        )
        _require(
            all(
                _CJK.search((self.dashboard / relative).read_text(encoding="utf-8"))
                is not None
                for relative in localized_files
            ),
            "one or more zh-CN Dashboard presentation files lacked Chinese text",
        )

        expected_project_paths = {
            ".ipd/task_profile.yaml",
            ".ipd/tailored_process.yaml",
            ".ipd/project_state.yaml",
            ".ipd/agent_runtime.yaml",
            ".ipd/artifact_bindings.yaml",
            ".ipd/verify_report.json",
            ".ipd/reconcile_report.json",
        }
        missing_project_files = sorted(
            relative
            for relative in expected_project_paths
            if not (self.root / relative).is_file()
        )
        expected_directories = {".ipd", "docs", "src", "tests", "dashboard", "state"}
        missing_directories = sorted(
            relative
            for relative in expected_directories
            if not (self.root / relative).is_dir()
        )
        _require(
            not missing_project_files and not missing_directories,
            "initialized project structure or authoritative outputs were missing",
        )
        _require(
            repository.get("kind") == "git" and reconciliation.get("status") == "passed",
            "repository inspection or reconciliation was not successful",
        )

        return {
            "phases": len(process.get("phases", [])),
            "deliverables": len(state.get("deliverables", [])),
            "gates": len(state.get("gates", [])),
            "accepted_deliverables": sum(
                item.get("status") == "accepted" for item in state.get("deliverables", [])
            ),
            "approved_gates": sum(
                item.get("status") == "approved" for item in state.get("gates", [])
            ),
            "current_phase": state.get("project", {}).get("phase"),
            "state_revision": state.get("revision"),
            "runtime_revision": runtime.get("revision"),
            "runtime_events": len(runtime.get("events", [])),
            "active_claims": len(runtime.get("active_claims", {})),
            "dashboard_files": len(actual_files),
            "dashboard_locale": manifest.get("locale"),
            "dashboard_state_revision": manifest.get("state_revision"),
            "graph_nodes": len(graph_data.get("nodes", [])),
            "graph_edges": len(graph_data.get("edges", [])),
            "reconciliation_status": reconciliation.get("status"),
            "repository_kind": repository.get("kind"),
            "repository_branch": repository.get("branch"),
            "blocked_iterations": self.blocked_iterations,
            "deliverable_rejections": self.deliverable_rejections,
            "gate_rejections": self.gate_rejections,
            "expired_claim_recoveries": self.expired_claim_recoveries,
            "agent_approval_denials": self.agent_approval_denials,
            "phase_advances": self.phase_advances,
            "lifecycle_complete": True,
            "missing_project_files": missing_project_files,
            "missing_directories": missing_directories,
        }


def run_simulation() -> dict[str, Any]:
    """Run the complete scenario and return a JSON-serializable report."""

    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "scenario": "full-ipd-project-lifecycle",
        "task_types": list(TASK_TYPES),
        "locale": "zh-CN",
        "passed": False,
        "missing_outputs": [],
        "severe_issues": [],
        "checks": {},
        "iterations": [],
        "commands": [],
        "cleanup_confirmed": False,
    }
    project_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="ipd-full-lifecycle-") as directory:
            project_root = Path(directory) / "simulated-project"
            scenario = LifecycleScenario(project_root)
            git_baseline = scenario.initialize_git()
            process, _ = scenario.initialize_ipd()
            repository_initial = scenario.repository_read_only_check()
            scenario.run_lifecycle(process)
            scenario.refresh_and_verify("lifecycle-completion-idempotence")
            repository_final = scenario.repository_read_only_check()
            reconciliation = scenario.reconcile()
            checks = scenario.final_checks(process, repository_final, reconciliation)
            checks["git_baseline_branch"] = git_baseline["branch"]
            checks["git_baseline_revision"] = git_baseline["revision"]
            checks["repository_initial_revision"] = repository_initial.get("revision")
            report["checks"] = checks
            report["iterations"] = scenario.iterations
            report["commands"] = scenario.commands
            report["missing_outputs"] = []
            report["passed"] = True
        report["cleanup_confirmed"] = project_root is not None and not project_root.exists()
        if not report["cleanup_confirmed"]:
            report["passed"] = False
            report["severe_issues"].append("temporary project directory was not removed")
    except Exception as exc:  # The report is the diagnostic contract for this harness.
        report["severe_issues"].append(f"{type(exc).__name__}: {exc}")
        if project_root is not None:
            dashboard = project_root / ".ipd" / "dashboard"
            if dashboard.exists():
                actual = {
                    path.relative_to(dashboard).as_posix()
                    for path in dashboard.rglob("*")
                    if path.is_file()
                }
                report["missing_outputs"] = sorted(EXPECTED_DASHBOARD_FILES - actual)
        report["cleanup_confirmed"] = project_root is None or not project_root.exists()
    report["duration_seconds"] = round(time.perf_counter() - started, 3)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render a compact developer-facing report without embedding temp paths."""

    status = "PASS" if report.get("passed") else "FAIL"
    checks = report.get("checks", {})
    missing = report.get("missing_outputs", [])
    severe = report.get("severe_issues", [])
    lines = [
        "# Simulated Full Lifecycle Test Report",
        "",
        f"**Result:** {status}",
        "",
        "## Scenario",
        "",
        "A temporary Git project was initialized in `zh-CN` for software, embedded, "
        "robotics, and AI-system work. The public CLI executed all six product phases, "
        "including blocked work recovery, deliverable and Gate rejection/rework, "
        "expired-claim recovery, human-only approvals, phase governance, Dashboard "
        "refresh, verification, and repository reconciliation.",
        "",
        "## Outcome",
        "",
        f"- Phases: {checks.get('phases', 0)}",
        f"- Accepted deliverables: {checks.get('accepted_deliverables', 0)}/{checks.get('deliverables', 0)}",
        f"- Approved Gates: {checks.get('approved_gates', 0)}/{checks.get('gates', 0)}",
        f"- Dashboard files: {checks.get('dashboard_files', 0)}",
        f"- Iteration checkpoints: {len(report.get('iterations', []))}",
        f"- Runtime events: {checks.get('runtime_events', 0)}",
        f"- Missing outputs: {len(missing)}",
        f"- Severe issues: {len(severe)}",
        f"- Temporary project cleaned: {report.get('cleanup_confirmed')}",
        f"- Duration: {report.get('duration_seconds', 0)} seconds",
    ]
    if missing:
        lines.extend(("", "## Missing outputs", ""))
        lines.extend(f"- `{item}`" for item in missing)
    if severe:
        lines.extend(("", "## Severe issues", ""))
        lines.extend(f"- {item}" for item in severe)
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate a complete IPD project lifecycle in an isolated Git repository."
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional Markdown report path. No report is written by default.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured report instead of the Markdown summary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_simulation()
    markdown = render_markdown(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(markdown, encoding="utf-8", newline="\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(markdown, end="")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

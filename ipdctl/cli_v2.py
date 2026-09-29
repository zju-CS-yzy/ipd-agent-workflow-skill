"""v0.2 lifecycle command line for the IPD Agent Workflow Framework."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .engine import (
    TransitionError,
    approve_deliverable,
    claim_deliverable,
    close_deliverable,
    record_deliverable_review,
    reject_deliverable,
    set_deliverable_status,
    start_deliverable_review,
    transition_workflow,
)
from .model import TASK_TYPES, WORKFLOW_STEPS
from .policy import PolicyError, load_policy
from .project import (
    ProjectError,
    context_snapshot,
    initialize_project,
    load_project,
    project_paths,
    refresh_project,
    sync_state_with_process,
    verify_project,
)
from .repository import inspect_repository
from .runtime import (
    RuntimeError as AgentRuntimeError,
    claim as claim_runtime,
    close_claim,
    load_runtime,
    record_event,
    save_runtime,
)
from .state import StateError, load_state, resolve_state_path, write_state
from .validation import validate_state

VERSION = "0.2.0-beta"


def _add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", nargs="?", default=".")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipdctl",
        description="Tailor, execute, review, visualize, and verify an IPD project.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create an IPD project workspace")
    init.add_argument("target", nargs="?", default=".")
    init.add_argument("--name")
    init.add_argument("--task-type", action="append", dest="task_types")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=_cmd_init)

    tailor = commands.add_parser("tailor", help="generate a tailored IPD process")
    _add_target(tailor)
    tailor.add_argument("--profile")
    tailor.add_argument("--output")
    tailor.set_defaults(handler=_cmd_tailor)

    context = commands.add_parser("context", help="show current work and blockers")
    _add_target(context)
    context.add_argument("--json", action="store_true")
    context.set_defaults(handler=_cmd_context)

    for name, handler, help_text in (
        ("claim", _cmd_claim, "claim a deliverable and begin work"),
        ("close", _cmd_close, "submit a deliverable for review"),
        ("review", _cmd_review, "start or record a deliverable review"),
        ("approve", _cmd_approve, "record authorized human acceptance"),
        ("reject", _cmd_reject, "record authorized human rejection"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("deliverable")
        command.add_argument("--project-root", default=".")
        if name in {"claim", "close"}:
            command.add_argument("--actor", default="agent")
        if name == "claim":
            command.add_argument("--lease-minutes", type=int, default=240)
        if name == "close":
            command.add_argument("--evidence", action="append", default=[])
            command.add_argument(
                "--status", choices=["ready_for_review", "blocked"], default="ready_for_review"
            )
            command.add_argument("--note")
        if name in {"review", "approve", "reject"}:
            command.add_argument("--reviewer", required=True)
            command.add_argument("--actor-type", choices=["agent", "human"], default="agent")
            command.add_argument("--evidence")
            command.add_argument("--authorized", action="store_true")
        if name == "review":
            command.add_argument("--decision", choices=["approve", "reject"])
        command.set_defaults(handler=handler)

    refresh = commands.add_parser("refresh", help="rebuild dashboards, graphs, and matrices")
    _add_target(refresh)
    refresh.set_defaults(handler=_cmd_refresh)

    verify = commands.add_parser("verify", help="verify state, process, and generated views")
    _add_target(verify)
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(handler=_cmd_verify)

    repository = commands.add_parser("repository", help="inspect Git or SVN without mutation")
    _add_target(repository)
    repository.add_argument("--json", action="store_true")
    repository.set_defaults(handler=_cmd_repository)

    reconcile = commands.add_parser("reconcile", help="map repository changes to deliverables")
    _add_target(reconcile)
    reconcile.add_argument("--bindings")
    reconcile.add_argument("--json", action="store_true")
    reconcile.set_defaults(handler=_cmd_reconcile)

    validate = commands.add_parser("validate", help="validate project state and optional policy")
    _add_target(validate)
    validate.add_argument("--policy")
    validate.set_defaults(handler=_cmd_validate)

    status = commands.add_parser("status", help="compatibility alias for context")
    _add_target(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=_cmd_context)
    return parser


def _normalize_task_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"ai": "ai_system", "material": "material_change"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in TASK_TYPES:
        raise ProjectError(
            f"unsupported task type {value!r}; choose from: {', '.join(TASK_TYPES)}"
        )
    return normalized


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)


def _cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.target).resolve()
    name = args.name or root.name
    task_types = [_normalize_task_type(value) for value in (args.task_types or ["software"])]
    paths = initialize_project(root, name=name, task_types=task_types, force=args.force)
    print(f"Initialized IPD project: {paths['root']}")
    print(f"Task profile: {paths['profile']}")
    print(f"Project state: {paths['state']}")
    return 0


def _cmd_tailor(args: argparse.Namespace) -> int:
    root = Path(args.target).resolve()
    paths = project_paths(root)
    profile = Path(args.profile).resolve() if args.profile else paths["profile"]
    output = Path(args.output).resolve() if args.output else paths["process"]
    from .tailoring import tailor_file

    process = tailor_file(profile, output)
    state = load_state(paths["state"])
    state = sync_state_with_process(state, process)
    write_state(paths["state"], state)
    print(f"Tailored process: {output}")
    print(f"Deliverables: {len(process.get('deliverables', []))}")
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    snapshot = context_snapshot(args.target)
    if args.json:
        print(_json(snapshot))
        return 0
    print(f"Project: {snapshot['project']}")
    print(f"Phase: {snapshot['phase']}")
    print(f"TR: {snapshot['tr'] or '-'}")
    print(f"DCP: {snapshot['dcp'] or '-'}")
    print(f"Gate: {snapshot['gate'] or '-'}")
    print("Available tasks: " + (", ".join(item["id"] for item in snapshot["available_tasks"]) or "none"))
    print("Blocked items: " + (", ".join(item["id"] for item in snapshot["blocked_items"]) or "none"))
    return 0


def _advance_workflow(state: dict[str, Any], target: str) -> dict[str, Any]:
    for _ in WORKFLOW_STEPS:
        if state["project"]["workflow_step"] == target:
            return state
        current = state["project"]["workflow_step"]
        expected = WORKFLOW_STEPS[(WORKFLOW_STEPS.index(current) + 1) % len(WORKFLOW_STEPS)]
        state = transition_workflow(state, expected)
    raise TransitionError(f"could not advance workflow to {target!r}")


def _cmd_claim(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state = load_state(paths["state"])
    updated_state = claim_deliverable(state, args.deliverable)
    updated_state = _advance_workflow(updated_state, "work")
    updated_runtime = claim_runtime(
        load_runtime(root),
        args.deliverable,
        actor=args.actor,
        lease_minutes=args.lease_minutes,
    )
    write_state(paths["state"], updated_state)
    save_runtime(root, updated_runtime)
    print(f"Claimed {args.deliverable} for {args.actor}")
    return 0


def _cmd_close(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state = load_state(paths["state"])
    if args.status == "blocked":
        state = set_deliverable_status(
            state,
            args.deliverable,
            "blocked",
            evidence=args.evidence,
            blocked_reason=args.note or "blocked during work",
        )
    else:
        state = close_deliverable(state, args.deliverable, evidence=args.evidence)
    state = _advance_workflow(state, "close")
    runtime = close_claim(
        load_runtime(root), args.deliverable, actor=args.actor, action="close"
    )
    write_state(paths["state"], state)
    save_runtime(root, runtime)
    print(f"Closed {args.deliverable} as {args.status}")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state = start_deliverable_review(load_state(paths["state"]), args.deliverable)
    if args.decision:
        if not args.evidence:
            raise TransitionError("a recorded review decision requires --evidence")
        state = record_deliverable_review(
            state,
            args.deliverable,
            reviewer=args.reviewer,
            reviewer_type=args.actor_type,
            authorized=bool(args.authorized and args.actor_type == "human"),
            decision=args.decision,
            evidence=args.evidence,
        )
    runtime = record_event(
        load_runtime(root),
        "review",
        details={"deliverable": args.deliverable, "reviewer": args.reviewer},
    )
    write_state(paths["state"], state)
    save_runtime(root, runtime)
    print(f"Review started for {args.deliverable}")
    return 0


def _require_review_evidence(args: argparse.Namespace) -> str:
    if not args.evidence:
        raise TransitionError("final review requires --evidence")
    return args.evidence


def _cmd_approve(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state = approve_deliverable(
        load_state(paths["state"]),
        args.deliverable,
        reviewer=args.reviewer,
        reviewer_type=args.actor_type,
        authorized=args.authorized,
        evidence=_require_review_evidence(args),
    )
    runtime = record_event(
        load_runtime(root),
        "approve",
        details={"deliverable": args.deliverable, "reviewer": args.reviewer},
    )
    write_state(paths["state"], state)
    save_runtime(root, runtime)
    print(f"Accepted {args.deliverable}")
    return 0


def _cmd_reject(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state = reject_deliverable(
        load_state(paths["state"]),
        args.deliverable,
        reviewer=args.reviewer,
        reviewer_type=args.actor_type,
        authorized=args.authorized,
        evidence=_require_review_evidence(args),
    )
    runtime = record_event(
        load_runtime(root),
        "reject",
        details={"deliverable": args.deliverable, "reviewer": args.reviewer},
    )
    write_state(paths["state"], state)
    save_runtime(root, runtime)
    print(f"Rejected {args.deliverable}")
    return 0


def _cmd_refresh(args: argparse.Namespace) -> int:
    manifest = refresh_project(args.target)
    outputs = manifest.get("outputs", []) if isinstance(manifest, dict) else []
    print(f"Dashboard refreshed ({len(outputs)} outputs)")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    report = verify_project(args.target)
    if args.json or report["status"] != "passed":
        print(_json(report))
    else:
        print(f"IPD verification passed (revision {report['state_revision']})")
    return 0 if report["status"] == "passed" else 1


def _cmd_repository(args: argparse.Namespace) -> int:
    info = inspect_repository(args.target).as_dict()
    if args.json:
        print(_json(info))
    else:
        for key in ("kind", "root", "branch", "revision", "dirty", "remote"):
            print(f"{key.replace('_', ' ').title()}: {info.get(key) if info.get(key) is not None else '-'}")
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    from .reconcile import reconcile_project

    root = Path(args.target).resolve()
    state = load_state(project_paths(root)["state"])
    report = reconcile_project(root, state, bindings_path=args.bindings, write=True)
    if args.json:
        print(_json(report))
    else:
        print(f"Reconciliation: {report.get('status')}")
        print(f"Changed paths: {len(report.get('changed_paths', []))}")
        print(f"Issues: {len(report.get('issues', []))}")
    return 1 if report.get("status") == "failed" else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    path = resolve_state_path(args.target)
    state = load_state(path)
    issues = validate_state(state)
    if issues:
        print(f"Invalid IPD state: {path}", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    if args.policy:
        load_policy(args.policy)
    print(f"Valid IPD state (revision {state['revision']}): {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (
        AgentRuntimeError,
        PolicyError,
        ProjectError,
        StateError,
        TransitionError,
        ValueError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

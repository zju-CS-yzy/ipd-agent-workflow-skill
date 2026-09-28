"""Command-line interface for initializing and validating IPD state."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from .policy import PolicyError, load_policy
from .repository import inspect_repository
from .state import StateError, create_initial_state, load_state, resolve_state_path, write_state
from .validation import validate_state


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipdctl",
        description="Initialize, inspect, and validate traceable IPD project state.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0a1")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="create .ipd/project-state.json")
    init_parser.add_argument("target", nargs="?", default=".")
    init_parser.add_argument("--name", help="project name; defaults to the directory name")
    init_parser.add_argument(
        "--force", action="store_true", help="replace an existing state file"
    )
    init_parser.set_defaults(handler=_cmd_init)

    validate_parser = commands.add_parser("validate", help="validate project state")
    validate_parser.add_argument("target", nargs="?", default=".")
    validate_parser.add_argument(
        "--policy", help="also validate a JSON-compatible YAML tailoring policy"
    )
    validate_parser.set_defaults(handler=_cmd_validate)

    status_parser = commands.add_parser("status", help="summarize valid project state")
    status_parser.add_argument("target", nargs="?", default=".")
    status_parser.add_argument("--json", action="store_true", help="emit JSON")
    status_parser.set_defaults(handler=_cmd_status)

    repository_parser = commands.add_parser(
        "repository", help="inspect the enclosing Git or SVN working copy"
    )
    repository_parser.add_argument("target", nargs="?", default=".")
    repository_parser.add_argument("--json", action="store_true", help="emit JSON")
    repository_parser.set_defaults(handler=_cmd_repository)
    return parser


def _default_project_name(target: str, state_path: Path) -> str:
    target_path = Path(target)
    if target_path.suffix.lower() == ".json":
        parent = state_path.parent.parent if state_path.parent.name == ".ipd" else state_path.parent
        return parent.resolve().name
    return target_path.resolve().name


def _cmd_init(args: argparse.Namespace) -> int:
    state_path = resolve_state_path(args.target)
    if state_path.exists() and not args.force:
        print(f"error: state file already exists: {state_path}", file=sys.stderr)
        return 1
    name = args.name or _default_project_name(args.target, state_path)
    state = create_initial_state(name)
    write_state(state_path, state)
    print(f"Initialized IPD state: {state_path}")
    return 0


def _load_valid_state(target: str) -> tuple[dict[str, Any] | None, int]:
    state_path = resolve_state_path(target)
    state = load_state(state_path)
    issues = validate_state(state)
    if issues:
        print(f"Invalid IPD state: {state_path}", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return None, 1
    return state, 0


def _cmd_validate(args: argparse.Namespace) -> int:
    state, status = _load_valid_state(args.target)
    if status:
        return status
    if args.policy:
        load_policy(args.policy)
    assert state is not None
    print(f"Valid IPD state (revision {state['revision']}): {resolve_state_path(args.target)}")
    if args.policy:
        print(f"Valid tailoring policy: {args.policy}")
    return 0


def _summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": state["project"]["name"],
        "phase": state["project"]["phase"],
        "workflow_step": state["project"]["workflow_step"],
        "revision": state["revision"],
        "claims": dict(sorted(Counter(item["status"] for item in state["claims"]).items())),
        "deliverables": dict(
            sorted(Counter(item["status"] for item in state["deliverables"]).items())
        ),
        "gates": dict(sorted(Counter(item["status"] for item in state["gates"]).items())),
    }


def _cmd_status(args: argparse.Namespace) -> int:
    state, status = _load_valid_state(args.target)
    if status:
        return status
    assert state is not None
    summary = _summary(state)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"Project: {summary['project']}")
        print(f"Phase: {summary['phase']}")
        print(f"Workflow step: {summary['workflow_step']}")
        print(f"Revision: {summary['revision']}")
        for collection in ("claims", "deliverables", "gates"):
            counts = summary[collection]
            rendered = ", ".join(f"{key}={value}" for key, value in counts.items())
            print(f"{collection.title()}: {rendered or 'none'}")
    return 0


def _cmd_repository(args: argparse.Namespace) -> int:
    info = inspect_repository(args.target)
    if args.json:
        print(json.dumps(info.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"Kind: {info.kind}")
        print(f"Root: {info.root or '-'}")
        print(f"Revision: {info.revision or '-'}")
        dirty = "unknown" if info.dirty is None else str(info.dirty).lower()
        print(f"Dirty: {dirty}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (PolicyError, StateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

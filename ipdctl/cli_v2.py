"""Lifecycle command line for the IPD Agent Workflow Framework."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .engine import (
    TransitionError,
    approve_deliverable,
    approve_gate,
    claim_deliverable,
    close_deliverable,
    record_deliverable_review,
    record_gate_review,
    reject_deliverable,
    reject_gate,
    set_deliverable_status,
    set_gate_ready,
    start_deliverable_review,
)
from .eligibility import (
    binding_eligibility,
    claim_protocol_readiness,
    deliverable_binding_status,
)
from .i18n import (
    DEFAULT_LOCALE,
    LocaleError,
    Translator,
    get_translator,
    load_project_locale,
    localized_exception_message,
    normalize_locale,
)
from .model import TASK_TYPES, WORKFLOW_STEPS
from .lifecycle import advance_phase
from .governance import apply_phase_pointers, phase_history_issues, phase_pointers
from .policy import PolicyError, load_policy
from .project import (
    ProjectError,
    adopt_artifact_baseline,
    artifact_baseline_preview,
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
    expire_claims,
    load_runtime,
    record_event,
    save_runtime,
    utc_now,
)
from .state import StateError, load_state, resolve_state_path, revised_copy, write_state
from .transaction import project_access_guard, project_mutation_guard
from .validation import validate_state

VERSION = "0.3.2-beta"


class LocalizedArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with project-scoped headings and error prefix."""

    def __init__(self, *args: Any, translator: Translator | None = None, **kwargs: Any) -> None:
        self.translator = translator or get_translator(DEFAULT_LOCALE)
        super().__init__(*args, **kwargs)

    def format_help(self) -> str:
        text = super().format_help()
        replacements = {
            "usage:": self.translator.text("cli.parser.usage"),
            "options:": self.translator.text("cli.parser.options"),
            "positional arguments:": self.translator.text(
                "cli.parser.positional_arguments"
            ),
        }
        for source, replacement in replacements.items():
            if text.startswith(source):
                text = replacement + text[len(source) :]
            text = text.replace(f"\n{source}\n", f"\n{replacement}\n")
        return text

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        prefix = self.translator.text("cli.error.prefix")
        self.exit(2, f"{self.prog}: {prefix}: {message}\n")


def _add_target(parser: argparse.ArgumentParser, translator: Translator) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help=translator.text("cli.argument.target.help"),
    )


def _build_parser(translator: Translator | None = None) -> argparse.ArgumentParser:
    translator = translator or get_translator(DEFAULT_LOCALE)
    parser = LocalizedArgumentParser(
        prog="ipdctl",
        description=translator.text("cli.parser.description"),
        translator=translator,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser(
        "init",
        help=translator.text("cli.command.init.help"),
        description=translator.text("cli.command.init.help"),
        translator=translator,
    )
    _add_target(init, translator)
    init.add_argument("--name", help=translator.text("cli.argument.name.help"))
    init.add_argument(
        "--task-type",
        action="append",
        dest="task_types",
        help=translator.text("cli.argument.task_type.help"),
    )
    init.add_argument(
        "--locale",
        choices=list(("en", "zh-CN")),
        default=DEFAULT_LOCALE,
        help=translator.text("cli.argument.locale.help"),
    )
    init.add_argument(
        "--force", action="store_true", help=translator.text("cli.argument.force.help")
    )
    init.set_defaults(handler=_cmd_init)

    tailor = commands.add_parser(
        "tailor",
        help=translator.text("cli.command.tailor.help"),
        description=translator.text("cli.command.tailor.help"),
        translator=translator,
    )
    _add_target(tailor, translator)
    tailor.add_argument("--profile", help=translator.text("cli.argument.profile.help"))
    tailor.add_argument("--output", help=translator.text("cli.argument.output.help"))
    tailor.set_defaults(handler=_cmd_tailor)

    context = commands.add_parser(
        "context",
        help=translator.text("cli.command.context.help"),
        description=translator.text("cli.command.context.help"),
        translator=translator,
    )
    _add_target(context, translator)
    context.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    context.set_defaults(handler=_cmd_context)

    adopt_baseline = commands.add_parser(
        "adopt-baseline",
        help=translator.text("cli.command.adopt_baseline.help"),
        description=translator.text("cli.command.adopt_baseline.help"),
        translator=translator,
    )
    _add_target(adopt_baseline, translator)
    adopt_baseline.add_argument(
        "--actor", help=translator.text("cli.argument.baseline_actor.help")
    )
    adopt_baseline.add_argument(
        "--actor-type",
        choices=["human"],
        help=translator.text("cli.argument.baseline_actor_type.help"),
    )
    adopt_baseline.add_argument(
        "--authorized",
        action="store_true",
        help=translator.text("cli.argument.baseline_authorized.help"),
    )
    adopt_baseline.add_argument(
        "--reason", help=translator.text("cli.argument.reason.help")
    )
    adopt_baseline.add_argument(
        "--preview",
        action="store_true",
        help=translator.text("cli.argument.preview.help"),
    )
    adopt_baseline.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    adopt_baseline.set_defaults(handler=_cmd_adopt_baseline)

    for name, handler in (
        ("claim", _cmd_claim),
        ("close", _cmd_close),
        ("review", _cmd_review),
        ("approve", _cmd_approve),
        ("reject", _cmd_reject),
    ):
        command = commands.add_parser(
            name,
            help=translator.text(f"cli.command.{name}.help"),
            description=translator.text(f"cli.command.{name}.help"),
            translator=translator,
        )
        argument = "deliverable" if name in {"claim", "close"} else "subject"
        help_key = (
            "cli.argument.deliverable.help"
            if argument == "deliverable"
            else "cli.argument.subject.help"
        )
        command.add_argument(argument, help=translator.text(help_key))
        command.add_argument(
            "--project-root",
            default=".",
            help=translator.text("cli.argument.project_root.help"),
        )
        if name in {"claim", "close"}:
            command.add_argument(
                "--actor", default="agent", help=translator.text("cli.argument.actor.help")
            )
        if name == "claim":
            command.add_argument(
                "--lease-minutes",
                type=int,
                default=240,
                help=translator.text("cli.argument.lease_minutes.help"),
            )
            command.add_argument(
                "--recover",
                action="store_true",
                help=translator.text("cli.argument.recover.help"),
            )
        if name == "close":
            command.add_argument(
                "--evidence",
                action="append",
                default=[],
                help=translator.text("cli.argument.evidence.help"),
            )
            command.add_argument(
                "--status",
                choices=["ready_for_review", "blocked"],
                default="ready_for_review",
                help=translator.text("cli.argument.close_status.help"),
            )
            command.add_argument("--note", help=translator.text("cli.argument.note.help"))
        if name in {"review", "approve", "reject"}:
            command.add_argument(
                "--reviewer", required=True, help=translator.text("cli.argument.reviewer.help")
            )
            command.add_argument(
                "--actor-type",
                choices=["agent", "human"],
                default="agent",
                help=translator.text("cli.argument.actor_type.help"),
            )
            command.add_argument("--evidence", help=translator.text("cli.argument.evidence.help"))
            command.add_argument(
                "--authorized",
                action="store_true",
                help=translator.text("cli.argument.authorized.help"),
            )
        if name == "review":
            command.add_argument(
                "--decision",
                choices=["approve", "reject"],
                help=translator.text("cli.argument.decision.help"),
            )
        command.set_defaults(handler=handler)

    advance = commands.add_parser(
        "advance-phase",
        help=translator.text("cli.command.advance_phase.help"),
        description=translator.text("cli.command.advance_phase.help"),
        translator=translator,
    )
    _add_target(advance, translator)
    advance.set_defaults(handler=_cmd_advance_phase)

    refresh = commands.add_parser(
        "refresh",
        help=translator.text("cli.command.refresh.help"),
        description=translator.text("cli.command.refresh.help"),
        translator=translator,
    )
    _add_target(refresh, translator)
    refresh.set_defaults(handler=_cmd_refresh)

    verify = commands.add_parser(
        "verify",
        help=translator.text("cli.command.verify.help"),
        description=translator.text("cli.command.verify.help"),
        translator=translator,
    )
    _add_target(verify, translator)
    verify.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    verify.set_defaults(handler=_cmd_verify)

    repository = commands.add_parser(
        "repository",
        help=translator.text("cli.command.repository.help"),
        description=translator.text("cli.command.repository.help"),
        translator=translator,
    )
    _add_target(repository, translator)
    repository.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    repository.set_defaults(handler=_cmd_repository)

    reconcile = commands.add_parser(
        "reconcile",
        help=translator.text("cli.command.reconcile.help"),
        description=translator.text("cli.command.reconcile.help"),
        translator=translator,
    )
    _add_target(reconcile, translator)
    reconcile.add_argument("--bindings", help=translator.text("cli.argument.bindings.help"))
    reconcile.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    reconcile.set_defaults(handler=_cmd_reconcile)

    validate = commands.add_parser(
        "validate",
        help=translator.text("cli.command.validate.help"),
        description=translator.text("cli.command.validate.help"),
        translator=translator,
    )
    _add_target(validate, translator)
    validate.add_argument("--policy", help=translator.text("cli.argument.policy.help"))
    validate.set_defaults(handler=_cmd_validate)

    status = commands.add_parser(
        "status",
        help=translator.text("cli.command.status.help"),
        description=translator.text("cli.command.status.help"),
        translator=translator,
    )
    _add_target(status, translator)
    status.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    status.set_defaults(handler=_cmd_context)
    return parser


_COMMAND_NAMES = {
    "init",
    "tailor",
    "context",
    "adopt-baseline",
    "claim",
    "close",
    "review",
    "approve",
    "reject",
    "advance-phase",
    "refresh",
    "verify",
    "repository",
    "reconcile",
    "validate",
    "status",
}
_PROJECT_ROOT_COMMANDS = {"claim", "close", "review", "approve", "reject"}
_TRANSACTIONAL_COMMANDS = {
    "init",
    "tailor",
    "context",
    "adopt-baseline",
    "claim",
    "close",
    "review",
    "approve",
    "reject",
    "advance-phase",
    "refresh",
    "verify",
    "reconcile",
    "status",
}
_OPTIONS_WITH_VALUES = {
    "--name",
    "--task-type",
    "--locale",
    "--profile",
    "--output",
    "--project-root",
    "--actor",
    "--lease-minutes",
    "--evidence",
    "--status",
    "--note",
    "--reviewer",
    "--actor-type",
    "--decision",
    "--bindings",
    "--policy",
    "--reason",
}


def _option_value(arguments: Sequence[str], name: str) -> str | None:
    for index, token in enumerate(arguments):
        if token == name and index + 1 < len(arguments):
            return arguments[index + 1]
        if token.startswith(name + "="):
            return token.split("=", 1)[1]
    return None


def _command_and_tail(arguments: Sequence[str]) -> tuple[str | None, list[str]]:
    for index, token in enumerate(arguments):
        if token in _COMMAND_NAMES:
            return token, list(arguments[index + 1 :])
    return None, []


def _target_hint(command: str, tail: Sequence[str]) -> str:
    if command in _PROJECT_ROOT_COMMANDS:
        return _option_value(tail, "--project-root") or "."
    skip_next = False
    for token in tail:
        if skip_next:
            skip_next = False
            continue
        option = token.split("=", 1)[0]
        if option in _OPTIONS_WITH_VALUES:
            skip_next = "=" not in token
            continue
        if token.startswith("-"):
            continue
        return token
    return "."


def _locale_root(target: str | Path) -> Path:
    path = Path(target)
    if path.suffix.lower() in {".json", ".yaml", ".yml"} and path.parent.name == ".ipd":
        return path.parent.parent
    return path


def _infer_cli_locale(arguments: Sequence[str]) -> str:
    command, tail = _command_and_tail(arguments)
    if command == "init":
        configured = _option_value(tail, "--locale")
        return normalize_locale(configured) if configured is not None else DEFAULT_LOCALE
    if command is None:
        return DEFAULT_LOCALE
    return load_project_locale(_locale_root(_target_hint(command, tail)))


def _translator_for_args(args: argparse.Namespace) -> Translator:
    if args.command == "init":
        return get_translator(args.locale)
    target = args.project_root if args.command in _PROJECT_ROOT_COMMANDS else args.target
    return get_translator(load_project_locale(_locale_root(target)))


def _translator(args: argparse.Namespace) -> Translator:
    return getattr(args, "_translator", get_translator(DEFAULT_LOCALE))


def _normalize_task_type(value: str, translator: Translator | None = None) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"ai": "ai_system", "material": "material_change"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in TASK_TYPES:
        translator = translator or get_translator(DEFAULT_LOCALE)
        raise ProjectError(
            translator.text(
                "error.unsupported_task_type",
                value=value,
                choices=", ".join(TASK_TYPES),
            )
        )
    return normalized


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)


def _transaction_options(
    args: argparse.Namespace, root: Path
) -> tuple[tuple[Path, ...], bool] | None:
    """Return the complete write scope for one serialized CLI command."""

    if args.command not in _TRANSACTIONAL_COMMANDS:
        return None
    if args.command == "adopt-baseline" and args.preview:
        return None
    paths = project_paths(root)
    extras: tuple[Path, ...] = ()
    include_dashboard = False
    if args.command == "init":
        extras = (
            paths["profile"],
            paths["bindings"],
            paths["ipd"] / "project_state.yaml",
        )
    elif args.command == "tailor":
        extras = (paths["process"], paths["bindings"])
    elif args.command == "refresh":
        include_dashboard = True
    elif args.command == "verify":
        extras = (paths["verify_report"],)
        include_dashboard = True
    elif args.command == "reconcile":
        extras = (paths["reconcile_report"],)
    return extras, include_dashboard


def _cmd_init(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    name = args.name or root.name
    task_types = [
        _normalize_task_type(value, translator)
        for value in (args.task_types or ["software"])
    ]
    paths = initialize_project(
        root,
        name=name,
        task_types=task_types,
        locale=args.locale,
        force=args.force,
    )
    print(translator.text("cli.init.completed", path=paths["root"]))
    print(translator.text("cli.init.profile", path=paths["profile"]))
    print(translator.text("cli.init.state", path=paths["state"]))
    return 0


def _cmd_tailor(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    paths = project_paths(root)
    profile = Path(args.profile).resolve() if args.profile else paths["profile"]
    output = Path(args.output).resolve() if args.output else paths["process"]
    if output != paths["process"]:
        raise ProjectError(
            translator.text("error.tailor_output_canonical", path=paths["process"])
        )
    from .reconcile import load_artifact_bindings, sync_evidence_bindings
    from .tailoring import load_profile, tailor_profile

    # Compile and validate the entire bundle before replacing any authority
    # file.  A rejected re-tailor therefore leaves both process and state
    # untouched instead of publishing half of the new contract.
    process = tailor_profile(load_profile(profile))
    state = load_state(paths["state"])
    state = sync_state_with_process(state, process)
    bindings = sync_evidence_bindings(
        load_artifact_bindings(paths["bindings"]), process
    )
    with project_mutation_guard(
        root, extra_files=(paths["process"], paths["bindings"])
    ):
        write_state(paths["process"], process)
        write_state(paths["state"], state)
        write_state(paths["bindings"], bindings)
    print(translator.text("cli.tailor.process", path=output))
    print(
        translator.text(
            "cli.tailor.deliverables", count=len(process.get("deliverables", []))
        )
    )
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    translator = _translator(args)
    snapshot = context_snapshot(args.target)
    if args.json:
        print(_json(snapshot))
        return 0
    unavailable = translator.text("common.not_available")
    none = translator.text("common.none")
    print(translator.text("cli.context.project", value=snapshot["project"]))
    print(translator.text("cli.context.phase", value=snapshot["phase"]))
    print(translator.text("cli.context.tr", value=snapshot["tr"] or unavailable))
    print(translator.text("cli.context.dcp", value=snapshot["dcp"] or unavailable))
    print(translator.text("cli.context.gate", value=snapshot["gate"] or unavailable))
    print(
        translator.text(
            "cli.context.available_tasks",
            value=", ".join(item["id"] for item in snapshot["available_tasks"]) or none,
        )
    )
    print(
        translator.text(
            "cli.context.blocked_items",
            value=", ".join(item["id"] for item in snapshot["blocked_items"]) or none,
        )
    )
    return 0


def _cmd_adopt_baseline(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    if args.preview:
        eligibility = artifact_baseline_preview(root)
        snapshot = None
        if eligibility["eligible"]:
            from .reconcile import artifact_baseline_snapshot

            state = load_state(project_paths(root)["state"])
            snapshot = artifact_baseline_snapshot(
                root,
                state,
                bindings_path=project_paths(root)["bindings"],
            )
        result = {
            "schema_version": "1.0",
            "status": eligibility["status"],
            "eligible": eligibility["eligible"],
            "preview": True,
            "adopted": False,
            "idempotent": False,
            "baseline_id": (
                snapshot.get("baseline_id") if isinstance(snapshot, dict) else None
            ),
            "artifact_baseline": snapshot,
            "eligibility": eligibility,
        }
    else:
        if not isinstance(args.actor, str) or not args.actor.strip():
            raise ProjectError(
                translator.text("error.adopt_baseline_actor_required")
            )
        if args.actor_type != "human":
            raise ProjectError(
                translator.text("error.adopt_baseline_actor_type")
            )
        if args.authorized is not True:
            raise ProjectError(
                translator.text("error.adopt_baseline_authorized")
            )
        if not isinstance(args.reason, str) or not args.reason.strip():
            raise ProjectError(
                translator.text("error.adopt_baseline_reason_required")
            )
        result = adopt_artifact_baseline(
            root,
            actor=args.actor,
            actor_type=args.actor_type,
            authorized=args.authorized,
            reason=args.reason,
        )
    if args.json:
        print(_json(result))
    elif result.get("preview"):
        print(
            translator.text(
                "cli.adopt_baseline.preview_eligible"
                if result.get("eligible")
                else "cli.adopt_baseline.preview_blocked"
            )
        )
    elif result.get("adopted"):
        print(
            translator.text(
                "cli.adopt_baseline.adopted", baseline_id=result.get("baseline_id")
            )
        )
    else:
        print(
            translator.text(
                "cli.adopt_baseline.unchanged", baseline_id=result.get("baseline_id")
            )
        )
    return 0 if result.get("eligible") else 1


def _set_workflow_step(state: dict[str, Any], target: str) -> dict[str, Any]:
    """Set the next executable stage once; never synthesize skipped commands."""

    if target not in WORKFLOW_STEPS:
        raise TransitionError(f"unknown workflow step: {target!r}")
    if state["project"]["workflow_step"] == target:
        return state
    updated = revised_copy(state)
    updated["project"]["workflow_step"] = target
    issues = validate_state(updated)
    if issues:
        raise TransitionError(str(issues[0]))
    return updated


def _require_workflow_step(
    state: dict[str, Any],
    allowed: set[str],
    *,
    action: str,
    translator: Translator,
) -> None:
    current = state["project"]["workflow_step"]
    if current not in allowed:
        raise TransitionError(
            translator.text(
                "error.workflow_stage",
                action=action,
                current=current,
                expected=", ".join(sorted(allowed)),
            )
        )


def _require_current_verification(
    state: dict[str, Any],
    runtime: dict[str, Any],
    *,
    project_root: Path,
    action: str,
    translator: Translator,
) -> None:
    readiness = claim_protocol_readiness(project_root, state, runtime)
    if readiness["eligible"]:
        return
    if readiness.get("reason_code") == "CLAIM_VERIFICATION_INPUTS_CHANGED":
        raise TransitionError(
            translator.text("error.verification_inputs_changed", action=action)
        )
    if readiness.get("reason_code") == "CLAIM_VERIFICATION_REQUIRED":
        raise TransitionError(
            translator.text("error.verification_required", action=action)
        )
    raise TransitionError(
        translator.text(
            "error.workflow_stage",
            action=action,
            current=state.get("project", {}).get("workflow_step"),
            expected="context, verify",
        )
    )


def _require_phase_history(
    state: dict[str, Any],
    process: dict[str, Any] | None,
    runtime: dict[str, Any],
    translator: Translator,
) -> None:
    if process is None:
        raise TransitionError(translator.text("error.tailored_process_missing"))
    issues = phase_history_issues(state, process, runtime)
    if issues:
        raise TransitionError(
            translator.text("error.phase_history_invalid", issue=issues[0])
        )


def _cmd_claim(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state, process = load_project(root)
    instant = utc_now()
    runtime, expired = expire_claims(load_runtime(root), now=instant)
    _require_phase_history(state, process, runtime, translator)
    deliverable = next(
        (item for item in state.get("deliverables", []) if item.get("id") == args.deliverable),
        None,
    )
    if deliverable is None:
        raise TransitionError(
            translator.text("error.unknown_subject", subject=args.deliverable)
        )
    active = runtime.get("active_claims", {}).get(args.deliverable)
    recovering = False
    if deliverable.get("status") == "in_progress":
        _require_workflow_step(
            state, {"work"}, action="claim", translator=translator
        )
        if active is not None and active.get("actor") == args.actor:
            print(
                translator.text(
                    "cli.claim.already_active",
                    deliverable=args.deliverable,
                    actor=args.actor,
                )
            )
            return 0
        if active is not None:
            updated_state = state
        elif args.deliverable in expired or args.recover:
            recovering = True
            reason = translator.text(
                "state.claim.expired"
                if args.deliverable in expired
                else "state.claim.orphaned"
            )
            updated_state = set_deliverable_status(
                state,
                args.deliverable,
                "blocked",
                blocked_reason=reason,
            )
            updated_state = claim_deliverable(updated_state, args.deliverable)
        else:
            raise TransitionError(
                translator.text(
                    "error.orphan_claim_recover", deliverable=args.deliverable
                )
            )
    else:
        _require_workflow_step(
            state, {"context", "verify"}, action="claim", translator=translator
        )
        if state["project"]["workflow_step"] == "verify":
            _require_current_verification(
                state,
                runtime,
                project_root=root,
                action="claim",
                translator=translator,
            )
        updated_state = claim_deliverable(state, args.deliverable)
    updated_state = _set_workflow_step(updated_state, "work")
    eligibility = binding_eligibility(
        root,
        state,
        runtime,
        bindings_path=paths["bindings"],
        target_deliverable=args.deliverable,
    )
    binding_status = deliverable_binding_status(eligibility, args.deliverable)
    if not binding_status["eligible"]:
        issue_codes = binding_status.get("issue_codes", [])
        reason = issue_codes[0] if issue_codes else "BINDING_READINESS_UNAVAILABLE"
        raise TransitionError(
            f"claim preflight failed for {args.deliverable!r}: {reason}"
        )
    from .reconcile import (
        create_claim_binding_window,
        recover_claim_binding_window,
    )

    if recovering:
        binding_window = recover_claim_binding_window(
            runtime,
            args.deliverable,
            project_root=root,
            state=state,
            bindings_path=paths["bindings"],
        )
        if binding_window is None:
            raise TransitionError(
                translator.text(
                    "error.claim_recovery_window_missing",
                    deliverable=args.deliverable,
                )
            )
    else:
        binding_window = create_claim_binding_window(
            root,
            state,
            runtime,
            args.deliverable,
            bindings_path=paths["bindings"],
        )
    updated_runtime = claim_runtime(
        runtime,
        args.deliverable,
        actor=args.actor,
        lease_minutes=args.lease_minutes,
        state_revision=updated_state["revision"],
        binding_window=binding_window,
        now=instant,
    )
    with project_mutation_guard(root):
        write_state(paths["state"], updated_state)
        save_runtime(root, updated_runtime)
    print(
        translator.text(
            "cli.claim.completed", deliverable=args.deliverable, actor=args.actor
        )
    )
    return 0


def _cmd_close(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state, process = load_project(root)
    instant = utc_now()
    runtime, expired = expire_claims(load_runtime(root), now=instant)
    _require_phase_history(state, process, runtime, translator)
    if expired:
        # Persist the time-driven lease expiry even though close will now fail
        # and require an explicit recovery claim.
        save_runtime(root, runtime)
    _require_workflow_step(
        state, {"work"}, action="close", translator=translator
    )
    if args.status == "blocked":
        state = set_deliverable_status(
            state,
            args.deliverable,
            "blocked",
            evidence=args.evidence,
            blocked_reason=args.note or translator.text("state.blocked.default"),
        )
    else:
        state = close_deliverable(state, args.deliverable, evidence=args.evidence)
    next_step = "refresh" if args.status == "blocked" else "review"
    state = _set_workflow_step(state, next_step)
    runtime = close_claim(
        runtime,
        args.deliverable,
        actor=args.actor,
        action="close",
        details={
            "status": args.status,
            "note": args.note,
            "evidence": list(args.evidence),
            "state_revision": state["revision"],
        },
        now=instant,
    )
    with project_mutation_guard(root):
        write_state(paths["state"], state)
        save_runtime(root, runtime)
    print(
        translator.text(
            "cli.close.completed",
            deliverable=args.deliverable,
            status=translator.text(f"status.{args.status}"),
        )
    )
    return 0


def _resolve_subject(
    state: dict[str, Any],
    process: dict[str, Any] | None,
    subject: str,
    translator: Translator,
) -> tuple[str, str]:
    if any(item.get("id") == subject for item in state.get("deliverables", [])):
        return "deliverable", subject
    gate_id = subject
    if process is not None:
        for collection in ("technical_reviews", "decision_checkpoints"):
            for item in process.get(collection, []):
                if isinstance(item, dict) and item.get("id") == subject:
                    gate_id = item.get("gate_id") or subject
                    break
        process_gate_ids = {
            item.get("id")
            for item in process.get("gates", [])
            if isinstance(item, dict)
        }
        if gate_id not in process_gate_ids and subject not in process_gate_ids:
            raise TransitionError(
                translator.text("error.unknown_subject", subject=subject)
            )
    if any(item.get("id") == gate_id for item in state.get("gates", [])):
        return "gate", gate_id
    raise TransitionError(translator.text("error.unknown_subject", subject=subject))


def _gate_status(state: dict[str, Any], gate_id: str) -> str:
    return next(
        str(item.get("status"))
        for item in state.get("gates", [])
        if item.get("id") == gate_id
    )


def _require_current_gate(
    state: dict[str, Any],
    process: dict[str, Any] | None,
    gate_id: str,
    translator: Translator,
) -> None:
    """Restrict Gate decisions to the current Phase's next canonical Gate."""

    if process is None:
        raise TransitionError(translator.text("error.tailored_process_missing"))
    project = state.get("project", {})
    current_gate = project.get("current_gate")
    current_phase = project.get("phase")
    canonical_gate = phase_pointers(state, process)["current_gate"]
    if current_gate != canonical_gate:
        raise TransitionError(
            translator.text(
                "error.gate_pointer_stale",
                current=current_gate or "none",
                expected=canonical_gate or "none",
            )
        )
    if gate_id != canonical_gate:
        raise TransitionError(
            translator.text(
                "error.gate_not_current",
                gate=gate_id,
                current=canonical_gate or "none",
                phase=current_phase or "unknown",
            )
        )


def _runtime_subject_details(subject_type: str, subject_id: str) -> dict[str, Any]:
    details: dict[str, Any] = {
        "subject_type": subject_type,
        "subject": subject_id,
    }
    details["deliverable" if subject_type == "deliverable" else "gate"] = subject_id
    return details


def _cmd_review(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state, process = load_project(root)
    runtime = load_runtime(root)
    _require_phase_history(state, process, runtime, translator)
    subject_type, subject_id = _resolve_subject(
        state, process, args.subject, translator
    )
    if subject_type == "deliverable":
        _require_workflow_step(
            state, {"review"}, action="review", translator=translator
        )
        state = start_deliverable_review(state, subject_id)
    else:
        _require_workflow_step(
            state, {"review", "verify"}, action="review gate", translator=translator
        )
        if state["project"]["workflow_step"] == "verify":
            _require_current_verification(
                state,
                runtime,
                project_root=root,
                action="review gate",
                translator=translator,
            )
        _require_current_gate(state, process, subject_id, translator)
        status = _gate_status(state, subject_id)
        if status in {"planned", "rejected"}:
            state = set_gate_ready(state, subject_id)
        elif status != "ready":
            raise TransitionError(
                translator.text(
                    "error.gate_review_status", gate=subject_id, status=status
                )
            )
    if args.decision:
        if not args.evidence:
            raise TransitionError(
                translator.text("error.review_decision_evidence")
            )
        record = (
            record_deliverable_review
            if subject_type == "deliverable"
            else record_gate_review
        )
        state = record(
            state,
            subject_id,
            reviewer=args.reviewer,
            reviewer_type=args.actor_type,
            authorized=bool(args.authorized and args.actor_type == "human"),
            decision=args.decision,
            evidence=args.evidence,
        )
    state = _set_workflow_step(state, "review")
    details = _runtime_subject_details(subject_type, subject_id)
    details["reviewer"] = args.reviewer
    details["reviewer_type"] = args.actor_type
    details["authorized"] = bool(args.authorized and args.actor_type == "human")
    details["decision"] = args.decision
    details["evidence"] = args.evidence
    details["state_revision"] = state["revision"]
    runtime = record_event(
        runtime,
        "review",
        details=details,
    )
    with project_mutation_guard(root):
        write_state(paths["state"], state)
        save_runtime(root, runtime)
    print(translator.text("cli.review.started", subject=args.subject))
    return 0


def _require_review_evidence(
    args: argparse.Namespace, translator: Translator | None = None
) -> str:
    if not args.evidence:
        translator = translator or get_translator(DEFAULT_LOCALE)
        raise TransitionError(translator.text("error.final_review_evidence"))
    return args.evidence


def _cmd_approve(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state, process = load_project(root)
    runtime = load_runtime(root)
    _require_phase_history(state, process, runtime, translator)
    subject_type, subject_id = _resolve_subject(
        state, process, args.subject, translator
    )
    _require_workflow_step(
        state, {"review"}, action="approve", translator=translator
    )
    evidence = _require_review_evidence(args, translator)
    if subject_type == "deliverable":
        state = approve_deliverable(
            state,
            subject_id,
            reviewer=args.reviewer,
            reviewer_type=args.actor_type,
            authorized=args.authorized,
            evidence=evidence,
        )
    else:
        _require_current_gate(state, process, subject_id, translator)
        state = record_gate_review(
            state,
            subject_id,
            reviewer=args.reviewer,
            reviewer_type=args.actor_type,
            authorized=args.authorized,
            decision="approve",
            evidence=evidence,
        )
        state = approve_gate(state, subject_id)
        apply_phase_pointers(state, process)
    state = _set_workflow_step(state, "refresh")
    details = _runtime_subject_details(subject_type, subject_id)
    details["reviewer"] = args.reviewer
    details["reviewer_type"] = args.actor_type
    details["authorized"] = args.authorized
    details["decision"] = "approve"
    details["evidence"] = evidence
    details["state_revision"] = state["revision"]
    runtime = record_event(
        runtime,
        "approve",
        details=details,
    )
    with project_mutation_guard(root):
        write_state(paths["state"], state)
        save_runtime(root, runtime)
    key = "cli.approve.completed" if subject_type == "deliverable" else "cli.approve.gate"
    print(translator.text(key, subject=args.subject))
    return 0


def _cmd_reject(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.project_root).resolve()
    paths = project_paths(root)
    state, process = load_project(root)
    runtime = load_runtime(root)
    _require_phase_history(state, process, runtime, translator)
    subject_type, subject_id = _resolve_subject(
        state, process, args.subject, translator
    )
    _require_workflow_step(
        state, {"review"}, action="reject", translator=translator
    )
    evidence = _require_review_evidence(args, translator)
    if subject_type == "deliverable":
        state = reject_deliverable(
            state,
            subject_id,
            reviewer=args.reviewer,
            reviewer_type=args.actor_type,
            authorized=args.authorized,
            evidence=evidence,
        )
    else:
        _require_current_gate(state, process, subject_id, translator)
        state = record_gate_review(
            state,
            subject_id,
            reviewer=args.reviewer,
            reviewer_type=args.actor_type,
            authorized=args.authorized,
            decision="reject",
            evidence=evidence,
        )
        state = reject_gate(state, subject_id)
        apply_phase_pointers(state, process)
    state = _set_workflow_step(state, "refresh")
    details = _runtime_subject_details(subject_type, subject_id)
    details["reviewer"] = args.reviewer
    details["reviewer_type"] = args.actor_type
    details["authorized"] = args.authorized
    details["decision"] = "reject"
    details["evidence"] = evidence
    details["state_revision"] = state["revision"]
    runtime = record_event(
        runtime,
        "reject",
        details=details,
    )
    with project_mutation_guard(root):
        write_state(paths["state"], state)
        save_runtime(root, runtime)
    print(translator.text("cli.reject.completed", subject=args.subject))
    return 0


def _cmd_advance_phase(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    paths = project_paths(root)
    state, process = load_project(root)
    if process is None:
        raise ProjectError(translator.text("error.tailored_process_missing"))
    runtime = load_runtime(root)
    _require_phase_history(state, process, runtime, translator)
    _require_workflow_step(
        state, {"verify"}, action="advance-phase", translator=translator
    )
    _require_current_verification(
        state,
        runtime,
        project_root=root,
        action="advance-phase",
        translator=translator,
    )
    current = state["project"]["phase"]
    state = advance_phase(
        state,
        process,
        verified_state_revision=runtime["last_verification"]["state_revision"],
    )
    next_phase = state["project"]["phase"]
    runtime = record_event(
        runtime,
        "advance_phase",
        details={
            "from_phase": current,
            "to_phase": next_phase,
            "state_revision": state["revision"],
        },
    )
    with project_mutation_guard(root):
        write_state(paths["state"], state)
        save_runtime(root, runtime)
    print(
        translator.text(
            "cli.advance_phase.completed", current=current, next=next_phase
        )
    )
    print(translator.text("cli.advance_phase.refresh_required"))
    return 0


def _cmd_refresh(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    paths = project_paths(root)
    state = load_state(paths["state"])
    with project_mutation_guard(root, include_dashboard=True):
        if state["project"].get("workflow_step") == "refresh":
            state = _set_workflow_step(state, "verify")
            write_state(paths["state"], state)
        manifest = refresh_project(args.target)
    outputs = manifest.get("outputs", []) if isinstance(manifest, dict) else []
    print(translator.text("cli.refresh.completed", count=len(outputs) + 1))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    paths = project_paths(root)
    with project_mutation_guard(
        root,
        extra_files=(paths["verify_report"],),
        include_dashboard=True,
    ):
        report = verify_project(root)
    if args.json or report["status"] != "passed":
        print(_json(report))
    else:
        print(
            translator.text(
                "cli.verify.passed", revision=report["state_revision"]
            )
        )
    return 0 if report["status"] == "passed" else 1


def _cmd_repository(args: argparse.Namespace) -> int:
    translator = _translator(args)
    info = inspect_repository(args.target).as_dict()
    if args.json:
        print(_json(info))
    else:
        for key in ("kind", "root", "branch", "revision", "dirty", "remote"):
            value = info.get(key)
            if value is None:
                value = translator.text("common.not_available")
            elif type(value) is bool:
                value = translator.text("common.yes" if value else "common.no")
            print(translator.text(f"cli.repository.{key}", value=value))
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    translator = _translator(args)
    from .reconcile import reconcile_project

    root = Path(args.target).resolve()
    state = load_state(project_paths(root)["state"])
    report = reconcile_project(
        root,
        state,
        bindings_path=args.bindings,
        runtime=load_runtime(root),
        write=True,
    )
    if args.json:
        print(_json(report))
    else:
        status = report.get("status")
        status_key = f"report.status.{status}"
        display_status = translator.text(status_key) if translator.has_key(status_key) else status
        print(translator.text("cli.reconcile.status", value=display_status))
        print(
            translator.text(
                "cli.reconcile.changed_paths",
                count=len(report.get("changed_paths", [])),
            )
        )
        print(
            translator.text(
                "cli.reconcile.issues", count=len(report.get("issues", []))
            )
        )
    return 1 if report.get("status") == "failed" else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    translator = _translator(args)
    target = Path(args.target)
    project_target = target.is_dir()
    path = resolve_state_path(target)
    state = load_state(path)
    issues = validate_state(state)
    if issues:
        print(translator.text("cli.validate.invalid", path=path), file=sys.stderr)
        for issue in issues:
            print(translator.text("cli.validate.issue", issue=issue), file=sys.stderr)
        return 1
    if args.policy:
        load_policy(args.policy)
    if project_target:
        from .reconcile import load_artifact_bindings

        deliverable_ids = {
            item["id"]
            for item in state.get("deliverables", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        load_artifact_bindings(
            project_paths(target)["bindings"],
            known_deliverables=deliverable_ids,
        )
    print(
        translator.text(
            "cli.validate.valid", revision=state["revision"], path=path
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    try:
        bootstrap_translator = get_translator(_infer_cli_locale(arguments))
    except LocaleError as exc:
        fallback = get_translator(DEFAULT_LOCALE)
        print(f"{fallback.text('cli.error.prefix')}: {exc}", file=sys.stderr)
        return 1
    parser = _build_parser(bootstrap_translator)
    args = parser.parse_args(arguments)
    try:
        target = (
            getattr(args, "project_root", None)
            if args.command in _PROJECT_ROOT_COMMANDS
            else getattr(args, "target", None)
        )
        if target is not None:
            candidate = Path(target).resolve()
            if candidate.is_file():
                candidate = (
                    candidate.parent.parent
                    if candidate.parent.name == ".ipd"
                    else candidate.parent
                )
            transaction_options = _transaction_options(args, candidate)
            if (
                transaction_options is not None
                and (
                    args.command == "init"
                    or resolve_state_path(candidate).is_file()
                )
            ):
                extra_files, include_dashboard = transaction_options
                with project_mutation_guard(
                    candidate,
                    extra_files=extra_files,
                    include_dashboard=include_dashboard,
                ):
                    args._translator = _translator_for_args(args)
                    return args.handler(args)
            with project_access_guard(candidate):
                args._translator = _translator_for_args(args)
                return args.handler(args)
        args._translator = _translator_for_args(args)
        return args.handler(args)
    except (
        AgentRuntimeError,
        LocaleError,
        PolicyError,
        ProjectError,
        StateError,
        TransitionError,
        ValueError,
        OSError,
    ) as exc:
        translator = _translator(args)
        message = localized_exception_message(exc, translator)
        print(f"{translator.text('cli.error.prefix')}: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

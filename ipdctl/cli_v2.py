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
    bind_current_iteration_subject,
    claim_deliverable,
    clear_current_iteration_subject,
    close_deliverable,
    record_deliverable_review,
    record_gate_review,
    reject_deliverable,
    reject_gate,
    recover_current_iteration_subject,
    set_deliverable_status,
    set_gate_ready,
    start_deliverable_review,
)
from .eligibility import (
    binding_eligibility,
    claim_protocol_readiness,
    deliverable_binding_status,
    deliverable_refinement_status,
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
    closed_phase_process_changes,
    context_snapshot,
    deliverable_has_history,
    effective_dependency_corrections,
    governed_deliverable_rewrites,
    initialize_project,
    load_project,
    project_consistency_issues,
    project_paths,
    project_traceability_projection,
    refresh_project,
    render_project_dashboard,
    sync_state_with_process,
    verify_project,
)
from .repository import inspect_repository
from .runtime import (
    RuntimeError as AgentRuntimeError,
    claim as claim_runtime,
    close_claim,
    expire_claims,
    format_time,
    load_runtime,
    record_event,
    record_process_refinement,
    save_runtime,
    utc_now,
)
from .state import StateError, load_state, resolve_state_path, revised_copy, write_state
from .transaction import project_access_guard, project_mutation_guard
from .validation import validate_state
from .version import PUBLIC_VERSION

VERSION = PUBLIC_VERSION


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
    tailor.add_argument(
        "--preview",
        action="store_true",
        help=translator.text("cli.argument.preview.help"),
    )
    tailor.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    tailor.add_argument(
        "--apply-migrations",
        action="store_true",
        help=translator.text("cli.argument.apply_migrations.help"),
    )
    tailor.add_argument(
        "--actor", help=translator.text("cli.argument.migration_actor.help")
    )
    tailor.add_argument(
        "--actor-type",
        choices=["human"],
        help=translator.text("cli.argument.migration_actor_type.help"),
    )
    tailor.add_argument(
        "--authorized",
        action="store_true",
        help=translator.text("cli.argument.migration_authorized.help"),
    )
    tailor.add_argument(
        "--reason", help=translator.text("cli.argument.migration_reason.help")
    )
    tailor.set_defaults(handler=_cmd_tailor)

    refine = commands.add_parser(
        "refine",
        help=translator.text("cli.command.refine.help"),
        description=translator.text("cli.command.refine.help"),
        translator=translator,
    )
    _add_target(refine, translator)
    refine.add_argument(
        "--plan",
        required=True,
        help=translator.text("cli.argument.plan.help"),
    )
    mode = refine.add_mutually_exclusive_group()
    mode.add_argument(
        "--preview",
        action="store_true",
        help=translator.text("cli.argument.refine_preview.help"),
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        dest="apply_refinement",
        help=translator.text("cli.argument.apply_refinement.help"),
    )
    refine.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
    refine.add_argument("--actor", help=translator.text("cli.argument.refine_actor.help"))
    refine.add_argument(
        "--actor-type",
        choices=["human"],
        help=translator.text("cli.argument.refine_actor_type.help"),
    )
    refine.add_argument(
        "--authorized",
        action="store_true",
        help=translator.text("cli.argument.refine_authorized.help"),
    )
    refine.add_argument("--reason", help=translator.text("cli.argument.refine_reason.help"))
    refine.set_defaults(handler=_cmd_refine)

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
            command.add_argument(
                "--recover-subject",
                action="store_true",
                help=translator.text("cli.argument.recover_subject.help"),
            )
            command.add_argument(
                "--reason",
                help=translator.text("cli.argument.review_recovery_reason.help"),
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

    render_dashboard_command = commands.add_parser(
        "render-dashboard",
        help=translator.text("cli.command.render_dashboard.help"),
        description=translator.text("cli.command.render_dashboard.help"),
        translator=translator,
    )
    _add_target(render_dashboard_command, translator)
    render_dashboard_command.set_defaults(handler=_cmd_render_dashboard)

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
    validate.add_argument(
        "--json", action="store_true", help=translator.text("cli.argument.json.help")
    )
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
    "refine",
    "context",
    "adopt-baseline",
    "claim",
    "close",
    "review",
    "approve",
    "reject",
    "advance-phase",
    "refresh",
    "render-dashboard",
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
    "refine",
    "context",
    "adopt-baseline",
    "claim",
    "close",
    "review",
    "approve",
    "reject",
    "advance-phase",
    "refresh",
    "render-dashboard",
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
    "--plan",
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
    if path.suffix.lower() in {".json", ".yaml", ".yml"}:
        return path.parent.parent if path.parent.name == ".ipd" else path.parent
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


def _enrich_tailor_preview(
    diff: dict[str, Any], state: dict[str, Any], process: dict[str, Any]
) -> dict[str, Any]:
    """Add state projection and typed migration facts without changing five keys."""

    # Validate replay safety against the current state even in no-write mode.
    effective_dependency_corrections(state, process)
    _, impact = project_traceability_projection(state, process)
    for edge in impact["added"]:
        diff["added"].append(
            {
                "collection": "state.traceability",
                "id": f"{edge['source']}|{edge['relation']}|{edge['target']}",
            }
        )
    for edge in impact["removed"]:
        diff["removed"].append(
            {
                "collection": "state.traceability",
                "id": f"{edge['source']}|{edge['relation']}|{edge['target']}",
            }
        )
    for redirect in impact["redirected"]:
        before = redirect["before"]
        after = redirect["after"]
        diff["changed"].append(
            {
                "collection": "state.traceability",
                "id": f"{before['source']}|{before['relation']}|{before['target']}",
                "fields": list(redirect["fields"]),
                "before": before,
                "after": after,
            }
        )
    for blocker in impact["blocked"]:
        diff["ambiguous"].append(
            {"kind": "state_traceability_blocked", **blocker}
        )
    diff["migrations"].extend(
        {"entity_type": "gate", **dict(item)}
        for item in process.get("gate_migrations", [])
        if isinstance(item, dict)
    )
    diff["migrations"].extend(
        {"entity_type": "deliverable_dependency", **dict(item)}
        for item in process.get("dependency_corrections", [])
        if isinstance(item, dict)
    )
    sort_key = lambda item: json.dumps(
        item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    for field in ("added", "removed", "changed", "migrations", "ambiguous"):
        diff[field] = sorted(diff[field], key=sort_key)
    return diff


def _transaction_options(
    args: argparse.Namespace, root: Path
) -> tuple[tuple[Path, ...], bool] | None:
    """Return the complete write scope for one serialized CLI command."""

    if args.command not in _TRANSACTIONAL_COMMANDS:
        return None
    if args.command == "adopt-baseline" and args.preview:
        return None
    if args.command == "tailor" and args.preview:
        return None
    if args.command == "refine" and not args.apply_refinement:
        return None
    paths = project_paths(root)
    extras: tuple[Path, ...] = ()
    include_dashboard = False
    if args.command == "init":
        extras = (
            paths["profile"],
            paths["extensions"],
            paths["bindings"],
            paths["ipd"] / "project_state.yaml",
        )
    elif args.command == "tailor":
        extras = (paths["extensions"], paths["process"], paths["bindings"])
    elif args.command == "refine":
        extras = (paths["extensions"], paths["process"], paths["bindings"])
    elif args.command in {"refresh", "render-dashboard"}:
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
    from .process_extensions import load_process_extension
    from .reconcile import load_artifact_bindings, sync_evidence_bindings
    from .tailoring import load_profile, preview_process_diff, tailor_profile

    # Compile and validate the entire bundle before replacing any authority
    # file.  A rejected re-tailor therefore leaves both process and state
    # untouched instead of publishing half of the new contract.
    extension_existed = paths["extensions"].is_file()
    extension = load_process_extension(
        paths["extensions"] if extension_existed else None
    )
    process = tailor_profile(load_profile(profile), extension)
    current_process = (
        load_state(paths["process"]) if paths["process"].is_file() else None
    )
    previous_state = load_state(paths["state"])
    diff = _enrich_tailor_preview(
        preview_process_diff(current_process, process), previous_state, process
    )
    if args.preview:
        if args.json:
            print(_json(diff))
        else:
            print(translator.text("cli.tailor.preview_title"))
            for field in ("added", "removed", "changed", "migrations", "ambiguous"):
                print(
                    translator.text(
                        "cli.tailor.preview_count",
                        field=field,
                        count=len(diff.get(field, [])),
                    )
                )
        return 0

    if previous_state.get("project", {}).get("workflow_step") == "review":
        raise ProjectError(
            translator.text(
                "error.process_active_review",
                subject=previous_state.get("project", {}).get(
                    "current_iteration_subject"
                )
                or "unknown",
            )
        )

    closed_phase_changes = (
        closed_phase_process_changes(
            diff,
            previous_state,
            current_process,
            process,
        )
        if current_process is not None
        else []
    )
    if closed_phase_changes:
        raise ProjectError(
            translator.text(
                "error.tailor_closed_phase_change",
                issue="changes target closed phases: "
                + ", ".join(closed_phase_changes),
            )
        )

    refinement_changes = [
        item
        for field in ("added", "removed", "changed")
        for item in diff.get(field, [])
        if isinstance(item, dict) and item.get("collection") == "refinements"
    ]
    if refinement_changes:
        raise ProjectError(
            translator.text("error.tailor_refinement_requires_command")
        )
    if current_process is not None:
        from .refinement import (
            refinement_authority_projection,
            refinement_children,
        )

        current_declared_roots = set(
            refinement_authority_projection(current_process)["roots"]
        )
        candidate_declared_roots = set(
            refinement_authority_projection(process)["roots"]
        )
        applied_roots = {
            item.get("root")
            for item in current_process.get("refinements", [])
            if isinstance(item, dict) and isinstance(item.get("root"), str)
        }
        due_roots = {
            root
            for root in current_declared_roots
            if deliverable_refinement_status(previous_state, root).get(
                "refinement_status"
            )
            == "due"
        }
        protected_roots = applied_roots | due_roots
        mutable_roots = (
            current_declared_roots | candidate_declared_roots
        ) - protected_roots
        candidate_applied_roots = {
            item.get("root")
            for item in process.get("refinements", [])
            if isinstance(item, dict) and isinstance(item.get("root"), str)
        }
        if any(
            refinement_children(current_process, root)
            or refinement_children(process, root)
            or root in candidate_applied_roots
            for root in mutable_roots
        ):
            raise ProjectError(
                translator.text("error.tailor_refinement_requires_command")
            )
        current_authority = refinement_authority_projection(
            current_process,
            protected_roots=protected_roots,
            mutable_requirement_roots=mutable_roots,
        )
        candidate_authority = refinement_authority_projection(
            process,
            protected_roots=protected_roots,
            mutable_requirement_roots=mutable_roots,
        )
        if current_authority != candidate_authority:
            raise ProjectError(
                translator.text("error.tailor_refinement_requires_command")
            )

    governed_rewrites = governed_deliverable_rewrites(
        diff,
        previous_state,
        current_process or {},
        process,
    )
    declared_corrections = {
        item.get("deliverable"): item
        for item in process.get("dependency_corrections", [])
        if isinstance(item, dict) and isinstance(item.get("deliverable"), str)
    }
    effective_corrections = {
        item["deliverable"]: item
        for item in effective_dependency_corrections(previous_state, process)
    }
    state_deliverables = {
        item.get("id"): item
        for item in previous_state.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    authorized_dependency_rewrites = {
        identifier
        for identifier, fields in governed_rewrites.items()
        if fields == ["depends_on"]
        and identifier in declared_corrections
        and (
            identifier in effective_corrections
            or state_deliverables.get(identifier, {}).get("depends_on", [])
            == declared_corrections[identifier].get("after")
        )
    }
    unsafe_governed_rewrites = {
        identifier: fields
        for identifier, fields in governed_rewrites.items()
        if identifier not in authorized_dependency_rewrites
    }
    if unsafe_governed_rewrites:
        detail = ", ".join(
            f"{identifier} ({'/'.join(fields)})"
            for identifier, fields in unsafe_governed_rewrites.items()
        )
        raise ProjectError(
            translator.text(
                "error.tailor_governed_deliverable_rewrite",
                deliverables=detail,
            )
        )

    runtime = load_runtime(root)
    active_claims = runtime.get("active_claims", {})
    if active_claims:
        raise ProjectError(
            translator.text(
                "error.tailor_active_claim",
                claims=", ".join(sorted(active_claims)),
            )
        )
    state = sync_state_with_process(
        previous_state,
        process,
        apply_migrations=args.apply_migrations,
    )
    candidate_history_issues = phase_history_issues(state, process, runtime)
    if candidate_history_issues:
        raise ProjectError(
            translator.text(
                "error.tailor_closed_phase_change",
                issue=candidate_history_issues[0],
            )
        )
    bindings = sync_evidence_bindings(
        load_artifact_bindings(paths["bindings"]), process
    )
    process_ids = {
        item.get("id")
        for item in process.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    previous_ids = {
        item.get("id")
        for item in previous_state.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    previous_statuses = {
        item.get("id"): item.get("status")
        for item in previous_state.get("deliverables", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    migrated_state_ids = {
        item.get("id")
        for item in state.get("deliverables", [])
        if isinstance(item, dict) and item.get("status") == "superseded"
    }
    applied_migrations = [
        migration
        for migration in process.get("migrations", [])
        if isinstance(migration, dict)
        and migration.get("from") in previous_ids - process_ids
        and migration.get("from") in migrated_state_ids
        and previous_statuses.get(migration.get("from")) != "superseded"
    ]
    previous_gate_ids = {
        item.get("id")
        for item in previous_state.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    candidate_gate_ids = {
        item.get("id")
        for item in process.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    applied_gate_migrations = [
        migration
        for migration in process.get("gate_migrations", [])
        if isinstance(migration, dict)
        and migration.get("from") in previous_gate_ids
        and migration.get("to") in candidate_gate_ids
        and migration.get("from") != migration.get("to")
    ]
    applied_dependency_corrections = [
        correction
        for identifier, correction in sorted(effective_corrections.items())
        if deliverable_has_history(state_deliverables.get(identifier, {}))
    ]
    if (
        applied_migrations
        or applied_gate_migrations
        or applied_dependency_corrections
    ):
        if not isinstance(args.actor, str) or not args.actor.strip():
            raise ProjectError(
                translator.text("error.tailor_migration_actor_required")
            )
        if args.actor_type != "human":
            raise ProjectError(
                translator.text("error.tailor_migration_actor_type")
            )
        if args.authorized is not True:
            raise ProjectError(
                translator.text("error.tailor_migration_authorized")
            )
        if not isinstance(args.reason, str) or not args.reason.strip():
            raise ProjectError(
                translator.text("error.tailor_migration_reason_required")
            )
        event_details: dict[str, Any] = {
            "actor": args.actor.strip(),
            "actor_type": args.actor_type,
            "authorized": True,
            "reason": args.reason.strip(),
            "state_revision": state["revision"],
            "previous_process_schema_version": (
                current_process.get("schema_version")
                if isinstance(current_process, dict)
                else None
            ),
            "process_schema_version": process.get("schema_version"),
        }
        if applied_migrations:
            event_details["migrations"] = applied_migrations
        if applied_gate_migrations:
            event_details["gate_migrations"] = applied_gate_migrations
        if applied_dependency_corrections:
            event_details["dependency_corrections"] = applied_dependency_corrections
        runtime = record_event(
            runtime,
            "process_migration",
            details=event_details,
        )
    with project_mutation_guard(
        root,
        extra_files=(paths["extensions"], paths["process"], paths["bindings"]),
    ):
        if not extension_existed:
            write_state(paths["extensions"], extension)
        write_state(paths["process"], process)
        write_state(paths["state"], state)
        write_state(paths["bindings"], bindings)
        save_runtime(root, runtime)
    if args.json:
        print(_json(diff))
        return 0
    print(translator.text("cli.tailor.process", path=output))
    print(
        translator.text(
            "cli.tailor.deliverables", count=len(process.get("deliverables", []))
        )
    )
    return 0


def _cmd_refine(args: argparse.Namespace) -> int:
    """Preview or apply one explicit, human-authorized refinement plan."""

    translator = _translator(args)
    root = Path(args.target).resolve()
    paths = project_paths(root)
    state, current_process = load_project(root)
    if current_process is None:
        raise ProjectError(translator.text("error.tailored_process_missing"))

    from .process_extensions import load_process_extension
    from .reconcile import (
        load_artifact_bindings,
        preview_refinement_binding_impact,
        sync_evidence_bindings,
    )
    from .refinement import (
        finalize_refinement_record,
        load_refinement_plan,
        merge_refinement_plan,
        historical_dependency_rewrites,
        historical_deliverable_id_reuse,
        process_fingerprint,
        refinement_plan_digest,
    )
    from .tailoring import load_profile, preview_process_diff, tailor_profile

    extension = load_process_extension(paths["extensions"])
    profile = load_profile(paths["profile"])
    current_fingerprint = process_fingerprint(current_process)
    # A refinement event may only add the reviewed plan to the exact process
    # inputs that produced the governed baseline.  Without this check, an
    # operator could edit process_extensions.yaml or task_profile.yaml and
    # piggyback unrelated changes on an otherwise valid refinement plan.
    compiled_baseline = tailor_profile(profile, extension)
    if process_fingerprint(compiled_baseline) != current_fingerprint:
        raise ProjectError(translator.text("error.refine_inputs_stale"))

    plan = load_refinement_plan(Path(args.plan).resolve())
    plan_digest = refinement_plan_digest(plan)
    runtime = load_runtime(root)
    bundle_issues = project_consistency_issues(state, current_process, runtime)
    if bundle_issues:
        raise ProjectError(
            translator.text(
                "error.refine_project_inconsistent", detail=bundle_issues[0]
            )
        )
    previous = next(
        (
            item
            for item in extension.get("refinements", [])
            if isinstance(item, dict) and item.get("id") == plan["id"]
        ),
        None,
    )
    if previous is not None:
        if previous.get("plan_digest") != plan_digest:
            raise ProjectError(
                f"refinement id {plan['id']!r} is already applied with a different digest"
            )
        matching_events = [
            item
            for item in runtime.get("events", [])
            if isinstance(item, dict)
            and item.get("action") == "process_refinement_applied"
            and item.get("plan_id") == plan["id"]
        ]
        expected_replay = {
            "plan_digest": plan_digest,
            "base_process_fingerprint": plan["base_process_fingerprint"],
            "root": plan["root"],
            "children": [item["id"] for item in plan["deliverables"]],
            "result_process_fingerprint": previous.get(
                "result_process_fingerprint"
            ),
            "invalidated_gates": previous.get("invalidated_gates"),
        }
        if len(matching_events) != 1 or any(
            matching_events[0].get(field) != value
            for field, value in expected_replay.items()
        ):
            raise ProjectError(
                translator.text("error.refine_replay_inconsistent")
            )
        result = {
            "schema_version": "1.0",
            "plan_id": plan["id"],
            "plan_digest": plan_digest,
            "root": plan["root"],
            "base_process_fingerprint": plan["base_process_fingerprint"],
            "current_process_fingerprint": current_fingerprint,
            "result_process_fingerprint": current_fingerprint,
            "refinement_status": "resolved",
            "applicable": True,
            "already_applied": True,
            "applied": False,
            "blockers": [],
            "diff": {
                "added": [],
                "removed": [],
                "changed": [],
                "migrations": [],
                "ambiguous": [],
            },
            "gate_impact": [],
            "binding_impact": {
                "schema_version": "1.0",
                "eligible": True,
                "status": "passed",
                "new_concrete_children": [],
                "issues": [],
                "summary": {
                    "new_concrete_children": 0,
                    "binding_ready": 0,
                    "managed_evidence_only": 0,
                    "missing_owner": 0,
                    "conflicts": 0,
                    "errors": 0,
                    "warnings": 0,
                },
            },
        }
        if args.json:
            print(_json(result))
        else:
            print(translator.text("cli.refine.already_applied", plan=plan["id"]))
        return 0

    if plan["base_process_fingerprint"] != current_fingerprint:
        raise ProjectError(translator.text("error.refine_stale_base"))
    # Context-aware validation is deliberately after replay detection: a
    # successful plan remains an idempotent no-op against its evolved process.
    plan = load_refinement_plan(
        plan, process=current_process, extension=extension
    )
    reused_historical_ids = historical_deliverable_id_reuse(
        plan, state, current_process
    )
    if reused_historical_ids:
        raise ProjectError(
            translator.text(
                "error.refine_historical_id_reuse",
                deliverables=", ".join(reused_historical_ids),
            )
        )

    root_deliverable = next(
        (
            item
            for item in state.get("deliverables", [])
            if isinstance(item, dict) and item.get("id") == plan["root"]
        ),
        None,
    )
    if root_deliverable is None:
        raise ProjectError(f"unknown refinement root {plan['root']!r}")
    refinement = deliverable_refinement_status(state, plan["root"])
    blockers: list[dict[str, Any]] = []
    if runtime.get("active_claims"):
        blockers.append(
            {
                "code": "ACTIVE_CLAIM",
                "message": translator.text(
                    "error.refine_active_claim",
                    claims=", ".join(sorted(runtime["active_claims"])),
                ),
            }
        )
    if state.get("project", {}).get("workflow_step") == "review":
        blockers.append(
            {
                "code": "ACTIVE_REVIEW",
                "message": translator.text(
                    "error.process_active_review",
                    subject=state.get("project", {}).get(
                        "current_iteration_subject"
                    )
                    or "unknown",
                ),
            }
        )
    if root_deliverable.get("phase") != state["project"].get("phase"):
        blockers.append(
            {
                "code": "CLOSED_PHASE",
                "message": translator.text("error.refine_closed_phase"),
            }
        )
    if refinement.get("refinement_status") != "due":
        blockers.append(
            {
                "code": "REFINEMENT_TRIGGER_PENDING",
                "message": translator.text("error.refine_trigger_pending"),
            }
        )

    merged_extension, applied = merge_refinement_plan(
        extension, plan, process=current_process
    )
    if not applied:
        raise ProjectError("unexpected refinement replay state")
    candidate_process = tailor_profile(profile, merged_extension)
    diff = preview_process_diff(current_process, candidate_process)
    dependency_rewrites = historical_dependency_rewrites(diff, state)
    if dependency_rewrites:
        raise ProjectError(
            translator.text(
                "error.refine_historical_dependency_rewrite",
                deliverables=", ".join(dependency_rewrites),
            )
        )
    candidate_state = sync_state_with_process(state, candidate_process)
    existing_bindings = load_artifact_bindings(paths["bindings"])
    candidate_bindings = sync_evidence_bindings(
        existing_bindings, candidate_process
    )
    binding_impact = preview_refinement_binding_impact(
        candidate_bindings, current_process, candidate_process, diff
    )

    old_gates = {
        item["id"]: item
        for item in state.get("gates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    gate_impact: list[dict[str, Any]] = []
    invalidated_gates: list[str] = []
    for gate in candidate_state.get("gates", []):
        if not isinstance(gate, dict) or not isinstance(gate.get("id"), str):
            continue
        prior = old_gates.get(gate["id"], {})
        changed = prior.get("requirements_fingerprint") != gate.get(
            "requirements_fingerprint"
        )
        invalidated = bool(
            changed
            and prior
            and gate.get("stale") is True
            and gate.get("review_epoch", 0) > prior.get("review_epoch", 0)
        )
        if changed:
            gate_impact.append(
                {
                    "id": gate["id"],
                    "previous_requirements_fingerprint": prior.get(
                        "requirements_fingerprint"
                    ),
                    "requirements_fingerprint": gate.get(
                        "requirements_fingerprint"
                    ),
                    "previous_review_epoch": prior.get("review_epoch", 0),
                    "review_epoch": gate.get("review_epoch", 0),
                    "invalidated": invalidated,
                }
            )
        if invalidated:
            invalidated_gates.append(gate["id"])

    result_process_fingerprint = process_fingerprint(candidate_process)
    merged_extension = finalize_refinement_record(
        merged_extension,
        plan_id=plan["id"],
        result_process_fingerprint=result_process_fingerprint,
        invalidated_gates=invalidated_gates,
    )
    candidate_process = tailor_profile(profile, merged_extension)
    if process_fingerprint(candidate_process) != result_process_fingerprint:
        raise ProjectError("refinement result fingerprint is not stable")
    diff = preview_process_diff(current_process, candidate_process)

    result = {
        "schema_version": "1.0",
        "plan_id": plan["id"],
        "plan_digest": plan_digest,
        "root": plan["root"],
        "base_process_fingerprint": plan["base_process_fingerprint"],
        "current_process_fingerprint": current_fingerprint,
        "result_process_fingerprint": result_process_fingerprint,
        "refinement_status": refinement.get("refinement_status"),
        "applicable": not blockers,
        "already_applied": False,
        "applied": False,
        "blockers": blockers,
        "diff": diff,
        "gate_impact": gate_impact,
        "binding_impact": binding_impact,
    }
    if not args.apply_refinement:
        if args.json:
            print(_json(result))
        else:
            print(translator.text("cli.refine.preview_title", plan=plan["id"]))
            for field in ("added", "removed", "changed", "ambiguous"):
                print(
                    translator.text(
                        "cli.refine.preview_count",
                        field=field,
                        count=len(diff.get(field, [])),
                    )
                )
        return 0

    if blockers:
        raise ProjectError(str(blockers[0]["message"]))
    if not isinstance(args.actor, str) or not args.actor.strip():
        raise ProjectError(translator.text("error.refine_actor_required"))
    if args.actor_type != "human":
        raise ProjectError(translator.text("error.refine_actor_type"))
    if args.authorized is not True:
        raise ProjectError(translator.text("error.refine_authorized"))
    if not isinstance(args.reason, str) or not args.reason.strip():
        raise ProjectError(translator.text("error.refine_reason_required"))

    event = {
        "action": "process_refinement_applied",
        "at": format_time(utc_now()),
        "plan_id": plan["id"],
        "plan_digest": plan_digest,
        "base_process_fingerprint": plan["base_process_fingerprint"],
        "result_process_fingerprint": result["result_process_fingerprint"],
        "actor": args.actor.strip(),
        "actor_type": "human",
        "authorized": True,
        "reason": args.reason.strip(),
        "state_revision": candidate_state["revision"],
        "root": plan["root"],
        "children": [item["id"] for item in plan["deliverables"]],
        "invalidated_gates": sorted(invalidated_gates),
    }
    candidate_runtime, recorded = record_process_refinement(runtime, event)
    if not recorded:
        raise ProjectError("unexpected refinement runtime replay state")
    with project_mutation_guard(
        root,
        extra_files=(paths["extensions"], paths["process"], paths["bindings"]),
    ):
        write_state(paths["extensions"], merged_extension)
        write_state(paths["process"], candidate_process)
        write_state(paths["state"], candidate_state)
        write_state(paths["bindings"], candidate_bindings)
        save_runtime(root, candidate_runtime)
    result["applied"] = True
    if args.json:
        print(_json(result))
    else:
        print(translator.text("cli.refine.applied", plan=plan["id"]))
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
            "cli.context.current_iteration_subject",
            value=snapshot["current_iteration_subject"] or unavailable,
        )
    )
    print(
        translator.text(
            "cli.context.available_tasks",
            value=", ".join(item["id"] for item in snapshot["available_tasks"]) or none,
        )
    )
    for field, message_key in (
        ("waiting_items", "cli.context.waiting_items"),
        ("explicit_blockers", "cli.context.explicit_blockers"),
        ("governance_blockers", "cli.context.governance_blockers"),
    ):
        print(
            translator.text(
                message_key,
                value=", ".join(item["id"] for item in snapshot[field]) or none,
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


def _set_workflow_step(
    state: dict[str, Any], target: str, *, subject: str | None = None
) -> dict[str, Any]:
    """Set the next executable stage once; never synthesize skipped commands."""

    if target not in WORKFLOW_STEPS:
        raise TransitionError(f"unknown workflow step: {target!r}")
    current = state["project"]["workflow_step"]
    if target == "review":
        if not isinstance(subject, str) or not subject:
            raise TransitionError(
                "REVIEW_SUBJECT_REQUIRED: entering Review requires a canonical subject"
            )
        return bind_current_iteration_subject(state, subject)
    if current == "review":
        if target != "refresh":
            raise TransitionError(
                "REVIEW_SUBJECT_ACTIVE: Review can only complete into Refresh"
            )
        bound = state["project"].get("current_iteration_subject")
        if not isinstance(bound, str) or not bound:
            raise TransitionError(
                "REVIEW_SUBJECT_REQUIRED: cannot leave Review without a locked subject"
            )
        if subject is not None and subject != bound:
            raise TransitionError(
                f"REVIEW_SUBJECT_MISMATCH: current iteration reviews {bound!r}, not {subject!r}"
            )
        return clear_current_iteration_subject(state, bound)
    if subject is not None:
        raise TransitionError(
            "a workflow subject is only valid when entering or completing Review"
        )
    if current == target:
        return state
    updated = revised_copy(state)
    updated["project"]["workflow_step"] = target
    updated["project"]["current_iteration_subject"] = None
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
    # Surface the target's concrete artifact/refinement blocker before the
    # generic verification-freshness gate. Both checks are read-only and
    # fail-closed, but this order tells the user what must be fixed before a
    # newly refined Deliverable can ever become verifiable or claimable.
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
    state = _set_workflow_step(
        state,
        next_step,
        subject=args.deliverable if next_step == "review" else None,
    )
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
    if args.recover_subject:
        if args.actor_type != "human" or not args.authorized:
            raise TransitionError(
                translator.text("error.review_recovery_authority")
            )
        if not isinstance(args.reason, str) or not args.reason.strip():
            raise TransitionError(
                translator.text("error.review_recovery_reason_required")
            )
        if args.decision is not None or args.evidence is not None:
            raise TransitionError(
                translator.text("error.review_recovery_decision_forbidden")
            )
        if subject_type == "deliverable":
            subject_record = next(
                item
                for item in state.get("deliverables", [])
                if item.get("id") == subject_id
            )
            if subject_record.get("status") not in {
                "ready_for_review",
                "in_review",
            }:
                raise TransitionError(
                    translator.text(
                        "error.review_recovery_status",
                        subject=subject_id,
                        status=subject_record.get("status"),
                    )
                )
        else:
            _require_current_gate(state, process, subject_id, translator)
            status = _gate_status(state, subject_id)
            if status != "ready":
                raise TransitionError(
                    translator.text(
                        "error.review_recovery_status",
                        subject=subject_id,
                        status=status,
                    )
                )
        state = recover_current_iteration_subject(state, subject_id)
        details = {
            "subject_type": subject_type,
            "subject": subject_id,
            "actor": args.reviewer,
            "actor_type": "human",
            "authorized": True,
            "reason": args.reason.strip(),
            "state_revision": state["revision"],
        }
        runtime = record_event(
            runtime,
            "review_subject_recovered",
            details=details,
        )
        with project_mutation_guard(root):
            write_state(paths["state"], state)
            save_runtime(root, runtime)
        print(
            translator.text(
                "cli.review.subject_recovered", subject=args.subject
            )
        )
        return 0
    if subject_type == "deliverable":
        _require_workflow_step(
            state, {"review"}, action="review", translator=translator
        )
        state = _set_workflow_step(state, "review", subject=subject_id)
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
        state = _set_workflow_step(state, "review", subject=subject_id)
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
    state = _set_workflow_step(state, "review", subject=subject_id)
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
    state = _set_workflow_step(state, "refresh", subject=subject_id)
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
    state = _set_workflow_step(state, "refresh", subject=subject_id)
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
    with project_mutation_guard(root, include_dashboard=True):
        manifest = refresh_project(args.target)
    outputs = manifest.get("outputs", []) if isinstance(manifest, dict) else []
    print(translator.text("cli.refresh.completed", count=len(outputs) + 1))
    return 0


def _cmd_render_dashboard(args: argparse.Namespace) -> int:
    translator = _translator(args)
    root = Path(args.target).resolve()
    with project_mutation_guard(root, include_dashboard=True):
        manifest = render_project_dashboard(root)
    outputs = manifest.get("outputs", []) if isinstance(manifest, dict) else []
    print(
        translator.text(
            "cli.render_dashboard.completed", count=len(outputs) + 1
        )
    )
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
    state: dict[str, Any] | None = None
    report_issues: list[dict[str, Any]] = []
    checks = {
        "state": "not_run",
        "policy": "not_requested" if not args.policy else "not_run",
        "bindings": "not_applicable" if not project_target else "not_run",
        "governance_document": (
            "not_applicable" if not project_target else "not_run"
        ),
    }

    def add_issue(code: str, message: str, *, issue_path: str | None = None) -> None:
        issue: dict[str, Any] = {
            "severity": "error",
            "code": code,
            "message": message,
        }
        if issue_path is not None:
            issue["path"] = issue_path
        report_issues.append(issue)

    try:
        state = load_state(path)
    except (StateError, OSError, ValueError) as exc:
        checks["state"] = "failed"
        add_issue("STATE_INPUT_INVALID", str(exc), issue_path=str(path))
    else:
        state_issues = validate_state(state)
        checks["state"] = "failed" if state_issues else "passed"
        for issue in state_issues:
            add_issue(
                "STATE_VALIDATION_ERROR",
                issue.message,
                issue_path=issue.path,
            )

    if args.policy:
        try:
            load_policy(args.policy)
        except (PolicyError, OSError, ValueError) as exc:
            checks["policy"] = "failed"
            add_issue("POLICY_INVALID", str(exc), issue_path=str(args.policy))
        else:
            checks["policy"] = "passed"

    if project_target and state is not None:
        from .reconcile import ReconcileError, load_artifact_bindings

        deliverable_ids = {
            item["id"]
            for item in state.get("deliverables", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        try:
            load_artifact_bindings(
                project_paths(target)["bindings"],
                known_deliverables=deliverable_ids,
            )
        except ReconcileError as exc:
            checks["bindings"] = "failed"
            report_issues.append(exc.as_issue())
        except (OSError, ValueError) as exc:
            checks["bindings"] = "failed"
            add_issue(
                "ARTIFACT_BINDINGS_INVALID",
                str(exc),
                issue_path=str(project_paths(target)["bindings"]),
            )
        else:
            checks["bindings"] = "passed"
    elif project_target:
        checks["bindings"] = "not_run"

    if project_target and state is not None:
        paths = project_paths(target)
        if not paths["process"].is_file():
            checks["governance_document"] = "not_applicable"
        else:
            try:
                from .governance_documents import governance_document_issues

                process = load_state(paths["process"])
                governance_path = paths["dashboard"] / "governance.md"
                governance_text = (
                    governance_path.read_text(encoding="utf-8")
                    if governance_path.is_file()
                    else None
                )
                governance_issues = governance_document_issues(
                    governance_text,
                    process,
                    state,
                    translator=translator,
                    locale=translator.locale,
                )
            except (OSError, StateError, TypeError, ValueError) as exc:
                checks["governance_document"] = "failed"
                add_issue(
                    "GOVERNANCE_DOCUMENT_INPUT_INVALID",
                    str(exc),
                    issue_path=str(paths["dashboard"] / "governance.md"),
                )
            else:
                checks["governance_document"] = (
                    "failed" if governance_issues else "passed"
                )
                report_issues.extend(governance_issues)
    elif project_target:
        checks["governance_document"] = "not_run"

    if args.json:
        report = {
            "schema_version": "1.0",
            "command": "validate",
            "status": "failed" if report_issues else "passed",
            "locale": translator.locale,
            "scope": "project" if project_target else "state",
            "target": str(target),
            "state_path": str(path),
            "state_revision": state.get("revision") if state is not None else None,
            "checks": checks,
            "issues": report_issues,
        }
        print(_json(report))
        return 1 if report_issues else 0

    if report_issues:
        print(translator.text("cli.validate.invalid", path=path), file=sys.stderr)
        for issue in report_issues:
            detail = (
                f"{issue['path']}: {issue['message']}"
                if issue.get("path")
                else issue["message"]
            )
            print(translator.text("cli.validate.issue", issue=detail), file=sys.stderr)
        return 1
    assert state is not None
    print(
        translator.text(
            "cli.validate.valid", revision=state["revision"], path=path
        )
    )
    return 0


def _configure_utf8_stdio() -> None:
    """Make the console-script byte contract deterministic on every platform."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        _configure_utf8_stdio()
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

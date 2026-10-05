"""Agent runtime facts for claims, leases, and auditable command events."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from .state import StateError, write_state

RUNTIME_RELATIVE_PATH = Path(".ipd") / "agent_runtime.yaml"


class RuntimeError(ValueError):
    """Raised when an Agent runtime action violates the session protocol."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"invalid runtime timestamp {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError(f"runtime timestamp must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def create_runtime_state() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "revision": 0,
        "active_claims": {},
        "events": [],
        "last_refresh": None,
        "last_verification": None,
    }


def runtime_path(project_root: str | Path) -> Path:
    return Path(project_root) / RUNTIME_RELATIVE_PATH


def _binding_window_issues(value: Any) -> list[str]:
    """Validate the portable binding facts captured when a Claim opens."""

    if not isinstance(value, dict):
        return ["field 'binding_window' must be an object"]
    issues: list[str] = []
    if value.get("schema_version") != "1.0":
        issues.append("field 'binding_window.schema_version' must be '1.0'")
    for field in ("bindings_sha256", "snapshot_sha256"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            issues.append(
                f"field 'binding_window.{field}' must be a non-empty string"
            )
    baseline_id = value.get("baseline_id")
    if baseline_id is not None and (
        not isinstance(baseline_id, str) or not baseline_id.strip()
    ):
        issues.append(
            "field 'binding_window.baseline_id' must be a non-empty string or null"
        )
    opened_paths = value.get("opened_paths")
    if not isinstance(opened_paths, dict):
        issues.append("field 'binding_window.opened_paths' must be an object")
    else:
        for path, digest in opened_paths.items():
            if not isinstance(path, str) or not path.strip():
                issues.append(
                    "field 'binding_window.opened_paths' contains an invalid path"
                )
                continue
            if digest is not None and (
                not isinstance(digest, str) or not digest.strip()
            ):
                issues.append(
                    f"field 'binding_window.opened_paths[{path!r}]' "
                    "must be a non-empty string or null"
                )
    return issues


def claim_event_issues(
    event: Any,
    *,
    current_state_revision: int | None = None,
    require_binding_window: bool = False,
) -> list[str]:
    """Validate the fields that make a Claim event usable as provenance."""

    if not isinstance(event, dict) or event.get("action") != "claim":
        return ["must be a Claim event object"]
    issues: list[str] = []
    for field in ("deliverable", "actor", "at"):
        if not isinstance(event.get(field), str) or not event[field].strip():
            issues.append(f"field {field!r} must be a non-empty string")
    event_at = event.get("at")
    if isinstance(event_at, str) and event_at.strip():
        try:
            _parse_time(event_at)
        except RuntimeError as exc:
            issues.append(str(exc))
    state_revision = event.get("state_revision")
    if type(state_revision) is not int or state_revision < 0:
        issues.append("field 'state_revision' must be a non-negative integer")
    elif (
        current_state_revision is not None
        and state_revision > current_state_revision
    ):
        issues.append(
            "field 'state_revision' exceeds the current project revision"
        )
    if "binding_window" in event:
        issues.extend(_binding_window_issues(event.get("binding_window")))
    elif require_binding_window:
        issues.append("field 'binding_window' is required for binding provenance")
    return issues


def advance_phase_event_issues(event: Any) -> list[str]:
    """Validate the auditable fields of a Phase advancement event."""

    if not isinstance(event, dict) or event.get("action") != "advance_phase":
        return ["must be an advance_phase event object"]
    issues: list[str] = []
    for field in ("from_phase", "to_phase", "at"):
        if not isinstance(event.get(field), str) or not event[field].strip():
            issues.append(f"field {field!r} must be a non-empty string")
    event_at = event.get("at")
    if isinstance(event_at, str) and event_at.strip():
        try:
            _parse_time(event_at)
        except RuntimeError as exc:
            issues.append(str(exc))
    state_revision = event.get("state_revision")
    if type(state_revision) is not int or state_revision < 0:
        issues.append("field 'state_revision' must be a non-negative integer")
    return issues


def artifact_baseline_event_issues(event: Any) -> list[str]:
    """Validate an explicitly authorized artifact-baseline adoption event."""

    if not isinstance(event, dict) or event.get("action") != "artifact_baseline_adopted":
        return ["must be an artifact_baseline_adopted event object"]
    issues: list[str] = []
    for field in ("actor", "reason", "at", "baseline_id"):
        if not isinstance(event.get(field), str) or not event[field].strip():
            issues.append(f"field {field!r} must be a non-empty string")
    if event.get("actor_type") != "human":
        issues.append("field 'actor_type' must be 'human'")
    if event.get("authorized") is not True:
        issues.append("field 'authorized' must be true")
    state_revision = event.get("state_revision")
    if type(state_revision) is not int or state_revision < 0:
        issues.append("field 'state_revision' must be a non-negative integer")
    event_at = event.get("at")
    if isinstance(event_at, str) and event_at.strip():
        try:
            _parse_time(event_at)
        except RuntimeError as exc:
            issues.append(str(exc))
    snapshot = event.get("artifact_baseline")
    if not isinstance(snapshot, dict):
        issues.append("field 'artifact_baseline' must be an object")
    else:
        snapshot_id = snapshot.get("snapshot_sha256")
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            issues.append(
                "field 'artifact_baseline.snapshot_sha256' must be a non-empty string"
            )
        if snapshot.get("baseline_id") != event.get("baseline_id"):
            issues.append("field 'baseline_id' must match the artifact baseline")
    return issues


def process_migration_event_issues(event: Any) -> list[str]:
    """Validate one explicitly authorized process-history migration event."""

    if not isinstance(event, dict) or event.get("action") != "process_migration":
        return ["must be a process_migration event object"]
    issues: list[str] = []
    for field in ("actor", "reason", "at"):
        if not isinstance(event.get(field), str) or not event[field].strip():
            issues.append(f"field {field!r} must be a non-empty string")
    if event.get("actor_type") != "human":
        issues.append("field 'actor_type' must be 'human'")
    if event.get("authorized") is not True:
        issues.append("field 'authorized' must be true")
    state_revision = event.get("state_revision")
    if type(state_revision) is not int or state_revision < 0:
        issues.append("field 'state_revision' must be a non-negative integer")
    event_at = event.get("at")
    if isinstance(event_at, str) and event_at.strip():
        try:
            _parse_time(event_at)
        except RuntimeError as exc:
            issues.append(str(exc))
    if event.get("previous_process_schema_version") not in {"1.0", "2.0"}:
        issues.append(
            "field 'previous_process_schema_version' must be '1.0' or '2.0'"
        )
    if event.get("process_schema_version") != "2.0":
        issues.append("field 'process_schema_version' must be '2.0'")
    migrations = event.get("migrations", [])
    gate_migrations = event.get("gate_migrations", [])
    dependency_corrections = event.get("dependency_corrections", [])
    for field, values in (
        ("migrations", migrations),
        ("gate_migrations", gate_migrations),
        ("dependency_corrections", dependency_corrections),
    ):
        if not isinstance(values, list):
            issues.append(f"field {field!r} must be an array")
    if not any(
        isinstance(values, list) and values
        for values in (migrations, gate_migrations, dependency_corrections)
    ):
        issues.append(
            "at least one of 'migrations', 'gate_migrations', or "
            "'dependency_corrections' must be a non-empty array"
        )
    if not isinstance(migrations, list):
        migrations = []
    seen_migration_records: list[dict[str, Any]] = []
    seen_migration_pairs: set[tuple[str, str]] = set()
    migration_targets_by_source: dict[str, set[str]] = {}
    migration_sources_by_target: dict[str, set[str]] = {}
    migration_strategies_by_source: dict[str, set[str]] = {}
    for index, migration in enumerate(migrations):
        if not isinstance(migration, dict):
            issues.append(f"field 'migrations[{index}]' must be an object")
            continue
        if migration in seen_migration_records:
            issues.append(
                f"field 'migrations[{index}]' duplicates an earlier migration entry"
            )
        seen_migration_records.append(migration)
        expected = {"from", "to", "strategy", "reason", "preserve_history"}
        if set(migration) != expected:
            issues.append(f"field 'migrations[{index}]' has invalid fields")
        for field in ("from", "to", "reason"):
            if not isinstance(migration.get(field), str) or not migration[field].strip():
                issues.append(
                    f"field 'migrations[{index}].{field}' must be a non-empty string"
                )
        if migration.get("strategy") not in {"replace", "split"}:
            issues.append(
                f"field 'migrations[{index}].strategy' must be 'replace' or 'split'"
            )
        source = migration.get("from")
        target = migration.get("to")
        strategy = migration.get("strategy")
        if isinstance(source, str) and isinstance(target, str) and source == target:
            issues.append(
                f"field 'migrations[{index}]' must not map a Deliverable to itself"
            )
        if isinstance(source, str) and source and isinstance(target, str) and target:
            pair = (source, target)
            if pair in seen_migration_pairs:
                issues.append(
                    f"field 'migrations[{index}]' duplicates migration mapping {pair!r}"
                )
            seen_migration_pairs.add(pair)
            migration_targets_by_source.setdefault(source, set()).add(target)
            migration_sources_by_target.setdefault(target, set()).add(source)
            if isinstance(strategy, str) and strategy:
                migration_strategies_by_source.setdefault(source, set()).add(strategy)
        if migration.get("preserve_history") is not True:
            issues.append(
                f"field 'migrations[{index}].preserve_history' must be true"
            )
    for source, targets in sorted(migration_targets_by_source.items()):
        strategies = migration_strategies_by_source.get(source, set())
        if len(strategies) > 1:
            issues.append(
                f"field 'migrations' source {source!r} must use exactly one strategy"
            )
        if len(targets) > 1 and strategies != {"split"}:
            issues.append(
                f"field 'migrations' source {source!r} with multiple targets must use split"
            )
    for target, sources in sorted(migration_sources_by_target.items()):
        if len(sources) > 1:
            issues.append(
                f"field 'migrations' target {target!r} has multiple sources; merge is unsupported"
            )
    if not isinstance(gate_migrations, list):
        gate_migrations = []
    gate_sources: set[str] = set()
    gate_targets: set[str] = set()
    for index, migration in enumerate(gate_migrations):
        if not isinstance(migration, dict):
            issues.append(f"field 'gate_migrations[{index}]' must be an object")
            continue
        expected = {"from", "to", "reason", "preserve_history"}
        if set(migration) != expected:
            issues.append(f"field 'gate_migrations[{index}]' has invalid fields")
        for field in ("from", "to", "reason"):
            if not isinstance(migration.get(field), str) or not migration[field].strip():
                issues.append(
                    f"field 'gate_migrations[{index}].{field}' must be a non-empty string"
                )
        source = migration.get("from")
        target = migration.get("to")
        if isinstance(source, str) and isinstance(target, str) and source == target:
            issues.append(
                f"field 'gate_migrations[{index}]' must not map a Gate to itself"
            )
        if isinstance(source, str) and source:
            if source in gate_sources:
                issues.append(
                    f"field 'gate_migrations[{index}].from' duplicates source {source!r}"
                )
            gate_sources.add(source)
        if isinstance(target, str) and target:
            if target in gate_targets:
                issues.append(
                    f"field 'gate_migrations[{index}].to' duplicates target {target!r}"
                )
            gate_targets.add(target)
        if migration.get("preserve_history") is not True:
            issues.append(
                f"field 'gate_migrations[{index}].preserve_history' must be true"
            )
    if not isinstance(dependency_corrections, list):
        dependency_corrections = []
    corrected_deliverables: set[str] = set()
    for index, correction in enumerate(dependency_corrections):
        if not isinstance(correction, dict):
            issues.append(
                f"field 'dependency_corrections[{index}]' must be an object"
            )
            continue
        expected = {
            "deliverable",
            "before",
            "after",
            "reason",
            "preserve_history",
            "require_reapproval",
        }
        if set(correction) != expected:
            issues.append(
                f"field 'dependency_corrections[{index}]' has invalid fields"
            )
        for field in ("deliverable", "reason"):
            if not isinstance(correction.get(field), str) or not correction[field].strip():
                issues.append(
                    f"field 'dependency_corrections[{index}].{field}' must be a non-empty string"
                )
        deliverable = correction.get("deliverable")
        if isinstance(deliverable, str) and deliverable.strip():
            if deliverable in corrected_deliverables:
                issues.append(
                    f"field 'dependency_corrections[{index}].deliverable' "
                    f"{deliverable!r} must have exactly one dependency correction"
                )
            corrected_deliverables.add(deliverable)
        for field in ("before", "after"):
            values = correction.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                issues.append(
                    f"field 'dependency_corrections[{index}].{field}' must be an array of non-empty strings"
                )
            elif len(values) != len(set(values)):
                issues.append(
                    f"field 'dependency_corrections[{index}].{field}' must not contain duplicates"
                )
        before = correction.get("before")
        after = correction.get("after")
        if (
            isinstance(before, list)
            and isinstance(after, list)
            and all(isinstance(value, str) for value in before + after)
            and set(before) == set(after)
        ):
            issues.append(
                f"field 'dependency_corrections[{index}]' must change dependencies"
            )
        if correction.get("preserve_history") is not True:
            issues.append(
                f"field 'dependency_corrections[{index}].preserve_history' must be true"
            )
        if correction.get("require_reapproval") is not True:
            issues.append(
                f"field 'dependency_corrections[{index}].require_reapproval' must be true"
            )
    return issues


def process_refinement_event_issues(event: Any) -> list[str]:
    """Validate one authorized and replay-safe process refinement event."""

    if not isinstance(event, dict) or event.get("action") != "process_refinement_applied":
        return ["must be a process_refinement_applied event object"]
    expected = {
        "action",
        "at",
        "plan_id",
        "plan_digest",
        "base_process_fingerprint",
        "result_process_fingerprint",
        "actor",
        "actor_type",
        "authorized",
        "reason",
        "state_revision",
        "root",
        "children",
        "invalidated_gates",
    }
    issues: list[str] = []
    missing = sorted(expected - set(event))
    unknown = sorted(set(event) - expected)
    for field in missing:
        issues.append(f"field {field!r} is required")
    for field in unknown:
        issues.append(f"field {field!r} is not allowed")
    for field in (
        "at",
        "plan_id",
        "plan_digest",
        "base_process_fingerprint",
        "result_process_fingerprint",
        "actor",
        "reason",
        "root",
    ):
        if not isinstance(event.get(field), str) or not event[field].strip():
            issues.append(f"field {field!r} must be a non-empty string")
    for field in (
        "plan_digest",
        "base_process_fingerprint",
        "result_process_fingerprint",
    ):
        value = event.get(field)
        if isinstance(value, str) and not re.fullmatch(
            r"sha256:[0-9a-f]{64}", value
        ):
            issues.append(
                f"field {field!r} must use sha256:<64 lowercase hex>"
            )
    event_at = event.get("at")
    if isinstance(event_at, str) and event_at.strip():
        try:
            _parse_time(event_at)
        except RuntimeError as exc:
            issues.append(str(exc))
    if event.get("actor_type") != "human":
        issues.append("field 'actor_type' must be 'human'")
    if event.get("authorized") is not True:
        issues.append("field 'authorized' must be true")
    state_revision = event.get("state_revision")
    if type(state_revision) is not int or state_revision < 0:
        issues.append("field 'state_revision' must be a non-negative integer")
    for field, allow_empty in (("children", False), ("invalidated_gates", True)):
        values = event.get(field)
        if not isinstance(values, list):
            issues.append(f"field {field!r} must be an array")
            continue
        if not allow_empty and not values:
            issues.append(f"field {field!r} must not be empty")
        parsed = [item for item in values if isinstance(item, str) and item.strip()]
        if len(parsed) != len(values):
            issues.append(f"field {field!r} must contain only non-empty strings")
        if len(set(parsed)) != len(parsed):
            issues.append(f"field {field!r} must not contain duplicates")
    if event.get("root") in (event.get("children") or []):
        issues.append("field 'children' must not contain the refinement root")
    return issues


def validate_runtime(runtime: Any) -> list[str]:
    """Validate the packaged runtime contract without external dependencies."""

    if not isinstance(runtime, dict):
        return ["Agent runtime root must be an object"]
    issues: list[str] = []
    required = {
        "schema_version",
        "revision",
        "active_claims",
        "events",
        "last_refresh",
        "last_verification",
    }
    for field in sorted(required - set(runtime)):
        issues.append(f"Agent runtime field {field!r} is missing")
    for field in sorted(set(runtime) - required):
        issues.append(f"Agent runtime field {field!r} is unknown")
    if runtime.get("schema_version") != "1.0":
        issues.append("unsupported Agent runtime schema")
    revision = runtime.get("revision")
    if type(revision) is not int or revision < 0:
        issues.append("runtime revision must be a non-negative integer")
    claims = runtime.get("active_claims")
    if not isinstance(claims, dict):
        issues.append("runtime active_claims must be an object")
    else:
        expected_fields = {"deliverable", "actor", "started_at", "expires_at"}
        for identifier, claim_record in claims.items():
            if not isinstance(identifier, str) or not identifier:
                issues.append("runtime claim IDs must be non-empty strings")
                continue
            if not isinstance(claim_record, dict):
                issues.append(f"runtime claim {identifier!r} must be an object")
                continue
            if set(claim_record) != expected_fields:
                issues.append(f"runtime claim {identifier!r} has invalid fields")
            if claim_record.get("deliverable") != identifier:
                issues.append(f"runtime claim {identifier!r} has a mismatched deliverable")
            for field in ("actor", "started_at", "expires_at"):
                if not isinstance(claim_record.get(field), str) or not claim_record[field].strip():
                    issues.append(
                        f"runtime claim {identifier!r} field {field!r} must be a non-empty string"
                    )
            started_at = claim_record.get("started_at")
            expires_at = claim_record.get("expires_at")
            if isinstance(started_at, str) and started_at.strip():
                try:
                    parsed_started = _parse_time(started_at)
                except RuntimeError as exc:
                    issues.append(f"runtime claim {identifier!r}: {exc}")
                    parsed_started = None
            else:
                parsed_started = None
            if isinstance(expires_at, str) and expires_at.strip():
                try:
                    parsed_expires = _parse_time(expires_at)
                except RuntimeError as exc:
                    issues.append(f"runtime claim {identifier!r}: {exc}")
                    parsed_expires = None
            else:
                parsed_expires = None
            if (
                parsed_started is not None
                and parsed_expires is not None
                and parsed_expires <= parsed_started
            ):
                issues.append(
                    f"runtime claim {identifier!r} expires_at must be after started_at"
                )
    events = runtime.get("events")
    if not isinstance(events, list):
        issues.append("runtime events must be an array")
    else:
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                issues.append(f"runtime event {index} must be an object")
                continue
            for field in ("action", "at"):
                if not isinstance(event.get(field), str) or not event[field].strip():
                    issues.append(
                        f"runtime event {index} field {field!r} must be a non-empty string"
                    )
            if event.get("action") == "claim":
                issues.extend(
                    f"runtime event {index} {issue}"
                    for issue in claim_event_issues(event)
                )
            elif event.get("action") == "advance_phase":
                issues.extend(
                    f"runtime event {index} {issue}"
                    for issue in advance_phase_event_issues(event)
                )
            elif event.get("action") == "artifact_baseline_adopted":
                issues.extend(
                    f"runtime event {index} {issue}"
                    for issue in artifact_baseline_event_issues(event)
                )
            elif event.get("action") == "process_migration":
                issues.extend(
                    f"runtime event {index} {issue}"
                    for issue in process_migration_event_issues(event)
                )
            elif event.get("action") == "process_refinement_applied":
                issues.extend(
                    f"runtime event {index} {issue}"
                    for issue in process_refinement_event_issues(event)
                )
            else:
                event_at = event.get("at")
                if isinstance(event_at, str) and event_at.strip():
                    try:
                        _parse_time(event_at)
                    except RuntimeError as exc:
                        issues.append(f"runtime event {index}: {exc}")
    for field in ("last_refresh", "last_verification"):
        if runtime.get(field) is not None and not isinstance(runtime.get(field), dict):
            issues.append(f"runtime {field} must be an object or null")
    return sorted(set(issues))


def load_runtime(project_root: str | Path) -> dict[str, Any]:
    path = runtime_path(project_root)
    if not path.exists():
        return create_runtime_state()
    from .state import load_state

    value = load_state(path)
    issues = validate_runtime(value)
    if issues:
        raise RuntimeError(issues[0])
    return value


def save_runtime(project_root: str | Path, runtime: dict[str, Any]) -> None:
    issues = validate_runtime(runtime)
    if issues:
        raise RuntimeError(issues[0])
    try:
        write_state(runtime_path(project_root), runtime)
    except StateError as exc:
        raise RuntimeError(str(exc)) from exc


def _revised(runtime: dict[str, Any]) -> dict[str, Any]:
    issues = validate_runtime(runtime)
    if issues:
        raise RuntimeError(issues[0])
    updated = deepcopy(runtime)
    revision = updated.get("revision", 0)
    if type(revision) is not int or revision < 0:
        raise RuntimeError("runtime revision must be a non-negative integer")
    updated["revision"] = revision + 1
    return updated


def _expire_claims(runtime: dict[str, Any], now: datetime) -> None:
    for deliverable_id, claim in list(runtime["active_claims"].items()):
        expires_at = claim.get("expires_at")
        if not isinstance(expires_at, str):
            raise RuntimeError(
                f"runtime claim {deliverable_id!r} expires_at must be a string"
            )
        parsed = _parse_time(expires_at)
        if parsed <= now:
            runtime["events"].append(
                {
                    "action": "claim_expired",
                    "deliverable": deliverable_id,
                    "actor": claim.get("actor"),
                    "at": format_time(now),
                }
            )
            del runtime["active_claims"][deliverable_id]


def expire_claims(
    runtime: dict[str, Any], *, now: datetime | None = None
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Remove expired leases and return their IDs with auditable events.

    A no-op returns the original object without changing its revision. Callers
    can use the expired IDs to recover matching ``in_progress`` deliverables.
    """

    instant = now or utc_now()
    issues = validate_runtime(runtime)
    if issues:
        raise RuntimeError(issues[0])
    candidate = deepcopy(runtime)
    before = set(candidate.get("active_claims", {}))
    _expire_claims(candidate, instant)
    expired = tuple(sorted(before - set(candidate.get("active_claims", {}))))
    if not expired:
        return runtime, ()
    revision = candidate.get("revision", 0)
    if type(revision) is not int or revision < 0:
        raise RuntimeError("runtime revision must be a non-negative integer")
    candidate["revision"] = revision + 1
    return candidate, expired


def claim(
    runtime: dict[str, Any],
    deliverable_id: str,
    *,
    actor: str,
    lease_minutes: int = 240,
    state_revision: int,
    binding_window: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not actor.strip():
        raise RuntimeError("claim actor must not be empty")
    if lease_minutes <= 0:
        raise RuntimeError("lease_minutes must be positive")
    if type(state_revision) is not int or state_revision < 0:
        raise RuntimeError("claim state_revision must be a non-negative integer")
    if binding_window is not None:
        window_issues = _binding_window_issues(binding_window)
        if window_issues:
            raise RuntimeError(window_issues[0])
    instant = now or utc_now()
    updated = _revised(runtime)
    _expire_claims(updated, instant)
    existing = updated["active_claims"].get(deliverable_id)
    if existing and existing.get("actor") != actor:
        raise RuntimeError(
            f"deliverable {deliverable_id!r} is already claimed by {existing.get('actor')!r}"
        )
    claim_record = {
        "deliverable": deliverable_id,
        "actor": actor,
        "started_at": format_time(instant),
        "expires_at": format_time(instant + timedelta(minutes=lease_minutes)),
    }
    updated["active_claims"][deliverable_id] = claim_record
    event = {
        "action": "claim",
        "deliverable": deliverable_id,
        "actor": actor,
        "at": claim_record["started_at"],
    }
    event["state_revision"] = state_revision
    if binding_window is not None:
        event["binding_window"] = deepcopy(binding_window)
    updated["events"].append(event)
    return updated


def close_claim(
    runtime: dict[str, Any],
    deliverable_id: str,
    *,
    actor: str,
    action: str,
    details: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    updated = _revised(runtime)
    instant = now or utc_now()
    _expire_claims(updated, instant)
    claim_record = updated["active_claims"].get(deliverable_id)
    if claim_record is None:
        raise RuntimeError(
            f"deliverable {deliverable_id!r} has no active claim lease; claim or recover it before close"
        )
    if claim_record.get("actor") != actor:
        raise RuntimeError(
            f"deliverable {deliverable_id!r} is claimed by {claim_record.get('actor')!r}"
        )
    updated["active_claims"].pop(deliverable_id, None)
    event = {
        "action": action,
        "deliverable": deliverable_id,
        "actor": actor,
        "at": format_time(instant),
    }
    if details:
        for key, value in details.items():
            if key not in event:
                event[key] = deepcopy(value)
    updated["events"].append(event)
    return updated


def record_event(
    runtime: dict[str, Any], action: str, *, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    updated = _revised(runtime)
    event = {"action": action, "at": format_time(utc_now())}
    if details:
        event.update(details)
    updated["events"].append(event)
    return updated


def record_artifact_baseline_adoption(
    runtime: dict[str, Any], event: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Append one adoption event, or return the exact runtime for a no-op.

    Snapshot equality, not actor metadata or timestamp, defines idempotency.
    The latest successful verification is also a baseline authority, so
    adopting that exact snapshot does not manufacture a redundant event.
    """

    issues = validate_runtime(runtime)
    if issues:
        raise RuntimeError(issues[0])
    event_issues = artifact_baseline_event_issues(event)
    if event_issues:
        raise RuntimeError(event_issues[0])
    snapshot = event["artifact_baseline"]
    known_snapshots: list[dict[str, Any]] = []
    verification = runtime.get("last_verification")
    if isinstance(verification, dict) and isinstance(
        verification.get("artifact_baseline"), dict
    ):
        known_snapshots.append(verification["artifact_baseline"])
    known_snapshots.extend(
        item["artifact_baseline"]
        for item in runtime.get("events", [])
        if isinstance(item, dict)
        and item.get("action") == "artifact_baseline_adopted"
        and isinstance(item.get("artifact_baseline"), dict)
    )
    if any(candidate == snapshot for candidate in known_snapshots):
        return runtime, False
    updated = _revised(runtime)
    updated["events"].append(deepcopy(event))
    return updated, True


def record_process_refinement(
    runtime: dict[str, Any], event: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Append an authorized refinement exactly once.

    A replay of the same plan digest against the same base process is a no-op.
    Reusing a plan ID for changed content or another base is a governance
    conflict and therefore fails closed.
    """

    issues = validate_runtime(runtime)
    if issues:
        raise RuntimeError(issues[0])
    event_issues = process_refinement_event_issues(event)
    if event_issues:
        raise RuntimeError(event_issues[0])
    for existing in runtime.get("events", []):
        if not isinstance(existing, dict):
            continue
        if existing.get("action") != "process_refinement_applied":
            continue
        if existing.get("plan_id") != event["plan_id"]:
            continue
        replay_fields = (
            "plan_digest",
            "base_process_fingerprint",
            "result_process_fingerprint",
            "actor",
            "actor_type",
            "authorized",
            "reason",
            "state_revision",
            "root",
            "children",
            "invalidated_gates",
        )
        if all(existing.get(field) == event.get(field) for field in replay_fields):
            return runtime, False
        raise RuntimeError(
            f"process refinement plan {event['plan_id']!r} conflicts with an "
            "already applied result, authority, or process contract"
        )
    updated = _revised(runtime)
    updated["events"].append(deepcopy(event))
    return updated, True

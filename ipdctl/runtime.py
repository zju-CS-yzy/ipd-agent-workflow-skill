"""Agent runtime facts for claims, leases, and auditable command events."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
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


def claim_event_issues(
    event: Any, *, current_state_revision: int | None = None
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
) -> dict[str, Any]:
    if not actor.strip():
        raise RuntimeError("claim actor must not be empty")
    if lease_minutes <= 0:
        raise RuntimeError("lease_minutes must be positive")
    if type(state_revision) is not int or state_revision < 0:
        raise RuntimeError("claim state_revision must be a non-negative integer")
    now = utc_now()
    updated = _revised(runtime)
    _expire_claims(updated, now)
    existing = updated["active_claims"].get(deliverable_id)
    if existing and existing.get("actor") != actor:
        raise RuntimeError(
            f"deliverable {deliverable_id!r} is already claimed by {existing.get('actor')!r}"
        )
    claim_record = {
        "deliverable": deliverable_id,
        "actor": actor,
        "started_at": format_time(now),
        "expires_at": format_time(now + timedelta(minutes=lease_minutes)),
    }
    updated["active_claims"][deliverable_id] = claim_record
    event = {
        "action": "claim",
        "deliverable": deliverable_id,
        "actor": actor,
        "at": claim_record["started_at"],
    }
    event["state_revision"] = state_revision
    updated["events"].append(event)
    return updated


def close_claim(
    runtime: dict[str, Any],
    deliverable_id: str,
    *,
    actor: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = _revised(runtime)
    now = utc_now()
    _expire_claims(updated, now)
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
        "at": format_time(now),
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

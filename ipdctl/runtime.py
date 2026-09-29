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


def load_runtime(project_root: str | Path) -> dict[str, Any]:
    path = runtime_path(project_root)
    if not path.exists():
        return create_runtime_state()
    from .state import load_state

    value = load_state(path)
    if value.get("schema_version") != "1.0":
        raise RuntimeError("unsupported Agent runtime schema")
    if not isinstance(value.get("active_claims"), dict) or not isinstance(
        value.get("events"), list
    ):
        raise RuntimeError("invalid Agent runtime structure")
    return value


def save_runtime(project_root: str | Path, runtime: dict[str, Any]) -> None:
    try:
        write_state(runtime_path(project_root), runtime)
    except StateError as exc:
        raise RuntimeError(str(exc)) from exc


def _revised(runtime: dict[str, Any]) -> dict[str, Any]:
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
            continue
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            continue
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


def claim(
    runtime: dict[str, Any],
    deliverable_id: str,
    *,
    actor: str,
    lease_minutes: int = 240,
) -> dict[str, Any]:
    if not actor.strip():
        raise RuntimeError("claim actor must not be empty")
    if lease_minutes <= 0:
        raise RuntimeError("lease_minutes must be positive")
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
    updated["events"].append(
        {
            "action": "claim",
            "deliverable": deliverable_id,
            "actor": actor,
            "at": claim_record["started_at"],
        }
    )
    return updated


def close_claim(
    runtime: dict[str, Any], deliverable_id: str, *, actor: str, action: str
) -> dict[str, Any]:
    updated = _revised(runtime)
    claim_record = updated["active_claims"].get(deliverable_id)
    if claim_record and claim_record.get("actor") not in {actor, None}:
        raise RuntimeError(
            f"deliverable {deliverable_id!r} is claimed by {claim_record.get('actor')!r}"
        )
    updated["active_claims"].pop(deliverable_id, None)
    updated["events"].append(
        {
            "action": action,
            "deliverable": deliverable_id,
            "actor": actor,
            "at": format_time(utc_now()),
        }
    )
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

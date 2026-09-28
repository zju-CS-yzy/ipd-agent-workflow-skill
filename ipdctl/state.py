"""Project-state creation and atomic persistence."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .model import SCHEMA_VERSION

DEFAULT_STATE_RELATIVE_PATH = Path(".ipd") / "project-state.json"


class StateError(ValueError):
    """Raised when a state file cannot be read or safely written."""


def create_initial_state(project_name: str) -> dict[str, Any]:
    """Create a deterministic, empty project state."""

    name = project_name.strip()
    if not name:
        raise StateError("project name must not be empty")
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "project": {
            "name": name,
            "phase": "concept",
            "workflow_step": "context",
        },
        "claims": [],
        "deliverables": [],
        "gates": [],
        "traceability": [],
    }


def resolve_state_path(target: str | Path = ".") -> Path:
    """Resolve a repository/directory argument or an explicit JSON state path."""

    path = Path(target)
    if path.suffix.lower() == ".json" or (path.exists() and path.is_file()):
        return path
    return path / DEFAULT_STATE_RELATIVE_PATH


def load_state(path: str | Path) -> dict[str, Any]:
    """Load a state object and provide stable, user-facing errors."""

    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateError(f"state file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise StateError(
            f"invalid JSON in {source} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise StateError(f"cannot read state file {source}: {exc}") from exc

    if not isinstance(value, dict):
        raise StateError(f"state root must be an object: {source}")
    return value


def write_state(path: str | Path, state: dict[str, Any]) -> None:
    """Atomically write state without leaving a temporary file behind."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, destination)
    except OSError as exc:
        raise StateError(f"cannot write state file {destination}: {exc}") from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def revised_copy(state: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with its revision incremented once."""

    updated = deepcopy(state)
    revision = updated.get("revision")
    if type(revision) is not int or revision < 0:
        raise StateError("revision must be a non-negative integer")
    updated["revision"] = revision + 1
    return updated

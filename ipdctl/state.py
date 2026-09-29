"""Project-state creation and atomic persistence."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .model import SCHEMA_VERSION

DEFAULT_STATE_RELATIVE_PATH = Path(".ipd") / "project_state.yaml"
LEGACY_STATE_RELATIVE_PATH = Path(".ipd") / "project-state.json"


class StateError(ValueError):
    """Raised when a state file cannot be read or safely written."""


def create_initial_state(
    project_name: str, task_types: list[str] | tuple[str, ...] | None = None
) -> dict[str, Any]:
    """Create a deterministic, empty project state."""

    name = project_name.strip()
    if not name:
        raise StateError("project name must not be empty")
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "project": {
            "name": name,
            "task_types": list(task_types or ["software"]),
            "phase": "concept",
            "workflow_step": "context",
            "current_tr": None,
            "current_dcp": None,
            "current_gate": None,
        },
        "claims": [],
        "deliverables": [],
        "gates": [],
        "traceability": [],
    }


def resolve_state_path(target: str | Path = ".") -> Path:
    """Resolve a project directory or an explicit JSON/YAML state path.

    New projects use ``.ipd/project_state.yaml``.  The v0.1 JSON location is
    still discovered for read/validation compatibility, but new writes never
    create both formats.
    """

    path = Path(target)
    if path.suffix.lower() in {".json", ".yaml", ".yml"} or (
        path.exists() and path.is_file()
    ):
        return path
    preferred = path / DEFAULT_STATE_RELATIVE_PATH
    legacy = path / LEGACY_STATE_RELATIVE_PATH
    if preferred.exists() or not legacy.exists():
        return preferred
    return legacy


def load_state(path: str | Path) -> dict[str, Any]:
    """Load a state object and provide stable, user-facing errors."""

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".json":
            value = json.loads(text)
        else:
            value = yaml.safe_load(text)
    except FileNotFoundError as exc:
        raise StateError(f"state file does not exist: {source}") from exc
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        line = getattr(exc, "lineno", None)
        column = getattr(exc, "colno", None)
        if line is None and getattr(exc, "problem_mark", None) is not None:
            line = exc.problem_mark.line + 1
            column = exc.problem_mark.column + 1
        raise StateError(
            f"invalid state data in {source}"
            + (f" at line {line}, column {column}" if line is not None else "")
            + f": {getattr(exc, 'msg', str(exc))}"
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
    if destination.suffix.lower() == ".json":
        payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    else:
        payload = yaml.safe_dump(
            state,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
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

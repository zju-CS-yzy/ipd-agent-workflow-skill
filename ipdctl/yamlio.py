"""Safe, deterministic YAML persistence helpers.

The workflow keeps authored inputs and generated process definitions in YAML.
All writes are completed through a same-directory temporary file so readers
never observe a partially written document.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


class YamlError(ValueError):
    """Raised when a YAML document cannot be read or safely written."""


def load_yaml(path: str | Path) -> Any:
    """Safely load one YAML document from *path*.

    ``yaml.safe_load`` deliberately rejects Python-specific constructors.  An
    empty document is returned as ``None`` so callers can report the contract
    that applies to their particular artifact.
    """

    source = Path(path)
    try:
        return yaml.safe_load(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise YamlError(f"YAML file does not exist: {source}") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = (
            f" at line {mark.line + 1}, column {mark.column + 1}"
            if mark is not None
            else ""
        )
        problem = getattr(exc, "problem", None) or str(exc)
        raise YamlError(f"invalid YAML in {source}{location}: {problem}") from exc
    except OSError as exc:
        raise YamlError(f"cannot read YAML file {source}: {exc}") from exc


def dump_yaml(value: Any) -> str:
    """Serialize *value* using the portable safe YAML representation."""

    return yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def write_yaml_atomic(path: str | Path, value: Any) -> None:
    """Atomically replace *path* with a deterministic YAML document."""

    destination = Path(path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise YamlError(f"cannot create YAML directory {destination.parent}: {exc}") from exc

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(dump_yaml(value))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, destination)
    except OSError as exc:
        raise YamlError(f"cannot write YAML file {destination}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


# Short aliases keep integration code readable while retaining an explicit
# atomic primitive for callers that want to emphasize persistence semantics.
read_yaml = load_yaml
write_yaml = write_yaml_atomic


__all__ = [
    "YamlError",
    "dump_yaml",
    "load_yaml",
    "read_yaml",
    "write_yaml",
    "write_yaml_atomic",
]

"""Reconcile local repository changes with IPD deliverable bindings."""

from __future__ import annotations

import fnmatch
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .repository import changed_paths


class ReconcileError(ValueError):
    """Raised when an artifact-binding contract cannot be loaded safely."""


_MANDATORY_IGNORES = (
    ".git/**",
    ".svn/**",
    ".ipd/dashboard/**",
    ".ipd/reconcile_report.json",
)

DEFAULT_ARTIFACT_BINDINGS: dict[str, Any] = {
    "schema_version": "1.0",
    "description": "Project paths mapped to IPD deliverables",
    "ignore": [*_MANDATORY_IGNORES],
    "critical_roots": [
        "src/**",
        "software/**",
        "firmware/**",
        "hardware/**",
        "algorithms/**",
        "tests/**",
        "docs/**",
        "config/**",
        "tools/**",
    ],
    "bindings": [],
}


def default_artifact_bindings() -> dict[str, Any]:
    """Return an independent copy of the default bindings contract."""

    return deepcopy(DEFAULT_ARTIFACT_BINDINGS)


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ReconcileError(f"artifact bindings field '{field}' must be a string list")
    return list(value)


def load_artifact_bindings(path: str | Path | None) -> dict[str, Any]:
    """Load and normalize a YAML/JSON artifact-binding contract.

    A missing path intentionally yields the default empty contract so a new
    project can still be reconciled and receive explicit unbound-path issues.
    """

    if path is None:
        return default_artifact_bindings()
    source = Path(path)
    if not source.exists():
        return default_artifact_bindings()
    try:
        value = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ReconcileError(f"cannot load artifact bindings {source}: {exc}") from exc
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ReconcileError(f"artifact bindings root must be an object: {source}")

    data = dict(value)
    if "bindings" not in data and "artifact_bindings" in data:
        data["bindings"] = data.pop("artifact_bindings")
    bindings = data.get("bindings", [])
    if not isinstance(bindings, list) or any(
        not isinstance(item, Mapping) for item in bindings
    ):
        raise ReconcileError("artifact bindings field 'bindings' must be an object list")

    ignore = _string_list(
        data.get("ignore", DEFAULT_ARTIFACT_BINDINGS["ignore"]), "ignore"
    )
    for pattern in _MANDATORY_IGNORES:
        if pattern not in ignore:
            ignore.append(pattern)
    data["schema_version"] = str(data.get("schema_version") or "1.0")
    data["ignore"] = ignore
    data["critical_roots"] = _string_list(
        data.get("critical_roots", DEFAULT_ARTIFACT_BINDINGS["critical_roots"]),
        "critical_roots",
    )
    data["bindings"] = [dict(item) for item in bindings]
    return data


# Short alias retained for projects migrating from the v1.4 runtime scripts.
load_bindings = load_artifact_bindings


def normalize_relative_path(path: str | Path) -> str:
    value = str(path).replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def path_matches(path: str, pattern: str) -> bool:
    """Match normalized project paths, including directory-wide ``/**``."""

    normalized_path = normalize_relative_path(path)
    normalized_pattern = normalize_relative_path(pattern)
    if fnmatch.fnmatchcase(normalized_path, normalized_pattern):
        return True
    try:
        if PurePosixPath(normalized_path).match(normalized_pattern):
            return True
    except ValueError:
        pass
    if normalized_pattern.endswith("/**"):
        prefix = normalized_pattern[:-3].rstrip("/")
        return normalized_path == prefix or normalized_path.startswith(prefix + "/")
    return False


def _rule_patterns(rule: Mapping[str, Any]) -> list[str]:
    value = rule.get("glob") or rule.get("globs") or rule.get("paths") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _rule_deliverables(rule: Mapping[str, Any]) -> list[str]:
    value = rule.get("deliverable") or rule.get("deliverables") or []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({str(item) for item in value if str(item).strip()})


def map_paths_to_deliverables(
    paths: Sequence[str], bindings: Mapping[str, Any]
) -> dict[str, Any]:
    """Map paths through explicit binding rules without inferring ownership."""

    result: dict[str, Any] = {
        "paths": {},
        "deliverables": {},
        "unbound": [],
        "ignored": [],
    }
    ignore_patterns = [str(item) for item in bindings.get("ignore", [])]
    rules = [
        item for item in bindings.get("bindings", []) if isinstance(item, Mapping)
    ]
    normalized_paths = sorted(
        {
            normalize_relative_path(path)
            for path in paths
            if normalize_relative_path(path)
        }
    )
    for path in normalized_paths:
        if any(path_matches(path, pattern) for pattern in ignore_patterns):
            result["ignored"].append(path)
            continue

        matched: list[dict[str, Any]] = []
        for rule in rules:
            if not any(path_matches(path, pattern) for pattern in _rule_patterns(rule)):
                continue
            deliverables = _rule_deliverables(rule)
            if not deliverables:
                continue
            matched.append(
                {
                    "rule_id": rule.get("id"),
                    "deliverables": deliverables,
                    "critical": bool(rule.get("critical", True)),
                    "review_required": rule.get("review_required"),
                    "description": rule.get("description"),
                }
            )

        if not matched:
            result["paths"][path] = []
            result["unbound"].append(path)
            continue

        result["paths"][path] = matched
        deliverable_ids = sorted(
            {
                deliverable
                for rule_match in matched
                for deliverable in rule_match["deliverables"]
            }
        )
        for deliverable_id in deliverable_ids:
            result["deliverables"].setdefault(deliverable_id, []).append(path)
    return result


def is_critical_path(path: str, bindings: Mapping[str, Any]) -> bool:
    return any(
        path_matches(path, str(pattern))
        for pattern in bindings.get("critical_roots", [])
    )


def _deliverable_ids(state: Mapping[str, Any]) -> set[str]:
    rows = state.get("deliverables", [])
    if not isinstance(rows, list):
        return set()
    return {
        str(row["id"])
        for row in rows
        if isinstance(row, Mapping) and row.get("id") is not None
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def reconcile_project(
    project_root: str | Path,
    state: Mapping[str, Any],
    bindings_path: str | Path | None = None,
    write: bool = True,
    *,
    staged: bool = False,
    base: str | None = None,
) -> dict[str, Any]:
    """Reconcile local changes with deliverables and optionally persist a report."""

    if not isinstance(state, Mapping):
        raise ReconcileError("project state must be an object")
    root = Path(project_root).resolve()
    source = (
        Path(bindings_path)
        if bindings_path is not None
        else root / ".ipd" / "artifact_bindings.yaml"
    )
    if bindings_path is not None and not source.is_absolute():
        source = root / source
    bindings = load_artifact_bindings(source)
    _, paths = changed_paths(root, staged=staged, base=base)
    mapping = map_paths_to_deliverables(paths, bindings)

    issues: list[dict[str, Any]] = []
    for path in mapping["unbound"]:
        severity = "error" if is_critical_path(path, bindings) else "warning"
        issues.append(
            {
                "severity": severity,
                "code": "UNBOUND_CHANGED_PATH",
                "path": path,
                "message": "Changed path is not bound to an IPD deliverable",
            }
        )

    known_deliverables = _deliverable_ids(state)
    for deliverable_id, bound_paths in mapping["deliverables"].items():
        if deliverable_id not in known_deliverables:
            issues.append(
                {
                    "severity": "error",
                    "code": "BINDING_UNKNOWN_DELIVERABLE",
                    "deliverable_id": deliverable_id,
                    "paths": bound_paths,
                    "message": "Binding references a deliverable absent from project state",
                }
            )

    summary = {
        "changed_paths": len(paths),
        "mapped_paths": sum(
            1 for matches in mapping["paths"].values() if matches
        ),
        "ignored_paths": len(mapping["ignored"]),
        "unbound_paths": len(mapping["unbound"]),
        "deliverables_touched": len(mapping["deliverables"]),
        "errors": sum(1 for issue in issues if issue["severity"] == "error"),
        "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
    }
    status = (
        "failed"
        if summary["errors"]
        else "warning"
        if summary["warnings"]
        else "passed"
    )
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "changed_paths": paths,
        "mapping": mapping,
        "issues": issues,
        "summary": summary,
    }
    if write:
        _write_report(root / ".ipd" / "reconcile_report.json", report)
    return report

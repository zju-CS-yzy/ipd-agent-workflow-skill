"""Read-only, portable file navigation derived from explicit IPD bindings."""
from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

from .reconcile import path_matches, validate_artifact_bindings


def _reparse(path: Path) -> bool:
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
    )


def _local_path(value: str) -> str | None:
    value = value.replace("\\", "/")
    parts = value.split("/")
    if not value or value.startswith("/") or ":" in value or any(
        part in {"", ".", ".."} or any(ord(c) < 32 for c in part) for part in parts
    ):
        return None
    return PurePosixPath(value).as_posix()


def _files(root: Path) -> list[str]:
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if d != ".git" and not _reparse(base / d)
                         and (base / d).relative_to(root).as_posix()
                         not in {".ipd/dashboard", ".ipd/generated"})
        for name in sorted(files):
            path = base / name
            if name != '.git' and not _reparse(path):
                result.append(path.relative_to(root).as_posix())
    return sorted(result)


def project_file_navigation(
    root: Path, deliverables: list[dict[str, Any]], bindings: Mapping[str, Any] | None
) -> None:
    """Attach file metadata without reading contents or following filesystem links."""
    root = root.resolve()
    inventory = _files(root)
    existing = set(inventory)
    contract = validate_artifact_bindings(bindings) if bindings is not None else {}
    ignored = contract.get('ignore', [])
    bound_inventory = [p for p in inventory if not any(path_matches(p, mask) for mask in ignored)]

    def reference(value: str) -> dict[str, Any]:
        try:
            parsed = urlsplit(value)
        except ValueError:
            parsed = urlsplit('')
        if parsed.scheme.lower() in {"http", "https"} and parsed.hostname:
            return {"path": value, "exists": None, "external": True,
                    "href": value if not any(ord(c) < 32 for c in value) else None}
        path = _local_path(value)
        present = path in existing if path else False
        return {"path": path or value, "exists": present, "external": False,
                "href": "../../" + quote(path, safe="/") if present else None}

    for item in deliverables:
        groups: dict[str, dict[str, Any]] = {"owned_files": {}, "shared_files": {}}
        rules = []
        for rule in contract.get("bindings", []):
            owners = rule.get("deliverables", [rule.get("deliverable")])
            if item["id"] not in owners:
                continue
            patterns = rule.get("paths", rule.get("globs", [rule.get("glob")]))
            patterns = [p for p in patterns if isinstance(p, str)]
            role = "shared_evidence" if rule.get("role") == "shared_evidence" else "owner"
            rules.append({"id": rule["id"], "role": role, "patterns": sorted(patterns)})
            group = groups["shared_files" if role == "shared_evidence" else "owned_files"]
            for pattern in patterns:
                matches = [p for p in bound_inventory if path_matches(p, pattern)]
                if not matches and not any(c in pattern for c in "*?["):
                    matches = [] if any(path_matches(pattern, mask) for mask in ignored) else [pattern]
                for path in matches:
                    group[path] = reference(path)
        item.update({key: [value[p] for p in sorted(value)] for key, value in groups.items()})
        item["file_binding_rules"] = sorted(rules, key=lambda r: r["id"])
        item["evidence_files"] = [reference(p) for p in item.get("evidence", [])]

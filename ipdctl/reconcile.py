"""Reconcile local repository changes with IPD deliverable bindings."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .repository import changed_paths, inspect_repository
from .runtime import artifact_baseline_event_issues, claim_event_issues


class ReconcileError(ValueError):
    """Raised when an artifact-binding contract cannot be loaded safely."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ARTIFACT_BINDINGS_INVALID",
        path: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.details = dict(details or {})

    def as_issue(self) -> dict[str, Any]:
        issue: dict[str, Any] = {
            "severity": "error",
            "code": self.code,
            "message": str(self),
        }
        if self.path is not None:
            issue["path"] = self.path
        issue.update(self.details)
        return issue


_MANDATORY_IGNORES = (
    ".git/**",
    ".svn/**",
    ".ipd/**",
)

_MANAGED_BINDING_OWNER = "ipdctl.tailor"
_MANAGED_BINDING_KIND = "deliverable_evidence"
_MANAGED_EVIDENCE_RULE_PREFIX = "ipd-evidence-"
_ARTIFACT_BINDINGS_SCHEMA_VERSION = "1.0"
_ARTIFACT_SNAPSHOT_SCHEMA_VERSION = "1.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "description",
    "ignore",
    "critical_roots",
    "bindings",
    "artifact_bindings",
    "extensions",
}
_RULE_FIELDS = {
    "id",
    "glob",
    "globs",
    "paths",
    "deliverable",
    "deliverables",
    "critical",
    "review_required",
    "description",
    "managed_by",
    "managed_kind",
}
_PATTERN_FIELDS = ("glob", "globs", "paths")
_OWNER_FIELDS = ("deliverable", "deliverables")

DEFAULT_ARTIFACT_BINDINGS: dict[str, Any] = {
    "schema_version": "1.0",
    "description": "Project paths mapped to IPD deliverables",
    "ignore": [*_MANDATORY_IGNORES, "evidence/gates/**"],
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


def sync_evidence_bindings(
    existing: Mapping[str, Any], tailored_process: Mapping[str, Any]
) -> dict[str, Any]:
    """Return bindings with deterministic framework-managed evidence rules.

    User-authored rules are preserved verbatim and in their original order.
    Rules carrying both framework management markers are regenerated from the
    current tailored process, which removes stale rules after re-tailoring and
    repairs modified framework-owned rules without inferring ownership for
    project source, documentation, or test paths.
    """

    if not isinstance(existing, Mapping):
        raise ReconcileError("artifact bindings must be an object")
    if not isinstance(tailored_process, Mapping):
        raise ReconcileError("tailored process must be an object")

    raw_bindings = existing.get("bindings", [])
    if not isinstance(raw_bindings, list) or any(
        not isinstance(item, Mapping) for item in raw_bindings
    ):
        raise ReconcileError("artifact bindings field 'bindings' must be an object list")

    raw_deliverables = tailored_process.get("deliverables", [])
    if not isinstance(raw_deliverables, list) or any(
        not isinstance(item, Mapping) for item in raw_deliverables
    ):
        raise ReconcileError("tailored process field 'deliverables' must be an object list")

    deliverable_ids: set[str] = set()
    for item in raw_deliverables:
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ReconcileError(
                "tailored process deliverables must have non-empty string ids"
            )
        deliverable_ids.add(identifier.strip())

    user_rules = [
        deepcopy(dict(rule))
        for rule in raw_bindings
        if not (
            rule.get("managed_by") == _MANAGED_BINDING_OWNER
            and rule.get("managed_kind") == _MANAGED_BINDING_KIND
        )
    ]
    managed_rules = [
        {
            "id": f"{_MANAGED_EVIDENCE_RULE_PREFIX}{identifier}",
            "glob": f"evidence/{identifier}/**",
            "deliverable": identifier,
            "critical": True,
            "managed_by": _MANAGED_BINDING_OWNER,
            "managed_kind": _MANAGED_BINDING_KIND,
            "description": (
                "Framework-managed evidence path for deliverable " + identifier
            ),
        }
        for identifier in sorted(deliverable_ids)
    ]

    result = deepcopy(dict(existing))
    result["bindings"] = user_rules + managed_rules
    return result


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ReconcileError(f"artifact bindings field '{field}' must be a string list")
    return list(value)


def _invalid_bindings(
    message: str,
    *,
    path: str | None = None,
    code: str = "ARTIFACT_BINDINGS_INVALID",
    details: Mapping[str, Any] | None = None,
) -> ReconcileError:
    return ReconcileError(message, code=code, path=path, details=details)


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _invalid_bindings(
                    "artifact binding extension keys must be strings",
                    path=path,
                )
            _validate_json_value(item, f"{path}.{key}")
        return
    raise _invalid_bindings(
        "artifact binding extensions must contain JSON-compatible values",
        path=path,
    )


def _pattern_problem(pattern: Any) -> str | None:
    if not isinstance(pattern, str) or not pattern.strip():
        return "must be a non-empty string"
    if pattern != pattern.strip():
        return "must not have leading or trailing whitespace"
    if "\\" in pattern:
        return "must use POSIX '/' separators"
    if pattern.startswith("/") or re.match(r"^[A-Za-z]:", pattern):
        return "must be repository-relative"
    if "\x00" in pattern:
        return "must not contain NUL"
    if "//" in pattern:
        return "must not contain empty path segments"
    segments = pattern.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        return "must not contain '.', '..', or empty path segments"
    if pattern.count("[") != pattern.count("]"):
        return "contains an unbalanced character class"
    return None


def _strict_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise _invalid_bindings("must be an array of strings", path=path)
    result: list[str] = []
    for index, item in enumerate(value):
        problem = _pattern_problem(item)
        if problem is not None:
            raise _invalid_bindings(
                f"invalid artifact binding pattern: {problem}",
                code="BINDING_INVALID_PATTERN",
                path=f"{path}[{index}]",
            )
        result.append(item)
    return result


def _validated_rule(rule: Mapping[str, Any], index: int) -> dict[str, Any]:
    path = f"$.bindings[{index}]"
    unknown = sorted(set(rule) - _RULE_FIELDS)
    if unknown:
        raise _invalid_bindings(
            f"unknown artifact binding rule field {unknown[0]!r}",
            path=f"{path}.{unknown[0]}",
        )

    identifier = rule.get("id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise _invalid_bindings(
            "artifact binding rule id must be a non-empty string",
            path=f"{path}.id",
        )
    if identifier != identifier.strip():
        raise _invalid_bindings(
            "artifact binding rule id must not have surrounding whitespace",
            path=f"{path}.id",
        )

    present_pattern_fields = [field for field in _PATTERN_FIELDS if field in rule]
    if len(present_pattern_fields) != 1:
        raise _invalid_bindings(
            "artifact binding rule must define exactly one of 'glob', 'globs', or 'paths'",
            path=path,
        )
    pattern_field = present_pattern_fields[0]
    raw_patterns = rule[pattern_field]
    if pattern_field == "glob":
        raw_patterns = [raw_patterns]
    if not isinstance(raw_patterns, (list, tuple)) or not raw_patterns:
        raise _invalid_bindings(
            "artifact binding rule patterns must be a non-empty string list",
            path=f"{path}.{pattern_field}",
        )
    for pattern_index, pattern in enumerate(raw_patterns):
        problem = _pattern_problem(pattern)
        if problem is not None:
            raise _invalid_bindings(
                f"invalid artifact binding pattern: {problem}",
                code="BINDING_INVALID_PATTERN",
                path=(
                    f"{path}.{pattern_field}"
                    if pattern_field == "glob"
                    else f"{path}.{pattern_field}[{pattern_index}]"
                ),
                details={"rule_ids": [identifier]},
            )

    present_owner_fields = [field for field in _OWNER_FIELDS if field in rule]
    if len(present_owner_fields) != 1:
        raise _invalid_bindings(
            "artifact binding rule must define exactly one owner field",
            code="BINDING_CRITICAL_MULTIPLE_DELIVERABLES",
            path=path,
            details={"rule_ids": [identifier]},
        )
    owner_field = present_owner_fields[0]
    raw_owners = rule[owner_field]
    if owner_field == "deliverable":
        raw_owners = [raw_owners]
    if not isinstance(raw_owners, (list, tuple)) or not raw_owners:
        raise _invalid_bindings(
            "artifact binding rule must have at least one deliverable owner",
            path=f"{path}.{owner_field}",
            details={"rule_ids": [identifier]},
        )
    if bool(rule.get("critical", True)) and len(raw_owners) != 1:
        raise _invalid_bindings(
            "critical artifact binding rule must have exactly one deliverable owner",
            code="BINDING_CRITICAL_MULTIPLE_DELIVERABLES",
            path=f"{path}.{owner_field}",
            details={"rule_ids": [identifier]},
        )
    seen_owners: set[str] = set()
    for owner_index, owner in enumerate(raw_owners):
        if not isinstance(owner, str) or not owner.strip() or owner != owner.strip():
            raise _invalid_bindings(
                "artifact binding rule owner must be a non-empty trimmed string",
                path=(
                    f"{path}.{owner_field}"
                    if owner_field == "deliverable"
                    else f"{path}.{owner_field}[{owner_index}]"
                ),
                details={"rule_ids": [identifier]},
            )
        if owner in seen_owners:
            raise _invalid_bindings(
                "artifact binding rule owners must be unique",
                path=f"{path}.{owner_field}[{owner_index}]",
                details={"rule_ids": [identifier]},
            )
        seen_owners.add(owner)

    for field in ("critical", "review_required"):
        if field in rule and type(rule[field]) is not bool:
            raise _invalid_bindings(
                f"artifact binding rule field {field!r} must be boolean",
                path=f"{path}.{field}",
                details={"rule_ids": [identifier]},
            )
    for field in ("description", "managed_by", "managed_kind"):
        if field in rule and not isinstance(rule[field], str):
            raise _invalid_bindings(
                f"artifact binding rule field {field!r} must be a string",
                path=f"{path}.{field}",
                details={"rule_ids": [identifier]},
            )
    return deepcopy(dict(rule))


def validate_artifact_bindings(
    value: Any,
    *,
    known_deliverables: Sequence[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Validate and normalize the strict schema-1.0 binding contract.

    The legacy top-level ``artifact_bindings`` alias and rule aliases
    ``globs``/``paths`` and ``deliverables`` remain readable.  Aliases never
    weaken the single-owner rule.
    """

    if not isinstance(value, Mapping):
        raise _invalid_bindings("artifact bindings root must be an object", path="$")
    data = deepcopy(dict(value))
    unknown = sorted(set(data) - _TOP_LEVEL_FIELDS)
    if unknown:
        raise _invalid_bindings(
            f"unknown artifact bindings field {unknown[0]!r}",
            path=f"$.{unknown[0]}",
        )
    if "bindings" in data and "artifact_bindings" in data:
        raise _invalid_bindings(
            "artifact bindings must not define both 'bindings' and legacy 'artifact_bindings'",
            path="$",
        )
    if "bindings" not in data and "artifact_bindings" in data:
        data["bindings"] = data.pop("artifact_bindings")

    version = data.get("schema_version", _ARTIFACT_BINDINGS_SCHEMA_VERSION)
    if version != _ARTIFACT_BINDINGS_SCHEMA_VERSION:
        raise _invalid_bindings(
            "artifact bindings schema_version must equal '1.0'",
            path="$.schema_version",
        )
    data["schema_version"] = _ARTIFACT_BINDINGS_SCHEMA_VERSION
    if "description" in data and not isinstance(data["description"], str):
        raise _invalid_bindings(
            "artifact bindings description must be a string",
            path="$.description",
        )
    if "extensions" in data:
        if not isinstance(data["extensions"], Mapping):
            raise _invalid_bindings(
                "artifact bindings extensions must be an object",
                path="$.extensions",
            )
        _validate_json_value(data["extensions"], "$.extensions")

    data["ignore"] = _strict_string_list(
        data.get("ignore", list(DEFAULT_ARTIFACT_BINDINGS["ignore"])),
        "$.ignore",
    )
    for pattern in _MANDATORY_IGNORES:
        if pattern not in data["ignore"]:
            data["ignore"].append(pattern)
    data["critical_roots"] = _strict_string_list(
        data.get(
            "critical_roots",
            list(DEFAULT_ARTIFACT_BINDINGS["critical_roots"]),
        ),
        "$.critical_roots",
    )

    raw_rules = data.get("bindings", [])
    if not isinstance(raw_rules, list):
        raise _invalid_bindings(
            "artifact bindings field 'bindings' must be an object list",
            path="$.bindings",
        )
    rules: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    owners = set(known_deliverables) if known_deliverables is not None else None
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, Mapping):
            raise _invalid_bindings(
                "artifact binding rules must be objects",
                path=f"$.bindings[{index}]",
            )
        rule = _validated_rule(raw_rule, index)
        identifier = str(rule["id"])
        if identifier in seen_ids:
            raise _invalid_bindings(
                f"duplicate artifact binding rule id {identifier!r}",
                code="BINDING_DUPLICATE_RULE_ID",
                path=f"$.bindings[{index}].id",
                details={"rule_ids": [identifier]},
            )
        seen_ids.add(identifier)
        for owner in _rule_deliverables(rule):
            if owners is not None and owner not in owners:
                raise _invalid_bindings(
                    f"binding references unknown deliverable {owner!r}",
                    code="BINDING_UNKNOWN_DELIVERABLE",
                    path=f"$.bindings[{index}]",
                    details={"deliverable_id": owner, "rule_ids": [identifier]},
                )
        rules.append(rule)
    data["bindings"] = rules
    return data


def load_artifact_bindings(
    path: str | Path | None,
    *,
    allow_default: bool = False,
    known_deliverables: Sequence[str] | set[str] | None = None,
) -> dict[str, Any]:
    """Load and normalize a YAML/JSON artifact-binding contract.

    Missing configuration fails closed during normal operation.  ``allow_default``
    exists only for initialization paths that have not written the project
    contract yet.
    """

    if path is None:
        if allow_default:
            return default_artifact_bindings()
        raise ReconcileError(
            "artifact bindings path is required",
            code="ARTIFACT_BINDINGS_MISSING",
            path=".ipd/artifact_bindings.yaml",
        )
    source = Path(path)
    if not source.exists():
        if allow_default:
            return default_artifact_bindings()
        raise ReconcileError(
            f"artifact bindings file does not exist: {source}",
            code="ARTIFACT_BINDINGS_MISSING",
            path=source.as_posix(),
        )
    try:
        value = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ReconcileError(
            f"cannot load artifact bindings {source}: {exc}",
            code="ARTIFACT_BINDINGS_INVALID",
            path=source.as_posix(),
        ) from exc
    if value is None:
        value = {}
    try:
        return validate_artifact_bindings(
            value, known_deliverables=known_deliverables
        )
    except ReconcileError as exc:
        if exc.path is None:
            exc.path = source.as_posix()
        raise


# Short alias retained for projects migrating from the v1.4 runtime scripts.
load_bindings = load_artifact_bindings


def _canonical_binding_contract(bindings: Mapping[str, Any]) -> dict[str, Any]:
    validated = validate_artifact_bindings(bindings)
    canonical_rules: list[dict[str, Any]] = []
    for rule in validated["bindings"]:
        canonical: dict[str, Any] = {
            "id": rule["id"],
            "patterns": sorted(set(_rule_patterns(rule))),
            "deliverables": _rule_deliverables(rule),
            "critical": bool(rule.get("critical", True)),
        }
        for field in (
            "review_required",
            "description",
            "managed_by",
            "managed_kind",
        ):
            if field in rule:
                canonical[field] = deepcopy(rule[field])
        canonical_rules.append(canonical)
    canonical_rules.sort(key=lambda item: item["id"])
    result: dict[str, Any] = {
        "schema_version": _ARTIFACT_BINDINGS_SCHEMA_VERSION,
        "ignore": sorted(set(validated["ignore"])),
        "critical_roots": sorted(set(validated["critical_roots"])),
        "bindings": canonical_rules,
    }
    for field in ("description", "extensions"):
        if field in validated:
            result[field] = deepcopy(validated[field])
    return result


def artifact_bindings_digest(bindings: Mapping[str, Any]) -> str:
    """Return a formatting-, order-, and legacy-alias-stable SHA-256 digest."""

    canonical = _canonical_binding_contract(bindings)
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# Explicit aliases used by callers that treat the value as a field rather than
# an operation.  Keep one implementation so the digest contract cannot drift.
stable_bindings_digest = artifact_bindings_digest
bindings_sha256 = artifact_bindings_digest


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


def _checked_relative_path(path: str | Path) -> str:
    normalized = normalize_relative_path(path)
    if not normalized:
        raise ReconcileError(
            "repository-relative path must not be empty",
            code="BINDING_BASELINE_INVALID",
        )
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ReconcileError(
            f"path is not safely repository-relative: {path!s}",
            code="BINDING_BASELINE_INVALID",
            path=normalized,
        )
    if re.match(r"^[A-Za-z]:", normalized):
        raise ReconcileError(
            f"path is not safely repository-relative: {path!s}",
            code="BINDING_BASELINE_INVALID",
            path=normalized,
        )
    return normalized


def repository_path_hashes(
    project_root: str | Path, paths: Sequence[str | Path]
) -> dict[str, str | None]:
    """Hash repository-relative path content without persisting checkout paths.

    ``None`` represents a missing path, which is necessary to make deletions
    and reversions part of an exact baseline/window snapshot.  Symbolic links
    hash their link text instead of reading a target that may leave the project.
    """

    root = Path(project_root).resolve()
    result: dict[str, str | None] = {}
    for raw_path in sorted({_checked_relative_path(path) for path in paths}):
        candidate = root.joinpath(*PurePosixPath(raw_path).parts)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ReconcileError(
                f"path leaves project root: {raw_path}",
                code="BINDING_BASELINE_INVALID",
                path=raw_path,
            ) from exc
        try:
            if candidate.is_symlink():
                payload = b"symlink\0" + os.readlink(candidate).encode(
                    "utf-8", errors="surrogatepass"
                )
                result[raw_path] = hashlib.sha256(payload).hexdigest()
            elif candidate.is_file():
                digest = hashlib.sha256()
                with candidate.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                result[raw_path] = digest.hexdigest()
            elif candidate.is_dir():
                result[raw_path] = hashlib.sha256(b"directory\0").hexdigest()
            else:
                result[raw_path] = None
        except OSError as exc:
            raise ReconcileError(
                f"cannot hash repository path {raw_path!r}: {exc}",
                code="BINDING_BASELINE_INVALID",
                path=raw_path,
            ) from exc
    return result


path_hashes = repository_path_hashes


def _portable_repository_snapshot(project_root: Path) -> dict[str, Any]:
    info = inspect_repository(project_root)
    return {"kind": info.kind, "revision": info.revision}


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    payload = {
        key: deepcopy(snapshot.get(key))
        for key in ("schema_version", "bindings_sha256", "repository", "paths")
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_issues(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, Mapping):
        return ["artifact baseline must be an object"]
    issues: list[str] = []
    allowed = {
        "schema_version",
        "baseline_id",
        "snapshot_sha256",
        "bindings_sha256",
        "repository",
        "paths",
    }
    unknown = sorted(set(snapshot) - allowed)
    if unknown:
        issues.append(f"unknown artifact baseline field {unknown[0]!r}")
    if snapshot.get("schema_version") != _ARTIFACT_SNAPSHOT_SCHEMA_VERSION:
        issues.append("artifact baseline schema_version must equal '1.0'")
    for field in ("baseline_id", "snapshot_sha256", "bindings_sha256"):
        if not isinstance(snapshot.get(field), str) or not _SHA256_RE.fullmatch(
            snapshot[field]
        ):
            issues.append(f"artifact baseline field {field!r} must be a SHA-256 hex digest")
    repository = snapshot.get("repository")
    if not isinstance(repository, Mapping):
        issues.append("artifact baseline repository must be an object")
    else:
        if set(repository) - {"kind", "revision"}:
            issues.append("artifact baseline repository has unknown fields")
        if repository.get("kind") not in {"git", "svn", "none"}:
            issues.append("artifact baseline repository kind is invalid")
        if repository.get("revision") is not None and not isinstance(
            repository.get("revision"), str
        ):
            issues.append("artifact baseline repository revision must be a string or null")
    paths = snapshot.get("paths")
    if not isinstance(paths, Mapping):
        issues.append("artifact baseline paths must be an object")
    else:
        for path, digest in paths.items():
            try:
                normalized = _checked_relative_path(path)
            except ReconcileError as exc:
                issues.append(str(exc))
                continue
            if normalized != path:
                issues.append(f"artifact baseline path is not normalized: {path!r}")
            if digest is not None and (
                not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest)
            ):
                issues.append(f"artifact baseline path hash is invalid: {path!r}")
    if not issues:
        expected = _snapshot_digest(snapshot)
        if snapshot.get("snapshot_sha256") != expected:
            issues.append("artifact baseline snapshot_sha256 does not match its content")
        if snapshot.get("baseline_id") != expected:
            issues.append("artifact baseline baseline_id does not match its content")
    return issues


def validate_artifact_baseline(snapshot: Any) -> dict[str, Any]:
    issues = _snapshot_issues(snapshot)
    if issues:
        raise ReconcileError(
            issues[0],
            code="BINDING_BASELINE_INVALID",
            path="$.artifact_baseline",
        )
    return deepcopy(dict(snapshot))


def artifact_baseline_snapshot(
    project_root: str | Path,
    state: Mapping[str, Any] | None = None,
    bindings_path: str | Path | None = None,
    *,
    bindings: Mapping[str, Any] | None = None,
    staged: bool = False,
    base: str | None = None,
) -> dict[str, Any]:
    """Capture the exact governed working-copy snapshot used by v0.3.2."""

    root = Path(project_root).resolve()
    known = _deliverable_ids(state) if isinstance(state, Mapping) else None
    contract = (
        validate_artifact_bindings(bindings, known_deliverables=known)
        if bindings is not None
        else load_artifact_bindings(
            bindings_path or root / ".ipd" / "artifact_bindings.yaml",
            known_deliverables=known,
        )
    )
    _, changed = changed_paths(root, staged=staged, base=base)
    governed_paths = [
        path
        for path in changed
        if not any(path_matches(path, pattern) for pattern in contract["ignore"])
    ]
    snapshot: dict[str, Any] = {
        "schema_version": _ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
        "bindings_sha256": artifact_bindings_digest(contract),
        "repository": _portable_repository_snapshot(root),
        "paths": repository_path_hashes(root, governed_paths),
    }
    digest = _snapshot_digest(snapshot)
    snapshot["snapshot_sha256"] = digest
    snapshot["baseline_id"] = digest
    return snapshot


def _deliverable_ids(state: Mapping[str, Any]) -> set[str]:
    rows = state.get("deliverables", [])
    if not isinstance(rows, list):
        return set()
    return {
        str(row["id"])
        for row in rows
        if isinstance(row, Mapping) and row.get("id") is not None
    }


def _latest_claim_events(
    runtime: Mapping[str, Any] | None, *, current_state_revision: int
) -> dict[str, dict[str, Any]]:
    """Return only the latest readable Claim for each Deliverable.

    A v0.3.1 Claim remains readable runtime history but lacks ``binding_window``
    and is therefore rejected later as v0.3.2 ownership evidence.
    """

    if runtime is None:
        return {}
    events = runtime.get("events", [])
    if not isinstance(events, list):
        raise ReconcileError(
            "Agent runtime events must be an array",
            code="BINDING_WINDOW_INVALID",
            path="$.events",
        )
    latest: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        if not isinstance(event, Mapping) or event.get("action") != "claim":
            continue
        deliverable = event.get("deliverable")
        if not isinstance(deliverable, str) or not deliverable.strip():
            continue
        record = deepcopy(dict(event))
        record["_event_index"] = index
        record["_core_issues"] = claim_event_issues(
            dict(event), current_state_revision=current_state_revision
        )
        latest[deliverable.strip()] = record
    return latest


def _claim_window_issues(window: Any) -> list[str]:
    if not isinstance(window, Mapping):
        return ["Claim binding_window must be an object"]
    allowed = {
        "schema_version",
        "bindings_sha256",
        "baseline_id",
        "opened_paths",
        "snapshot_sha256",
    }
    issues: list[str] = []
    unknown = sorted(set(window) - allowed)
    if unknown:
        issues.append(f"unknown Claim binding_window field {unknown[0]!r}")
    if window.get("schema_version") != _ARTIFACT_SNAPSHOT_SCHEMA_VERSION:
        issues.append("Claim binding_window schema_version must equal '1.0'")
    for field in ("bindings_sha256", "snapshot_sha256"):
        if not isinstance(window.get(field), str) or not _SHA256_RE.fullmatch(
            window[field]
        ):
            issues.append(f"Claim binding_window field {field!r} must be a SHA-256 digest")
    baseline_id = window.get("baseline_id")
    if baseline_id is not None and (
        not isinstance(baseline_id, str) or not _SHA256_RE.fullmatch(baseline_id)
    ):
        issues.append("Claim binding_window baseline_id must be a SHA-256 digest or null")
    paths = window.get("opened_paths")
    if not isinstance(paths, Mapping):
        issues.append("Claim binding_window opened_paths must be an object")
    else:
        for path, digest in paths.items():
            try:
                normalized = _checked_relative_path(path)
            except ReconcileError as exc:
                issues.append(str(exc))
                continue
            if normalized != path:
                issues.append(f"Claim binding_window path is not normalized: {path!r}")
            if digest is not None and (
                not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest)
            ):
                issues.append(f"Claim binding_window path hash is invalid: {path!r}")
    return issues


def validate_claim_binding_window(window: Any) -> dict[str, Any]:
    issues = _claim_window_issues(window)
    if issues:
        raise ReconcileError(
            issues[0],
            code="BINDING_WINDOW_INVALID",
            path="$.binding_window",
        )
    return deepcopy(dict(window))


def recover_claim_binding_window(
    runtime: Mapping[str, Any],
    deliverable_id: str,
    *,
    project_root: str | Path | None = None,
    state: Mapping[str, Any] | None = None,
    bindings_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return the original binding window for an unfinished Claim iteration.

    Lease expiry and orphan recovery transfer execution responsibility; they do
    not move the provenance boundary. Reopening a window from the dirty working
    tree would make work created under the original Claim appear to predate the
    recovery Claim. A terminal event ends the iteration, so subsequent rework
    captures a new window instead.
    """

    events = runtime.get("events", [])
    if not isinstance(events, list):
        return None
    terminal_actions = {"close", "review", "approve", "reject"}
    iteration_start = 0
    for index in range(len(events) - 1, -1, -1):
        event = events[index]
        if (
            isinstance(event, Mapping)
            and event.get("deliverable") == deliverable_id
            and event.get("action") in terminal_actions
        ):
            iteration_start = index + 1
            break
    first_legacy_claim_index: int | None = None
    for index, event in enumerate(events[iteration_start:], start=iteration_start):
        if (
            not isinstance(event, Mapping)
            or event.get("action") != "claim"
            or event.get("deliverable") != deliverable_id
        ):
            continue
        if "binding_window" not in event:
            if first_legacy_claim_index is None:
                first_legacy_claim_index = index
            continue
        window = event["binding_window"]
        if _claim_window_issues(window):
            return None
        return validate_claim_binding_window(window)

    if (
        first_legacy_claim_index is None
        or project_root is None
        or not isinstance(state, Mapping)
    ):
        return None

    # A windowless v0.3.1 Claim can cross the v0.3.2 migration boundary only
    # through an explicit human adoption recorded after that Claim. Stale or
    # malformed historical adoptions cannot authorize recovery, but neither
    # may they permanently mask a later exact adoption of the current tree.
    # Once the recovery Claim records the derived window, later recoveries use
    # that immutable window above even if legitimate work has changed paths.
    try:
        current_snapshot = artifact_baseline_snapshot(
            project_root,
            state,
            bindings_path=bindings_path,
        )
    except (OSError, ReconcileError, ValueError):
        return None

    for event in events[first_legacy_claim_index + 1 :]:
        if not isinstance(event, Mapping):
            continue
        if event.get("action") != "artifact_baseline_adopted":
            continue
        if artifact_baseline_event_issues(dict(event)):
            continue
        if event.get("state_revision") != state.get("revision"):
            continue
        try:
            adopted_snapshot = validate_artifact_baseline(
                event.get("artifact_baseline")
            )
        except ReconcileError:
            continue
        if adopted_snapshot != current_snapshot:
            continue
        return validate_claim_binding_window(
            {
                "schema_version": _ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
                "bindings_sha256": adopted_snapshot["bindings_sha256"],
                "baseline_id": adopted_snapshot["baseline_id"],
                "opened_paths": deepcopy(adopted_snapshot["paths"]),
                "snapshot_sha256": adopted_snapshot["snapshot_sha256"],
            }
        )
    return None


def _latest_artifact_baseline(
    runtime: Mapping[str, Any] | None,
    *,
    current_repository: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if runtime is None:
        return None, None
    events = runtime.get("events", [])
    if not isinstance(events, list):
        raise ReconcileError(
            "Agent runtime events must be an array",
            code="BINDING_BASELINE_INVALID",
            path="$.events",
        )

    event_candidate: Any = None
    event_source: str | None = None
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            continue
        if event.get("action") == "artifact_baseline_adopted":
            event_candidate = event.get(
                "artifact_baseline", event.get("snapshot")
            )
            event_source = "artifact_baseline_adopted"
        elif event.get("action") == "verify" and event.get("status") == "passed":
            snapshot = event.get("artifact_baseline")
            if snapshot is not None:
                event_candidate = snapshot
                event_source = "verify"

    if event_candidate is not None:
        return validate_artifact_baseline(event_candidate), event_source

    # Compatibility cache for runtimes written before successful Verify events
    # carried their full immutable snapshot.
    last_verification = runtime.get("last_verification")
    if (
        isinstance(last_verification, Mapping)
        and last_verification.get("status") == "passed"
        and last_verification.get("artifact_baseline") is not None
    ):
        return (
            validate_artifact_baseline(last_verification["artifact_baseline"]),
            "last_verification",
        )

    # A first Claim may open on a clean repository before any successful
    # verification exists.  Its exact window is the only permissible implicit
    # baseline and remains valid only when its own snapshot hash is also its
    # baseline identity.
    for event in reversed(events):
        if not isinstance(event, Mapping) or event.get("action") != "claim":
            continue
        window = event.get("binding_window")
        if _claim_window_issues(window):
            continue
        if window.get("baseline_id") != window.get("snapshot_sha256"):
            continue
        if current_repository is None:
            continue
        candidate = {
            "schema_version": window["schema_version"],
            "bindings_sha256": window["bindings_sha256"],
            "repository": deepcopy(dict(current_repository)),
            "paths": deepcopy(window["opened_paths"]),
            "snapshot_sha256": window["snapshot_sha256"],
            "baseline_id": window["baseline_id"],
        }
        return validate_artifact_baseline(candidate), "claim_binding_window"
    else:
        return None, None


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    path: str | None = None,
    deliverable_id: str | None = None,
    reason_code: str | None = None,
    rule_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path is not None:
        row["path"] = path
    if deliverable_id is not None:
        row["deliverable_id"] = deliverable_id
    if reason_code is not None:
        row["reason_code"] = reason_code
    if rule_ids:
        row["rule_ids"] = sorted(set(rule_ids))
    return row


def _path_owner_details(matches: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    owners = sorted(
        {
            owner
            for match in matches
            for owner in match.get("deliverables", [])
            if isinstance(owner, str)
        }
    )
    rule_ids = sorted(
        {
            str(match["rule_id"])
            for match in matches
            if match.get("rule_id") is not None
        }
    )
    return owners, rule_ids


def _provenance_reason(
    claim_event: Mapping[str, Any] | None,
    *,
    deliverable_id: str,
    path: str,
    bindings_digest: str,
    baseline: Mapping[str, Any],
    current_snapshot: Mapping[str, Any],
) -> str | None:
    if claim_event is None:
        return "CLAIM_WINDOW_MISSING"
    if claim_event.get("_core_issues"):
        return "CLAIM_WINDOW_MISSING"
    window = claim_event.get("binding_window")
    if window is None:
        return "CLAIM_WINDOW_MISSING"
    if _claim_window_issues(window):
        return "CLAIM_WINDOW_MISSING"
    if claim_event.get("deliverable") != deliverable_id:
        return "CLAIM_OWNER_MISMATCH"
    if window.get("bindings_sha256") != bindings_digest:
        return "CLAIM_BINDINGS_STALE"
    if window.get("baseline_id") != baseline.get("baseline_id"):
        return "BASELINE_MISMATCH"
    window_paths = window.get("opened_paths", {})
    current_paths = current_snapshot.get("paths", {})
    if current_paths.get(path) == window_paths.get(path) and (
        path in current_paths or path in window_paths
    ):
        return "PATH_PREDATES_CLAIM"
    return None


def _binding_source(root: Path, bindings_path: str | Path | None) -> Path:
    source = (
        Path(bindings_path)
        if bindings_path is not None
        else root / ".ipd" / "artifact_bindings.yaml"
    )
    return source if source.is_absolute() else root / source


def _empty_readiness(target_deliverable: str | None) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "failed",
        "eligible": False,
        "target_deliverable": target_deliverable,
        "bindings_sha256": None,
        "baseline_id": None,
        "issues": [],
        "paths": {},
        "deliverables": {},
        "summary": {
            "changed_paths": 0,
            "governed_paths": 0,
            "baseline_paths": 0,
            "window_paths": 0,
            "mapped_paths": 0,
            "ignored_paths": 0,
            "unbound_paths": 0,
            "deliverables_touched": 0,
            "errors": 0,
            "warnings": 0,
        },
    }


def _evaluate_bindings(
    project_root: str | Path,
    state: Mapping[str, Any],
    runtime: Mapping[str, Any] | None,
    bindings_path: str | Path | None,
    *,
    target_deliverable: str | None,
    staged: bool,
    base: str | None,
    require_baseline: bool,
    enforce_provenance: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, set[str]]:
    report = _empty_readiness(target_deliverable)
    compatibility_mapping: dict[str, Any] = {
        "paths": {},
        "deliverables": {},
        "unbound": [],
        "ignored": [],
    }
    claimed: set[str] = set()
    if not isinstance(state, Mapping):
        report["issues"].append(
            _issue("ARTIFACT_BINDINGS_INVALID", "project state must be an object")
        )
        report["summary"]["errors"] = 1
        return report, compatibility_mapping, None, claimed

    root = Path(project_root).resolve()
    try:
        bindings = load_artifact_bindings(_binding_source(root, bindings_path))
    except ReconcileError as exc:
        report["issues"].append(exc.as_issue())
        report["summary"]["errors"] = 1
        return report, compatibility_mapping, None, claimed

    digest = artifact_bindings_digest(bindings)
    report["bindings_sha256"] = digest
    known_deliverables = _deliverable_ids(state)
    if target_deliverable is not None and target_deliverable not in known_deliverables:
        report["issues"].append(
            _issue(
                "BINDING_UNKNOWN_DELIVERABLE",
                "Target Deliverable is absent from project state",
                deliverable_id=target_deliverable,
            )
        )

    rules_by_owner: dict[str, list[str]] = {}
    for rule in bindings["bindings"]:
        for owner in _rule_deliverables(rule):
            rules_by_owner.setdefault(owner, []).append(str(rule["id"]))
            if owner not in known_deliverables:
                report["issues"].append(
                    _issue(
                        "BINDING_UNKNOWN_DELIVERABLE",
                        "Binding references a Deliverable absent from project state",
                        deliverable_id=owner,
                        rule_ids=[str(rule["id"])],
                    )
                )

    try:
        _, changed = changed_paths(root, staged=staged, base=base)
        compatibility_mapping = map_paths_to_deliverables(changed, bindings)
        governed_changed = [
            path for path in changed if path not in compatibility_mapping["ignored"]
        ]
        current_snapshot = artifact_baseline_snapshot(
            root,
            bindings=bindings,
            staged=staged,
            base=base,
        )
    except ReconcileError as exc:
        report["issues"].append(exc.as_issue())
        errors = sum(
            1 for issue in report["issues"] if issue.get("severity") == "error"
        )
        report["summary"].update(
            changed_paths=len(locals().get("changed", [])), errors=errors
        )
        return report, compatibility_mapping, None, claimed

    baseline: dict[str, Any] | None = None
    baseline_valid = False
    if require_baseline:
        try:
            baseline, _ = _latest_artifact_baseline(
                runtime, current_repository=current_snapshot["repository"]
            )
        except ReconcileError as exc:
            report["issues"].append(exc.as_issue())
        if baseline is None and not current_snapshot["paths"]:
            baseline = current_snapshot
            baseline_valid = True
            report["baseline_id"] = current_snapshot["baseline_id"]
        elif baseline is None:
            report["issues"].append(
                _issue(
                    "BINDING_BASELINE_MISSING",
                    "No adopted or successfully verified artifact baseline exists",
                )
            )
        else:
            report["baseline_id"] = baseline["baseline_id"]
            baseline_valid = True
            bindings_stale = baseline.get("bindings_sha256") != digest
            repository_stale = (
                baseline.get("repository") != current_snapshot.get("repository")
            )
            if not current_snapshot["paths"] and (
                bindings_stale or repository_stale
            ):
                baseline = current_snapshot
                baseline_valid = True
                report["baseline_id"] = current_snapshot["baseline_id"]
            elif bindings_stale:
                report["issues"].append(
                    _issue(
                        "BINDING_BASELINE_STALE",
                        "Artifact bindings changed after the authoritative baseline",
                        reason_code="CLAIM_BINDINGS_STALE",
                    )
                )
                baseline_valid = False
            if repository_stale and current_snapshot["paths"]:
                report["issues"].append(
                    _issue(
                        "BINDING_BASELINE_STALE",
                        "Repository revision changed after the authoritative baseline",
                        reason_code="CLAIM_REPOSITORY_STALE",
                    )
                )
                baseline_valid = False
    else:
        baseline = current_snapshot
        baseline_valid = True
        report["baseline_id"] = current_snapshot["baseline_id"]

    baseline_paths = baseline.get("paths", {}) if baseline is not None else {}
    current_paths = current_snapshot["paths"]
    if require_baseline and baseline is not None:
        window_paths = sorted(
            path
            for path in set(baseline_paths) | set(current_paths)
            if baseline_paths.get(path) != current_paths.get(path)
            or (path in baseline_paths) != (path in current_paths)
        )
    else:
        window_paths = sorted(current_paths)
    window_mapping = map_paths_to_deliverables(window_paths, bindings)

    latest_claims = (
        _latest_claim_events(
            runtime,
            current_state_revision=(
                state.get("revision") if type(state.get("revision")) is int else -1
            ),
        )
        if enforce_provenance and require_baseline and baseline_valid
        else {}
    )
    for path in window_paths:
        matches = window_mapping["paths"].get(path, [])
        owners, rule_ids = _path_owner_details(matches)
        critical = is_critical_path(path, bindings) or any(
            bool(match.get("critical", True)) for match in matches
        )
        report["paths"][path] = {
            "sha256": current_paths.get(path),
            "baseline_sha256": baseline_paths.get(path),
            "changed_since_baseline": require_baseline,
            "critical": critical,
            "rule_ids": rule_ids,
            "deliverable_ids": owners,
            "binding_ready": bool(matches) and (len(owners) == 1 or not critical),
            "issue_codes": [],
        }
        if not matches:
            severity = "error" if critical else "warning"
            issue = _issue(
                "UNBOUND_CHANGED_PATH",
                "Changed path is not bound to an IPD Deliverable",
                severity=severity,
                path=path,
            )
            report["issues"].append(issue)
            report["paths"][path]["issue_codes"].append(issue["code"])
            continue
        if len(owners) > 1:
            issue = _issue(
                "BINDING_CRITICAL_OWNER_CONFLICT",
                "Changed path resolves to more than one Deliverable owner",
                severity="error" if critical else "warning",
                path=path,
                rule_ids=rule_ids,
            )
            report["issues"].append(issue)
            report["paths"][path]["issue_codes"].append(issue["code"])
            if critical:
                continue
            # Non-critical multi-Deliverable rules are trace links, not an
            # authoritative ownership claim.  Preserve the mapping and warn,
            # but do not require one arbitrary owner to prove provenance.
            continue
        owner = owners[0]
        if owner not in known_deliverables:
            report["paths"][path]["issue_codes"].append(
                "BINDING_UNKNOWN_DELIVERABLE"
            )
            continue
        if enforce_provenance and require_baseline and baseline_valid:
            reason = _provenance_reason(
                latest_claims.get(owner),
                deliverable_id=owner,
                path=path,
                bindings_digest=digest,
                baseline=baseline,
                current_snapshot=current_snapshot,
            )
            if reason is None:
                claimed.add(owner)
            else:
                issue = _issue(
                    "BINDING_UNCLAIMED_DELIVERABLE",
                    "Changed path lacks v0.3.2 Claim binding-window provenance",
                    path=path,
                    deliverable_id=owner,
                    reason_code=reason,
                    rule_ids=rule_ids,
                )
                report["issues"].append(issue)
                report["paths"][path]["issue_codes"].append(issue["code"])

    global_blocking_codes = {
        "ARTIFACT_BINDINGS_MISSING",
        "ARTIFACT_BINDINGS_INVALID",
        "BINDING_BASELINE_MISSING",
        "BINDING_BASELINE_INVALID",
        "BINDING_BASELINE_STALE",
    }
    binding_blocking_codes = {
        "ARTIFACT_BINDINGS_INVALID",
        "BINDING_DUPLICATE_RULE_ID",
        "BINDING_INVALID_PATTERN",
        "BINDING_CRITICAL_MULTIPLE_DELIVERABLES",
        "BINDING_CRITICAL_OWNER_CONFLICT",
        "BINDING_UNKNOWN_DELIVERABLE",
    }
    for deliverable_id in sorted(known_deliverables):
        touched_paths = sorted(window_mapping["deliverables"].get(deliverable_id, []))
        relevant_issues = [
            issue
            for issue in report["issues"]
            if issue.get("deliverable_id") == deliverable_id
            or issue.get("path") in touched_paths
            or (
                issue.get("path") is None
                and issue.get("code") in global_blocking_codes
            )
        ]
        has_binding = bool(rules_by_owner.get(deliverable_id))
        binding_ready = has_binding and not any(
            issue.get("severity") == "error"
            and issue.get("code") in binding_blocking_codes
            for issue in relevant_issues
        )
        issue_codes = sorted({str(issue["code"]) for issue in relevant_issues})
        blockers = sorted(
            {
                str(issue.get("reason_code") or issue["code"])
                for issue in relevant_issues
                if issue.get("severity") == "error"
            }
        )
        report["deliverables"][deliverable_id] = {
            "eligible": binding_ready and not blockers,
            "binding_ready": binding_ready,
            "issue_codes": issue_codes,
            "blockers": blockers,
            "paths": touched_paths,
            "rule_ids": sorted(rules_by_owner.get(deliverable_id, [])),
        }

    if target_deliverable in report["deliverables"] and not rules_by_owner.get(
        target_deliverable
    ):
        issue = _issue(
            "ARTIFACT_BINDINGS_INVALID",
            "Target Deliverable has no artifact binding rule",
            deliverable_id=target_deliverable,
            reason_code="TARGET_HAS_NO_BINDING",
        )
        report["issues"].append(issue)
        target_row = report["deliverables"][target_deliverable]
        target_row["eligible"] = False
        target_row["binding_ready"] = False
        target_row["issue_codes"] = sorted(
            set(target_row["issue_codes"] + [issue["code"]])
        )
        target_row["blockers"] = sorted(
            set(target_row["blockers"] + [issue["reason_code"]])
        )

    errors = sum(1 for issue in report["issues"] if issue["severity"] == "error")
    warnings = sum(
        1 for issue in report["issues"] if issue["severity"] == "warning"
    )
    target_row = report["deliverables"].get(target_deliverable)
    report["eligible"] = (
        errors == 0
        and (target_row is None or bool(target_row.get("eligible")))
    )
    report["status"] = "failed" if errors else "warning" if warnings else "passed"
    report["summary"] = {
        "changed_paths": len(changed),
        "governed_paths": len(governed_changed),
        "baseline_paths": len(baseline_paths),
        "window_paths": len(window_paths),
        "mapped_paths": sum(
            1 for matches in window_mapping["paths"].values() if matches
        ),
        "ignored_paths": len(compatibility_mapping["ignored"]),
        "unbound_paths": len(window_mapping["unbound"]),
        "deliverables_touched": len(window_mapping["deliverables"]),
        "errors": errors,
        "warnings": warnings,
    }
    return report, compatibility_mapping, current_snapshot, claimed


def binding_readiness(
    project_root: str | Path,
    state: Mapping[str, Any],
    runtime: Mapping[str, Any] | None = None,
    bindings_path: str | Path | None = None,
    *,
    target_deliverable: str | None = None,
    staged: bool = False,
    base: str | None = None,
) -> dict[str, Any]:
    """Return the shared fail-closed Binding/Claim eligibility contract."""

    report, _, _, _ = _evaluate_bindings(
        project_root,
        state,
        runtime,
        bindings_path,
        target_deliverable=target_deliverable,
        staged=staged,
        base=base,
        require_baseline=True,
        enforce_provenance=True,
    )
    return report


artifact_binding_readiness = binding_readiness
binding_preflight = binding_readiness


def preview_artifact_baseline(
    project_root: str | Path,
    state: Mapping[str, Any],
    bindings_path: str | Path | None = None,
    *,
    staged: bool = False,
    base: str | None = None,
) -> dict[str, Any]:
    """Preview whether the current governed tree can become a baseline."""

    report, _, _, _ = _evaluate_bindings(
        project_root,
        state,
        None,
        bindings_path,
        target_deliverable=None,
        staged=staged,
        base=base,
        require_baseline=False,
        enforce_provenance=False,
    )
    return report


def create_claim_binding_window(
    project_root: str | Path,
    state: Mapping[str, Any],
    runtime: Mapping[str, Any],
    deliverable_id: str,
    bindings_path: str | Path | None = None,
) -> dict[str, Any]:
    """Capture the exact eligible baseline at Claim-open time."""

    readiness, _, snapshot, _ = _evaluate_bindings(
        project_root,
        state,
        runtime,
        bindings_path,
        target_deliverable=deliverable_id,
        staged=False,
        base=None,
        require_baseline=True,
        enforce_provenance=True,
    )
    if not readiness["eligible"] or snapshot is None:
        first = next(
            (
                issue
                for issue in readiness["issues"]
                if issue.get("severity") == "error"
            ),
            None,
        )
        raise ReconcileError(
            first.get("message", "Claim binding window is not ready")
            if first
            else "Claim binding window is not ready",
            code="BINDING_WINDOW_MISMATCH",
            path=first.get("path") if first else None,
            details={"reason_code": first.get("reason_code", first.get("code"))}
            if first
            else None,
        )
    window = {
        "schema_version": _ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
        "bindings_sha256": snapshot["bindings_sha256"],
        "baseline_id": readiness["baseline_id"],
        "opened_paths": deepcopy(snapshot["paths"]),
        "snapshot_sha256": snapshot["snapshot_sha256"],
    }
    return validate_claim_binding_window(window)


claim_binding_window = create_claim_binding_window


def build_artifact_baseline_adoption(
    project_root: str | Path,
    state: Mapping[str, Any],
    *,
    actor: str,
    actor_type: str,
    authorized: bool,
    reason: str,
    bindings_path: str | Path | None = None,
    preview: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build, but never persist, an authorized baseline-adoption event."""

    if (
        actor_type != "human"
        or authorized is not True
        or not isinstance(actor, str)
        or not actor.strip()
    ):
        raise ReconcileError(
            "Artifact baseline adoption requires an authorized human actor",
            code="BASELINE_ADOPTION_UNAUTHORIZED",
        )
    if not isinstance(reason, str) or not reason.strip():
        raise ReconcileError(
            "Artifact baseline adoption requires a non-empty reason",
            code="BASELINE_ADOPTION_NOT_READY",
        )
    current_preview = preview_artifact_baseline(
        project_root, state, bindings_path=bindings_path
    )
    if not current_preview["eligible"]:
        raise ReconcileError(
            "Artifact baseline preview contains blocking issues",
            code="BASELINE_ADOPTION_NOT_READY",
            details={
                "reason_code": next(
                    (
                        issue["code"]
                        for issue in current_preview["issues"]
                        if issue.get("severity") == "error"
                    ),
                    "ARTIFACT_BINDINGS_INVALID",
                )
            },
        )
    if preview is not None and preview.get("baseline_id") != current_preview.get(
        "baseline_id"
    ):
        raise ReconcileError(
            "Artifact baseline preview is stale",
            code="BASELINE_ADOPTION_NOT_READY",
            details={"reason_code": "BINDING_BASELINE_STALE"},
        )
    snapshot = artifact_baseline_snapshot(
        project_root, state, bindings_path=bindings_path
    )
    if snapshot["baseline_id"] != current_preview["baseline_id"]:
        raise ReconcileError(
            "Artifact baseline changed while adoption was being prepared",
            code="BASELINE_ADOPTION_NOT_READY",
            details={"reason_code": "BINDING_BASELINE_STALE"},
        )
    state_revision = state.get("revision")
    if type(state_revision) is not int or state_revision < 0:
        raise ReconcileError(
            "project state revision must be a non-negative integer",
            code="BASELINE_ADOPTION_NOT_READY",
        )
    return {
        "action": "artifact_baseline_adopted",
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "actor": actor.strip(),
        "actor_type": actor_type,
        "authorized": True,
        "reason": reason.strip(),
        "state_revision": state_revision,
        "baseline_id": snapshot["baseline_id"],
        "artifact_baseline": snapshot,
    }


adopt_artifact_baseline = build_artifact_baseline_adoption


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
    runtime: Mapping[str, Any] | None = None,
    staged: bool = False,
    base: str | None = None,
) -> dict[str, Any]:
    """Reconcile local changes with deliverables and optionally persist a report."""

    if not isinstance(state, Mapping):
        raise ReconcileError("project state must be an object")
    root = Path(project_root).resolve()
    report, mapping, _, claimed_deliverables = _evaluate_bindings(
        root,
        state,
        runtime,
        bindings_path,
        target_deliverable=None,
        staged=staged,
        base=base,
        require_baseline=runtime is not None,
        enforce_provenance=runtime is not None,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    report["changed_paths"] = sorted(
        set(mapping.get("paths", {})) | set(mapping.get("ignored", []))
    )
    report["mapping"] = mapping
    report["claim_provenance"] = sorted(claimed_deliverables)
    report["summary"]["claimed_deliverables"] = len(claimed_deliverables)
    if write:
        _write_report(root / ".ipd" / "reconcile_report.json", report)
    return report

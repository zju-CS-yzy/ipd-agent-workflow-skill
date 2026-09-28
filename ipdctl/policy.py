"""Loading and validation for the repository's tailoring policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

POLICY_VERSION = 1
NON_NEGOTIABLE_DEFAULTS = {
    "preserve_traceability",
    "require_evidence_for_acceptance",
    "require_authorized_human_gate_approval",
    "block_gate_on_incomplete_deliverables",
}


class PolicyError(ValueError):
    """Raised when a tailoring policy is unreadable or unsafe."""


def validate_policy(value: Any) -> list[str]:
    """Validate the dependency-free JSON-compatible YAML policy format."""

    issues: list[str] = []
    if not isinstance(value, dict):
        return ["$: must be an object"]
    allowed_fields = {"version", "defaults", "tailoring"}
    for field in sorted(value.keys() - allowed_fields):
        issues.append(f"$.{field}: unknown field")
    for field in sorted(allowed_fields - value.keys()):
        issues.append(f"$.{field}: required field is missing")

    if value.get("version") != POLICY_VERSION:
        issues.append(f"$.version: must equal {POLICY_VERSION}")

    defaults = value.get("defaults")
    if not isinstance(defaults, dict):
        issues.append("$.defaults: must be an object")
    else:
        for field in sorted(NON_NEGOTIABLE_DEFAULTS - defaults.keys()):
            issues.append(f"$.defaults.{field}: required field is missing")
        for field in sorted(defaults.keys() - NON_NEGOTIABLE_DEFAULTS):
            issues.append(f"$.defaults.{field}: unknown field")
        for field in sorted(NON_NEGOTIABLE_DEFAULTS & defaults.keys()):
            if defaults[field] is not True:
                issues.append(
                    f"$.defaults.{field}: must be true; this invariant cannot be tailored out"
                )

    tailoring = value.get("tailoring")
    if not isinstance(tailoring, dict):
        issues.append("$.tailoring: must be an object")
    else:
        allowed_tailoring = {"may", "must_not"}
        for field in sorted(tailoring.keys() - allowed_tailoring):
            issues.append(f"$.tailoring.{field}: unknown field")
        for field in sorted(allowed_tailoring - tailoring.keys()):
            issues.append(f"$.tailoring.{field}: required field is missing")
        for field in sorted(allowed_tailoring & tailoring.keys()):
            entries = tailoring[field]
            if not isinstance(entries, list) or not all(
                isinstance(entry, str) and entry.strip() for entry in entries
            ):
                issues.append(
                    f"$.tailoring.{field}: must be an array of non-empty strings"
                )
            elif len(entries) != len(set(entries)):
                issues.append(f"$.tailoring.{field}: must not contain duplicates")
    return issues


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load a policy stored as JSON-compatible YAML and enforce invariants."""

    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"policy file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyError(
            f"policy must use JSON-compatible YAML; invalid content at line "
            f"{exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise PolicyError(f"cannot read policy file {source}: {exc}") from exc

    issues = validate_policy(value)
    if issues:
        raise PolicyError("invalid policy:\n- " + "\n- ".join(issues))
    return value

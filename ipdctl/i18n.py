"""Project-scoped localization for user-facing IPD output.

Machine contracts remain English.  A project's presentation locale is read
only from ``.ipd/task_profile.yaml``; callers pass the resulting Translator
explicitly so concurrent projects cannot leak language state into one another.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml


DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "zh-CN")


class LocaleError(ValueError):
    """Raised when a configured locale or message catalog is invalid."""


class MessageFormatError(LocaleError):
    """Raised when a localized message is missing required parameters."""


_EXCEPTION_MESSAGE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"re-tailoring requires explicit --apply-migrations for historical "
            r"deliverables: (?P<deliverables>.+)"
        ),
        "error.tailor_migrations_required",
    ),
    (
        re.compile(
            r"re-tailoring would remove unmapped historical deliverables: "
            r"(?P<deliverables>.+)"
        ),
        "error.tailor_unmapped_history",
    ),
    (
        re.compile(
            r"state-only superseded history has invalid replacements or trace "
            r"links: (?P<deliverables>.+)"
        ),
        "error.tailor_invalid_superseded_history",
    ),
    (
        re.compile(
            r"deliverable (?P<deliverable>.+?) belongs to phase "
            r"(?P<deliverable_phase>.+?); current phase is (?P<current_phase>.+)"
        ),
        "error.deliverable_phase_mismatch",
    ),
    (
        re.compile(
            r"deliverable (?P<deliverable>.+?) has unmet dependencies: "
            r"(?P<dependencies>.+)"
        ),
        "error.deliverable_unmet_dependencies",
    ),
    (
        re.compile(
            r"deliverable (?P<deliverable>.+?) has no active claim lease; "
            r"claim or recover it before close"
        ),
        "error.claim_missing_for_close",
    ),
    (
        re.compile(
            r"deliverable (?P<deliverable>.+?) is already claimed by (?P<actor>.+)"
        ),
        "error.claim_already_owned",
    ),
    (
        re.compile(r"deliverable (?P<deliverable>.+?) is claimed by (?P<actor>.+)"),
        "error.claim_actor_mismatch",
    ),
    (
        re.compile(r"closing a deliverable requires evidence"),
        "error.close_evidence_required",
    ),
    (
        re.compile(
            r"REVIEW_SUBJECT_REQUIRED: workflow_step 'review' has no globally "
            r"locked current_iteration_subject; migrate or repair the state explicitly"
        ),
        "error.review_subject_required",
    ),
    (
        re.compile(
            r"REVIEW_SUBJECT_MISMATCH: current iteration reviews "
            r"(?P<bound>.+?), not (?P<requested>.+)"
        ),
        "error.review_subject_mismatch",
    ),
    (
        re.compile(
            r"REVIEW_SUBJECT_INACTIVE: review operations require workflow_step "
            r"'review'; current step is (?P<current>.+)"
        ),
        "error.review_subject_inactive",
    ),
    (
        re.compile(
            r"deliverable status (?P<current>.+?) cannot transition to "
            r"(?P<target>.+?); allowed: (?P<allowed>.+)"
        ),
        "error.deliverable_status_transition",
    ),
    (
        re.compile(r"final deliverable approval requires an authorized human reviewer"),
        "error.deliverable_approval_authority",
    ),
    (
        re.compile(r"final deliverable rejection requires an authorized human reviewer"),
        "error.deliverable_rejection_authority",
    ),
    (
        re.compile(r"only a planned or rejected gate can be marked ready"),
        "error.gate_mark_ready_status",
    ),
    (
        re.compile(r"only a ready gate can be approved"),
        "error.gate_approve_status",
    ),
    (
        re.compile(r"only a ready gate can be rejected"),
        "error.gate_reject_status",
    ),
    (
        re.compile(r"gate rejection requires a latest authorized human rejection review"),
        "error.gate_rejection_authority",
    ),
    (
        re.compile(
            r"gate approval requires a latest authorized human approval "
            r"in review epoch (?P<epoch>\d+)"
        ),
        "error.gate_approval_review_epoch",
    ),
    (
        re.compile(
            r"(?P<path>\$[^:]+): gate prerequisites are not accepted: "
            r"(?P<deliverables>.+)"
        ),
        "error.gate_prerequisites_not_accepted",
    ),
    (
        re.compile(
            r"(?P<path>\$[^:]+): approved TR/DCP gate requires an authorized "
            r"human approval"
        ),
        "error.gate_approval_authority",
    ),
    (
        re.compile(r"current phase is missing gate state: (?P<gates>.+)"),
        "error.phase_gate_state_missing",
    ),
    (
        re.compile(r"current phase gates are not approved: (?P<gates>.+)"),
        "error.phase_gates_not_approved",
    ),
    (
        re.compile(r"current phase has no governed gates: (?P<phase>.+)"),
        "error.phase_has_no_gates",
    ),
    (
        re.compile(r"current phase must be refreshed before it can advance"),
        "error.phase_refresh_required",
    ),
    (
        re.compile(
            r"current state revision must pass verification before phase advancement"
        ),
        "error.phase_verification_required",
    ),
    (
        re.compile(r"final lifecycle phase is already complete: (?P<phase>.+)"),
        "error.final_phase_complete",
    ),
    (
        re.compile(r"transaction path leaves project root: (?P<path>.+)"),
        "error.transaction_path_outside_project",
    ),
    (
        re.compile(r"cannot read pending project transaction: (?P<detail>.+)"),
        "error.transaction_unreadable",
    ),
    (
        re.compile(r"pending project transaction has an invalid schema"),
        "error.transaction_schema_invalid",
    ),
    (
        re.compile(r"pending project transaction has invalid files"),
        "error.transaction_files_invalid",
    ),
    (
        re.compile(r"pending transaction file record is invalid"),
        "error.transaction_file_record_invalid",
    ),
    (
        re.compile(r"pending transaction backup is missing"),
        "error.transaction_backup_missing",
    ),
    (
        re.compile(r"pending transaction backup leaves its directory"),
        "error.transaction_backup_outside_directory",
    ),
    (
        re.compile(r"pending transaction Dashboard backup is missing"),
        "error.transaction_dashboard_backup_missing",
    ),
    (
        re.compile(r"project transaction is still active in process (?P<pid>\d+)"),
        "error.transaction_active",
    ),
    (
        re.compile(
            r"cannot determine whether project transaction owner process "
            r"(?P<pid>.+?) is active"
        ),
        "error.transaction_owner_unknown",
    ),
    (
        re.compile(r"another project transaction started concurrently"),
        "error.transaction_concurrent",
    ),
    (
        re.compile(
            r"nested project transaction exceeds the outer transaction scope: "
            r"(?P<paths>.+)"
        ),
        "error.transaction_nested_scope_paths",
    ),
    (
        re.compile(r"nested project transaction exceeds the outer transaction scope"),
        "error.transaction_nested_scope",
    ),
    (
        re.compile(
            r"project rollback failed after (?P<kind>[^:]+): (?P<detail>.+)"
        ),
        "error.transaction_rollback_failed",
    ),
)


def normalize_locale(value: Any) -> str:
    """Return a supported canonical locale or raise an actionable error."""

    if not isinstance(value, str) or not value.strip():
        raise LocaleError(
            f"locale must be one of: {', '.join(SUPPORTED_LOCALES)}"
        )
    locale = value.strip()
    if locale not in SUPPORTED_LOCALES:
        raise LocaleError(
            f"unsupported locale {value!r}; choose from: {', '.join(SUPPORTED_LOCALES)}"
        )
    return locale


def locale_from_profile(profile: Any) -> str:
    """Resolve a locale from a task profile, defaulting legacy profiles to English."""

    if not isinstance(profile, dict):
        raise LocaleError("task profile root must be an object")
    presentation = profile.get("presentation")
    if presentation is None:
        return DEFAULT_LOCALE
    if not isinstance(presentation, dict):
        raise LocaleError("task profile presentation must be an object")
    if "locale" not in presentation:
        return DEFAULT_LOCALE
    return normalize_locale(presentation["locale"])


def _profile_path(project_root: str | Path) -> Path:
    path = Path(project_root)
    if path.is_file() or path.suffix.lower() in {".yaml", ".yml"}:
        return path
    if path.name == ".ipd":
        return path / "task_profile.yaml"
    return path / ".ipd" / "task_profile.yaml"


def load_project_locale(project_root: str | Path = ".") -> str:
    """Read the project's configured locale; missing legacy profiles use English."""

    profile_path = _profile_path(project_root)
    if not profile_path.exists():
        return DEFAULT_LOCALE
    try:
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LocaleError(f"invalid task profile YAML in {profile_path}: {exc}") from exc
    except OSError as exc:
        raise LocaleError(f"cannot read task profile {profile_path}: {exc}") from exc
    return locale_from_profile(profile)


def _freeze_messages(value: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(value))


@lru_cache(maxsize=1)
def _catalog() -> tuple[str, Mapping[str, Mapping[str, str]]]:
    """Load and validate the packaged catalog once without storing locale state."""

    try:
        resource = resources.files("ipdctl").joinpath("messages.yaml")
        with resource.open("r", encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise LocaleError(f"cannot load localization catalog: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise LocaleError("localization catalog must use schema_version '1.0'")
    default_locale = normalize_locale(value.get("default_locale"))
    raw_messages = value.get("messages")
    if not isinstance(raw_messages, dict):
        raise LocaleError("localization catalog messages must be an object")
    catalogs: dict[str, Mapping[str, str]] = {}
    for locale in SUPPORTED_LOCALES:
        entries = raw_messages.get(locale)
        if not isinstance(entries, dict):
            raise LocaleError(f"localization catalog is missing locale {locale!r}")
        invalid = [key for key, text in entries.items() if not isinstance(key, str) or not isinstance(text, str) or not text]
        if invalid:
            raise LocaleError(f"localization catalog {locale!r} contains invalid messages")
        catalogs[locale] = _freeze_messages(entries)
    expected = set(catalogs[default_locale])
    for locale, entries in catalogs.items():
        missing = sorted(expected - set(entries))
        extra = sorted(set(entries) - expected)
        if missing or extra:
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("extra: " + ", ".join(extra))
            raise LocaleError(f"localization keys differ for {locale}: {'; '.join(details)}")
    return default_locale, MappingProxyType(catalogs)


@dataclass(frozen=True)
class Translator:
    """Immutable view of one locale in the packaged message catalog."""

    locale: str
    _messages: Mapping[str, str]
    _fallback: Mapping[str, str]

    def text(self, key: str, **params: Any) -> str:
        template = self._messages.get(key, self._fallback.get(key, key))
        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError) as exc:
            raise MessageFormatError(
                f"cannot format message {key!r} for locale {self.locale!r}: {exc}"
            ) from exc

    def t(self, key: str, **params: Any) -> str:
        """Short alias suited to renderer templates."""

        return self.text(key, **params)

    def has_key(self, key: str) -> bool:
        return key in self._messages or key in self._fallback


def localized_exception_message(error: BaseException, translator: Translator) -> str:
    """Translate stable lifecycle exceptions while preserving technical values.

    Engine and runtime exceptions remain locale-neutral contracts.  The CLI uses
    these exact, anchored patterns as an adapter so unmatched diagnostics are
    never hidden or guessed.
    """

    message = str(error)
    for pattern, key in _EXCEPTION_MESSAGE_RULES:
        match = pattern.fullmatch(message)
        if match is not None:
            return translator.text(key, **match.groupdict())
    return message


@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def get_translator(locale: str = DEFAULT_LOCALE) -> Translator:
    canonical = normalize_locale(locale)
    default_locale, catalogs = _catalog()
    return Translator(canonical, catalogs[canonical], catalogs[default_locale])


def catalog_keys(locale: str = DEFAULT_LOCALE) -> frozenset[str]:
    """Expose immutable catalog keys for release and parity tests."""

    translator = get_translator(locale)
    return frozenset(translator._messages)


__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "LocaleError",
    "MessageFormatError",
    "Translator",
    "catalog_keys",
    "get_translator",
    "load_project_locale",
    "localized_exception_message",
    "locale_from_profile",
    "normalize_locale",
]

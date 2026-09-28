#!/usr/bin/env python3
"""Fail when a release tree contains residue, secrets, or missing contracts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = (
    "README.md",
    "SKILL.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "RELEASE_CHECKLIST.md",
    "pyproject.toml",
    "agents/openai.yaml",
    "schemas/project_state.schema.json",
    "schemas/tailoring_policy.schema.json",
    "policies/default/tailoring_rules.yaml",
)

GENERATED_DIRECTORIES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "build",
    "dist",
    "htmlcov",
}
GENERATED_DIRECTORY_SUFFIXES = (".egg-info",)
GENERATED_FILES = {".coverage", "coverage.xml"}
GENERATED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak", ".log", ".swp"}

SENSITIVE_FILENAMES = (
    re.compile(r"^\.env(?:\..+)?$", re.IGNORECASE),
    re.compile(r"^id_(?:rsa|dsa|ecdsa|ed25519)$", re.IGNORECASE),
    re.compile(r"^.*\.(?:pem|p12|pfx|key)$", re.IGNORECASE),
    re.compile(r"^(?:credentials?|secrets?)(?:\..+)?$", re.IGNORECASE),
)

SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "GitHub token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    ),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|password|passwd|secret|token)\s*[:=]\s*"
            r"[\"'][^\"'\s]{8,}[\"']"
        ),
    ),
    (
        "personal absolute path",
        re.compile(r"(?i)\b[A-Z]:\\Users\\(?!USERNAME\\|user\\|<)[^\\\s]+"),
    ),
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    message: str


def _is_generated_directory(relative: Path) -> bool:
    name = relative.name
    return (
        name in GENERATED_DIRECTORIES
        or name.endswith(GENERATED_DIRECTORY_SUFFIXES)
        or relative.as_posix() == ".ipd/generated"
    )


def _is_sensitive_filename(name: str) -> bool:
    if name == ".env.example":
        return False
    return any(pattern.fullmatch(name) for pattern in SENSITIVE_FILENAMES)


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > 1_000_000 or b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def audit_repository(root: Path) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    scanned_files = 0

    if not (root / ".git").exists():
        findings.append(Finding(".git", "Git repository is not initialized"))

    for required in REQUIRED_FILES:
        path = root / required
        if not path.is_file():
            findings.append(Finding(required, "required release file is missing"))
        elif path.stat().st_size == 0:
            findings.append(Finding(required, "required release file is empty"))

    for current, directories, files in os.walk(root):
        current_path = Path(current)
        kept_directories: list[str] = []
        for directory in directories:
            if directory == ".git":
                continue
            relative = (current_path / directory).relative_to(root)
            if _is_generated_directory(relative):
                findings.append(Finding(relative.as_posix(), "generated/cache directory is present"))
                continue
            kept_directories.append(directory)
        directories[:] = kept_directories

        for filename in files:
            path = current_path / filename
            relative = path.relative_to(root)
            rendered = relative.as_posix()
            if filename in GENERATED_FILES or path.suffix.lower() in GENERATED_SUFFIXES:
                findings.append(Finding(rendered, "generated or temporary file is present"))
                continue
            if _is_sensitive_filename(filename):
                findings.append(Finding(rendered, "credential-like filename is present"))

            text = _read_text(path)
            if text is None:
                continue
            scanned_files += 1
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append(Finding(rendered, f"content matches {label} pattern"))

    skill_path = root / "SKILL.md"
    skill_text = _read_text(skill_path) if skill_path.is_file() else None
    if skill_text is not None:
        if not skill_text.startswith("---\n"):
            findings.append(Finding("SKILL.md", "YAML frontmatter is missing"))
        if not re.search(r"(?m)^name:\s*ipd-agent-workflow-skill\s*$", skill_text):
            findings.append(Finding("SKILL.md", "canonical skill name is missing"))
        if not re.search(r"(?m)^description:\s*\S", skill_text):
            findings.append(Finding("SKILL.md", "skill description is missing"))

    for relative in (
        "schemas/project_state.schema.json",
        "schemas/tailoring_policy.schema.json",
        "policies/default/tailoring_rules.yaml",
    ):
        path = root / relative
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding(relative, f"must be valid JSON-compatible YAML: {exc}"))

    return sorted(set(findings)), scanned_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    findings, scanned_files = audit_repository(root)
    if findings:
        print("Release hygiene check failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding.path}: {finding.message}", file=sys.stderr)
        return 1
    print(f"Release hygiene check passed ({scanned_files} text files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

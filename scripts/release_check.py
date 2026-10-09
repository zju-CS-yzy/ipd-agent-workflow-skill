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

PACKAGE_VERSION = "0.5.1b1"
PUBLIC_VERSION = "0.5.1-beta"
RELEASE_NOTES_PATH = f".github/release-notes/v{PUBLIC_VERSION}.md"
GH_RELEASE_ACTION_SHA = "5113cdc90fd4d541c801c55356214017bf5ae34b"

REQUIRED_FILES = (
    "README.md",
    "README.zh-CN.md",
    "SKILL.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "RELEASE_CHECKLIST.md",
    "AGENT_RUNTIME_PROTOCOL.md",
    "MANIFEST.in",
    "scripts/verify_v031_upgrade.py",
    "scripts/verify_v032_upgrade.py",
    "scripts/verify_v040_upgrade.py",
    "scripts/verify_v041_upgrade.py",
    "scripts/verify_v050_upgrade.py",
    "scripts/verify_local_golden.py",
    "scripts/verify_dashboard_browser.py",
    "ipdctl/dashboard_files.py",
    "scripts/simulate_capability_lifecycle.py",
    "scripts/simulate_progressive_refinement.py",
    "pyproject.toml",
    "agents/openai.yaml",
    ".github/workflows/test.yml",
    ".github/workflows/release.yml",
    RELEASE_NOTES_PATH,
    "ipdctl/messages.yaml",
    "ipdctl/version.py",
    "docs/architecture.md",
    "docs/architecture.zh-CN.md",
    "docs/deployment.md",
    "docs/deployment.zh-CN.md",
    "schemas/project_state.schema.json",
    "schemas/tailoring_policy.schema.json",
    "schemas/task_profile.schema.json",
    "schemas/tailored_process.schema.json",
    "schemas/agent_runtime.schema.json",
    "schemas/artifact_bindings.schema.json",
    "schemas/capability_policy.schema.json",
    "schemas/process_extensions.schema.json",
    "schemas/refinement_plan.schema.json",
    "policies/default/tailoring_rules.yaml",
    "policies/task-types/software.yaml",
    "policies/task-types/hardware.yaml",
    "policies/task-types/embedded.yaml",
    "policies/task-types/robotics.yaml",
    "policies/task-types/ai_system.yaml",
    "policies/task-types/material_change.yaml",
    "policies/capabilities/sourced_component_integration.yaml",
    "policies/capabilities/module_decomposition_and_verification.yaml",
    "policies/capabilities/interface_contract_and_integration.yaml",
    "policies/capabilities/release_and_lifecycle_assurance.yaml",
    "templates/project/.ipd/task_profile.yaml",
    "templates/project/.ipd/process_extensions.yaml",
    "templates/project/docs/README.md",
    "templates/project/dashboard/README.md",
    "templates/project/state/README.md",
    "templates/hooks/git-pre-commit.sh",
    "templates/hooks/git-pre-push.sh",
    "templates/hooks/svn-pre-commit.sh",
)

FORBIDDEN_ROOT_DIRECTORIES = {".ipd", "examples", "generated", "locales"}
FORBIDDEN_DIRECTORY_NAMES = {"examples", "generated", "locales"}

GENERATED_DIRECTORIES = {
    "__pycache__",
    ".golden-debug",
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
FORBIDDEN_BINARY_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}

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
        return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        return None


def _require_pattern(
    findings: list[Finding],
    root: Path,
    relative: str,
    pattern: str,
    message: str,
) -> None:
    path = root / relative
    text = _read_text(path) if path.is_file() else None
    if (
        text is not None
        and re.search(pattern, text, re.MULTILINE | re.DOTALL) is None
    ):
        findings.append(Finding(relative, message))


def _check_release_contract(findings: list[Finding], root: Path) -> None:
    escaped_package = re.escape(PACKAGE_VERSION)
    escaped_public = re.escape(PUBLIC_VERSION)
    checks = (
        (
            "pyproject.toml",
            rf'^version\s*=\s*"{escaped_package}"\s*$',
            f'project version must be "{PACKAGE_VERSION}"',
        ),
        (
            "pyproject.toml",
            r'\[tool\.setuptools\.package-data\].*?^ipdctl\s*=\s*\[\s*"messages\.yaml"\s*\]',
            "ipdctl/messages.yaml must be declared as package data",
        ),
        (
            "MANIFEST.in",
            r"^recursive-include scripts \*\.py\s*$",
            "sdist must include the release simulation scripts",
        ),
        (
            "ipdctl/version.py",
            rf'^PACKAGE_VERSION\s*=\s*"{escaped_package}"\s*$.*?^PUBLIC_VERSION\s*=\s*"{escaped_public}"\s*$',
            "canonical package and public versions must match the release",
        ),
        (
            "ipdctl/__init__.py",
            r'^from \.version import PACKAGE_VERSION\s*$.*?^__version__\s*=\s*PACKAGE_VERSION\s*$',
            "__version__ must use the canonical PACKAGE_VERSION",
        ),
        (
            "ipdctl/cli_v2.py",
            r'^from \.version import PUBLIC_VERSION\s*$.*?^VERSION\s*=\s*PUBLIC_VERSION\s*$',
            "CLI VERSION must use the canonical PUBLIC_VERSION",
        ),
        (
            "CHANGELOG.md",
            rf'^## \[{escaped_package}\]',
            f"changelog must contain a {PACKAGE_VERSION} release section",
        ),
        (
            "README.md",
            rf'`v{escaped_public}`',
            f"README must identify v{PUBLIC_VERSION}",
        ),
        (
            "README.zh-CN.md",
            rf'`v{escaped_public}`.*?`{escaped_package}`',
            "Chinese README must identify the current public and package versions",
        ),
        (
            "RELEASE_CHECKLIST.md",
            rf'target for this cycle is Python package `{escaped_package}` and public label `v{escaped_public}`',
            "release checklist must identify the current package and public versions",
        ),
        (
            RELEASE_NOTES_PATH,
            rf'^# IPD Agent Workflow Framework v{escaped_public}\s*$',
            "release notes title must identify the current public version",
        ),
        (
            RELEASE_NOTES_PATH,
            r"^### Compatibility\s*$.*?^### Approval boundary\s*$.*?^### Known limitations\s*$",
            "English release notes must document compatibility, approval boundaries, and known limitations",
        ),
        (
            RELEASE_NOTES_PATH,
            r"^### 兼容性\s*$.*?^### 审批边界\s*$.*?^### 已知限制\s*$",
            "Chinese release notes must document compatibility, approval boundaries, and known limitations",
        ),
        (
            ".github/workflows/release.yml",
            rf'uses:\s*softprops/action-gh-release@{GH_RELEASE_ACTION_SHA}.*?body_path:\s*{re.escape(RELEASE_NOTES_PATH)}.*?prerelease:\s*true',
            "release workflow must use the supported action, curated notes, and prerelease status",
        ),
        (
            ".github/workflows/release.yml",
            rf'^\s*-\s*"v{escaped_public}"\s*$',
            f"release workflow must trigger on tag v{PUBLIC_VERSION}",
        ),
        (
            ".github/workflows/release.yml",
            rf'ipd-agent-workflow-skill-v{escaped_public}\.zip.*?ipd_agent_workflow_skill-{escaped_package}-py3-none-any\.whl.*?ipd_agent_workflow_skill-{escaped_package}\.tar\.gz',
            "release workflow asset names must match the public and package versions",
        ),
        (
            ".github/workflows/release.yml",
            r"python -B scripts/verify_v031_upgrade\.py",
            "release workflow must qualify the published v0.3.1 in-place upgrade",
        ),
        (
            ".github/workflows/release.yml",
            r"python -B scripts/verify_v032_upgrade\.py",
            "release workflow must qualify the published v0.3.2 in-place upgrade",
        ),
        (
            ".github/workflows/release.yml",
            r"python -B scripts/verify_v040_upgrade\.py",
            "release workflow must qualify the direct v0.4.0 in-place upgrade",
        ),
        (
            ".github/workflows/release.yml",
            r"python -B scripts/verify_v041_upgrade\.py",
            "release workflow must qualify the direct v0.4.1 in-place upgrade",
        ),
        (
            ".github/workflows/release.yml",
            r"python -B scripts/verify_v050_upgrade\.py",
            "release workflow must qualify the direct v0.5.0 in-place upgrade",
        ),
        (
            ".github/workflows/release.yml",
            r'ipdctl"\s+validate\s+"\$project"\s+--json',
            "release artifact smoke tests must exercise validate --json",
        ),
        (
            ".github/workflows/release.yml",
            r'test "\$\(find "\$project/\.ipd/dashboard" -type f \| wc -l\)" -eq 16',
            "release artifact smoke tests must require the 16-file Dashboard",
        ),
        (
            ".github/workflows/test.yml",
            r"fetch-depth:\s*0.*?python -B scripts/verify_v031_upgrade\.py",
            "CI must fetch release history and qualify the v0.3.1 in-place upgrade",
        ),
        (
            ".github/workflows/test.yml",
            r"upgrade-v032:.*?fetch-depth:\s*0.*?python -B scripts/verify_v032_upgrade\.py",
            "CI must fetch release history and qualify the published v0.3.2 upgrade",
        ),
        (
            ".github/workflows/test.yml",
            r"upgrade-v040:.*?fetch-depth:\s*0.*?python -B scripts/verify_v040_upgrade\.py",
            "CI must fetch release history and qualify the direct v0.4.0 upgrade",
        ),
        (
            ".github/workflows/test.yml",
            r"upgrade-v041:.*?fetch-depth:\s*0.*?python -B scripts/verify_v041_upgrade\.py",
            "CI must fetch release history and qualify the direct v0.4.1 upgrade",
        ),
        (
            ".github/workflows/test.yml",
            r"upgrade-v050:.*?fetch-depth:\s*0.*?python -B scripts/verify_v050_upgrade\.py",
            "CI must fetch release history and qualify the direct v0.5.0 upgrade",
        ),
        (
            ".github/workflows/test.yml",
            r"^\s{2}governance-gate:\s*$.*?needs:\s*$.*?-\s+test\s*$.*?-\s+package\s*$.*?-\s+upgrade-v031\s*$.*?-\s+upgrade-v032\s*$.*?-\s+upgrade-v040\s*$.*?-\s+upgrade-v041\s*$.*?-\s+upgrade-v050\s*$",
            "CI must expose the stable governance-gate over all release-contract jobs",
        ),
        (
            ".github/workflows/test.yml",
            r"UPGRADE_V032_RESULT:\s*\$\{\{\s*needs\.upgrade-v032\.result\s*\}\}.*?test \"\$UPGRADE_V032_RESULT\" = \"success\"",
            "governance-gate must explicitly require the v0.3.2 upgrade result",
        ),
        (
            ".github/workflows/test.yml",
            r"UPGRADE_V040_RESULT:\s*\$\{\{\s*needs\.upgrade-v040\.result\s*\}\}.*?test \"\$UPGRADE_V040_RESULT\" = \"success\"",
            "governance-gate must explicitly require the v0.4.0 upgrade result",
        ),
        (
            ".github/workflows/test.yml",
            r"UPGRADE_V041_RESULT:\s*\$\{\{\s*needs\.upgrade-v041\.result\s*\}\}.*?test \"\$UPGRADE_V041_RESULT\" = \"success\"",
            "governance-gate must explicitly require the v0.4.1 upgrade result",
        ),
        (
            ".github/workflows/test.yml",
            r"UPGRADE_V050_RESULT:\s*\$\{\{\s*needs\.upgrade-v050\.result\s*\}\}.*?test \"\$UPGRADE_V050_RESULT\" = \"success\"",
            "governance-gate must explicitly require the v0.5.0 upgrade result",
        ),
        (
            "scripts/verify_v040_upgrade.py",
            r'^RELEASE_TAG\s*=\s*"v0\.4\.0-beta"\s*$',
            "direct upgrade qualification must use the published v0.4.0-beta tag",
        ),
        (
            "scripts/verify_v041_upgrade.py",
            r'^RELEASE_TAG\s*=\s*"v0\.4\.1-beta"\s*$',
            "direct upgrade qualification must use the published v0.4.1-beta tag",
        ),
        (
            "scripts/verify_v050_upgrade.py",
            r'^RELEASE_TAG\s*=\s*"v0\.5\.0-beta"\s*$',
            "direct upgrade qualification must use the published v0.5.0-beta tag",
        ),
        (
            ".github/workflows/test.yml",
            r"IPD_TEST_LOCALE:\s*\$\{\{\s*matrix\.locale\s*\}\}.*?python -B -m unittest discover -s tests -v",
            "CI must run the complete lifecycle simulation in each locale matrix entry",
        ),
        (
            ".github/workflows/release.yml",
            r"python -B -m unittest discover -s tests -v.*?IPD_TEST_LOCALE=en python -B -m unittest.*?tests\.test_full_lifecycle_simulation -v",
            "release workflow must qualify the complete lifecycle in both locales",
        ),
        (
            ".github/workflows/test.yml",
            r"tar -tzf \"\$sdist\" \| grep '/scripts/simulate_progressive_refinement\.py\$'.*?cp \"\$source_root/scripts/simulate_progressive_refinement\.py\".*?sdist-progressive/simulate_progressive_refinement\.py.*?sdist-venv/bin/python.*?simulate_progressive_refinement\.py --json",
            "CI must inspect the sdist and execute its progressive simulation against the installed package outside the extracted source",
        ),
        (
            ".github/workflows/release.yml",
            r"tar -tzf \"\$sdist\" \| grep '/scripts/simulate_progressive_refinement\.py\$'.*?cp \"\$sdist_root/scripts/simulate_progressive_refinement\.py\".*?sdist-progressive/simulate_progressive_refinement\.py.*?sdist-validation-venv/bin/python.*?simulate_progressive_refinement\.py --json",
            "release workflow must inspect the sdist and execute its progressive simulation against the installed package outside the extracted source",
        ),
        (
            ".github/workflows/test.yml",
            r"cp scripts/simulate_progressive_refinement\.py.*?wheel-progressive/simulate_progressive_refinement\.py.*?wheel-progressive.*?simulate_progressive_refinement\.py --json",
            "CI must execute the progressive simulation against the installed wheel outside the checkout",
        ),
        (
            ".github/workflows/release.yml",
            r"cp \"\$GITHUB_WORKSPACE/scripts/simulate_progressive_refinement\.py\".*?wheel-progressive/simulate_progressive_refinement\.py.*?wheel-refinement-venv/bin/pip.*?wheel-progressive.*?simulate_progressive_refinement\.py --json",
            "release workflow must execute the progressive simulation against the installed wheel outside the checkout",
        ),
        (
            "docs/deployment.md",
            rf'`v{escaped_public}`.*?`{escaped_package}`.*?`v0\.5\.0-beta`',
            "deployment guide must identify the release and direct upgrade baseline",
        ),
        (
            "docs/deployment.zh-CN.md",
            rf'`v{escaped_public}`.*?`{escaped_package}`.*?`v0\.5\.0-beta`',
            "Chinese deployment guide must identify the release and direct upgrade baseline",
        ),
        (
            "SKILL.md",
            r'presentation\.locale.*?zh-CN',
            "Skill language contract must route generated presentation by project locale",
        ),
        (
            "ipdctl/messages.yaml",
            r'^\s*en:\s*$',
            "message catalog must contain the en locale",
        ),
        (
            "ipdctl/messages.yaml",
            r'^\s*zh-CN:\s*$',
            "message catalog must contain the zh-CN locale",
        ),
    )
    for relative, pattern, message in checks:
        _require_pattern(findings, root, relative, pattern, message)

    capability_paths = (
        "policies/capabilities/sourced_component_integration.yaml",
        "policies/capabilities/module_decomposition_and_verification.yaml",
        "policies/capabilities/interface_contract_and_integration.yaml",
        "policies/capabilities/release_and_lifecycle_assurance.yaml",
    )
    for capability_path in capability_paths:
        escaped_path = re.escape(capability_path)
        _require_pattern(
            findings,
            root,
            ".github/workflows/test.yml",
            rf"zipfile -l \"\$wheel\" \| grep '{escaped_path}'.*?tar -tzf \"\$sdist\" \| grep '/{escaped_path}\$'",
            f"CI package inspection must require {capability_path} in wheel and sdist",
        )
        _require_pattern(
            findings,
            root,
            ".github/workflows/release.yml",
            rf"zipfile -l \"\$wheel\" \| grep '{escaped_path}'.*?tar -tzf \"\$sdist\" \| grep '/{escaped_path}\$'.*?test -f \"\$skill_root/{escaped_path}\"",
            f"release artifact inspection must require {capability_path} in wheel, sdist, and Skill ZIP",
        )

    catalog_pattern = (
        r"for pattern in.*?sourced_component_integration.*?"
        r"module_decomposition_and_verification.*?"
        r"interface_contract_and_integration.*?"
        r"release_and_lifecycle_assurance.*?"
        r'ipdctl\" tailor \"\$project\".*?ipdctl\" render-dashboard \"\$project\".*?ipdctl\" validate \"\$project\" --json'
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/test.yml",
        catalog_pattern,
        "CI must tailor and validate every installed capability policy",
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/release.yml",
        catalog_pattern,
        "release artifact smoke tests must tailor and validate every installed capability policy",
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/test.yml",
        r"tar -tzf \"\$sdist\" \| grep '/scripts/verify_v041_upgrade\.py\$'",
        "CI must require the v0.4.1 upgrade probe in the sdist",
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/release.yml",
        r"tar -tzf \"\$sdist\" \| grep '/scripts/verify_v041_upgrade\.py\$'",
        "release artifact inspection must require the v0.4.1 upgrade probe in the sdist",
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/test.yml",
        r"tar -tzf \"\$sdist\" \| grep '/scripts/verify_v050_upgrade\.py\$'",
        "CI must require the v0.5.0 upgrade probe in the sdist",
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/release.yml",
        r"tar -tzf \"\$sdist\" \| grep '/scripts/verify_v050_upgrade\.py\$'",
        "release artifact inspection must require the v0.5.0 upgrade probe in the sdist",
    )
    _require_pattern(
        findings,
        root,
        ".github/workflows/release.yml",
        r'test -f "\$skill_root/scripts/verify_v050_upgrade\.py"',
        "release artifact inspection must require the v0.5.0 upgrade probe in the Skill ZIP",
    )
    for workflow in (".github/workflows/test.yml", ".github/workflows/release.yml"):
        _require_pattern(
            findings,
            root,
            workflow,
            r"tar -tzf \"\$sdist\" \| grep '/scripts/simulate_capability_lifecycle\.py\$'",
            "package inspection must require the capability lifecycle simulation in the sdist",
        )
    _require_pattern(
        findings,
        root,
        ".github/workflows/release.yml",
        r'test -f "\$skill_root/scripts/simulate_capability_lifecycle\.py"',
        "release artifact inspection must require the capability lifecycle simulation in the Skill ZIP",
    )

    action_pattern = re.compile(
        r"^\s*(?:-\s*)?uses:\s*[^@\s]+@([^\s#]+)", re.MULTILINE
    )
    for relative in (".github/workflows/test.yml", ".github/workflows/release.yml"):
        path = root / relative
        text = _read_text(path) if path.is_file() else None
        if text is None:
            continue
        for match in action_pattern.finditer(text):
            if re.fullmatch(r"[0-9a-f]{40}", match.group(1)) is None:
                findings.append(
                    Finding(
                        relative,
                        "every GitHub Action must be pinned to a full commit SHA",
                    )
                )
                break


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

    _check_release_contract(findings, root)

    for current, directories, files in os.walk(root):
        current_path = Path(current)
        kept_directories: list[str] = []
        for directory in directories:
            if directory == ".git":
                continue
            relative = (current_path / directory).relative_to(root)
            if (
                relative.parent == Path(".")
                and directory in FORBIDDEN_ROOT_DIRECTORIES
            ) or directory in FORBIDDEN_DIRECTORY_NAMES:
                findings.append(Finding(relative.as_posix(), "project instance or generated output is present"))
                continue
            if _is_generated_directory(relative):
                findings.append(Finding(relative.as_posix(), "generated/cache directory is present"))
                continue
            kept_directories.append(directory)
        directories[:] = kept_directories

        for filename in files:
            path = current_path / filename
            relative = path.relative_to(root)
            rendered = relative.as_posix()
            if rendered == "MIGRATION_REPORT.md":
                continue
            if filename in GENERATED_FILES or path.suffix.lower() in GENERATED_SUFFIXES:
                findings.append(Finding(rendered, "generated or temporary file is present"))
                continue
            if path.suffix.lower() in FORBIDDEN_BINARY_SUFFIXES:
                findings.append(Finding(rendered, "generated screenshot or binary project output is present"))
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

    for path in sorted((root / "schemas").glob("*.json")):
        relative = path.relative_to(root).as_posix()
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

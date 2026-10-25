"""Version-pinned Markdown templates; substitution never evaluates code."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


class RequirementError(ValueError):
    """Stable diagnostic code and localized explanation at the CLI boundary."""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    """Reject ambiguous names, links and Windows junctions at every component."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise RequirementError("PATH_UNSAFE: use a portable relative path")
    parts = PurePosixPath(relative).parts
    if PurePosixPath(relative).is_absolute() or any(
        p in {".", ".."} or p.endswith((".", " ")) or
        re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p)
        for p in parts
    ) or str(PurePosixPath(relative)) != relative:
        raise RequirementError("PATH_UNSAFE: invalid relative path")
    root = root.resolve()
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise RequirementError("PATH_LINK: links and junctions are not permitted")
        # Python 3.10/3.11 lack is_junction().
        if path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise RequirementError("PATH_LINK: reparse points are not permitted")
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise RequirementError("PATH_ESCAPE: path leaves the project") from exc
    return path


def load_pack(root: Path, pin: dict | None = None) -> tuple[dict, Path]:
    directory = Path(__file__).parent / "document_templates"
    if pin and pin.get("path"):
        directory = safe_path(root, pin["path"])
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if pin and not pin.get("path") and (pin.get("id"), pin.get("version")) != (manifest["id"], manifest["version"]):
        archived = safe_path(directory, "archives/" + pin["id"] + "-" + pin["version"])
        if (archived / "manifest.json").is_file():
            directory = archived
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    from .requirement_contract import TEMPLATE_PACK, validate
    try:
        validate(manifest, TEMPLATE_PACK)
    except RequirementError as exc:
        raise RequirementError("TEMPLATE_CONTRACT: invalid template pack schema") from exc
    if set(manifest) != {"schema_version", "id", "version", "contract", "layer", "templates"}:
        raise RequirementError("TEMPLATE_CONTRACT: invalid template pack fields")
    if manifest["schema_version"] != "1.0" or manifest["contract"] not in {"0.5.3", "0.5.4"}:
        raise RequirementError("TEMPLATE_CONTRACT: incompatible template contract")
    if manifest["layer"] not in {"core", "organization", "project"}:
        raise RequirementError("TEMPLATE_CONTRACT: invalid template layer")
    seen = set()
    for record in manifest["templates"]:
        if set(record) != {"document_type", "id", "version", "locale", "path", "sections", "sha256", "requirement_kinds", "phases", "filename_pattern"}:
            raise RequirementError("TEMPLATE_CONTRACT: invalid template entry")
        key = (record["document_type"], record["locale"])
        if key in seen or record["locale"] not in {"en", "zh-CN"}:
            raise RequirementError("TEMPLATE_DUPLICATE: duplicate type/locale")
        seen.add(key)
        try:
            re.compile(record["filename_pattern"])
        except re.error as exc:
            raise RequirementError("TEMPLATE_CONTRACT: invalid filename pattern") from exc
        if not record["sections"] or len(record["sections"]) != len(set(record["sections"])) or not set(record["requirement_kinds"]) <= {"IR", "SR", "AR"} or not set(record["phases"]) <= {"concept", "plan", "develop", "qualify", "launch", "lifecycle"}:
            raise RequirementError("TEMPLATE_CONTRACT: invalid sections or applicability")
        data = safe_path(directory, record["path"]).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise RequirementError("TEMPLATE_TAMPERED: template digest differs")
    if pin and "sha256" in pin and (pin["sha256"] != digest(manifest) or pin["id"] != manifest["id"] or
                pin["version"] != manifest["version"]):
        raise RequirementError("TEMPLATE_PIN: pinned template pack differs")
    return manifest, directory


def template(root: Path, pin: dict, document_type: str, locale: str) -> tuple[dict, str]:
    manifest, directory = load_pack(root, pin)
    record = next((r for r in manifest["templates"]
                   if (r["document_type"], r["locale"]) == (document_type, locale)), None)
    if record is None:
        raise RequirementError("TEMPLATE_MISSING: no pinned template for type and locale")
    return record, safe_path(directory, record["path"]).read_text(encoding="utf-8")


def lint_instances(root: Path, instances: list[dict], canonical: dict) -> dict[str, list[str]]:
    """Validate each immutable pack once per call, never cache across mutations."""
    packs, result = {}, {}
    for item in instances:
        issues = []
        try:
            key = digest(item["pack"])
            if key not in packs:
                manifest, directory = load_pack(root, item["pack"])
                packs[key] = (manifest, directory)
            manifest, directory = packs[key]
            record = next((r for r in manifest["templates"] if (r["document_type"], r["locale"]) == (item["document_type"], item["locale"])), None)
            if record is None:
                raise RequirementError("TEMPLATE_MISSING: type or locale absent")
            if record["sha256"] != item["template_sha256"]:
                issues.append("TEMPLATE_PIN")
            source = safe_path(directory, record["path"]).read_text(encoding="utf-8")
            if hashlib.sha256(source.replace("\r\n", "\n").encode()).hexdigest() != record["sha256"]:
                raise RequirementError("TEMPLATE_TAMPERED: template changed during validation")
            text = safe_path(root, item["path"]).read_text(encoding="utf-8")
            issues.extend(lint(text, item, source, record["sections"], canonical=canonical))
        except (ValueError, OSError) as exc:
            issues.append("DOCUMENT_INVALID:" + str(exc))
        result[item["id"]] = sorted(set(issues))
    return result


def metadata(instance: dict) -> dict:
    return {"instance_id": instance["id"], "increment": instance["increment"],
            "requirements": ", ".join(instance["requirements"]), "owner": instance["owner"],
            "document_type": instance["document_type"], "template_id": instance["template_id"],
            "template_version": instance["template_version"],
            "template_sha256": instance["template_sha256"], "locale": instance["locale"],
            "scope": instance["scope"]}


def instantiate(text: str, instance: dict) -> str:
    variables = set(re.findall(r"\{\{([^{}]+)\}\}", text))
    allowed = {"instance_id", "increment", "requirements", "owner", "document_type", "template_id",
               "template_version", "template_sha256", "locale", "scope", "title"}
    if not variables <= allowed:
        raise RequirementError("TEMPLATE_VARIABLE: unknown substitution variable")
    fields = {**metadata(instance), "title": instance["title"]}
    def replace(match: re.Match) -> str:
        key = match[1]
        if key not in fields:
            raise RequirementError("TEMPLATE_VARIABLE: unknown substitution variable")
        value = fields[key]
        if any(c in value for c in "\r\n\x00") or "{{" in value:
            raise RequirementError("TEMPLATE_VALUE: multiline or recursive substitution")
        return value.replace("'", "''") if key != "title" else value
    rendered = re.sub(r"\{\{([^{}]+)\}\}", replace, text)
    if "{{" in rendered:
        raise RequirementError("TEMPLATE_VARIABLE: malformed substitution")
    return rendered


def lint(text: str, instance: dict, source: str, sections: list[str], *,
         canonical: dict | None = None) -> list[str]:
    issues = []
    try:
        front = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
        if not front or yaml.safe_load(front[1]) != metadata(instance):
            issues.append("DOCUMENT_METADATA")
    except yaml.YAMLError:
        issues.append("DOCUMENT_METADATA")
    expected = instantiate(source, instance)
    anchors = re.findall(r"<!-- ipd-section:([a-z0-9_]+) -->", text)
    if anchors != sections:
        issues.append("DOCUMENT_SECTIONS")
    for sid in sections:
        pattern = r"<!-- ipd-section:" + re.escape(sid) + r" -->\s*\n(## [^\n]+)"
        heading = re.search(pattern, expected)
        actual = re.search(pattern, text)
        if not actual or not heading or heading[1] != actual[1]:
            issues.append("DOCUMENT_HEADING:" + sid)
        block = re.search(r"<!-- ipd-section:" + re.escape(sid) + r" -->(.*?)(?=<!-- ipd-section:|\Z)", text, re.S)
        original = re.search(r"<!-- ipd-section:" + re.escape(sid) + r" -->(.*?)(?=<!-- ipd-section:|\Z)", expected, re.S)
        if block and original:
            fixed = {line.strip() for line in original[1].splitlines() if "[[TODO:" not in line}
            substantive = [line for line in block[1].splitlines() if line.strip() and line.strip() not in fixed]
            if not substantive:
                issues.append("DOCUMENT_UNFILLED:" + sid)
    expected_lines = expected.splitlines()
    for index, line in enumerate(expected_lines[:-1]):
        if line.startswith("|") and re.match(r"\|\s*:?-+", expected_lines[index + 1]) and line not in text.splitlines():
            issues.append("DOCUMENT_COLUMNS")
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"\|\s*:?-+", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if any(not cell for cell in cells):
                issues.append("DOCUMENT_FIELDS")
            if any(re.fullmatch(r"(?i)(n/?a|不适用)", cell) for cell in cells):
                issues.append("DOCUMENT_NA_REASON")
    # Comments and code fences cannot hide unfinished work.
    if re.search(r"\[\[TODO:|\{\{|\bTBD\b", text, re.I):
        issues.append("DOCUMENT_PLACEHOLDERS")
    from .document_tables import lint_tables
    issues.extend(lint_tables(text, expected, instance["requirements"], canonical=canonical,
                              document_type=instance["document_type"]))
    return sorted(set(issues))

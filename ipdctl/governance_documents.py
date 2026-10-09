"""Deterministic governance views derived only from canonical IPD facts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

from .i18n import Translator, get_translator
from .version import PACKAGE_VERSION, PUBLIC_VERSION


DOCUMENT_SCHEMA_VERSION = "1.0"


def _latest_human_decision(reviews: Any) -> str | None:
    if not isinstance(reviews, list):
        return None
    for review in reversed(reviews):
        if (
            isinstance(review, Mapping)
            and review.get("reviewer_type") == "human"
            and review.get("authorized") is True
            and review.get("decision") in {"approve", "reject"}
        ):
            return str(review["decision"])
    return None


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def build_governance_document_model(
    process: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the portable semantic snapshot represented by governance.md."""

    project = state.get("project") if isinstance(state.get("project"), Mapping) else {}
    deliverables = []
    for item in state.get("deliverables", []):
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            continue
        deliverables.append(
            {
                "id": item["id"],
                "title": str(item.get("title") or item["id"]),
                "phase": item.get("phase"),
                "status": item.get("status"),
                "evidence_count": len(item.get("evidence", [])),
                "review_count": len(item.get("reviews", [])),
                "latest_authorized_human_decision": _latest_human_decision(
                    item.get("reviews", [])
                ),
            }
        )

    state_gates = {
        item.get("id"): item
        for item in state.get("gates", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    gates = []
    for process_gate in process.get("gates", []):
        if not isinstance(process_gate, Mapping) or not isinstance(
            process_gate.get("id"), str
        ):
            continue
        identifier = process_gate["id"]
        state_gate = state_gates.get(identifier, {})
        gates.append(
            {
                "id": identifier,
                "title": str(
                    state_gate.get("title")
                    or process_gate.get("title")
                    or identifier
                ),
                "kind": state_gate.get("kind") or process_gate.get("kind"),
                "phase": state_gate.get("phase") or process_gate.get("phase"),
                "status": state_gate.get("status"),
                "required_deliverables": list(
                    state_gate.get(
                        "required_deliverables",
                        process_gate.get("required_deliverables", []),
                    )
                ),
                "review_count": len(state_gate.get("reviews", [])),
                "latest_authorized_human_decision": _latest_human_decision(
                    state_gate.get("reviews", [])
                ),
            }
        )

    return {
        "document_schema_version": DOCUMENT_SCHEMA_VERSION,
        "framework_version": PUBLIC_VERSION,
        "package_version": PACKAGE_VERSION,
        "process_schema_version": process.get("schema_version"),
        "state_schema_version": state.get("schema_version"),
        "state_revision": state.get("revision"),
        "project": {
            "name": project.get("name"),
            "phase": project.get("phase"),
            "workflow_step": project.get("workflow_step"),
            "current_tr": project.get("current_tr"),
            "current_dcp": project.get("current_dcp"),
            "current_gate": project.get("current_gate"),
            "current_iteration_subject": project.get(
                "current_iteration_subject"
            ),
        },
        "deliverables": deliverables,
        "gates": gates,
    }


def _status_label(translator: Translator, status: Any) -> str:
    raw = "unknown" if status is None else str(status)
    key = f"status.{raw}"
    return translator.text(key) if translator.has_key(key) else raw


def _table_header(translator: Translator, columns: tuple[str, ...]) -> str:
    return "| " + " | ".join(
        translator.text(f"governance.column.{key}") for key in columns
    ) + " |"


def render_governance_document(
    process: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    translator: Translator | None = None,
    locale: str = "en",
) -> str:
    """Render one human-readable document with a machine-verifiable header."""

    translator = translator or get_translator(locale)
    model = build_governance_document_model(process, state)
    header = {
        "document_schema_version": model["document_schema_version"],
        "framework_version": model["framework_version"],
        "package_version": model["package_version"],
        "process_schema_version": model["process_schema_version"],
        "state_schema_version": model["state_schema_version"],
        "state_revision": model["state_revision"],
        "project": model["project"],
        "gate_ids": [item["id"] for item in model["gates"]],
        "gate_statuses": {
            item["id"]: item["status"] for item in model["gates"]
        },
    }
    front_matter = yaml.safe_dump(
        header,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip()
    project = model["project"]
    lines = [
        "---",
        front_matter,
        "---",
        "",
        f"# {translator.text('governance.title')}",
        "",
        f"> {translator.text('governance.generated_warning')}",
        "",
        f"- {translator.text('governance.framework_version')}: `{model['framework_version']}`",
        f"- {translator.text('governance.state_revision')}: `{model['state_revision']}`",
        f"- {translator.text('governance.project_phase')}: `{project.get('phase')}`",
        f"- {translator.text('governance.workflow_step')}: `{project.get('workflow_step')}`",
        f"- {translator.text('governance.current_gate')}: `{project.get('current_gate') or 'none'}`",
        f"- {translator.text('governance.current_subject')}: `{project.get('current_iteration_subject') or 'none'}`",
        "",
        f"## {translator.text('governance.deliverable_register')}",
        "",
        _table_header(translator, (
            "id", "title", "phase", "status", "evidence", "reviews", "human_decision"
        )),
        "|---|---|---|---|---:|---:|---|",
    ]
    for item in model["deliverables"]:
        status = item.get("status")
        decision = item.get("latest_authorized_human_decision") or "-"
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    f"`{item['id']}`",
                    item["title"],
                    item.get("phase") or "-",
                    f"`{status}` ({_status_label(translator, status)})",
                    item["evidence_count"],
                    item["review_count"],
                    decision,
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"## {translator.text('governance.gate_plan')}",
            "",
            _table_header(translator, (
                "id", "kind", "phase", "status", "required_deliverables", "reviews", "human_decision"
            )),
            "|---|---|---|---|---|---:|---|",
        ]
    )
    for item in model["gates"]:
        status = item.get("status")
        required = ", ".join(item.get("required_deliverables", [])) or "-"
        decision = item.get("latest_authorized_human_decision") or "-"
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    f"`{item['id']}`",
                    item.get("kind") or "-",
                    item.get("phase") or "-",
                    f"`{status}` ({_status_label(translator, status)})",
                    required,
                    item["review_count"],
                    decision,
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _front_matter(text: str) -> dict[str, Any] | None:
    if not text.startswith("---\n"):
        return None
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return None
    try:
        value = yaml.safe_load(text[4:marker])
    except yaml.YAMLError:
        return None
    return value if isinstance(value, dict) else None


def governance_document_issues(
    actual: str | None,
    process: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    translator: Translator | None = None,
    locale: str = "en",
) -> list[dict[str, str]]:
    """Compare governance.md to facts without trusting its own metadata."""

    translator = translator or get_translator(locale)
    path = "$.dashboard.governance"
    if actual is None:
        return [
            {
                "severity": "error",
                "code": "governance_document_missing",
                "path": path,
                "message": translator.text("report.governance.missing"),
            }
        ]
    expected_model = build_governance_document_model(process, state)
    expected = render_governance_document(
        process, state, translator=translator, locale=translator.locale
    )
    if actual == expected:
        return []
    header = _front_matter(actual)
    if header is None:
        code = "governance_document_invalid"
        message_key = "report.governance.invalid"
    elif any(
        header.get(field) != expected_model.get(field)
        for field in (
            "document_schema_version",
            "framework_version",
            "package_version",
            "process_schema_version",
            "state_schema_version",
        )
    ):
        code = "governance_document_version_stale"
        message_key = "report.governance.version_stale"
    elif header.get("gate_ids") != [item["id"] for item in expected_model["gates"]]:
        code = "governance_document_gate_ids_stale"
        message_key = "report.governance.gate_ids_stale"
    elif header.get("gate_statuses") != {
        item["id"]: item["status"] for item in expected_model["gates"]
    } or header.get("project") != expected_model["project"] or header.get(
        "state_revision"
    ) != expected_model["state_revision"]:
        code = "governance_document_gate_status_stale"
        message_key = "report.governance.status_stale"
    else:
        code = "governance_document_content_stale"
        message_key = "report.governance.content_stale"
    return [
        {
            "severity": "error",
            "code": code,
            "path": path,
            "message": translator.text(message_key),
        }
    ]


__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "build_governance_document_model",
    "governance_document_issues",
    "render_governance_document",
]

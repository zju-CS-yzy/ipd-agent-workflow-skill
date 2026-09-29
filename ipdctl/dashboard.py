"""Deterministic, dependency-free IPD dashboard rendering.

The dashboard is a read-only projection of ``tailored_process.yaml`` and the
project state.  This module deliberately contains no state transitions: users
must update facts through the runtime and regenerate these views.
"""

from __future__ import annotations

import html
import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


DASHBOARD_RELATIVE_PATH = Path(".ipd") / "dashboard"
DISPLAY_STATUSES = {"planned": "not_started", "accepted": "approved"}
PHASE_ORDER = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
RELATIONS = ("depends_on", "supports", "verifies", "supersedes")


def _string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [_string(item) for item in sorted(value)]
    if isinstance(value, Iterable):
        return [_string(item) for item in value if item is not None]
    return [_string(value)]


def _records(value: Any) -> list[dict[str, Any]]:
    """Normalize list- or mapping-shaped records without changing the input."""

    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, Mapping):
                records.append(dict(item))
            elif item is not None:
                records.append({"id": _string(item), "title": _string(item)})
        return records
    if isinstance(value, Mapping):
        records = []
        for identifier in sorted(value, key=str):
            item = value[identifier]
            if isinstance(item, Mapping):
                record = dict(item)
                record.setdefault("id", _string(identifier))
            else:
                record = {"id": _string(identifier), "title": _string(item)}
            records.append(record)
        return records
    return []


def _identifier(record: Mapping[str, Any], *fallback_keys: str) -> str:
    for key in ("id", *fallback_keys):
        value = record.get(key)
        if value is not None and _string(value).strip():
            return _string(value).strip()
    return ""


def _title(record: Mapping[str, Any], identifier: str) -> str:
    return _string(record.get("title") or record.get("name") or identifier)


def _phase_sort_key(phase: Mapping[str, Any]) -> tuple[int, int, str]:
    identifier = _identifier(phase, "phase")
    try:
        canonical = PHASE_ORDER.index(identifier)
    except ValueError:
        canonical = len(PHASE_ORDER)
    sequence = phase.get("sequence")
    sequence_value = sequence if type(sequence) is int else canonical
    return sequence_value, canonical, identifier


def _phase_records(process: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = _records(process.get("phases"))
    known = {_identifier(item, "phase") for item in records}
    current = _string((state.get("project") or {}).get("phase"))
    if current and current not in known:
        records.append({"id": current, "title": current})
    if not records:
        records = [{"id": item, "title": item} for item in PHASE_ORDER]
    return sorted(records, key=_phase_sort_key)


def _process_deliverables(process: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def add(record: Mapping[str, Any], *, phase: str = "", activity: str = "") -> None:
        identifier = _identifier(record, "deliverable_id", "artifact_id")
        if not identifier:
            return
        merged = dict(result.get(identifier, {}))
        merged.update(dict(record))
        merged["id"] = identifier
        if phase:
            merged.setdefault("phase", phase)
        if activity:
            merged.setdefault("activity_id", activity)
        result[identifier] = merged

    for item in _records(process.get("deliverables")):
        add(item)
    for phase_record in _records(process.get("phases")):
        phase_id = _identifier(phase_record, "phase")
        for item in _records(phase_record.get("deliverables")):
            add(item, phase=phase_id)
        for activity in _records(phase_record.get("activities")):
            activity_id = _identifier(activity, "activity_id")
            for item in _records(activity.get("deliverables")):
                add(item, phase=phase_id, activity=activity_id)
    return result


def _checkpoint_records(process: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def add(value: Any, kind: str, category: str, phase: str = "") -> None:
        for item in _records(value):
            record = dict(item)
            record.setdefault("kind", kind)
            record["_category"] = category
            if phase:
                record.setdefault("phase", phase)
            if _identifier(record, "checkpoint_id", "gate_id"):
                result.append(record)

    add(process.get("technical_reviews") or process.get("trs"), "TR", "tr")
    add(process.get("decision_checkpoints") or process.get("dcps"), "DCP", "dcp")
    add(process.get("gates"), "Gate", "gate")
    for phase_record in _records(process.get("phases")):
        phase_id = _identifier(phase_record, "phase")
        add(
            phase_record.get("technical_reviews") or phase_record.get("trs"),
            "TR",
            "tr",
            phase_id,
        )
        add(
            phase_record.get("decision_checkpoints") or phase_record.get("dcps"),
            "DCP",
            "dcp",
            phase_id,
        )
        add(phase_record.get("gates"), "Gate", "gate", phase_id)

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for record in result:
        identifier = _identifier(record, "checkpoint_id", "gate_id")
        category = _string(record.get("_category") or "gate")
        unique[(category, identifier)] = record
    return sorted(
        unique.values(),
        key=lambda item: (
            _string(item.get("phase")),
            item.get("sequence") if type(item.get("sequence")) is int else 10_000,
            _string(item.get("_category")),
            _identifier(item, "checkpoint_id", "gate_id"),
        ),
    )


def _state_deliverables(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        identifier: record
        for record in _records(state.get("deliverables"))
        if (identifier := _identifier(record, "deliverable_id"))
    }


def _state_gates(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        identifier: record
        for record in _records(state.get("gates"))
        if (identifier := _identifier(record, "gate_id", "checkpoint_id"))
    }


def _display_status(status: str) -> str:
    return DISPLAY_STATUSES.get(status, status)


def _checkpoint_status(
    record: Mapping[str, Any], state_gates: Mapping[str, Mapping[str, Any]], current: str
) -> str:
    identifier = _identifier(record, "checkpoint_id", "gate_id")
    gate_id = _string(record.get("gate_id"))
    state_record = state_gates.get(identifier) or state_gates.get(gate_id)
    if state_record:
        return _string(state_record.get("status"), "planned")
    if identifier == current or (gate_id and gate_id == current):
        return "current"
    return _string(record.get("status"), "planned")


def _build_process_view(
    process: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    project = state.get("project") if isinstance(state.get("project"), Mapping) else {}
    current_phase = _string(project.get("phase"))
    current = {
        "phase": current_phase or None,
        "tr": project.get("current_tr"),
        "dcp": project.get("current_dcp"),
        "gate": project.get("current_gate"),
    }
    gates = _state_gates(state)
    checkpoints = _checkpoint_records(process)
    deliverables = _process_deliverables(process)
    phases: list[dict[str, Any]] = []
    for phase in _phase_records(process, state):
        phase_id = _identifier(phase, "phase")
        phase_checkpoints = [
            item for item in checkpoints if _string(item.get("phase")) == phase_id
        ]

        def summaries(category: str) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            for item in phase_checkpoints:
                if item.get("_category") != category:
                    continue
                identifier = _identifier(item, "checkpoint_id", "gate_id")
                current_id = _string(current.get(category))
                rows.append(
                    {
                        "id": identifier,
                        "title": _title(item, identifier),
                        "status": _checkpoint_status(item, gates, current_id),
                    }
                )
            return rows

        generic_gates = [
            item
            for item in phase_checkpoints
            if item.get("_category") == "gate"
        ]
        gate_rows = []
        for item in generic_gates:
            identifier = _identifier(item, "checkpoint_id", "gate_id")
            gate_rows.append(
                {
                    "id": identifier,
                    "title": _title(item, identifier),
                    "status": _checkpoint_status(
                        item, gates, _string(current.get("gate"))
                    ),
                }
            )
        phase_status = "current" if phase_id == current_phase else _string(
            phase.get("status"), "planned"
        )
        phases.append(
            {
                "id": phase_id,
                "title": _title(phase, phase_id),
                "status": phase_status,
                "technical_reviews": summaries("tr"),
                "decision_checkpoints": summaries("dcp"),
                "gates": gate_rows,
                "deliverable_count": sum(
                    1
                    for item in deliverables.values()
                    if _string(item.get("phase")) == phase_id
                ),
            }
        )
    return {
        "schema_version": "1.0",
        "view": "ipd_process",
        "source_revision": state.get("revision"),
        "project": _string(project.get("name") or (process.get("profile") or {}).get("name")),
        "current": current,
        "phases": phases,
    }


def _build_deliverable_matrix(
    process: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    process_items = _process_deliverables(process)
    state_items = _state_deliverables(state)
    identifiers = sorted(set(process_items) | set(state_items))
    rows: list[dict[str, Any]] = []
    for identifier in identifiers:
        process_item = process_items.get(identifier, {})
        state_item = state_items.get(identifier, {})
        status = _string(state_item.get("status"), "planned")
        reviews = [dict(item) for item in _records(state_item.get("reviews"))]
        rows.append(
            {
                "id": identifier,
                "title": _title(state_item or process_item, identifier),
                "phase": _string(state_item.get("phase") or process_item.get("phase")) or None,
                "activity": _string(
                    state_item.get("activity_id") or process_item.get("activity_id")
                )
                or None,
                "status": status,
                "display_status": _display_status(status),
                "depends_on": sorted(
                    set(
                        _string_list(
                            state_item.get("depends_on", process_item.get("depends_on"))
                        )
                    )
                ),
                "review_required": bool(
                    state_item.get(
                        "review_required", process_item.get("review_required", False)
                    )
                ),
                "evidence": sorted(set(_string_list(state_item.get("evidence")))),
                "reviews": reviews,
                "blocker": state_item.get("blocked_reason") or state_item.get("blocker"),
                "replacement": state_item.get("replacement"),
            }
        )
    return {
        "schema_version": "1.0",
        "view": "deliverable_matrix",
        "source_revision": state.get("revision"),
        "deliverables": rows,
    }


def _edge(record: Mapping[str, Any]) -> dict[str, str] | None:
    source = record.get("source") or record.get("from")
    target = record.get("target") or record.get("to")
    relation = _string(record.get("relation") or record.get("type"), "depends_on")
    if not source or not target or relation not in RELATIONS:
        return None
    return {"source": _string(source), "target": _string(target), "relation": relation}


def _build_dependency_graph(
    process: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    matrix = _build_deliverable_matrix(process, state)
    current_phase = _string((state.get("project") or {}).get("phase"))
    all_rows = matrix["deliverables"]
    has_phase_assignments = any(item.get("phase") for item in all_rows)
    if current_phase and has_phase_assignments:
        primary_rows = [
            item
            for item in all_rows
            if item.get("phase") in {None, current_phase}
        ]
    else:
        primary_rows = list(all_rows)

    candidates: list[dict[str, str]] = []
    for item in all_rows:
        for dependency in item["depends_on"]:
            candidates.append(
                {"source": item["id"], "target": dependency, "relation": "depends_on"}
            )
        if item.get("replacement"):
            candidates.append(
                {
                    "source": item["id"],
                    "target": _string(item["replacement"]),
                    "relation": "supersedes",
                }
            )
    for item in _records(process.get("dependencies")):
        normalized = _edge(item)
        if normalized:
            candidates.append(normalized)
    for item in _records(state.get("traceability")):
        normalized = _edge(item)
        if normalized:
            candidates.append(normalized)

    all_node_ids = {item["id"] for item in all_rows}
    node_ids = {item["id"] for item in primary_rows}
    # Keep upstream prerequisites visible even when they belong to an earlier
    # phase; otherwise the current-phase graph would hide the reason work is
    # blocked.  Do not pull in later-phase dependants.
    changed = True
    while changed:
        changed = False
        for item in candidates:
            if (
                item["relation"] == "depends_on"
                and item["source"] in node_ids
                and item["target"] in all_node_ids
                and item["target"] not in node_ids
            ):
                node_ids.add(item["target"])
                changed = True
    for item in candidates:
        if item["source"] in node_ids and item["target"] in all_node_ids:
            node_ids.add(item["target"])
    rows = [item for item in all_rows if item["id"] in node_ids]

    edges = {
        (item["source"], item["target"], item["relation"])
        for item in candidates
        if item["source"] in node_ids and item["target"] in node_ids
    }
    return {
        "schema_version": "1.0",
        "view": "deliverable_dependency_graph",
        "source_revision": state.get("revision"),
        "current_phase": current_phase or None,
        "status_aliases": dict(DISPLAY_STATUSES),
        "nodes": [
            {
                "id": item["id"],
                "title": item["title"],
                "phase": item["phase"],
                "status": item["status"],
                "display_status": item["display_status"],
                "in_current_phase": not current_phase
                or item["phase"] in {None, current_phase},
            }
            for item in rows
        ],
        "edges": [
            {"source": source, "target": target, "relation": relation}
            for source, target, relation in sorted(edges)
        ],
    }


def _review_records(value: Any) -> list[dict[str, Any]]:
    reviews = _records(value)
    return sorted(
        reviews,
        key=lambda item: (
            _string(item.get("reviewer")),
            _string(item.get("decision")),
            _string(item.get("evidence")),
        ),
    )


def _build_gate_matrix(
    process: Mapping[str, Any], state: Mapping[str, Any]
) -> dict[str, Any]:
    state_items = _state_gates(state)
    process_items: dict[str, dict[str, Any]] = {}
    for item in _records(process.get("gates")):
        identifier = _identifier(item, "gate_id", "checkpoint_id")
        if identifier:
            process_items[identifier] = item
    deliverables = _state_deliverables(state)
    rows: list[dict[str, Any]] = []
    for identifier in sorted(set(process_items) | set(state_items)):
        process_item = process_items.get(identifier, {})
        state_item = state_items.get(identifier, {})
        required = sorted(
            set(
                _string_list(
                    state_item.get(
                        "required_deliverables",
                        process_item.get("required_deliverables"),
                    )
                )
            )
        )
        blockers = []
        for deliverable_id in required:
            status = _string(deliverables.get(deliverable_id, {}).get("status"), "missing")
            if status != "accepted":
                blockers.append({"deliverable": deliverable_id, "status": status})
        for blocker in _string_list(state_item.get("blockers")):
            blockers.append({"deliverable": None, "status": blocker})
        reviews = _review_records(state_item.get("reviews"))
        evidence = sorted(
            set(
                _string_list(state_item.get("evidence"))
                + [
                    _string(review.get("evidence"))
                    for review in reviews
                    if review.get("evidence")
                ]
            )
        )
        authorized_approvals = [
            review
            for review in reviews
            if review.get("reviewer_type") == "human"
            and review.get("authorized") is True
            and review.get("decision") == "approve"
        ]
        authorized_rejections = [
            review
            for review in reviews
            if review.get("reviewer_type") == "human"
            and review.get("authorized") is True
            and review.get("decision") == "reject"
        ]
        status = _string(state_item.get("status") or process_item.get("status"), "planned")
        if authorized_rejections or status == "rejected":
            approval_status = "rejected"
        elif status == "approved" and authorized_approvals:
            approval_status = "approved"
        else:
            approval_status = "pending"
        rows.append(
            {
                "id": identifier,
                "title": _title(state_item or process_item, identifier),
                "kind": _string(state_item.get("kind") or process_item.get("kind"), "Gate"),
                "phase": _string(state_item.get("phase") or process_item.get("phase")) or None,
                "status": status,
                "required_deliverables": required,
                "readiness": {
                    "ready": not blockers,
                    "accepted": sum(
                        deliverables.get(item, {}).get("status") == "accepted"
                        for item in required
                    ),
                    "required": len(required),
                },
                "evidence": evidence,
                "blockers": blockers,
                "approval": {
                    "status": approval_status,
                    "authorized_human": bool(authorized_approvals),
                    "reviews": reviews,
                },
            }
        )
    return {
        "schema_version": "1.0",
        "view": "gate_matrix",
        "source_revision": state.get("revision"),
        "gates": rows,
    }


def _json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _html_document(title: str, body: str, data: Mapping[str, Any]) -> str:
    serialized = html.escape(_json_text(data), quote=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title, quote=True)}</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ margin: 0 auto; max-width: 1200px; padding: 2rem; line-height: 1.45; }}
a {{ color: #2f6feb; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
th, td {{ border: 1px solid #8886; padding: .55rem; text-align: left; vertical-align: top; }}
th {{ background: #8882; }}
code, pre {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
pre {{ overflow: auto; padding: 1rem; background: #8881; }}
.flow {{ display: flex; gap: .75rem; list-style: none; overflow-x: auto; padding: 0 0 1rem; }}
.flow > li {{ border: 1px solid #8886; border-radius: .5rem; min-width: 12rem; padding: .75rem; }}
.flow > li[aria-current="step"] {{ border-color: #2f6feb; box-shadow: inset 0 0 0 1px #2f6feb; }}
.graph {{ max-width: 100%; height: auto; border: 1px solid #8884; background: #fff; color: #172033; }}
.muted {{ opacity: .72; }}
</style>
</head>
<body>
<nav><a href="index.html">Dashboard index</a></nav>
<h1>{html.escape(title, quote=True)}</h1>
{body}
<details><summary>Canonical view data</summary><pre>{serialized}</pre></details>
</body>
</html>
"""


def _html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{html.escape(_string(item), quote=True)}</th>" for item in headers)
    rendered_rows = []
    for row in rows:
        rendered_rows.append(
            "<tr>"
            + "".join(f"<td>{html.escape(_string(item), quote=True)}</td>" for item in row)
            + "</tr>"
        )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rendered_rows)}</tbody></table>"


def _markdown_cell(value: Any) -> str:
    text = _string(value).replace("\r", " ").replace("\n", "; ")
    return html.escape(text, quote=False).replace("|", "\\|")


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(_markdown_cell(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_markdown_cell(item) for item in row) + " |" for row in rows
    )
    return "\n".join(lines)


def _list_summary(items: Sequence[Mapping[str, Any]]) -> str:
    return "; ".join(
        f"{item.get('id')} ({item.get('status')})" for item in items
    ) or "-"


def _process_flow_html(phases: Sequence[Mapping[str, Any]]) -> str:
    items: list[str] = []
    for phase in phases:
        current = ' aria-current="step"' if phase.get("status") == "current" else ""
        details = (
            f"TR: {_list_summary(phase['technical_reviews'])}<br>"
            f"DCP: {_list_summary(phase['decision_checkpoints'])}<br>"
            f"Gate: {_list_summary(phase['gates'])}"
        )
        items.append(
            f"<li{current}><strong>{html.escape(_string(phase['title']), quote=True)}</strong>"
            f"<br><span class=\"muted\">{html.escape(_string(phase['status']), quote=True)}</span>"
            f"<p>{html.escape(details, quote=True).replace('&lt;br&gt;', '<br>')}</p></li>"
        )
    return f"<ol class=\"flow\">{''.join(items)}</ol>"


def _process_documents(data: Mapping[str, Any]) -> tuple[str, str]:
    current = data["current"]
    rows = [
        (
            item["id"],
            item["title"],
            item["status"],
            _list_summary(item["technical_reviews"]),
            _list_summary(item["decision_checkpoints"]),
            _list_summary(item["gates"]),
            item["deliverable_count"],
        )
        for item in data["phases"]
    ]
    summary_values = (
        _string(current.get("phase"), "-"),
        _string(current.get("tr"), "-"),
        _string(current.get("dcp"), "-"),
        _string(current.get("gate"), "-"),
    )
    summary = (
        f"Current phase: {summary_values[0]} | "
        f"TR: {summary_values[1]} | "
        f"DCP: {summary_values[2]} | "
        f"Gate: {summary_values[3]}"
    )
    headers = ("Phase", "Title", "Status", "TR", "DCP", "Gate", "Deliverables")
    html_body = (
        f"<p>{html.escape(summary, quote=True)}</p>"
        + _process_flow_html(data["phases"])
        + _html_table(headers, rows)
    )
    safe_summary = " | ".join(
        (
            f"Current phase: {_markdown_cell(summary_values[0])}",
            f"TR: {_markdown_cell(summary_values[1])}",
            f"DCP: {_markdown_cell(summary_values[2])}",
            f"Gate: {_markdown_cell(summary_values[3])}",
        )
    )
    markdown = f"# IPD Process\n\n{safe_summary}\n\n{_markdown_table(headers, rows)}\n"
    return _html_document("IPD Process", html_body, data), markdown


def _deliverable_documents(data: Mapping[str, Any]) -> tuple[str, str]:
    rows = [
        (
            item["id"],
            item["title"],
            item["phase"] or "-",
            item["activity"] or "-",
            item["status"],
            item["display_status"],
            ", ".join(item["depends_on"]) or "-",
            "yes" if item["review_required"] else "no",
            ", ".join(item["evidence"]) or "-",
            item["blocker"] or "-",
        )
        for item in data["deliverables"]
    ]
    headers = (
        "ID",
        "Title",
        "Phase",
        "Activity",
        "Canonical status",
        "Display status",
        "Depends on",
        "Review required",
        "Evidence",
        "Blocker",
    )
    table = _html_table(headers, rows)
    markdown = f"# Deliverable Matrix\n\n{_markdown_table(headers, rows)}\n"
    return _html_document("Deliverable Matrix", table, data), markdown


def _graph_svg(data: Mapping[str, Any]) -> str:
    nodes = list(data["nodes"])
    if not nodes:
        return '<p class="muted">No deliverables belong to the current phase.</p>'
    columns = min(3, len(nodes))
    cell_width, cell_height = 250, 115
    box_width, box_height = 210, 62
    positions: dict[str, tuple[int, int]] = {}
    for index, node in enumerate(nodes):
        column, row = index % columns, index // columns
        positions[node["id"]] = (25 + column * cell_width, 25 + row * cell_height)
    rows = (len(nodes) + columns - 1) // columns
    width, height = columns * cell_width + 10, rows * cell_height + 20
    edge_parts: list[str] = []
    for edge in data["edges"]:
        source = positions.get(edge["source"])
        target = positions.get(edge["target"])
        if source is None or target is None:
            continue
        x1, y1 = source[0] + box_width / 2, source[1] + box_height / 2
        x2, y2 = target[0] + box_width / 2, target[1] + box_height / 2
        relation = html.escape(_string(edge["relation"]), quote=True)
        edge_parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            'stroke="#6b7280" stroke-width="1.5" marker-end="url(#arrow)"/>'
            f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 4}" '
            f'text-anchor="middle" font-size="10">{relation}</text>'
        )
    node_parts: list[str] = []
    for node in nodes:
        x, y = positions[node["id"]]
        identifier = html.escape(_string(node["id"]), quote=True)
        title = html.escape(_string(node["title"]), quote=True)
        status = html.escape(_string(node["display_status"]), quote=True)
        node_parts.append(
            f'<g><title>{title} - {status}</title>'
            f'<rect x="{x}" y="{y}" width="{box_width}" height="{box_height}" '
            'rx="8" fill="#eef4ff" stroke="#3768a6"/>'
            f'<text x="{x + 10}" y="{y + 24}" font-size="13" font-weight="600">{identifier}</text>'
            f'<text x="{x + 10}" y="{y + 46}" font-size="11">{status}</text></g>'
        )
    return (
        f'<svg class="graph" role="img" aria-label="Deliverable dependency graph" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#6b7280"/></marker></defs>'
        + "".join(edge_parts)
        + "".join(node_parts)
        + "</svg>"
    )


def _graph_documents(data: Mapping[str, Any]) -> tuple[str, str]:
    node_rows = [
        (
            item["id"],
            item["title"],
            item["phase"] or "-",
            "current" if item["in_current_phase"] else "upstream",
            item["status"],
            item["display_status"],
        )
        for item in data["nodes"]
    ]
    edge_rows = [
        (item["source"], item["relation"], item["target"]) for item in data["edges"]
    ]
    node_headers = (
        "Deliverable",
        "Title",
        "Phase",
        "Context",
        "Canonical status",
        "Display status",
    )
    edge_headers = ("Source", "Relation", "Target")
    body = (
        f"<p>Current phase: {html.escape(_string(data.get('current_phase'), '-'), quote=True)}</p>"
        + _graph_svg(data)
        + "<h2>Nodes</h2>"
        + _html_table(node_headers, node_rows)
        + "<h2>Edges</h2>"
        + _html_table(edge_headers, edge_rows)
    )
    markdown = (
        "# Deliverable Dependency Graph\n\n"
        f"Current phase: {_markdown_cell(data.get('current_phase') or '-')}\n\n"
        f"## Nodes\n\n{_markdown_table(node_headers, node_rows)}\n\n"
        f"## Edges\n\n{_markdown_table(edge_headers, edge_rows)}\n"
    )
    return _html_document("Deliverable Dependency Graph", body, data), markdown


def _gate_documents(data: Mapping[str, Any]) -> tuple[str, str]:
    rows = []
    for item in data["gates"]:
        blockers = ", ".join(
            f"{entry.get('deliverable') or 'gate'}:{entry.get('status')}"
            for entry in item["blockers"]
        ) or "-"
        readiness = item["readiness"]
        rows.append(
            (
                item["id"],
                item["title"],
                item["kind"],
                item["phase"] or "-",
                item["status"],
                f"{readiness['accepted']}/{readiness['required']} ({'ready' if readiness['ready'] else 'blocked'})",
                ", ".join(item["evidence"]) or "-",
                blockers,
                item["approval"]["status"],
            )
        )
    headers = (
        "ID",
        "Title",
        "Kind",
        "Phase",
        "Status",
        "Readiness",
        "Evidence",
        "Blockers",
        "Approval",
    )
    table = _html_table(headers, rows)
    markdown = f"# Gate Matrix\n\n{_markdown_table(headers, rows)}\n"
    return _html_document("Gate Matrix", table, data), markdown


def _index_document(project: str, revision: Any) -> str:
    safe_project = html.escape(project or "IPD project", quote=True)
    safe_revision = html.escape(_string(revision, "-"), quote=True)
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_project} - IPD Dashboard</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ margin: 0 auto; max-width: 900px; padding: 2rem; line-height: 1.5; }}
li {{ margin: .7rem 0; }} a {{ color: #2f6feb; }}
</style>
</head>
<body>
<h1>{safe_project} - IPD Dashboard</h1>
<p>Source state revision: {safe_revision}. Generated views are read-only.</p>
<ul>
<li><a href="ipd_process.html">IPD process</a> (<a href="ipd_process.json">JSON</a>, <a href="ipd_process.md">Markdown</a>)</li>
<li><a href="deliverable_dependency_graph.html">Deliverable dependency graph</a> (<a href="deliverable_dependency_graph.json">JSON</a>, <a href="deliverable_dependency_graph.md">Markdown</a>)</li>
<li><a href="deliverable_matrix.html">Deliverable matrix</a> (<a href="deliverable_matrix.json">JSON</a>, <a href="deliverable_matrix.md">Markdown</a>)</li>
<li><a href="gate_matrix.html">Gate matrix</a> (<a href="gate_matrix.json">JSON</a>, <a href="gate_matrix.md">Markdown</a>)</li>
</ul>
</body>
</html>
"""
    return body


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(text)
            temporary_name = handle.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_dashboard(
    project_root: str | Path,
    process: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    """Render all dashboard views and return the written manifest.

    No timestamps or absolute paths are emitted, so the same process and state
    produce byte-for-byte identical files regardless of checkout location.
    """

    if not isinstance(process, Mapping):
        raise TypeError("process must be a mapping")
    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")

    output = Path(project_root) / DASHBOARD_RELATIVE_PATH
    output.mkdir(parents=True, exist_ok=True)
    views = {
        "ipd_process": _build_process_view(process, state),
        "deliverable_dependency_graph": _build_dependency_graph(process, state),
        "deliverable_matrix": _build_deliverable_matrix(process, state),
        "gate_matrix": _build_gate_matrix(process, state),
    }
    renderers = {
        "ipd_process": _process_documents,
        "deliverable_dependency_graph": _graph_documents,
        "deliverable_matrix": _deliverable_documents,
        "gate_matrix": _gate_documents,
    }

    project = _string(
        (state.get("project") or {}).get("name")
        or (process.get("profile") or {}).get("name")
    )
    _atomic_write(output / "index.html", _index_document(project, state.get("revision")))
    for name in sorted(views):
        data = views[name]
        html_text, markdown_text = renderers[name](data)
        _atomic_write(output / f"{name}.html", html_text)
        _atomic_write(output / f"{name}.json", _json_text(data))
        _atomic_write(output / f"{name}.md", markdown_text)

    filenames = ["index.html"]
    for name in sorted(views):
        filenames.extend(f"{name}.{extension}" for extension in ("html", "json", "md"))
    outputs = [
        {
            "path": (DASHBOARD_RELATIVE_PATH / filename).as_posix(),
            "sha256": _sha256(output / filename),
        }
        for filename in filenames
    ]
    filenames.append("manifest.json")
    manifest = {
        "schema_version": "1.0",
        "output_directory": DASHBOARD_RELATIVE_PATH.as_posix(),
        "project": project,
        "state_revision": state.get("revision"),
        "source_revision": state.get("revision"),
        "process_schema_version": process.get("schema_version"),
        "files": filenames,
        "outputs": outputs,
        "views": {
            name: {
                "html": f"{name}.html",
                "json": f"{name}.json",
                "markdown": f"{name}.md",
            }
            for name in sorted(views)
        },
    }
    _atomic_write(output / "manifest.json", _json_text(manifest))
    return manifest


__all__ = ["DASHBOARD_RELATIVE_PATH", "render_dashboard"]

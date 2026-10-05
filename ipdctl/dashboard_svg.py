"""Deterministic SVG rendering for IPD dashboard graphs.

The renderer deliberately uses only the Python standard library.  It keeps the
layout data-driven and testable: every rendered node exposes its calculated
bounding box as ``data-*`` attributes and every relationship is an orthogonal
path with a relation-specific marker and line style.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from html import escape
from typing import Any, Iterable, Mapping, Sequence
import unicodedata
from urllib.parse import quote


PHASE_ORDER = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
TYPE_ORDER = {"Phase": 0, "TR": 1, "DCP": 2, "Gate": 3, "Activity": 4, "Deliverable": 5}
RELATION_ORDER = {
    "depends_on": 0,
    "supports": 1,
    "verifies": 2,
    "supersedes": 3,
    "refines": 4,
}

STATUS_ALIASES = {"not_started": "planned", "approved": "accepted"}
STATUS_STYLES = {
    "planned": ("#F8FAFC", "#98A2B3", "4 3"),
    "in_progress": ("#EFF8FF", "#1570EF", ""),
    "ready_for_review": ("#FFFAEB", "#DC6803", ""),
    "in_review": ("#F9F5FF", "#7F56D9", ""),
    "accepted": ("#ECFDF3", "#039855", ""),
    "rejected": ("#FEF3F2", "#D92D20", ""),
    "blocked": ("#FFF1F3", "#C01048", "6 3"),
    "superseded": ("#F2F4F7", "#667085", "2 4"),
}
RELATION_STYLES = {
    "depends_on": ("#475467", "", "arrow-depends"),
    "supports": ("#1570EF", "6 4", "arrow-supports"),
    "verifies": ("#7F56D9", "2 4", "arrow-verifies"),
    "supersedes": ("#DC6803", "10 4 2 4", "arrow-supersedes"),
    "refines": ("#0E9384", "5 4", "arrow-refines"),
}


@dataclass(frozen=True)
class _Node:
    id: str
    type: str
    title: str
    phase: str
    status: str
    current: bool
    blocked: bool
    refinement_due: bool
    detail_key: str


@dataclass(frozen=True)
class _Edge:
    source: str
    target: str
    relation: str


@dataclass(frozen=True)
class _Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _t(translator: Any, key: str, fallback: str, **params: Any) -> str:
    try:
        value = translator.text(key, **params)
    except (AttributeError, KeyError, TypeError, ValueError):
        value = key
    if value == key:
        try:
            return fallback.format(**params)
        except (KeyError, ValueError):
            return fallback
    return value


def _translator(value: Any = None, locale: str = "en") -> Any:
    if value is not None:
        return value
    from .i18n import get_translator

    return get_translator(locale)


def _canonical_type(value: Any) -> str:
    raw = _text(value).strip().lower().replace("_", "")
    return {
        "phase": "Phase",
        "tr": "TR",
        "technicalreview": "TR",
        "dcp": "DCP",
        "decisioncheckpoint": "DCP",
        "gate": "Gate",
        "activity": "Activity",
        "deliverable": "Deliverable",
    }.get(raw, "Deliverable")


def _canonical_status(value: Any) -> str:
    status = _text(value).strip().lower() or "planned"
    status = STATUS_ALIASES.get(status, status)
    return status if status in STATUS_STYLES else "planned"


def _normalise_graph(graph: Mapping[str, Any]) -> tuple[list[_Node], list[_Edge]]:
    nodes: list[_Node] = []
    seen: set[str] = set()
    for raw in graph.get("nodes", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        node_id = _text(raw.get("id")).strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        node_type = _canonical_type(raw.get("type"))
        phase = _text(raw.get("phase")).strip().lower()
        if node_type == "Phase" and not phase:
            phase = node_id.lower()
        status = _canonical_status(raw.get("status"))
        nodes.append(
            _Node(
                id=node_id,
                type=node_type,
                title=_text(raw.get("display_label") or raw.get("title")).strip() or node_id,
                phase=phase or "unassigned",
                status=status,
                current=bool(raw.get("current")),
                blocked=bool(raw.get("blocked")) or status == "blocked",
                refinement_due=raw.get("refinement_due") is True,
                detail_key=_text(raw.get("detail_key")).strip() or f"{node_type.lower()}:{node_id}",
            )
        )

    valid = {node.id for node in nodes}
    edges: list[_Edge] = []
    edge_keys: set[tuple[str, str, str]] = set()
    for raw in graph.get("edges", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        source = _text(raw.get("source")).strip()
        target = _text(raw.get("target")).strip()
        relation = _text(raw.get("relation")).strip().lower()
        if source not in valid or target not in valid or source == target:
            continue
        if relation not in RELATION_STYLES:
            relation = "depends_on"
        key = (source, target, relation)
        if key not in edge_keys:
            edge_keys.add(key)
            edges.append(_Edge(*key))

    nodes.sort(key=lambda item: (_phase_key(item.phase), TYPE_ORDER[item.type], item.id))
    edges.sort(key=lambda item: (RELATION_ORDER[item.relation], item.source, item.target))
    return nodes, edges


def _phase_key(phase: str) -> tuple[int, str]:
    try:
        return PHASE_ORDER.index(phase), phase
    except ValueError:
        return len(PHASE_ORDER), phase


def _phase_label(phase: str, translator: Any) -> str:
    fallback = phase.replace("_", " ").replace("-", " ").title()
    return _t(translator, f"phase.{phase}", fallback)


def _display_width(value: str) -> int:
    width = 0
    for character in value:
        if unicodedata.combining(character):
            continue
        width += 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
    return width


def _split_width(value: str, limit: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    width = 0
    for character in value:
        character_width = _display_width(character)
        if current and width + character_width > limit:
            chunks.append(current)
            current = character
            width = character_width
        else:
            current += character
            width += character_width
    if current:
        chunks.append(current)
    return chunks or [""]


def _wrap_text(value: str, max_chars: int, max_lines: int = 3) -> list[str]:
    value = " ".join(value.split())
    if not value:
        return [""]
    words = value.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        chunks = _split_width(word, max_chars) if _display_width(word) > max_chars else [word]
        for chunk in chunks:
            candidate = f"{current} {chunk}".strip()
            if current and _display_width(candidate) > max_chars:
                lines.append(current)
                current = chunk
            else:
                current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        tail = lines[-1]
        truncated = _split_width(tail, max(1, max_chars - 1))[0].rstrip()
        lines[-1] = truncated + "…"
    return lines


def _node_size(node: _Node) -> tuple[float, float]:
    return {
        "Phase": (244, 58),
        "TR": (196, 58),
        "DCP": (190, 84),
        "Gate": (216, 68),
        "Activity": (244, 62),
        "Deliverable": (264, 92),
    }[node.type]


def _topological_levels(nodes: Sequence[_Node], edges: Sequence[_Edge]) -> dict[str, int]:
    """Return execution levels using only canonical dependency facts.

    ``depends_on`` edges are stored as ``dependent -> prerequisite`` in the
    graph contract.  Execution diagrams intentionally project that fact in the
    readable direction ``prerequisite -> dependent``.  Traceability relations
    must never influence the execution rank.
    """

    ids = {node.id for node in nodes}
    incoming: dict[str, int] = {node.id: 0 for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.source in ids and edge.target in ids and edge.relation == "depends_on":
            prerequisite = edge.target
            dependent = edge.source
            outgoing[prerequisite].append(dependent)
            incoming[dependent] += 1
    queue = deque(sorted((node_id for node_id, count in incoming.items() if count == 0)))
    levels = {node_id: 0 for node_id in incoming}
    visited: set[str] = set()
    while queue:
        source = queue.popleft()
        visited.add(source)
        for target in sorted(outgoing[source]):
            levels[target] = max(levels[target], levels[source] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    # Cyclic/feedback nodes remain deterministic and are placed after their
    # strongest already-known prerequisite without attempting to break the
    # canonical data.
    for node_id in sorted(set(incoming) - visited):
        prerequisites = [
            edge.target
            for edge in edges
            if edge.relation == "depends_on"
            and edge.source == node_id
            and edge.target in visited
        ]
        levels[node_id] = max(
            (levels[prerequisite] + 1 for prerequisite in prerequisites),
            default=0,
        )
    return levels


def _process_layout(nodes: Sequence[_Node], edges: Sequence[_Edge]) -> tuple[dict[str, _Box], list[tuple[str, _Box]], float, float]:
    phases = sorted({node.phase for node in nodes}, key=_phase_key) or ["unassigned"]
    lane_width = 326.0
    lane_gap = 24.0
    margin_x = 36.0
    top = 96.0
    header_height = 126.0
    item_gap = 24.0
    grouped: dict[str, list[_Node]] = defaultdict(list)
    levels = _topological_levels(nodes, edges)
    for node in nodes:
        grouped[node.phase].append(node)
    for phase in phases:
        grouped[phase].sort(key=lambda node: (levels.get(node.id, 0), TYPE_ORDER[node.type], node.id))

    max_content = max(
        (
            sum(_node_size(node)[1] + item_gap for node in grouped[phase] if node.type != "Phase")
            + header_height
            + 26
        )
        for phase in phases
    )
    lane_height = max(400.0, max_content)
    boxes: dict[str, _Box] = {}
    lanes: list[tuple[str, _Box]] = []
    for lane_index, phase in enumerate(phases):
        lane_x = margin_x + lane_index * (lane_width + lane_gap)
        lane_box = _Box(lane_x, top, lane_width, lane_height)
        lanes.append((phase, lane_box))
        phase_nodes = [node for node in grouped[phase] if node.type == "Phase"]
        for index, node in enumerate(phase_nodes):
            width, height = _node_size(node)
            boxes[node.id] = _Box(lane_x + (lane_width - width) / 2, top + 48 + index * 62, width, height)
        cursor_y = top + header_height + 24
        for node in grouped[phase]:
            if node.type == "Phase":
                continue
            width, height = _node_size(node)
            boxes[node.id] = _Box(lane_x + (lane_width - width) / 2, cursor_y, width, height)
            cursor_y += height + item_gap
    width = margin_x * 2 + len(phases) * lane_width + (len(phases) - 1) * lane_gap
    height = top + lane_height + 238
    return boxes, lanes, width, height


def _dependency_layout(nodes: Sequence[_Node], edges: Sequence[_Edge]) -> tuple[dict[str, _Box], list[tuple[str, _Box]], float, float]:
    phases = sorted({node.phase for node in nodes}, key=_phase_key) or ["unassigned"]
    levels = _topological_levels(nodes, edges)
    max_level = max(levels.values(), default=0)
    column_width = 316.0
    margin_x = 46.0
    top = 96.0
    lane_gap = 28.0
    node_gap = 22.0
    boxes: dict[str, _Box] = {}
    lanes: list[tuple[str, _Box]] = []
    cursor_y = top

    for phase in phases:
        phase_nodes = [node for node in nodes if node.phase == phase and node.type != "Phase"]
        phase_header = [node for node in nodes if node.phase == phase and node.type == "Phase"]
        columns: dict[int, list[_Node]] = defaultdict(list)
        for node in phase_nodes:
            columns[levels.get(node.id, 0)].append(node)
        for column in columns.values():
            column.sort(key=lambda node: (TYPE_ORDER[node.type], node.id))
        max_column_height = max(
            (sum(_node_size(node)[1] + node_gap for node in column) for column in columns.values()),
            default=180.0,
        )
        lane_height = max(286.0, max_column_height + 122.0)
        lane_width = (max_level + 1) * column_width + 52.0
        lane_box = _Box(margin_x, cursor_y, lane_width, lane_height)
        lanes.append((phase, lane_box))
        for index, node in enumerate(phase_header):
            width, height = _node_size(node)
            boxes[node.id] = _Box(margin_x + 18 + index * (width + 12), cursor_y + 48, width, height)
        for level in range(max_level + 1):
            column = columns.get(level, [])
            y = cursor_y + 126.0
            for node in column:
                width, height = _node_size(node)
                x = margin_x + 26 + level * column_width + (column_width - width) / 2
                boxes[node.id] = _Box(x, y, width, height)
                y += height + node_gap
        cursor_y += lane_height + lane_gap

    width = margin_x * 2 + (max_level + 1) * column_width + 52.0
    height = cursor_y - lane_gap + 238.0
    return boxes, lanes, width, height


def _filter_graph(
    nodes: Sequence[_Node],
    edges: Sequence[_Edge],
    *,
    phase: str | None = None,
    node_types: set[str] | None = None,
    relations: set[str] | None = None,
    include_neighbours: bool = False,
) -> tuple[list[_Node], list[_Edge]]:
    active_edges = [edge for edge in edges if relations is None or edge.relation in relations]
    selected = {
        node.id
        for node in nodes
        if (phase is None or node.phase == phase.lower()) and (node_types is None or node.type in node_types)
    }
    if include_neighbours:
        node_by_id = {node.id: node for node in nodes}
        seeds = set(selected)
        for edge in active_edges:
            if edge.source in seeds and (
                node_types is None or node_by_id[edge.target].type in node_types
            ):
                selected.add(edge.target)
            if edge.target in seeds and (
                node_types is None or node_by_id[edge.source].type in node_types
            ):
                selected.add(edge.source)
    filtered_nodes = [node for node in nodes if node.id in selected]
    filtered_edges = [
        edge
        for edge in active_edges
        if edge.source in selected and edge.target in selected
    ]
    return filtered_nodes, filtered_edges


def _fmt(number: float | int) -> str:
    numeric = float(number)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:.1f}"


def _edge_path(source: _Box, target: _Box, edge_index: int) -> str:
    # Forward and same-lane routes reserve a small channel between columns.  A
    # backward relationship uses a gutter above both nodes, making feedback
    # visually obvious without placing a diagonal line through content.
    if target.left >= source.right + 12:
        channel_x = source.right + max(16.0, (target.left - source.right) / 2)
        return (
            f"M {_fmt(source.right)} {_fmt(source.cy)} "
            f"H {_fmt(channel_x)} V {_fmt(target.cy)} H {_fmt(target.left)}"
        )
    if source.left >= target.right + 12:
        gutter_y = max(78.0, min(source.top, target.top) - 12.0 - (edge_index % 5) * 5.0)
        return (
            f"M {_fmt(source.left)} {_fmt(source.cy)} H {_fmt(source.left - 14)} "
            f"V {_fmt(gutter_y)} H {_fmt(target.right + 14)} V {_fmt(target.cy)} H {_fmt(target.right)}"
        )
    gutter_x = max(source.right, target.right) + 14.0 + (edge_index % 5) * 6.0
    return (
        f"M {_fmt(source.right)} {_fmt(source.cy)} H {_fmt(gutter_x)} "
        f"V {_fmt(target.cy)} H {_fmt(target.right)}"
    )


def _render_defs() -> str:
    marker_defs = []
    for marker_id, colour in (
        ("arrow-depends", "#475467"),
        ("arrow-supports", "#1570EF"),
        ("arrow-verifies", "#7F56D9"),
        ("arrow-supersedes", "#DC6803"),
        ("arrow-refines", "#0E9384"),
    ):
        marker_defs.append(
            f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{colour}"/></marker>'
        )
    return "<defs>" + "".join(marker_defs) + "</defs>"


def _render_lanes(
    lanes: Sequence[tuple[str, _Box]],
    current_phase: str | None,
    translator: Any,
) -> str:
    parts: list[str] = []
    for index, (phase, box) in enumerate(lanes):
        current = phase == (current_phase or "").lower()
        fill = "#EFF8FF" if current else ("#FFFFFF" if index % 2 == 0 else "#F8FAFC")
        stroke = "#1570EF" if current else "#D0D5DD"
        stroke_width = 3 if current else 1
        parts.append(
            f'<g class="phase-lane" data-phase="{escape(phase, quote=True)}">'
            f'<rect x="{_fmt(box.x)}" y="{_fmt(box.y)}" width="{_fmt(box.width)}" '
            f'height="{_fmt(box.height)}" rx="18" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}"/>'
            f'<text x="{_fmt(box.x + 18)}" y="{_fmt(box.y + 30)}" class="lane-title">'
            f'{escape(_phase_label(phase, translator))}</text>'
            + (
                f'<g transform="translate({_fmt(box.right - 116)} {_fmt(box.y + 14)})">'
                '<rect width="98" height="26" rx="13" fill="#1570EF"/>'
                f'<text x="49" y="18" text-anchor="middle" class="lane-current">{escape(_t(translator, "svg.current", "CURRENT"))}</text></g>'
                if current
                else ""
            )
            + "</g>"
        )
    return "".join(parts)


def _render_edges(
    edges: Sequence[_Edge],
    boxes: Mapping[str, _Box],
    translator: Any,
) -> str:
    parts = ['<g class="edges" fill="none">']
    for index, edge in enumerate(edges):
        # Canonical dependency storage is ``dependent -> prerequisite``.  Keep
        # those endpoints in data-source/data-target for machine consumers,
        # while drawing the execution flow as ``prerequisite -> dependent``.
        visual_source_id = edge.target if edge.relation == "depends_on" else edge.source
        visual_target_id = edge.source if edge.relation == "depends_on" else edge.target
        source = boxes.get(visual_source_id)
        target = boxes.get(visual_target_id)
        if not source or not target:
            continue
        colour, dash, marker = RELATION_STYLES[edge.relation]
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<path class="edge edge-{edge.relation}" data-source="{escape(edge.source, quote=True)}" '
            f'data-target="{escape(edge.target, quote=True)}" data-relation="{edge.relation}" '
            f'data-visual-source="{escape(visual_source_id, quote=True)}" '
            f'data-visual-target="{escape(visual_target_id, quote=True)}" '
            f'd="{_edge_path(source, target, index)}" stroke="{colour}" stroke-width="2"'
            f'{dash_attr} marker-end="url(#{marker})"><title>'
            f'{escape(edge.source)} {escape(_t(translator, f"relation.{edge.relation}", edge.relation.replace("_", " ")))} {escape(edge.target)}'
            "</title></path>"
        )
    parts.append("</g>")
    return "".join(parts)


def _node_shape(node: _Node, box: _Box, fill: str, stroke: str, dash: str) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    common = f'fill="{fill}" stroke="{stroke}" stroke-width="{3 if node.current else 2}"{dash_attr}'
    if node.type == "DCP":
        points = (
            f"{_fmt(box.cx)},{_fmt(box.top)} {_fmt(box.right)},{_fmt(box.cy)} "
            f"{_fmt(box.cx)},{_fmt(box.bottom)} {_fmt(box.left)},{_fmt(box.cy)}"
        )
        return f'<polygon points="{points}" {common}/>'
    if node.type == "Gate":
        inset = 18.0
        points = (
            f"{_fmt(box.left + inset)},{_fmt(box.top)} {_fmt(box.right - inset)},{_fmt(box.top)} "
            f"{_fmt(box.right)},{_fmt(box.cy)} {_fmt(box.right - inset)},{_fmt(box.bottom)} "
            f"{_fmt(box.left + inset)},{_fmt(box.bottom)} {_fmt(box.left)},{_fmt(box.cy)}"
        )
        return f'<polygon points="{points}" {common}/>'
    radius = {"Phase": 16, "TR": 29, "Activity": 10, "Deliverable": 12}.get(node.type, 12)
    return (
        f'<rect x="{_fmt(box.x)}" y="{_fmt(box.y)}" width="{_fmt(box.width)}" '
        f'height="{_fmt(box.height)}" rx="{radius}" {common}/>'
    )


def _render_node(
    node: _Node,
    box: _Box,
    detail_href_prefix: str,
    translator: Any,
) -> str:
    status_fill, status_stroke, dash = STATUS_STYLES[node.status]
    if node.type == "TR":
        fill, stroke = "#FFFAEB", "#F79009"
    elif node.type == "DCP":
        fill, stroke = "#FFF4ED", "#EF6820"
    elif node.type == "Gate":
        fill, stroke = "#EFF8FF", "#1570EF"
    elif node.type == "Activity":
        fill, stroke = "#F9FAFB", "#667085"
    elif node.type == "Phase":
        fill, stroke = "#F2F4F7", "#344054"
    else:
        fill, stroke = status_fill, status_stroke
    if node.blocked:
        fill, stroke, dash = STATUS_STYLES["blocked"]
    if node.current:
        stroke = "#1570EF" if not node.blocked else "#C01048"

    # Keep the ``kind:id`` route separator readable so the parent Dashboard's
    # hash router can match it; quote any unsafe characters inside the ID.
    href = detail_href_prefix + quote(node.detail_key, safe=":")
    attrs = (
        f'data-node-id="{escape(node.id, quote=True)}" data-node-type="{node.type}" '
        f'data-status="{node.status}" data-x="{_fmt(box.x)}" data-y="{_fmt(box.y)}" '
        f'data-width="{_fmt(box.width)}" data-height="{_fmt(box.height)}" '
        f'data-refinement-due="{str(node.refinement_due).lower()}"'
    )
    node_type_label = _t(
        translator,
        f"node_type.{node.type.lower()}",
        node.type,
    )
    status_label = _t(
        translator,
        f"status.{node.status}",
        node.status.replace("_", " "),
    )
    parts = [
        f'<a href="{escape(href, quote=True)}" target="_top" aria-label="{escape(_t(translator, "svg.open_node", "Open {type} {title}", type=node_type_label, title=node.title), quote=True)}">',
        f'<g class="node node-{node.type.lower()} status-{node.status}" {attrs}>',
        f"<title>{escape(_t(translator, 'svg.node_title', '{type} {id}: {title}; status {status}', type=node_type_label, id=node.id, title=node.title, status=status_label))}</title>",
    ]
    if node.current:
        parts.append(
            f'<rect x="{_fmt(box.x - 5)}" y="{_fmt(box.y - 5)}" width="{_fmt(box.width + 10)}" '
            f'height="{_fmt(box.height + 10)}" rx="18" fill="none" stroke="#84CAFF" stroke-width="3"/>'
        )
    parts.append(_node_shape(node, box, fill, stroke, dash))

    if node.type == "Deliverable":
        parts.append(
            f'<rect x="{_fmt(box.x)}" y="{_fmt(box.y)}" width="8" height="{_fmt(box.height)}" '
            f'rx="4" fill="{status_stroke}" stroke="none"/>'
        )
    label_y = box.y + (26 if node.type == "Deliverable" else box.height / 2 - 2)
    if node.type == "DCP":
        max_chars = 18
    elif node.type in {"TR", "Gate"}:
        max_chars = 22
    else:
        max_chars = 28
    lines = _wrap_text(node.title, max_chars, 2 if node.type != "Deliverable" else 3)
    line_height = 16
    start_y = label_y - (len(lines) - 1) * line_height / 2
    text_x = box.cx + (4 if node.type == "Deliverable" else 0)
    parts.append(f'<text x="{_fmt(text_x)}" y="{_fmt(start_y)}" text-anchor="middle" class="node-title">')
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else line_height
        parts.append(f'<tspan x="{_fmt(text_x)}" dy="{dy}">{escape(line)}</tspan>')
    parts.append("</text>")
    if node.type == "Deliverable":
        parts.append(
            f'<text x="{_fmt(box.x + 18)}" y="{_fmt(box.bottom - 12)}" class="node-meta">'
            f'{escape(node.id)} · {escape(status_label.upper() if getattr(translator, "locale", "en") == "en" else status_label)}</text>'
        )
    elif node.type in {"TR", "DCP", "Gate"}:
        parts.append(
            f'<text x="{_fmt(box.cx)}" y="{_fmt(box.bottom - 10)}" text-anchor="middle" class="node-kind">'
            f'{escape(node_type_label)}</text>'
        )
    if node.blocked:
        badge_x = box.right - 72
        parts.append(
            f'<g class="blocked-badge" transform="translate({_fmt(badge_x)} {_fmt(box.y - 11)})">'
            '<rect width="68" height="22" rx="11" fill="#C01048"/>'
            f'<text x="34" y="15" text-anchor="middle">{escape(_t(translator, "svg.blocked", "BLOCKED"))}</text></g>'
        )
    if node.refinement_due:
        # Refinement due is an independent definition-governance signal.  Keep
        # it visible even when the lifecycle is also explicitly blocked.
        badge_x = box.x + 4 if node.blocked else box.right - 78
        parts.append(
            f'<g class="refinement-badge" transform="translate({_fmt(badge_x)} {_fmt(box.y - 11)})">'
            '<rect width="74" height="22" rx="11" fill="#0E9384"/>'
            f'<text x="37" y="15" text-anchor="middle">{escape(_t(translator, "svg.refinement_due", "REFINE"))}</text></g>'
        )
    parts.extend(("</g>", "</a>"))
    return "".join(parts)


def _render_legend(
    x: float,
    y: float,
    width: float,
    translator: Any,
    relations: set[str] | None = None,
) -> str:
    parts = [
        f'<g class="legend" transform="translate({_fmt(x)} {_fmt(y)})">',
        f'<rect width="{_fmt(width)}" height="208" rx="16" fill="#FFFFFF" stroke="#D0D5DD"/>',
        f'<text x="18" y="25" class="legend-title">{escape(_t(translator, "svg.legend", "Legend"))}</text>',
    ]
    node_items = (
        ("Phase", "#344054"),
        ("TR", "#F79009"),
        ("DCP", "#EF6820"),
        ("Gate", "#1570EF"),
        ("Activity", "#667085"),
        ("Deliverable", "#039855"),
    )
    for index, (label, colour) in enumerate(node_items):
        item_x = 18 + index * 118
        parts.append(
            f'<rect x="{item_x}" y="38" width="24" height="16" rx="5" fill="#FFFFFF" stroke="{colour}" stroke-width="2"/>'
            f'<text x="{item_x + 31}" y="51" class="legend-label">{escape(_t(translator, f"node_type.{label.lower()}", label))}</text>'
        )
    edge_x = 18
    edge_relations = tuple(
        relation
        for relation in ("depends_on", "supports", "verifies", "supersedes", "refines")
        if relations is None or relation in relations
    )
    for index, relation in enumerate(edge_relations):
        colour, dash, marker = RELATION_STYLES[relation]
        row, column = divmod(index, 4)
        item_x = edge_x + column * 184
        item_y = 82 + row * 28
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        relation_label = (
            _t(
                translator,
                "svg.dependency_direction",
                "Prerequisite → Dependent",
            )
            if relation == "depends_on"
            else _t(
                translator,
                f"relation.{relation}",
                relation.replace("_", " "),
            )
        )
        parts.append(
            f'<path d="M {item_x} {item_y} H {item_x + 46}" stroke="{colour}" stroke-width="2"{dash_attr} '
            f'marker-end="url(#{marker})"/>'
            f'<text x="{item_x + 56}" y="{item_y + 5}" class="legend-label">{escape(relation_label)}</text>'
        )
    statuses = tuple(STATUS_STYLES)
    status_start_y = 122 + (28 if len(edge_relations) > 4 else 0)
    for index, status in enumerate(statuses):
        row, column = divmod(index, 4)
        item_x = 18 + column * 182
        item_y = status_start_y + row * 28
        fill, stroke, _ = STATUS_STYLES[status]
        parts.append(
            f'<circle cx="{item_x + 7}" cy="{item_y}" r="7" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            f'<text x="{item_x + 20}" y="{item_y + 4}" class="legend-label">'
            f'{escape(_t(translator, f"status.{status}", status.replace("_", " ")))}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


def _empty_svg(
    title: str,
    detail: str,
    translator: Any,
    phase: str | None = None,
) -> str:
    phase_id = (phase or "unassigned").lower()
    phase_label = _phase_label(phase_id, translator)
    return "".join(
        (
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" '
            'viewBox="0 0 960 540" role="img" aria-labelledby="svg-title svg-desc" '
            'data-layout="hierarchical-swimlane" data-node-count="0" data-edge-count="0">',
            f'<title id="svg-title">{escape(title)}</title>',
            f'<desc id="svg-desc">{escape(detail)}</desc>',
            _render_defs(),
            '<rect width="960" height="540" fill="#F8FAFC"/>',
            f'<g class="phase-lane" data-phase="{escape(phase_id, quote=True)}">'
            '<rect x="36" y="92" width="888" height="190" rx="18" fill="#FFFFFF" '
            'stroke="#D0D5DD"/><text x="56" y="124" '
            'font-family="Segoe UI,Microsoft YaHei,PingFang SC,Noto Sans CJK SC,Tahoma,Arial,sans-serif" font-size="17" '
            f'font-weight="700" fill="#182230">{escape(phase_label)}</text></g>',
            '<text x="480" y="178" text-anchor="middle" '
            'font-family="Segoe UI,Microsoft YaHei,PingFang SC,Noto Sans CJK SC,Tahoma,Arial,sans-serif" font-size="24" '
            f'font-weight="700" fill="#344054">{escape(_t(translator, "svg.no_matching_nodes", "No matching workflow nodes"))}</text>',
            '<text x="480" y="208" text-anchor="middle" '
            'font-family="Segoe UI,Microsoft YaHei,PingFang SC,Noto Sans CJK SC,Tahoma,Arial,sans-serif" font-size="15" '
            f'fill="#667085">{escape(_t(translator, "svg.run_tailor_refresh", "Run tailoring and refresh the project state."))}</text>',
            _render_legend(36, 330, 888, translator),
            "</svg>",
        )
    )


def render_svg(
    graph: Mapping[str, Any],
    *,
    title: str,
    layout: str = "dependency",
    phase: str | None = None,
    current_phase: str | None = None,
    node_types: Iterable[str] | None = None,
    relations: Iterable[str] | None = None,
    include_neighbours: bool = False,
    detail_href_prefix: str = "../index.html#node=",
    emphasise_ids: Iterable[str] = (),
    blocked_ids: Iterable[str] = (),
    translator: Any | None = None,
    locale: str = "en",
) -> str:
    """Render a typed IPD graph as a standalone, deterministic SVG document.

    ``layout`` accepts ``"process"`` (phase columns) or ``"dependency"``
    (topological columns inside phase swimlanes).  Filtering happens before
    layout so omitted nodes cannot leave gaps or dangling edges.
    """

    translator = _translator(translator, locale)
    nodes, edges = _normalise_graph(graph)
    canonical_types = {_canonical_type(value) for value in node_types} if node_types is not None else None
    canonical_relations = (
        {_text(value).strip().lower() for value in relations}
        if relations is not None
        else None
    )
    nodes, edges = _filter_graph(
        nodes,
        edges,
        phase=phase,
        node_types=canonical_types,
        relations=canonical_relations,
        include_neighbours=include_neighbours,
    )
    emphasise = {_text(value) for value in emphasise_ids}
    blocked = {_text(value) for value in blocked_ids}
    if emphasise or blocked:
        nodes = [
            _Node(
                id=node.id,
                type=node.type,
                title=node.title,
                phase=node.phase,
                status="blocked" if node.id in blocked else node.status,
                current=node.current or node.id in emphasise,
                blocked=node.blocked or node.id in blocked,
                refinement_due=node.refinement_due,
                detail_key=node.detail_key,
            )
            for node in nodes
        ]
    if not nodes:
        return _empty_svg(
            title,
            _t(
                translator,
                "svg.empty_description",
                "{title}: no matching nodes",
                title=title,
            ),
            translator,
            phase=phase,
        )

    if layout == "process":
        boxes, lanes, width, height = _process_layout(nodes, edges)
    elif layout == "dependency":
        boxes, lanes, width, height = _dependency_layout(nodes, edges)
    else:
        raise ValueError(f"Unsupported SVG layout: {layout}")
    # The legend uses a compact single-row grammar.  Keep enough canvas width
    # for it even when a filtered view contains just one topological column.
    width = max(width, 840.0)
    safe_title = escape(title)
    description = _t(
        translator,
        "svg.description",
        "{title}. {nodes} nodes and {edges} relationships arranged in {lanes} phase swimlanes.",
        title=title,
        nodes=len(nodes),
        edges=len(edges),
        lanes=len(lanes),
    )
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(width)}" height="{_fmt(height)}" '
        f'viewBox="0 0 {_fmt(width)} {_fmt(height)}" role="img" aria-labelledby="svg-title svg-desc" '
        f'data-layout="hierarchical-swimlane" data-node-count="{len(nodes)}" data-edge-count="{len(edges)}">',
        f'<title id="svg-title">{safe_title}</title><desc id="svg-desc">{escape(description)}</desc>',
        _render_defs(),
        '<style>'
        'text{font-family:"Segoe UI","Microsoft YaHei","PingFang SC","Noto Sans CJK SC",Tahoma,Arial,sans-serif;fill:#182230}'
        '.canvas-title{font-size:24px;font-weight:750}.canvas-subtitle{font-size:13px;fill:#667085}'
        '.lane-title{font-size:17px;font-weight:700}.lane-current{font-size:11px;font-weight:800;fill:#fff;letter-spacing:.08em}'
        '.node-title{font-size:13px;font-weight:650}.node-meta{font-size:10px;font-weight:600;fill:#667085}'
        '.node-kind{font-size:9px;font-weight:800;fill:#667085;letter-spacing:.12em}'
        '.node{cursor:pointer}.node:hover>*:not(title){filter:brightness(.97)}'
        '.blocked-badge text,.refinement-badge text{font-size:9px;font-weight:800;fill:#fff;letter-spacing:.04em}'
        '.edge{opacity:.82}.legend-title{font-size:13px;font-weight:750}.legend-label{font-size:11px;fill:#475467}'
        '</style>',
        '<rect width="100%" height="100%" fill="#F8FAFC"/>',
        f'<text x="36" y="42" class="canvas-title">{safe_title}</text>',
        f'<text x="36" y="66" class="canvas-subtitle">{escape(_t(translator, "svg.summary", "{nodes} nodes · {edges} relationships · deterministic hierarchical layout", nodes=len(nodes), edges=len(edges)))}</text>',
        _render_lanes(lanes, current_phase, translator),
        _render_edges(edges, boxes, translator),
        '<g class="nodes">',
    ]
    for node in nodes:
        box = boxes.get(node.id)
        if box:
            parts.append(_render_node(node, box, detail_href_prefix, translator))
    parts.extend(
        (
            "</g>",
            _render_legend(
                36,
                height - 224,
                min(width - 72, 760),
                translator,
                canonical_relations,
            ),
            "</svg>",
        )
    )
    return "".join(parts)


def render_process_svg(
    graph: Mapping[str, Any],
    *,
    title: str = "IPD Process Flow",
    detail_href_prefix: str = "../index.html#node=",
    translator: Any | None = None,
    locale: str = "en",
) -> str:
    """Render the complete workflow as ordered phase swimlanes."""

    translator = _translator(translator, locale)
    if title == "IPD Process Flow":
        title = _t(translator, "dashboard.process_flow", title)
    return render_svg(
        graph,
        title=title,
        layout="process",
        detail_href_prefix=detail_href_prefix,
        translator=translator,
    )


def render_current_status_svg(
    graph: Mapping[str, Any],
    *,
    current_phase: str,
    available_ids: Iterable[str] = (),
    blocked_ids: Iterable[str] = (),
    filter_to_phase: bool = True,
    title: str = "Current Status Flow",
    detail_href_prefix: str = "../index.html#node=",
    translator: Any | None = None,
    locale: str = "en",
) -> str:
    """Render the current phase and its immediate cross-phase dependencies."""

    translator = _translator(translator, locale)
    if title == "Current Status Flow":
        title = _t(translator, "dashboard.current_status_diagram", title)
    available = tuple(available_ids)
    blocked = tuple(blocked_ids)
    return render_svg(
        graph,
        title=title,
        layout="dependency",
        phase=current_phase if filter_to_phase else None,
        current_phase=current_phase,
        include_neighbours=filter_to_phase,
        detail_href_prefix=detail_href_prefix,
        emphasise_ids=available,
        blocked_ids=blocked,
        translator=translator,
    )


def render_dependency_svg(
    graph: Mapping[str, Any],
    *,
    phase: str | None = None,
    title: str = "Deliverable Dependency",
    detail_href_prefix: str = "../index.html#node=",
    relations: Iterable[str] | None = ("depends_on", "refines"),
    filter_to_phase: bool = True,
    translator: Any | None = None,
    locale: str = "en",
) -> str:
    """Render execution dependencies and structural refinement relationships.

    Only ``depends_on`` influences topological levels; ``refines`` is a dashed
    trace overlay and cannot change execution order.
    """

    translator = _translator(translator, locale)
    if title == "Deliverable Dependency":
        title = _t(translator, "dashboard.deliverable_dependency_graph", title)
    elif title == "Current Phase Deliverable Dependencies":
        title = _t(translator, "dashboard.current_work", title)
    return render_svg(
        graph,
        title=title,
        layout="dependency",
        phase=phase if filter_to_phase else None,
        current_phase=phase,
        node_types={"Deliverable"},
        relations=relations,
        include_neighbours=filter_to_phase,
        detail_href_prefix=detail_href_prefix,
        translator=translator,
    )


__all__ = [
    "render_svg",
    "render_process_svg",
    "render_current_status_svg",
    "render_dependency_svg",
]

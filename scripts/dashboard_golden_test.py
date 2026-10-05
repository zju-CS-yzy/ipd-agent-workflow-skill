#!/usr/bin/env python3
"""Run the output-derived v1.4 dashboard renderer golden test.

The v1.4 example does not contain the original task profile, tailored process,
project state, or dashboard renderer.  This harness therefore treats the
surviving dependency graph as a read-only structural fixture.  It never copies
the fixture into this repository or writes into the legacy tree.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    # Direct source-tree execution starts with scripts/ on sys.path.
    sys.path.insert(0, str(REPOSITORY_ROOT))
DEFAULT_REPORT = REPOSITORY_ROOT / "DASHBOARD_GOLDEN_TEST_REPORT.md"
TASK_TYPES = (
    "software",
    "hardware",
    "embedded",
    "robotics",
    "ai_system",
    "material_change",
)
REQUIRED_DASHBOARD_FILES = (
    "index.html",
    "assets/ipd_flow.svg",
    "assets/current_status_flow.svg",
    "assets/deliverable_dependency.svg",
    "phases/concept.svg",
    "phases/plan.svg",
    "phases/develop.svg",
    "phases/qualify.svg",
    "phases/launch.svg",
    "matrices/deliverable_matrix.html",
    "matrices/gate_matrix.html",
    "data/state.json",
    "data/graph.json",
)
LEGACY_EXPECTED = {
    "files": 6,
    "html": 1,
    "json": 1,
    "markdown": 1,
    "svg": 3,
    "png": 0,
    "nodes": 286,
    "internal_edges": 144,
    "external_prerequisites": 31,
}
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_UNRESOLVED_MESSAGE_RE = re.compile(
    r"\b(?:common|status|node_type|relation|phase|dashboard|field|detail|matrix|svg)\.[a-z0-9_.-]+\b"
)


def locate_legacy_graph(legacy_root: Path) -> Path:
    """Locate the v1.4 graph without scanning or mutating unrelated trees."""

    root = legacy_root.expanduser().resolve()
    candidates = (
        root,
        root / "deliverable_dependency_graph.json",
        root / "generated" / "deliverable_dependency_graph.json",
        root
        / "examples"
        / "quadruped_perception_fusion"
        / "generated"
        / "deliverable_dependency_graph.json",
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.name == "deliverable_dependency_graph.json":
            return candidate
    raise FileNotFoundError(
        "Cannot find generated/deliverable_dependency_graph.json under "
        f"{legacy_root}"
    )


def _records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        result: list[Mapping[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                record = dict(item)
                record.setdefault("id", str(key))
                result.append(record)
        return result
    return []


def _stage_records(value: Any) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        return [(str(key), stage) for key, stage in value.items() if isinstance(stage, Mapping)]
    if isinstance(value, list):
        result = []
        for index, stage in enumerate(value):
            if not isinstance(stage, Mapping):
                continue
            stage_id = str(
                stage.get("id")
                or stage.get("stage_id")
                or stage.get("stage")
                or stage.get("name")
                or f"stage_{index + 1}"
            )
            result.append((stage_id, stage))
        return result
    return []


def _identifier(record: Mapping[str, Any], fallback: str) -> str:
    for key in ("id", "deliverable_id", "node_id", "key", "name"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


def _endpoint(record: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, Mapping):
            value = value.get("id") or value.get("deliverable_id")
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _external_count(value: Any) -> int:
    if isinstance(value, list):
        return sum(_external_count(item) for item in value)
    if isinstance(value, Mapping):
        record_keys = {
            "id",
            "source",
            "target",
            "from",
            "to",
            "deliverable_id",
            "prerequisite",
        }
        if record_keys.intersection(value):
            return 1
        return sum(_external_count(item) for item in value.values())
    return 1 if value not in (None, "") else 0


def _status(value: Any) -> str:
    status = str(value or "planned").strip().lower().replace(" ", "_")
    return {
        "not_started": "planned",
        "draft": "planned",
        "working": "in_progress",
        "ready": "ready_for_review",
        "review": "in_review",
        "approved": "accepted",
        "complete": "accepted",
        "completed": "accepted",
    }.get(status, status)


def _relation(value: Any) -> str:
    relation = str(value or "depends_on").strip().lower().replace(" ", "_")
    return {
        "hard": "depends_on",
        "hard_dependency": "depends_on",
        "dependency": "depends_on",
        "soft": "supports",
        "soft_dependency": "supports",
        "feedback": "supports",
    }.get(
        relation,
        relation
        if relation
        in {"depends_on", "supports", "verifies", "supersedes", "refines"}
        else "depends_on",
    )


def _source_label(source: Mapping[str, Any], identifier: str, index: int) -> str:
    """Preserve project-owned Golden labels regardless of their script."""

    for key in ("title", "label", "name"):
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    label = identifier.replace("_", " ").replace("-", " ").strip()
    return label or f"Deliverable {index + 1}"


def normalize_legacy_graph(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Convert surviving v1.4 stage data into the current renderer contract.

    Stage IDs prefix renderer IDs so stage-local identifiers cannot collide.
    The original identifier remains available as ``display_id`` and
    ``legacy_id``.  External prerequisites are counted for comparison but are
    not fabricated into graph nodes, keeping the render at the documented 286
    deliverable-node scale.
    """

    stages = _stage_records(payload.get("stages", []))
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    external_prerequisites = 0

    for stage_index, (stage_id, stage) in enumerate(stages):
        phase = str(stage.get("phase") or stage.get("name") or stage_id)
        phase_id = stage_id.strip().lower().replace(" ", "_")
        phases.append({"id": phase_id, "label": phase, "order": stage_index})
        id_map: dict[str, str] = {}
        stage_nodes = _records(stage.get("nodes", []))
        for node_index, source in enumerate(stage_nodes):
            legacy_id = _identifier(source, f"node_{node_index + 1}")
            render_id = f"{phase_id}:{legacy_id}"
            id_map[legacy_id] = render_id
            status = _status(
                source.get("status")
                or source.get("state")
                or source.get("review_status")
                or "planned"
            )
            label = _source_label(source, legacy_id, node_index)
            nodes.append(
                {
                    "id": render_id,
                    "display_id": legacy_id,
                    "legacy_id": legacy_id,
                    "label": label,
                    "title": label,
                    "type": "Deliverable",
                    "kind": "Deliverable",
                    "node_type": "Deliverable",
                    "phase": phase_id,
                    "phase_id": phase_id,
                    "status": status,
                    "owner": source.get("owner") or source.get("role") or "Unassigned",
                    "blocked": status == "blocked" or bool(source.get("blocked")),
                    "lane": source.get("lane") or source.get("source_kind") or "deliverables",
                    "source_kind": source.get("source_kind"),
                    "evidence": source.get("evidence", []),
                    "review_history": source.get("review_history", source.get("reviews", [])),
                }
            )

        for edge_index, source in enumerate(_records(stage.get("edges", []))):
            edge_source = _endpoint(source, ("source", "from", "from_id", "prerequisite"))
            edge_target = _endpoint(source, ("target", "to", "to_id", "deliverable"))
            if not edge_source or not edge_target:
                continue
            # Prefix unresolved endpoints as stage-local IDs too. The renderer
            # can safely ignore an edge whose endpoint is absent.
            edges.append(
                {
                    "id": str(source.get("id") or f"{phase_id}:edge_{edge_index + 1}"),
                    "source": id_map.get(edge_source, f"{phase_id}:{edge_source}"),
                    "target": id_map.get(edge_target, f"{phase_id}:{edge_target}"),
                    "relation": _relation(
                        source.get("relation")
                        or source.get("type")
                        or source.get("dependency_type")
                        or "depends_on"
                    ),
                    "type": _relation(
                        source.get("relation")
                        or source.get("type")
                        or source.get("dependency_type")
                        or "depends_on"
                    ),
                    "phase": phase_id,
                }
            )
        external_prerequisites += _external_count(stage.get("external_prerequisites", []))

    graph = {
        "schema_version": "0.2.0",
        "graph_type": "deliverable_dependency",
        "title": "v1.4 Golden Reference - Deliverable Dependency",
        "current_phase": phases[0]["id"] if phases else None,
        "phase_order": [phase["id"] for phase in phases],
        "phases": phases,
        "nodes": nodes,
        "edges": edges,
    }
    statistics = {
        "nodes": len(nodes),
        "internal_edges": len(edges),
        "external_prerequisites": external_prerequisites,
        "stages": len(phases),
    }
    return graph, statistics


def legacy_inventory(generated_root: Path) -> dict[str, int]:
    """Count only the six canonical v1.4 generated artifacts."""

    files = [path for path in generated_root.rglob("*") if path.is_file()]
    counts = Counter(path.suffix.lower() for path in files)
    return {
        "files": len(files),
        "html": counts[".html"],
        "json": counts[".json"],
        "markdown": counts[".md"],
        "svg": counts[".svg"],
        "png": counts[".png"],
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def legacy_fixture_fingerprints(
    generated_root: Path,
    legacy_graph_path: Path,
) -> dict[str, Any]:
    """Identify the external Golden fixture without copying it into this repo.

    The graph hash identifies the exact structural input.  The inventory hash
    covers every relative filename, byte length, and content hash under the
    external ``generated`` directory, making the report independently
    comparable across machines without recording an absolute local path.
    """

    entries = []
    for path in sorted(
        (item for item in generated_root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(generated_root).as_posix(),
    ):
        entries.append(
            {
                "path": path.relative_to(generated_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    inventory_payload = json.dumps(
        entries,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "dependency_graph_sha256": _sha256_file(legacy_graph_path),
        "inventory_sha256": hashlib.sha256(inventory_payload).hexdigest(),
        "inventory_entries": len(entries),
    }


def _node_boxes(svg_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(svg_text)
    boxes: list[dict[str, Any]] = []
    for element in root.iter():
        attrs = element.attrib
        if "data-node-id" not in attrs:
            continue
        try:
            boxes.append(
                {
                    "id": attrs["data-node-id"],
                    "phase": attrs.get("data-phase", ""),
                    "x": float(attrs["data-x"]),
                    "y": float(attrs["data-y"]),
                    "width": float(attrs["data-width"]),
                    "height": float(attrs["data-height"]),
                }
            )
        except (KeyError, ValueError):
            continue
    return boxes


def dependency_svg_contract(svg_text: str) -> dict[str, Any]:
    """Inspect the canonical and visual semantics of a dependency SVG."""

    root = ET.fromstring(svg_text)
    boxes = {box["id"]: box for box in _node_boxes(svg_text)}
    edges: list[dict[str, str]] = []
    for element in root.iter():
        attrs = element.attrib
        if not attrs.get("data-relation"):
            continue
        edges.append(
            {
                "source": attrs.get("data-source", ""),
                "target": attrs.get("data-target", ""),
                "relation": attrs.get("data-relation", ""),
                "visual_source": attrs.get("data-visual-source", ""),
                "visual_target": attrs.get("data-visual-target", ""),
            }
        )

    dependency_edges = [edge for edge in edges if edge["relation"] == "depends_on"]
    relations = sorted({edge["relation"] for edge in edges})
    projection_preserves_contract = bool(dependency_edges) and all(
        edge["visual_source"] == edge["target"]
        and edge["visual_target"] == edge["source"]
        for edge in dependency_edges
    )
    execution_order = bool(dependency_edges) and all(
        edge["visual_source"] in boxes
        and edge["visual_target"] in boxes
        and boxes[edge["visual_source"]]["x"] < boxes[edge["visual_target"]]["x"]
        for edge in dependency_edges
    )
    return {
        "node_ids": sorted(boxes),
        "rendered_relations": relations,
        "dependency_edges": dependency_edges,
        # ``refines`` is definition lineage, not an execution dependency.  It may
        # be overlaid in the dependency view without changing the only execution
        # topology, which remains ``depends_on``.
        "only_depends_on": bool(dependency_edges)
        and set(relations).issubset({"depends_on", "refines"}),
        "execution_relations": ["depends_on"] if dependency_edges else [],
        "lineage_relations": [
            relation for relation in relations if relation == "refines"
        ],
        "projection_preserves_contract": projection_preserves_contract,
        "execution_order": execution_order,
    }


def find_same_lane_overlaps(svg_text: str) -> list[tuple[str, str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for box in _node_boxes(svg_text):
        grouped[box["phase"]].append(box)
    overlaps: list[tuple[str, str]] = []
    for boxes in grouped.values():
        for index, left in enumerate(boxes):
            for right in boxes[index + 1 :]:
                separated = (
                    left["x"] + left["width"] <= right["x"]
                    or right["x"] + right["width"] <= left["x"]
                    or left["y"] + left["height"] <= right["y"]
                    or right["y"] + right["height"] <= left["y"]
                )
                if not separated:
                    overlaps.append((left["id"], right["id"]))
    return overlaps


def render_legacy_svg(
    graph: Mapping[str, Any],
    destination: Path,
    renderer: Callable[..., str] | None = None,
    *,
    locale: str = "en",
) -> dict[str, Any]:
    """Render the normalized graph; write only the new SVG destination."""

    if renderer is None:
        from ipdctl.dashboard_svg import render_dependency_svg

        renderer = render_dependency_svg
    svg = renderer(
        graph,
        phase=None,
        title="v1.4 Golden Reference - Deliverable Dependency",
        locale=locale,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding="utf-8")
    ET.fromstring(svg)
    overlaps = find_same_lane_overlaps(svg)
    return {
        "path": destination,
        "xml_valid": True,
        "graphviz_signature": "graphviz" in svg.lower(),
        "bbox_nodes": len(_node_boxes(svg)),
        "same_lane_overlaps": overlaps,
    }


@contextlib.contextmanager
def _working_directory(path: Path) -> Iterable[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _invoke_cli(arguments: list[str], cwd: Path) -> dict[str, Any]:
    from ipdctl.cli import main as cli_main

    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with _working_directory(cwd), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = cli_main(arguments)
        code = int(result or 0)
    except SystemExit as exc:
        code = int(exc.code or 0)
    except Exception as exc:  # surfaced in the report rather than hiding later profiles
        return {
            "command": "ipdctl " + " ".join(arguments),
            "exit_code": 1,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "command": "ipdctl " + " ".join(arguments),
        "exit_code": code,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }


def _set_task_type(project_root: Path, task_type: str) -> Path:
    import yaml

    candidates = (project_root / ".ipd" / "task_profile.yaml", project_root / "task_profile.yaml")
    profile_path = next((path for path in candidates if path.exists()), None)
    if profile_path is None:
        raise FileNotFoundError("ipdctl init did not create task_profile.yaml")
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    payload["task_type"] = task_type
    profile_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return profile_path


def run_cli_profiles(output_root: Path, locale: str = "en") -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for task_type in TASK_TYPES:
        project_root = output_root / "projects" / task_type
        project_root.mkdir(parents=True, exist_ok=True)
        commands = [
            _invoke_cli(
                [
                    "init",
                    ".",
                    "--name",
                    f"Golden {task_type}",
                    "--task-type",
                    task_type,
                    "--locale",
                    locale,
                ],
                project_root,
            )
        ]
        if all(command["exit_code"] == 0 for command in commands):
            for command in ("tailor", "refresh", "verify"):
                commands.append(_invoke_cli([command], project_root))
                if commands[-1]["exit_code"] != 0:
                    break
        dashboard_root = project_root / ".ipd" / "dashboard"
        profiles[task_type] = {
            "project_root": project_root,
            "dashboard_root": dashboard_root,
            "commands": commands,
            "passed": all(command["exit_code"] == 0 for command in commands),
        }
    return profiles


def inspect_dashboard(dashboard_root: Path, locale: str = "en") -> dict[str, Any]:
    files = sorted(path for path in dashboard_root.rglob("*") if path.is_file())
    relative = [path.relative_to(dashboard_root).as_posix() for path in files]
    suffixes = Counter(path.suffix.lower() for path in files)
    svg_files = [path for path in files if path.suffix.lower() == ".svg"]
    xml_errors: list[str] = []
    graphviz_files: list[str] = []
    overlaps: dict[str, list[tuple[str, str]]] = {}
    for path in svg_files:
        text = path.read_text(encoding="utf-8")
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            xml_errors.append(f"{path.name}: {exc}")
        if "graphviz" in text.lower():
            graphviz_files.append(path.relative_to(dashboard_root).as_posix())
        detected = find_same_lane_overlaps(text)
        if detected:
            overlaps[path.relative_to(dashboard_root).as_posix()] = detected

    language_violations: list[str] = []
    unresolved_message_keys: list[str] = []
    for path in files:
        if path.suffix.lower() not in {".html", ".svg", ".json", ".md"}:
            continue
        source = path.read_text(encoding="utf-8")
        if locale == "en" and _CJK_RE.search(source):
            language_violations.append(path.relative_to(dashboard_root).as_posix())
        if _UNRESOLVED_MESSAGE_RE.search(source):
            unresolved_message_keys.append(path.relative_to(dashboard_root).as_posix())

    graph_path = dashboard_root / "data" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.exists() else {}
    state_path = dashboard_root / "data" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    nodes = graph.get("nodes", []) if isinstance(graph, Mapping) else []
    edges = graph.get("edges", []) if isinstance(graph, Mapping) else []
    node_types = sorted(
        {
            str(node.get("type") or node.get("kind"))
            for node in nodes
            if isinstance(node, Mapping) and (node.get("type") or node.get("kind"))
        }
    )
    statuses = sorted(
        {
            str(node.get("status"))
            for node in nodes
            if isinstance(node, Mapping) and node.get("status")
        }
    )
    relations = sorted(
        {
            str(edge.get("relation") or edge.get("type"))
            for edge in edges
            if isinstance(edge, Mapping) and (edge.get("relation") or edge.get("type"))
        }
    )
    declared_relations = sorted(
        str(relation)
        for relation in (graph.get("relation_types", []) if isinstance(graph, Mapping) else [])
    )
    dependency_svg_paths = [dashboard_root / "assets" / "deliverable_dependency.svg"]
    dependency_svg_paths.extend(sorted((dashboard_root / "phases").glob("*.svg")))
    dependency_views = {
        path.relative_to(dashboard_root).as_posix(): dependency_svg_contract(
            path.read_text(encoding="utf-8")
        )
        for path in dependency_svg_paths
        if path.exists()
    }
    dependency_edges = [
        edge
        for view in dependency_views.values()
        for edge in view["dependency_edges"]
    ]
    rendered_dependency_relations = sorted(
        {
            relation
            for view in dependency_views.values()
            for relation in view["rendered_relations"]
        }
    )
    dependency_contract = {
        "rendered_relations": rendered_dependency_relations,
        "dependency_edges": dependency_edges,
        "only_depends_on": bool(dependency_edges)
        and set(rendered_dependency_relations).issubset({"depends_on", "refines"}),
        "execution_relations": ["depends_on"] if dependency_edges else [],
        "lineage_relations": [
            relation
            for relation in rendered_dependency_relations
            if relation == "refines"
        ],
        "projection_preserves_contract": bool(dependency_edges)
        and all(
            view["projection_preserves_contract"]
            for view in dependency_views.values()
            if view["dependency_edges"]
        ),
        "execution_order": bool(dependency_edges)
        and all(
            view["execution_order"]
            for view in dependency_views.values()
            if view["dependency_edges"]
        ),
        "views_checked": len(dependency_views),
    }
    canonical_edges = {
        (
            str(edge.get("source")),
            str(edge.get("target")),
            str(edge.get("relation") or edge.get("type")),
        )
        for edge in edges
        if isinstance(edge, Mapping)
    }
    expected_dependency_edges = {
        (str(deliverable.get("id")), str(prerequisite), "depends_on")
        for deliverable in (
            state.get("deliverables", []) if isinstance(state, Mapping) else []
        )
        if isinstance(deliverable, Mapping) and deliverable.get("id")
        for prerequisite in deliverable.get("depends_on", [])
        if prerequisite
    }
    graph_dependency_edges = {
        edge for edge in canonical_edges if edge[2] == "depends_on"
    }
    rendered_dependency_edges = {
        (edge["source"], edge["target"], edge["relation"])
        for edge in dependency_edges
    }
    dependency_contract["canonical_endpoints_match_graph"] = bool(
        dependency_contract["dependency_edges"]
    ) and all(
        (edge["source"], edge["target"], edge["relation"]) in canonical_edges
        for edge in dependency_contract["dependency_edges"]
    )
    dependency_contract["graph_matches_state"] = (
        graph_dependency_edges == expected_dependency_edges
    )
    dependency_contract["svg_covers_state"] = (
        rendered_dependency_edges == expected_dependency_edges
    )
    dependency_contract["expected_edges"] = len(expected_dependency_edges)
    dependency_contract["graph_edges"] = len(graph_dependency_edges)
    dependency_contract["rendered_edges"] = len(rendered_dependency_edges)
    deliverable_records = [
        item
        for item in (state.get("deliverables", []) if isinstance(state, Mapping) else [])
        if isinstance(item, Mapping) and item.get("id")
    ]
    current_project = state.get("project", {}) if isinstance(state, Mapping) else {}
    current_position = (
        current_project.get("current", {})
        if isinstance(current_project, Mapping)
        else {}
    )
    current_phase = (
        current_position.get("phase")
        if isinstance(current_position, Mapping)
        else None
    )

    def expected_view(phase: str | None) -> tuple[set[str], set[tuple[str, str, str]]]:
        selected = {
            str(item["id"])
            for item in deliverable_records
            if phase is None or item.get("phase") == phase
        }
        changed = True
        while changed:
            changed = False
            for source, target, relation in expected_dependency_edges:
                if relation == "depends_on" and source in selected and target not in selected:
                    selected.add(target)
                    changed = True
        selected_edges = {
            edge
            for edge in expected_dependency_edges
            if edge[0] in selected and edge[1] in selected
        }
        return selected, selected_edges

    view_mismatches: list[str] = []
    for relative_path, view in dependency_views.items():
        phase = (
            current_phase
            if relative_path == "assets/deliverable_dependency.svg"
            else Path(relative_path).stem
        )
        expected_nodes, expected_edges = expected_view(str(phase) if phase else None)
        actual_nodes = set(view["node_ids"])
        actual_edges = {
            (edge["source"], edge["target"], edge["relation"])
            for edge in view["dependency_edges"]
        }
        if actual_nodes != expected_nodes or actual_edges != expected_edges:
            view_mismatches.append(relative_path)
    dependency_contract["per_view_complete"] = not view_mismatches
    dependency_contract["view_mismatches"] = view_mismatches
    index_path = dashboard_root / "index.html"
    index = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    index_lower = index.lower()
    from ipdctl.i18n import get_translator

    translator = get_translator(locale)
    svg_text = "\n".join(path.read_text(encoding="utf-8") for path in svg_files)
    matrix_path = dashboard_root / "matrices" / "deliverable_matrix.html"
    matrix_text = matrix_path.read_text(encoding="utf-8") if matrix_path.exists() else ""
    def contains_localized_marker(text: str, marker: str) -> bool:
        """Accept visible text and JSON-script escaped localized labels."""

        escaped = json.dumps(marker, ensure_ascii=True)[1:-1]
        return marker in text or escaped in text

    locale_markers_present = all(
        (
            contains_localized_marker(index, translator.text("dashboard.current_phase")),
            contains_localized_marker(
                index, translator.text("dashboard.waiting_on_dependencies")
            ),
            contains_localized_marker(index, translator.text("detail.actionability")),
            contains_localized_marker(
                index, translator.text("detail.unmet_dependencies")
            ),
            contains_localized_marker(svg_text, translator.text("svg.legend")),
            contains_localized_marker(
                svg_text, translator.text("svg.dependency_direction")
            ),
            contains_localized_marker(
                matrix_text, translator.text("matrix.back_to_dashboard")
            ),
        )
    )
    interactions = {
        "node_links": "node=" in index_lower,
        "hash_navigation": "hashchange" in index_lower or "location.hash" in index_lower,
        "detail_panel": 'id="details"' in index_lower and 'id="detail-body"' in index_lower,
        "dependencies": "depends_on" in index_lower or "dependencies" in index_lower,
        "evidence": "item.evidence" in index_lower or "evidence" in index_lower,
        "review_history": "item.reviews" in index_lower or "review_history" in index_lower or "review history" in index_lower,
    }
    manifest_path = dashboard_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    structure = {
        "files": relative,
        "nodes": sorted(
            (str(node.get("id")), str(node.get("type") or node.get("kind")), str(node.get("phase")), str(node.get("status")))
            for node in nodes
            if isinstance(node, Mapping)
        ),
        "edges": sorted(
            (str(edge.get("source")), str(edge.get("target")), str(edge.get("relation") or edge.get("type")))
            for edge in edges
            if isinstance(edge, Mapping)
        ),
    }
    structure_fingerprint = hashlib.sha256(
        json.dumps(structure, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "root": dashboard_root,
        "files": relative,
        "file_count": len(files),
        "file_types": dict(sorted(suffixes.items())),
        "svg_count": suffixes[".svg"],
        "html_count": suffixes[".html"],
        "json_count": suffixes[".json"],
        "required_files_present": all(item in relative for item in REQUIRED_DASHBOARD_FILES),
        "xml_errors": xml_errors,
        "graphviz_files": graphviz_files,
        "same_lane_overlaps": overlaps,
        "language_violations": language_violations,
        "unresolved_message_keys": unresolved_message_keys,
        "locale": locale,
        "manifest_locale": manifest.get("locale"),
        "locale_markers_present": locale_markers_present,
        "structure_fingerprint": structure_fingerprint,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": node_types,
        "statuses": statuses,
        "relations": relations,
        "declared_relations": declared_relations,
        "dependency_contract": dependency_contract,
        "interactions": interactions,
    }


def _result(name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "evidence": evidence}


def evaluate(
    legacy_counts: Mapping[str, int],
    legacy_graph_stats: Mapping[str, int],
    golden_render: Mapping[str, Any],
    profiles: Mapping[str, Any],
    current: Mapping[str, Any],
) -> list[dict[str, Any]]:
    results = []
    dependency_contract = current.get("dependency_contract", {})
    results.append(
        _result(
            "Legacy artifact inventory",
            all(legacy_counts.get(key) == value for key, value in LEGACY_EXPECTED.items() if key in legacy_counts),
            ", ".join(f"{key}={legacy_counts.get(key, 0)}" for key in ("files", "html", "json", "markdown", "svg", "png")),
        )
    )
    results.append(
        _result(
            "Legacy graph scale",
            all(legacy_graph_stats.get(key) == LEGACY_EXPECTED[key] for key in ("nodes", "internal_edges", "external_prerequisites")),
            ", ".join(f"{key}={legacy_graph_stats.get(key, 0)}" for key in ("nodes", "internal_edges", "external_prerequisites")),
        )
    )
    results.append(_result("Golden SVG parses as XML", golden_render.get("xml_valid") is True, "ElementTree parse"))
    results.append(_result("Golden SVG is custom-rendered", not golden_render.get("graphviz_signature"), "No Graphviz signature"))
    results.append(
        _result(
            "Golden SVG has no same-lane node overlaps",
            not golden_render.get("same_lane_overlaps"),
            f"bbox_nodes={golden_render.get('bbox_nodes', 0)}, overlaps={len(golden_render.get('same_lane_overlaps', []))}",
        )
    )
    for task_type, profile in profiles.items():
        failed = [command["command"] for command in profile["commands"] if command["exit_code"] != 0]
        results.append(
            _result(
                f"CLI lifecycle: {task_type}",
                profile["passed"],
                "init -> tailor -> refresh -> verify" if not failed else "failed: " + ", ".join(failed),
            )
        )
    results.extend(
        [
            _result("Target dashboard inventory", current.get("required_files_present", False), f"files={current.get('file_count', 0)}"),
            _result(
                "Required SVG set",
                current.get("svg_count", 0) >= 8 and current.get("required_files_present", False),
                f"required=8, actual={current.get('svg_count', 0)}; additional lifecycle views are allowed",
            ),
            _result("Dashboard HTML structure", current.get("html_count", 0) >= 3, f"html={current.get('html_count', 0)}"),
            _result("SVG XML validity", not current.get("xml_errors"), f"errors={len(current.get('xml_errors', []))}"),
            _result("No Graphviz signature", not current.get("graphviz_files"), f"files={current.get('graphviz_files', [])}"),
            _result("No same-lane overlap", not current.get("same_lane_overlaps"), f"files={list(current.get('same_lane_overlaps', {}))}"),
            _result(
                "Generated text matches selected locale",
                not current.get("language_violations"),
                f"locale={current.get('locale')}, violations={current.get('language_violations', [])}",
            ),
            _result(
                "No unresolved localization keys",
                not current.get("unresolved_message_keys"),
                f"files={current.get('unresolved_message_keys', [])}",
            ),
            _result(
                "Dashboard manifest locale",
                current.get("manifest_locale") == current.get("locale"),
                f"expected={current.get('locale')}, actual={current.get('manifest_locale')}",
            ),
            _result(
                "Localized HTML, SVG, and Matrix markers",
                current.get("locale_markers_present") is True,
                f"locale={current.get('locale')}",
            ),
            _result("Interactive node details", all(current.get("interactions", {}).values()), str(current.get("interactions", {}))),
            _result("Typed graph nodes", {"Phase", "TR", "DCP", "Gate", "Activity", "Deliverable"}.issubset(set(current.get("node_types", []))), str(current.get("node_types", []))),
            _result(
                "Typed graph relation capability",
                set(current.get("declared_relations", []))
                == {"depends_on", "supports", "verifies", "supersedes", "refines"},
                "declared=" + str(current.get("declared_relations", []))
                + "; observed=" + str(current.get("relations", [])),
            ),
            _result(
                "Dependency view isolates dependency facts",
                dependency_contract.get("only_depends_on") is True
                and dependency_contract.get("svg_covers_state") is True
                and dependency_contract.get("per_view_complete") is True,
                "relations="
                + str(dependency_contract.get("rendered_relations", []))
                + f", expected={dependency_contract.get('expected_edges', 0)}"
                + f", rendered={dependency_contract.get('rendered_edges', 0)}"
                + f", mismatches={dependency_contract.get('view_mismatches', [])}",
            ),
            _result(
                "Dependency projection is prerequisite to dependent",
                all(
                    dependency_contract.get(key) is True
                    for key in (
                        "canonical_endpoints_match_graph",
                        "graph_matches_state",
                        "projection_preserves_contract",
                        "execution_order",
                    )
                ),
                ", ".join(
                    (
                        f"edges={len(dependency_contract.get('dependency_edges', []))}",
                        f"views={dependency_contract.get('views_checked', 0)}",
                        "canonical="
                        + str(dependency_contract.get("canonical_endpoints_match_graph")),
                        "state_graph="
                        + str(dependency_contract.get("graph_matches_state")),
                        "projection="
                        + str(dependency_contract.get("projection_preserves_contract")),
                        "order=" + str(dependency_contract.get("execution_order")),
                    )
                ),
            ),
            _result("State is displayed", bool(current.get("statuses")), str(current.get("statuses", []))),
        ]
    )
    return results


def build_report(
    legacy_graph_path: Path,
    legacy_counts: Mapping[str, int],
    legacy_graph_stats: Mapping[str, int],
    fixture_fingerprints: Mapping[str, Any],
    locale_runs: Mapping[str, Mapping[str, Any]],
) -> str:
    legacy_source_label = (Path(legacy_graph_path).parent.name + "/" + Path(legacy_graph_path).name)
    locale_summaries = {}
    for locale, locale_run in locale_runs.items():
        results = locale_run["results"]
        locale_summaries[locale] = {
            "passed": sum(1 for result in results if result["passed"]),
            "total": len(results),
        }
    overall = all(
        summary["passed"] == summary["total"] and summary["total"] > 0
        for summary in locale_summaries.values()
    )
    summary_text = "; ".join(
        f"{locale}: {summary['passed']}/{summary['total']}"
        for locale, summary in locale_summaries.items()
    )
    lines = [
        "# Dashboard Golden Test Report",
        "",
        f"**Overall result: {'PASS' if overall else 'FAIL'}** — {summary_text}.",
        "",
        "## Scope and limitation",
        "",
        "The v1.4 Golden Reference is read directly from the external `quadruped_perception_fusion/generated` directory. No Golden artifact is copied into this repository. The surviving example does not include its original task profile, tailored process, project state, or dashboard renderer. Therefore, this is an output-derived structural renderer test plus a separate current-version CLI lifecycle test; it is not claimed to be a same-source end-to-end reproduction.",
        "",
        f"Legacy graph source: external v1.4 Golden Reference `{legacy_source_label}`",
        "",
        "The hashes below identify the exact external fixture used for this run. They are evidence of fixture identity, not a claim that the missing v1.4 source inputs were reconstructed.",
        "",
        f"- Dependency graph SHA-256: `{fixture_fingerprints.get('dependency_graph_sha256', '')}`",
        f"- Generated inventory SHA-256: `{fixture_fingerprints.get('inventory_sha256', '')}`",
        f"- Fingerprinted inventory entries: {fixture_fingerprints.get('inventory_entries', 0)}",
        "",
        "## Golden Reference inventory",
        "",
        "| Metric | Observed | Expected |",
        "| --- | ---: | ---: |",
    ]
    for key in ("files", "html", "json", "markdown", "svg", "png"):
        lines.append(f"| {key.replace('_', ' ').title()} | {legacy_counts.get(key, 0)} | {LEGACY_EXPECTED[key]} |")
    lines.extend(["", "## Graph scale", "", "| Metric | Observed | Expected |", "| --- | ---: | ---: |"])
    for key in ("nodes", "internal_edges", "external_prerequisites"):
        lines.append(f"| {key.replace('_', ' ').title()} | {legacy_graph_stats.get(key, 0)} | {LEGACY_EXPECTED[key]} |")
    lines.extend(
        [
            "",
            "The normalized Golden graph is rendered in memory through the current custom SVG renderer. External prerequisites are counted but are not fabricated into nodes, preserving the 286-node render scale.",
            "",
            "## Locale summary",
            "",
            "| Locale | Result | Passed | Total | Structure fingerprint |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for locale, locale_run in locale_runs.items():
        summary = locale_summaries[locale]
        current = locale_run["current"]
        mark = "PASS" if summary["passed"] == summary["total"] else "FAIL"
        lines.append(
            f"| `{locale}` | {mark} | {summary['passed']} | {summary['total']} | "
            f"`{current.get('structure_fingerprint', '')}` |"
        )

    for locale, locale_run in locale_runs.items():
        current = locale_run["current"]
        profiles = locale_run["profiles"]
        results = locale_run["results"]
        summary = locale_summaries[locale]
        mark = "PASS" if summary["passed"] == summary["total"] else "FAIL"
        lines.extend(
            [
                "",
                f"## Locale `{locale}`",
                "",
                f"**{mark} — {summary['passed']} of {summary['total']} checks passed.**",
                "",
                "### Current dashboard results",
                "",
                f"- Structure fingerprint: `{current.get('structure_fingerprint', '')}`",
                f"- Files: {current.get('file_count', 0)}",
                f"- File types: `{json.dumps(current.get('file_types', {}), sort_keys=True)}`",
                f"- SVG: {current.get('svg_count', 0)}",
                f"- HTML: {current.get('html_count', 0)}",
                f"- JSON: {current.get('json_count', 0)}",
                f"- Graph nodes: {current.get('node_count', 0)}",
                f"- Graph edges: {current.get('edge_count', 0)}",
                f"- Node types: `{', '.join(current.get('node_types', []))}`",
                f"- Relations: `{', '.join(current.get('relations', []))}`",
                f"- Declared relation capability: `{', '.join(current.get('declared_relations', []))}`",
                f"- Statuses: `{', '.join(current.get('statuses', []))}`",
                "",
                "### Check results",
                "",
                "| Result | Check | Evidence |",
                "| --- | --- | --- |",
            ]
        )
        for result in results:
            result_mark = "PASS" if result["passed"] else "FAIL"
            evidence = str(result["evidence"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {result_mark} | {result['name']} | {evidence} |")
        lines.extend(["", "### CLI commands", ""])
        for task_type, profile in profiles.items():
            command_text = " -> ".join(command["command"] for command in profile["commands"])
            lines.append(
                f"- `{task_type}`: `{command_text}` "
                f"({'PASS' if profile['passed'] else 'FAIL'})"
            )
            for command in profile["commands"]:
                if command["exit_code"] != 0:
                    error = (
                        command.get("error")
                        or command.get("stderr")
                        or command.get("stdout")
                        or "unknown error"
                    )
                    lines.append(f"  - `{command['command']}`: {str(error).strip()}")

    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            f"**{'PASS' if overall else 'FAIL'}** — {summary_text}.",
            "",
            "Reproduce the bilingual formal report with one command:",
            "",
            "```text",
            "python scripts/dashboard_golden_test.py --legacy-root <v1.4-example-or-generated-directory> --locale both",
            "```",
            "",
            "Use `--locale en` or `--locale zh-CN` only when a single-locale diagnostic report is desired.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    legacy_root: Path,
    output_root: Path,
    report_path: Path,
    locale: str = "both",
) -> tuple[bool, str]:
    legacy_graph_path = locate_legacy_graph(legacy_root)
    generated_root = legacy_graph_path.parent
    payload = json.loads(legacy_graph_path.read_text(encoding="utf-8"))
    graph, legacy_graph_stats = normalize_legacy_graph(payload)
    counts = legacy_inventory(generated_root)
    fixture_fingerprints = legacy_fixture_fingerprints(generated_root, legacy_graph_path)
    locales = ("en", "zh-CN") if locale == "both" else (locale,)
    locale_runs: dict[str, dict[str, Any]] = {}
    for selected_locale in locales:
        locale_output = output_root / selected_locale
        golden_render = render_legacy_svg(
            graph,
            locale_output / "golden" / "deliverable_dependency.svg",
            locale=selected_locale,
        )
        profiles = run_cli_profiles(locale_output, locale=selected_locale)
        primary = profiles["software"]
        current = inspect_dashboard(primary["dashboard_root"], locale=selected_locale)
        results = evaluate(counts, legacy_graph_stats, golden_render, profiles, current)
        locale_runs[selected_locale] = {
            "golden_render": golden_render,
            "profiles": profiles,
            "current": current,
            "results": results,
        }
    report = build_report(
        legacy_graph_path,
        counts,
        legacy_graph_stats,
        fixture_fingerprints,
        locale_runs,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    passed = all(
        locale_run["results"]
        and all(result["passed"] for result in locale_run["results"])
        for locale_run in locale_runs.values()
    )
    return passed, report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--legacy-root",
        type=Path,
        required=True,
        help="v1.4 example root, generated directory, or dependency graph JSON",
    )
    parser.add_argument(
        "--locale",
        choices=("both", "en", "zh-CN"),
        default="both",
        help="Dashboard and CLI locale to exercise (default: both)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Keep generated test projects here; default uses an isolated temporary directory",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Report path (default: repository DASHBOARD_GOLDEN_TEST_REPORT.md)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output_root:
        output_root = args.output_root.expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        passed, _ = run(
            args.legacy_root,
            output_root,
            args.report.resolve(),
            locale=args.locale,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="ipd-dashboard-golden-") as temporary:
            passed, _ = run(
                args.legacy_root,
                Path(temporary),
                args.report.resolve(),
                locale=args.locale,
            )
    print(f"Dashboard Golden Test: {'PASS' if passed else 'FAIL'}")
    print(f"Report: {args.report.resolve()}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

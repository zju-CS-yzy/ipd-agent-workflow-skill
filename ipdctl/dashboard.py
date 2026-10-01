"""Deterministic, dependency-free IPD Dashboard publication facade.

The Dashboard is a read-only projection of tailored process, project state, and
Agent runtime facts.  Rendering is delegated to the typed model, HTML, and SVG
modules; this facade only stages, hashes, and atomically publishes the managed
output tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


DASHBOARD_RELATIVE_PATH = Path(".ipd") / "dashboard"


def _string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _json_text(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _value_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
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
    *,
    runtime: Mapping[str, Any] | None = None,
    bindings: Mapping[str, Any] | None = None,
    eligibility: Mapping[str, Any] | None = None,
    claim_readiness: Mapping[str, Any] | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    """Render and atomically publish the complete interactive Dashboard tree.

    The output is deterministic: no timestamps or absolute paths are emitted,
    so identical source facts and locale produce byte-for-byte identical files.
    """

    if not isinstance(process, Mapping):
        raise TypeError("process must be a mapping")
    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")
    if bindings is not None and not isinstance(bindings, Mapping):
        raise TypeError("bindings must be a mapping")
    if eligibility is not None and not isinstance(eligibility, Mapping):
        raise TypeError("eligibility must be a mapping")
    if claim_readiness is not None and not isinstance(claim_readiness, Mapping):
        raise TypeError("claim_readiness must be a mapping")

    from .dashboard_html import (
        render_deliverable_matrix,
        render_gate_matrix,
        render_index,
    )
    from .dashboard_model import PHASE_ORDER, build_dashboard_model, graph_slice
    from .dashboard_svg import (
        render_current_status_svg,
        render_dependency_svg,
        render_process_svg,
    )
    from .eligibility import claim_protocol_readiness, eligibility_fingerprint
    from .i18n import get_translator

    translator = get_translator(locale)
    eligibility_input = dict(eligibility) if isinstance(eligibility, Mapping) else {}
    if "bindings_sha256" in eligibility_input:
        bindings_sha256 = eligibility_input.get("bindings_sha256")
    elif isinstance(bindings, Mapping):
        bindings_sha256 = _value_sha256(bindings)
        eligibility_input["bindings_sha256"] = bindings_sha256
    else:
        bindings_sha256 = None
    claim_readiness_input = (
        dict(claim_readiness)
        if isinstance(claim_readiness, Mapping)
        else claim_protocol_readiness(
            Path(project_root),
            state,
            runtime if isinstance(runtime, Mapping) else {},
        )
    )
    state_data, graph_data = build_dashboard_model(
        process,
        state,
        runtime,
        eligibility=eligibility_input or None,
        claim_readiness=claim_readiness_input,
        translator=translator,
        locale=locale,
    )
    current_phase = _string(state_data["project"]["current"].get("phase"))
    available_ids = [item["id"] for item in state_data["available_tasks"]]
    blocked_ids = [
        item["id"]
        for item in state_data["deliverables"]
        if item.get("attention") == "explicitly_blocked"
    ]

    output = Path(project_root) / DASHBOARD_RELATIVE_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".dashboard.", dir=output.parent))
    try:
        process_graph = graph_slice(
            graph_data, node_types=("Phase", "TR", "DCP", "Gate")
        )
        current_graph = graph_slice(
            graph_data, phase=current_phase or None, include_upstream=True
        )
        dependency_graph = graph_slice(
            graph_data,
            phase=current_phase or None,
            node_types=("Deliverable",),
            include_upstream=True,
        )

        _atomic_write(staging / "data" / "state.json", _json_text(state_data))
        _atomic_write(staging / "data" / "graph.json", _json_text(graph_data))
        _atomic_write(
            staging / "assets" / "ipd_flow.svg",
            render_process_svg(process_graph, translator=translator),
        )
        _atomic_write(
            staging / "assets" / "current_status_flow.svg",
            render_current_status_svg(
                current_graph,
                current_phase=current_phase,
                available_ids=available_ids,
                blocked_ids=blocked_ids,
                filter_to_phase=False,
                translator=translator,
            ),
        )
        _atomic_write(
            staging / "assets" / "deliverable_dependency.svg",
            render_dependency_svg(
                dependency_graph,
                phase=current_phase or None,
                filter_to_phase=False,
                translator=translator,
            ),
        )

        discovered_phases = [item["id"] for item in state_data["phases"]]
        phase_ids: list[str] = []
        for phase_id in (*PHASE_ORDER[:5], *discovered_phases):
            if phase_id and phase_id not in phase_ids:
                phase_ids.append(phase_id)
        phase_files: dict[str, str] = {}
        for phase_id in phase_ids:
            phase_graph = graph_slice(
                graph_data,
                phase=phase_id,
                include_upstream=True,
            )
            filename = f"{phase_id}.svg"
            phase_files[phase_id] = f"phases/{filename}"
            phase_label = next(
                (
                    item.get("display_label") or item.get("title") or phase_id
                    for item in state_data["phases"]
                    if item.get("id") == phase_id
                ),
                phase_id,
            )
            _atomic_write(
                staging / "phases" / filename,
                render_dependency_svg(
                    phase_graph,
                    phase=phase_id,
                    title=translator.text("svg.phase_title", phase=phase_label),
                    filter_to_phase=False,
                    translator=translator,
                ),
            )

        _atomic_write(
            staging / "index.html",
            render_index(
                state_data,
                graph_data,
                phase_files,
                translator=translator,
            ),
        )
        _atomic_write(
            staging / "matrices" / "deliverable_matrix.html",
            render_deliverable_matrix(state_data, translator=translator),
        )
        _atomic_write(
            staging / "matrices" / "gate_matrix.html",
            render_gate_matrix(state_data, translator=translator),
        )

        filenames = sorted(
            path.relative_to(staging).as_posix()
            for path in staging.rglob("*")
            if path.is_file()
        )
        outputs = [
            {
                "path": (DASHBOARD_RELATIVE_PATH / filename).as_posix(),
                "sha256": _sha256(staging / filename),
            }
            for filename in filenames
        ]
        manifest = {
            "schema_version": "2.1",
            "locale": translator.locale,
            "output_directory": DASHBOARD_RELATIVE_PATH.as_posix(),
            "project": state_data["project"]["name"],
            "state_revision": state.get("revision"),
            "source_revision": state.get("revision"),
            "process_schema_version": process.get("schema_version"),
            "process_sha256": _value_sha256(process),
            "state_sha256": _value_sha256(state),
            "runtime_claims_sha256": _value_sha256(
                runtime.get("active_claims", {}) if isinstance(runtime, Mapping) else {}
            ),
            "bindings_sha256": bindings_sha256,
            "eligibility_sha256": eligibility_fingerprint(
                state_data.get("eligibility", {})
            ),
            "files": [*filenames, "manifest.json"],
            "outputs": outputs,
            "views": {
                "dashboard": "index.html",
                "process_flow": "assets/ipd_flow.svg",
                "current_status": "assets/current_status_flow.svg",
                "deliverable_dependency": "assets/deliverable_dependency.svg",
                "deliverable_matrix": "matrices/deliverable_matrix.html",
                "gate_matrix": "matrices/gate_matrix.html",
                "state": "data/state.json",
                "graph": "data/graph.json",
                "phases": phase_files,
            },
        }
        _atomic_write(staging / "manifest.json", _json_text(manifest))
        _publish_dashboard_tree(staging, output)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _publish_dashboard_tree(staging: Path, output: Path) -> None:
    """Replace one managed Dashboard tree without leaving mixed generations."""

    if staging.parent != output.parent:
        raise ValueError("dashboard staging and output directories must share a parent")
    backup = output.parent / f".{output.name}.previous"
    if backup.exists():
        shutil.rmtree(backup)
    had_output = output.exists()
    if had_output:
        os.replace(output, backup)
    try:
        os.replace(staging, output)
    except Exception:
        if had_output and backup.exists() and not output.exists():
            os.replace(backup, output)
        raise
    finally:
        if backup.exists():
            shutil.rmtree(backup)


__all__ = ["DASHBOARD_RELATIVE_PATH", "render_dashboard"]

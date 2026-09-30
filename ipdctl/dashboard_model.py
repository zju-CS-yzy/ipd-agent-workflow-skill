"""Normalize IPD process facts into a deterministic dashboard projection.

The renderer consumes this module's projection instead of reading project files
directly.  That keeps the Dashboard a read-only view of the process, state, and
Agent runtime facts while giving every renderer the same typed graph.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


PHASE_ORDER = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
RELATIONS = ("depends_on", "supports", "verifies", "supersedes")
DISPLAY_STATUSES = {"planned": "not_started", "accepted": "approved"}
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
        return [_string(item) for item in sorted(value, key=str)]
    if isinstance(value, Iterable):
        return [_string(item) for item in value if item is not None]
    return [_string(value)]


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        records: list[dict[str, Any]] = []
        for identifier in sorted(value, key=str):
            item = value[identifier]
            record = dict(item) if isinstance(item, Mapping) else {"title": item}
            record.setdefault("id", _string(identifier))
            records.append(record)
        return records
    return []


def _identifier(record: Mapping[str, Any], *fallback_keys: str) -> str:
    for key in ("id", *fallback_keys):
        value = _string(record.get(key)).strip()
        if value:
            return value
    return ""


def _humanize(identifier: str) -> str:
    value = identifier.rsplit(".", 1)[-1].replace("_", " ").replace("-", " ").strip()
    return value.title() or "Untitled"


def _display_text(value: Any, fallback: str) -> str:
    """Return source text unchanged, including non-Latin user content."""

    text = _string(value).strip()
    return text or fallback


def _safe_reference(value: Any) -> str | None:
    text = _string(value).strip()
    return text or None


def _translated_title(
    translator: Any,
    kind: str,
    identifier: str,
    value: Any,
    fallback: str,
) -> tuple[str, str]:
    """Return ``(source_title, display_label)`` for one workflow entity.

    Only a title that still matches the framework's English resource is
    localized.  A project-specific title, regardless of script, is preserved
    verbatim and remains the display label.
    """

    source = _display_text(value, fallback)
    if translator is None:
        return source, source
    catalog_identifier = identifier
    if kind == "checkpoint" and identifier.startswith("gate."):
        # Canonical Gate facts reuse the corresponding TR/DCP title.  The
        # catalog is keyed by the public checkpoint alias (``tr.*`` or
        # ``dcp.*``), while state deliberately stores only ``gate.*`` IDs.
        catalog_identifier = identifier.removeprefix("gate.")
    key = (
        f"phase.{catalog_identifier}"
        if kind == "phase"
        else f"workflow.{kind}.{catalog_identifier}"
    )
    try:
        from .i18n import get_translator

        english = get_translator("en").text(key)
        localized = translator.text(key)
    except (AttributeError, KeyError, TypeError, ValueError):
        return source, source
    if english != key and localized != key and source == english:
        return source, localized
    return source, source


def _phase_key(record: Mapping[str, Any]) -> tuple[int, int, str]:
    identifier = _identifier(record, "phase")
    try:
        canonical = PHASE_ORDER.index(identifier)
    except ValueError:
        canonical = len(PHASE_ORDER)
    sequence = record.get("sequence")
    return (sequence if type(sequence) is int else canonical, canonical, identifier)


def _status(value: Any, default: str = "planned") -> str:
    rendered = _string(value, default).strip() or default
    return rendered


def _display_status(value: str) -> str:
    return DISPLAY_STATUSES.get(value, value)


def _review_records(value: Any) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for raw in _records(value):
        evidence = _safe_reference(raw.get("evidence"))
        reviews.append(
            {
                "reviewer": _display_text(raw.get("reviewer"), "") or None,
                "reviewer_type": _string(raw.get("reviewer_type"), "unknown"),
                "authorized": raw.get("authorized") is True,
                "decision": _string(raw.get("decision"), "pending"),
                "evidence": evidence,
            }
        )
    # Review order is governance data: the latest authorized-human decision
    # controls the current outcome while all earlier evidence remains visible.
    return reviews


def _phase_records(process: Mapping[str, Any], current_phase: str) -> list[dict[str, Any]]:
    records = _records(process.get("phases"))
    known = {_identifier(item, "phase") for item in records}
    if current_phase and current_phase not in known:
        records.append({"id": current_phase, "title": _humanize(current_phase)})
    if not records:
        records = [
            {"id": phase, "title": _humanize(phase), "sequence": index}
            for index, phase in enumerate(PHASE_ORDER, start=1)
        ]
    return sorted(records, key=_phase_key)


def _activities(process: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def add(raw: Mapping[str, Any], phase: str = "") -> None:
        identifier = _identifier(raw, "activity_id")
        if not identifier:
            return
        record = dict(result.get(identifier, {}))
        record.update(dict(raw))
        record["id"] = identifier
        if phase:
            record.setdefault("phase", phase)
        result[identifier] = record

    for item in _records(process.get("activities")):
        add(item)
    for phase in _records(process.get("phases")):
        phase_id = _identifier(phase, "phase")
        for item in _records(phase.get("activities")):
            add(item, phase_id)
    return result


def _process_deliverables(process: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def add(raw: Mapping[str, Any], phase: str = "", activity: str = "") -> None:
        identifier = _identifier(raw, "deliverable_id", "artifact_id")
        if not identifier:
            return
        record = dict(result.get(identifier, {}))
        record.update(dict(raw))
        record["id"] = identifier
        if phase:
            record.setdefault("phase", phase)
        if activity:
            record.setdefault("activity_id", activity)
        result[identifier] = record

    for item in _records(process.get("deliverables")):
        add(item)
    for phase in _records(process.get("phases")):
        phase_id = _identifier(phase, "phase")
        for item in _records(phase.get("deliverables")):
            add(item, phase_id)
        for activity in _records(phase.get("activities")):
            activity_id = _identifier(activity, "activity_id")
            for item in _records(activity.get("deliverables")):
                add(item, phase_id, activity_id)
    return result


def _state_index(state: Mapping[str, Any], field: str, *fallbacks: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _records(state.get(field)):
        identifier = _identifier(item, *fallbacks)
        if identifier:
            result[identifier] = item
    return result


def _checkpoint_records(process: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def add(value: Any, node_type: str, phase: str = "") -> None:
        for raw in _records(value):
            record = dict(raw)
            record["node_type"] = node_type
            if phase:
                record.setdefault("phase", phase)
            identifier = _identifier(record, "checkpoint_id", "gate_id")
            if identifier:
                record["id"] = identifier
                result.append(record)

    add(process.get("technical_reviews") or process.get("trs"), "TR")
    add(process.get("decision_checkpoints") or process.get("dcps"), "DCP")
    add(process.get("gates"), "Gate")
    for phase in _records(process.get("phases")):
        phase_id = _identifier(phase, "phase")
        add(phase.get("technical_reviews") or phase.get("trs"), "TR", phase_id)
        add(phase.get("decision_checkpoints") or phase.get("dcps"), "DCP", phase_id)
        add(phase.get("gates"), "Gate", phase_id)

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in result:
        unique[(item["node_type"], item["id"])] = item
    return sorted(
        unique.values(),
        key=lambda item: (
            PHASE_ORDER.index(item.get("phase"))
            if item.get("phase") in PHASE_ORDER
            else len(PHASE_ORDER),
            item.get("sequence") if type(item.get("sequence")) is int else 10_000,
            {"TR": 0, "DCP": 1, "Gate": 2}.get(item["node_type"], 3),
            item["id"],
        ),
    )


def _checkpoint_state(
    record: Mapping[str, Any],
    state_gates: Mapping[str, Mapping[str, Any]],
    current: Mapping[str, Any],
) -> Mapping[str, Any]:
    identifier = _identifier(record)
    linked_gate = _string(record.get("gate_id"))
    linked_checkpoint = _string(record.get("checkpoint_id"))
    state_record = (
        state_gates.get(linked_gate)
        or state_gates.get(identifier)
        or state_gates.get(linked_checkpoint)
        or {}
    )
    if state_record:
        return state_record
    current_key = {"TR": "tr", "DCP": "dcp", "Gate": "gate"}.get(
        _string(record.get("node_type")), "gate"
    )
    if identifier == _string(current.get(current_key)):
        return {"status": "in_progress"}
    return {}


def _normalized_edges(
    process: Mapping[str, Any],
    state: Mapping[str, Any],
    deliverables: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    checkpoints: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> list[dict[str, str]]:
    node_ids = {
        item["id"] for group in (deliverables, activities, checkpoints, phases) for item in group
    }
    edges: set[tuple[str, str, str]] = set()

    def add(source: Any, target: Any, relation: Any) -> None:
        source_id, target_id = _string(source), _string(target)
        relation_id = _string(relation, "depends_on")
        if (
            source_id
            and target_id
            and source_id != target_id
            and source_id in node_ids
            and target_id in node_ids
            and relation_id in RELATIONS
        ):
            edges.add((source_id, target_id, relation_id))

    for deliverable in deliverables:
        for dependency in deliverable["depends_on"]:
            add(deliverable["id"], dependency, "depends_on")
        if deliverable.get("replacement"):
            add(deliverable["id"], deliverable["replacement"], "supersedes")
        if deliverable.get("activity"):
            add(deliverable["activity"], deliverable["id"], "supports")
    for activity in activities:
        add(activity.get("phase"), activity["id"], "supports")
    for checkpoint in checkpoints:
        phase = checkpoint.get("phase")
        if phase:
            add(phase, checkpoint["id"], "supports")
        for deliverable_id in checkpoint["required_deliverables"]:
            add(deliverable_id, checkpoint["id"], "verifies")
    for collection in (process.get("dependencies"), state.get("traceability")):
        for edge in _records(collection):
            add(
                edge.get("source") or edge.get("from"),
                edge.get("target") or edge.get("to"),
                edge.get("relation") or edge.get("type") or "depends_on",
            )
    return [
        {"source": source, "target": target, "relation": relation}
        for source, target, relation in sorted(edges)
    ]


def build_dashboard_model(
    process: Mapping[str, Any],
    state: Mapping[str, Any],
    runtime: Mapping[str, Any] | None = None,
    *,
    translator: Any | None = None,
    locale: str = "en",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the canonical state and graph documents used by every view."""

    if not isinstance(process, Mapping):
        raise TypeError("process must be a mapping")
    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")
    if translator is None:
        from .i18n import get_translator

        translator = get_translator(locale)
    locale = _string(getattr(translator, "locale", locale), locale)
    runtime = runtime if isinstance(runtime, Mapping) else {}
    project_state = state.get("project") if isinstance(state.get("project"), Mapping) else {}
    project_name = _display_text(
        project_state.get("name") or (process.get("profile") or {}).get("name"),
        "IPD Project",
    )
    current = {
        "phase": _string(project_state.get("phase")) or None,
        "tr": project_state.get("current_tr"),
        "dcp": project_state.get("current_dcp"),
        "gate": project_state.get("current_gate"),
    }
    current_phase = _string(current["phase"])
    active_claims = runtime.get("active_claims") if isinstance(runtime.get("active_claims"), Mapping) else {}

    state_deliverables = _state_index(state, "deliverables", "deliverable_id")
    process_deliverables = _process_deliverables(process)
    deliverables: list[dict[str, Any]] = []
    for identifier in sorted(set(process_deliverables) | set(state_deliverables)):
        process_item = process_deliverables.get(identifier, {})
        state_item = state_deliverables.get(identifier, {})
        canonical_status = _status(state_item.get("status"), "planned")
        claim = active_claims.get(identifier) if isinstance(active_claims, Mapping) else None
        orphaned_claim = canonical_status == "in_progress" and claim is None
        owner = claim.get("actor") if isinstance(claim, Mapping) else None
        owner = owner or state_item.get("owner") or process_item.get("owner")
        title, display_label = _translated_title(
            translator,
            "deliverable",
            identifier,
            state_item.get("title") or process_item.get("title"),
            _humanize(identifier),
        )
        evidence = [
            reference
            for item in _string_list(state_item.get("evidence"))
            if (reference := _safe_reference(item))
        ]
        deliverables.append(
            {
                "id": identifier,
                "title": title,
                "display_label": display_label,
                "phase": _string(state_item.get("phase") or process_item.get("phase")) or None,
                "activity": _string(
                    state_item.get("activity_id") or process_item.get("activity_id")
                )
                or None,
                "owner": _display_text(owner, "Unassigned") if owner else None,
                "status": canonical_status,
                "display_status": _display_status(canonical_status),
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
                "evidence": sorted(set(evidence)),
                "reviews": _review_records(state_item.get("reviews")),
                "blocker": (
                    translator.text("runtime.orphan_claim")
                    if orphaned_claim
                    else _display_text(
                        state_item.get("blocked_reason") or state_item.get("blocker"),
                        "Blocked by an unresolved condition",
                    )
                    if state_item.get("blocked_reason") or state_item.get("blocker")
                    else None
                ),
                "recoverable_claim": orphaned_claim,
                "replacement": _string(state_item.get("replacement")) or None,
            }
        )

    status_by_id = {item["id"]: item["status"] for item in deliverables}
    available_tasks: list[dict[str, Any]] = []
    blocked_items: list[dict[str, Any]] = []
    for item in deliverables:
        unmet = [
            dependency
            for dependency in item["depends_on"]
            if status_by_id.get(dependency) != "accepted"
        ]
        is_claimed = item["id"] in active_claims
        in_current_scope = not current_phase or item.get("phase") in {None, current_phase}
        if (
            in_current_scope
            and item["status"] in {"planned", "blocked", "rejected"}
            and not unmet
            and not is_claimed
        ):
            available_tasks.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "display_label": item["display_label"],
                    "phase": item["phase"],
                    "owner": item["owner"],
                    "status": item["status"],
                }
            )
        if in_current_scope and (
            item["status"] == "blocked" or unmet or item.get("recoverable_claim")
        ):
            blocked_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "display_label": item["display_label"],
                    "status": item["status"],
                    "unmet_dependencies": unmet,
                    "reason": item["blocker"],
                    "recoverable": bool(item.get("recoverable_claim")),
                }
            )

    process_activities = _activities(process)
    activities: list[dict[str, Any]] = []
    for identifier, item in sorted(process_activities.items()):
        child_statuses = [
            deliverable["status"]
            for deliverable in deliverables
            if deliverable.get("activity") == identifier
        ]
        if child_statuses and all(value == "accepted" for value in child_statuses):
            activity_status = "accepted"
        elif any(value == "blocked" for value in child_statuses):
            activity_status = "blocked"
        elif any(value not in {"planned", "superseded"} for value in child_statuses):
            activity_status = "in_progress"
        else:
            activity_status = "planned"
        title, display_label = _translated_title(
            translator,
            "activity",
            identifier,
            item.get("title"),
            _humanize(identifier),
        )
        activities.append(
            {
                "id": identifier,
                "title": title,
                "display_label": display_label,
                "phase": _string(item.get("phase")) or None,
                "status": activity_status,
                "deliverables": sorted(
                    deliverable["id"]
                    for deliverable in deliverables
                    if deliverable.get("activity") == identifier
                ),
            }
        )

    state_gates = _state_index(state, "gates", "gate_id", "checkpoint_id")
    checkpoints: list[dict[str, Any]] = []
    deliverables_by_id = {item["id"]: item for item in deliverables}
    for process_item in _checkpoint_records(process):
        state_item = _checkpoint_state(process_item, state_gates, current)
        required = sorted(
            set(
                _string_list(
                    state_item.get(
                        "required_deliverables", process_item.get("required_deliverables")
                    )
                )
            )
        )
        blockers = [
            {"deliverable": identifier, "status": deliverables_by_id.get(identifier, {}).get("status", "missing")}
            for identifier in required
            if deliverables_by_id.get(identifier, {}).get("status") != "accepted"
        ]
        blockers.extend(
            {"deliverable": None, "status": _display_text(item, "Unresolved blocker")}
            for item in _string_list(state_item.get("blockers"))
        )
        reviews = _review_records(state_item.get("reviews"))
        evidence = sorted(
            {
                reference
                for raw in _string_list(state_item.get("evidence"))
                if (reference := _safe_reference(raw))
            }
            | {review["evidence"] for review in reviews if review.get("evidence")}
        )
        node_type = _string(process_item.get("node_type"), "Gate")
        identifier = _identifier(process_item)
        canonical_status = _status(
            state_item.get("status") or process_item.get("status"), "planned"
        )
        authorized_human_reviews = [
            review
            for review in reviews
            if review["reviewer_type"] == "human"
            and review["authorized"]
            and review["decision"] in {"approve", "reject"}
        ]
        latest_authorized_decision = (
            authorized_human_reviews[-1]["decision"]
            if authorized_human_reviews
            else None
        )
        approval_status = (
            "rejected"
            if latest_authorized_decision == "reject"
            else "approved"
            if canonical_status in {"approved", "accepted"}
            and latest_authorized_decision == "approve"
            else "pending"
        )
        title, display_label = _translated_title(
            translator,
            "checkpoint",
            identifier,
            process_item.get("title"),
            _humanize(identifier),
        )
        checkpoints.append(
            {
                "id": identifier,
                "title": title,
                "display_label": display_label,
                "type": node_type,
                "phase": _string(process_item.get("phase")) or None,
                "status": canonical_status,
                "display_status": _display_status(canonical_status),
                "required_deliverables": required,
                "input_evidence": sorted(
                    {
                        evidence_item
                        for deliverable_id in required
                        for evidence_item in deliverables_by_id.get(deliverable_id, {}).get(
                            "evidence", []
                        )
                    }
                ),
                "output_deliverables": required,
                "evidence": evidence,
                "blockers": blockers,
                "readiness": {
                    "ready": not blockers,
                    "accepted": sum(
                        deliverables_by_id.get(item, {}).get("status") == "accepted"
                        for item in required
                    ),
                    "required": len(required),
                },
                "approval": {
                    "status": approval_status,
                    "authorized_human": latest_authorized_decision == "approve",
                    "latest_authorized_human_decision": latest_authorized_decision,
                    "reviews": reviews,
                },
            }
        )

    phases: list[dict[str, Any]] = []
    for raw in _phase_records(process, current_phase):
        identifier = _identifier(raw, "phase")
        title, display_label = _translated_title(
            translator,
            "phase",
            identifier,
            raw.get("title"),
            _humanize(identifier),
        )
        phase_deliverables = [item for item in deliverables if item.get("phase") == identifier]
        phase_gates = [
            item
            for item in checkpoints
            if item.get("phase") == identifier and item.get("type") == "Gate"
        ]
        explicitly_blocked = any(
            item["status"] in {"blocked", "rejected"}
            for item in phase_deliverables
        ) or any(item["status"] in {"blocked", "rejected"} for item in phase_gates)
        gates_approved = bool(phase_gates) and all(
            item["status"] in {"approved", "accepted"} for item in phase_gates
        )
        if explicitly_blocked:
            phase_status = "blocked"
        elif (
            phase_deliverables
            and all(item["status"] == "accepted" for item in phase_deliverables)
            and gates_approved
        ):
            phase_status = "accepted"
        elif identifier == current_phase:
            phase_status = "in_progress"
        else:
            phase_status = _status(raw.get("status"), "planned")
        phases.append(
            {
                "id": identifier,
                "title": title,
                "display_label": display_label,
                "sequence": raw.get("sequence"),
                "status": phase_status,
                "current": identifier == current_phase,
                "deliverable_count": len(phase_deliverables),
                "accepted_count": sum(item["status"] == "accepted" for item in phase_deliverables),
            }
        )

    graph_nodes: list[dict[str, Any]] = []
    for phase in phases:
        graph_nodes.append(
            {
                "id": phase["id"],
                "type": "Phase",
                "title": phase["title"],
                "display_label": phase["display_label"],
                "phase": phase["id"],
                "status": phase["status"],
                "display_status": _display_status(phase["status"]),
                "current": phase["current"],
                "blocked": phase["status"] == "blocked",
                "detail_key": f"phase:{phase['id']}",
            }
        )
    for activity in activities:
        graph_nodes.append(
            {
                "id": activity["id"],
                "type": "Activity",
                "title": activity["title"],
                "display_label": activity["display_label"],
                "phase": activity["phase"],
                "status": activity["status"],
                "display_status": _display_status(activity["status"]),
                "current": activity["phase"] == current_phase,
                "blocked": activity["status"] == "blocked",
                "detail_key": f"activity:{activity['id']}",
            }
        )
    blocked_ids = {item["id"] for item in blocked_items}
    for deliverable in deliverables:
        graph_nodes.append(
            {
                "id": deliverable["id"],
                "type": "Deliverable",
                "title": deliverable["title"],
                "display_label": deliverable["display_label"],
                "phase": deliverable["phase"],
                "status": deliverable["status"],
                "display_status": deliverable["display_status"],
                "current": deliverable["phase"] == current_phase,
                "blocked": deliverable["id"] in blocked_ids,
                "detail_key": f"deliverable:{deliverable['id']}",
            }
        )
    current_ids = {_string(value) for value in current.values() if value}
    for checkpoint in checkpoints:
        graph_nodes.append(
            {
                "id": checkpoint["id"],
                "type": checkpoint["type"],
                "title": checkpoint["title"],
                "display_label": checkpoint["display_label"],
                "phase": checkpoint["phase"],
                "status": checkpoint["status"],
                "display_status": checkpoint["display_status"],
                "current": checkpoint["id"] in current_ids,
                "blocked": checkpoint["status"] in {"blocked", "rejected"}
                or (
                    checkpoint["phase"] == current_phase
                    and bool(checkpoint["blockers"])
                ),
                "detail_key": f"{checkpoint['type'].lower()}:{checkpoint['id']}",
            }
        )

    edges = _normalized_edges(process, state, deliverables, activities, checkpoints, phases)
    repository = project_state.get("repository") if isinstance(project_state.get("repository"), Mapping) else {}
    accepted = sum(item["status"] == "accepted" for item in deliverables)
    review_queue = sum(
        item["status"] in {"ready_for_review", "in_review"} for item in deliverables
    )
    state_document = {
        "schema_version": "2.0",
        "locale": locale,
        "project": {
            "name": project_name,
            "state_revision": state.get("revision"),
            "process_schema_version": process.get("schema_version"),
            "workflow_step": _string(project_state.get("workflow_step"), "context"),
            "current": current,
            "repository": {
                "kind": _string(repository.get("kind"), "none"),
                "branch": _safe_reference(repository.get("branch")),
                "revision": _safe_reference(repository.get("revision")),
                "dirty": repository.get("dirty"),
                "remote": _safe_reference(repository.get("remote")),
            },
        },
        "summary": {
            "total_deliverables": len(deliverables),
            "accepted_deliverables": accepted,
            "progress_percent": round(100 * accepted / len(deliverables)) if deliverables else 0,
            "review_queue": review_queue,
            "blocked_items": len(blocked_items),
            "available_tasks": len(available_tasks),
        },
        "phases": phases,
        "activities": activities,
        "checkpoints": checkpoints,
        "deliverables": deliverables,
        "available_tasks": available_tasks,
        "blocked_items": blocked_items,
    }
    graph_document = {
        "schema_version": "2.0",
        "locale": locale,
        "project": project_name,
        "current_phase": current_phase or None,
        "node_types": ["Phase", "TR", "DCP", "Gate", "Activity", "Deliverable"],
        "relation_types": list(RELATIONS),
        "status_aliases": dict(DISPLAY_STATUSES),
        "nodes": sorted(
            graph_nodes,
            key=lambda item: (
                PHASE_ORDER.index(item.get("phase"))
                if item.get("phase") in PHASE_ORDER
                else len(PHASE_ORDER),
                {"Phase": 0, "Activity": 1, "Deliverable": 2, "TR": 3, "DCP": 4, "Gate": 5}.get(
                    item["type"], 6
                ),
                item["id"],
            ),
        ),
        "edges": edges,
    }
    return state_document, graph_document


def graph_slice(
    graph: Mapping[str, Any],
    *,
    phase: str | None = None,
    node_types: Iterable[str] | None = None,
    include_upstream: bool = False,
) -> dict[str, Any]:
    """Return a stable subgraph for one visualization."""

    types = set(node_types or ())
    all_nodes = {item["id"]: item for item in _records(graph.get("nodes"))}
    selected = {
        identifier
        for identifier, item in all_nodes.items()
        if (phase is None or item.get("phase") == phase)
        and (not types or item.get("type") in types)
    }
    if include_upstream:
        changed = True
        while changed:
            changed = False
            for edge in _records(graph.get("edges")):
                if (
                    edge.get("relation") == "depends_on"
                    and edge.get("source") in selected
                    and edge.get("target") in all_nodes
                    and edge.get("target") not in selected
                ):
                    selected.add(edge["target"])
                    changed = True
    edges = [
        edge
        for edge in _records(graph.get("edges"))
        if edge.get("source") in selected and edge.get("target") in selected
    ]
    result = dict(graph)
    result["nodes"] = [all_nodes[identifier] for identifier in sorted(selected)]
    result["edges"] = sorted(
        edges,
        key=lambda item: (
            _string(item.get("source")),
            _string(item.get("target")),
            _string(item.get("relation")),
        ),
    )
    return result


__all__ = [
    "DISPLAY_STATUSES",
    "PHASE_ORDER",
    "RELATIONS",
    "build_dashboard_model",
    "graph_slice",
]

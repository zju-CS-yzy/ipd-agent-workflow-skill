"""Offline HTML renderers for the IPD dashboard.

The module deliberately has no template or browser dependency.  Every renderer
returns a deterministic HTML document with renderer-owned inline SVGs when
provided, portable export links, and escaped project data in markup or
JavaScript.
"""

from __future__ import annotations

from html import escape
import json
import re
from typing import Any, Mapping, Sequence


def _text(value: Any, fallback: str = "—") -> str:
    """Return display text unchanged; escaping happens at the output boundary."""

    if value is None:
        return fallback
    result = str(value).strip()
    return result or fallback


def _h(value: Any, fallback: str = "—") -> str:
    return escape(_text(value, fallback), quote=True)


def _items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_text(item) for item in value if item is not None]


def _scrub(value: Any) -> Any:
    """Copy data into JSON-compatible containers without altering user text."""

    if isinstance(value, Mapping):
        return {str(key): _scrub(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        return value
    return value


def _json_script(value: Any) -> str:
    encoded = json.dumps(
        _scrub(value), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _status_class(value: Any) -> str:
    status = _text(value, "unknown").lower().replace(" ", "_")
    allowed = {
        "planned",
        "not_started",
        "in_progress",
        "ready_for_review",
        "in_review",
        "accepted",
        "approved",
        "rejected",
        "blocked",
        "superseded",
        "ready",
        "pending",
        "current",
        "missing",
    }
    return status if status in allowed else "unknown"


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


def _status_label(value: Any, translator: Any) -> str:
    status = _status_class(value)
    fallback = _text(value, "Unknown").replace("_", " ").title()
    return _t(translator, f"status.{status}", fallback)


def _phase_label(value: Any, translator: Any) -> str:
    phase = _text(value, "").strip()
    if not phase:
        return ""
    fallback = phase.replace("_", " ").replace("-", " ").title()
    return _t(translator, f"phase.{phase}", fallback)


def _binding_text(translator: Any, key: str) -> str:
    """Return local display copy while binding machine codes stay English."""

    copy = {
        "readiness": ("Binding readiness", "产物绑定就绪度"),
        "blockers": ("Binding blockers", "产物绑定阻塞项"),
        "ready": ("Ready", "已就绪"),
        "not_ready": ("Not ready", "未就绪"),
        "no_blockers": ("No binding blockers", "无产物绑定阻塞项"),
        "waiting_on_bindings": ("Waiting on bindings", "等待产物绑定"),
    }
    english, chinese = copy[key]
    locale = _text(getattr(translator, "locale", "en"), "en").lower()
    fallback = chinese if locale.startswith("zh") else english
    return _t(translator, f"dashboard.binding_{key}", fallback)


def _count(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return _text(value, "0")


_BASE_CSS = r"""
:root {
  color-scheme: light;
  --text: #182230;
  --muted: #667085;
  --line: #D0D5DD;
  --line-strong: #98A2B3;
  --bg: #F8FAFC;
  --surface: #FFFFFF;
  --blue: #1570EF;
  --blue-soft: #EFF8FF;
  --green: #039855;
  --green-soft: #ECFDF3;
  --amber: #DC6803;
  --amber-soft: #FFFAEB;
  --red: #D92D20;
  --red-soft: #FEF3F2;
  --purple: #7F56D9;
  --purple-soft: #F4F3FF;
  --shadow: 0 1px 2px rgba(16, 24, 40, .05), 0 8px 24px rgba(16, 24, 40, .06);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-width: 320px;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", Tahoma, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.45;
}
button, input, select { font: inherit; }
button, select, input { color: var(--text); }
a { color: var(--blue); }
:focus-visible { outline: 3px solid rgba(21,112,239,.28); outline-offset: 2px; }
.shell { width: min(1900px, calc(100% - 32px)); margin: 0 auto 56px; }
.topbar {
  margin: 16px 0 0;
  padding: 22px 26px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  background: #101828;
  color: #fff;
  border-radius: 8px 8px 0 0;
}
.eyebrow { margin: 0 0 4px; color: #B2CCFF; font-size: 12px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
h1 { margin: 0; font-size: clamp(22px, 2.2vw, 34px); line-height: 1.14; letter-spacing: -.025em; }
.top-meta { display: grid; grid-template-columns: repeat(2, minmax(110px, 1fr)); gap: 6px 24px; font-size: 12px; }
.top-meta span { color: #98A2B3; display: block; }
.top-meta strong { color: #F2F4F7; font-weight: 600; }
.summary-strip {
  display: grid;
  grid-template-columns: repeat(10, minmax(104px, 1fr));
  background: var(--surface);
  border: 1px solid var(--line);
  border-top: 0;
  box-shadow: var(--shadow);
}
.metric { min-height: 88px; padding: 16px 18px; border-right: 1px solid #EAECF0; }
.metric:last-child { border-right: 0; }
.metric-label { display: block; color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.metric-value { display: block; margin-top: 7px; font-size: 18px; font-weight: 750; line-height: 1.2; overflow-wrap: anywhere; }
.metric-value.alert { color: var(--red); }
.refinement-alert {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 14px;
  margin: 16px 0;
  padding: 14px 18px;
  border: 2px solid #0E9384;
  background: #F0FDF9;
  color: #134E48;
}
.refinement-alert .kicker { font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.refinement-alert strong { color: #107569; }
.progress { height: 5px; margin-top: 9px; overflow: hidden; background: #EAECF0; border-radius: 999px; }
.progress > span { display: block; height: 100%; background: var(--blue); }
.next-task {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 14px;
  margin: 16px 0;
  padding: 14px 18px;
  border: 1px solid #84ADFF;
  background: var(--blue-soft);
}
.next-task strong { font-size: 15px; }
.next-task .kicker { color: var(--blue); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.next-task .task-meta { color: var(--muted); font-size: 12px; }
.phase-rail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin: 0 0 16px;
  border: 1px solid var(--line);
  background: var(--surface);
}
.phase-card {
  appearance: none;
  min-height: 86px;
  padding: 13px 15px;
  text-align: left;
  border: 0;
  border-right: 1px solid #EAECF0;
  background: transparent;
  cursor: pointer;
}
.phase-card:last-child { border-right: 0; }
.phase-card:hover { background: #F9FAFB; }
.phase-card.active { box-shadow: inset 0 -4px 0 var(--blue); background: var(--blue-soft); }
.phase-sequence { color: var(--muted); font-size: 11px; font-weight: 700; }
.phase-title { display: block; margin: 3px 0 6px; font-size: 15px; font-weight: 750; }
.phase-count { color: var(--muted); font-size: 12px; }
.workspace { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
.workspace.detail-closed { grid-template-columns: minmax(0, 1fr); }
.main { min-width: 0; display: grid; gap: 16px; }
.panel { background: var(--surface); border: 1px solid var(--line); box-shadow: var(--shadow); }
.panel-head { min-height: 58px; padding: 13px 18px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid #EAECF0; }
.panel-head h2 { margin: 0; font-size: 16px; letter-spacing: -.01em; }
.panel-head p { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
.panel-body { padding: 16px 18px; }
.diagram-frame { min-height: 360px; overflow: auto; border: 1px solid #EAECF0; background: #fff; }
.diagram-frame.compact { min-height: 280px; }
.diagram-frame > svg { display:block; width:100%; height:auto; transform-origin:0 0; }
.relation-filtered .edge:not([data-relation="depends_on"]) { display:none; }
.relation-tools { display:flex; flex-wrap:wrap; gap:12px; align-items:center; border:0; margin:0 0 12px; padding:0; grid-column:1 / -1; }
.relation-tools label { display:flex; align-items:center; gap:5px; }
.file-path { overflow-wrap:anywhere; }
.file-actions { display:flex; gap:10px; margin:4px 0 10px; }
.diagram-frame object { display: block; width: 100%; height: 520px; transform-origin: 0 0; transition: transform .16s ease; }
.diagram-frame.compact object { height: 390px; }
.diagram-pair { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 12px; }
.tools { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.btn, .select, .search {
  min-height: 34px;
  border: 1px solid var(--line-strong);
  border-radius: 5px;
  background: #fff;
}
.btn { min-width: 34px; padding: 6px 10px; cursor: pointer; font-weight: 650; }
.btn:hover { border-color: var(--blue); color: var(--blue); }
.select { padding: 6px 28px 6px 9px; }
.search { width: min(260px, 34vw); padding: 6px 10px; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.table-scroll { overflow: auto; max-height: 560px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { position: sticky; top: 0; z-index: 1; padding: 9px 10px; text-align: left; color: #344054; background: #F2F4F7; border-bottom: 1px solid var(--line); white-space: nowrap; }
td { padding: 9px 10px; border-bottom: 1px solid #EAECF0; vertical-align: top; }
tbody tr[data-node] { cursor: pointer; }
tbody tr[data-node]:hover, tbody tr[data-node]:focus-within { background: var(--blue-soft); }
.row-link { color: var(--text); font-weight: 700; text-decoration: none; }
.muted { color: var(--muted); }
.badge { display: inline-block; padding: 2px 7px; border: 1px solid currentColor; border-radius: 999px; font-size: 10px; font-weight: 750; letter-spacing: .02em; white-space: nowrap; }
.status-planned, .status-not_started, .status-unknown { color: #667085; background: #F2F4F7; }
.status-pending, .status-current, .status-missing { color: #667085; background: #F2F4F7; }
.status-in_progress { color: var(--blue); background: var(--blue-soft); }
.status-ready_for_review, .status-ready { color: var(--amber); background: var(--amber-soft); }
.status-in_review { color: var(--purple); background: var(--purple-soft); }
.status-accepted, .status-approved { color: var(--green); background: var(--green-soft); }
.status-rejected, .status-blocked { color: var(--red); background: var(--red-soft); }
.status-superseded { color: #475467; background: #EAECF0; }
.details { position: sticky; top: 16px; max-height: calc(100vh - 32px); overflow: auto; background: #fff; border: 1px solid var(--line); box-shadow: var(--shadow); }
.details[hidden] { display: none; }
.details-head { position: sticky; top: 0; z-index: 2; display: flex; justify-content: space-between; gap: 12px; padding: 16px 18px; color: #fff; background: #101828; }
.details-head h2 { margin: 2px 0 0; font-size: 18px; overflow-wrap: anywhere; }
.details-head .eyebrow { margin: 0; }
.details-close { align-self: start; border: 1px solid #667085; background: transparent; color: #fff; border-radius: 4px; cursor: pointer; }
.details-body { padding: 4px 18px 22px; }
.detail-section { padding: 15px 0; border-bottom: 1px solid #EAECF0; }
.detail-section:last-child { border-bottom: 0; }
.detail-section h3 { margin: 0 0 8px; color: #344054; font-size: 11px; letter-spacing: .07em; text-transform: uppercase; }
.detail-section p { margin: 0; }
.detail-section code { white-space: pre-wrap; overflow-wrap: anywhere; color: #344054; }
.detail-list { margin: 0; padding-left: 18px; }
.detail-list li + li { margin-top: 5px; }
.empty { padding: 24px; color: var(--muted); text-align: center; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
@media (max-width: 1180px) {
  .summary-strip { grid-template-columns: repeat(4, 1fr); }
  .metric:nth-child(4) { border-right: 0; }
  .workspace { grid-template-columns: minmax(0, 1fr); }
  .details { position: fixed; z-index: 20; inset: 16px 16px 16px auto; width: min(420px, calc(100vw - 32px)); }
  .diagram-pair { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .shell { width: min(100% - 16px, 1900px); }
  .topbar { align-items: flex-start; flex-direction: column; padding: 18px; }
  .summary-strip { grid-template-columns: repeat(2, 1fr); }
  .metric:nth-child(even) { border-right: 0; }
  .next-task { grid-template-columns: 1fr; }
  .panel-head { align-items: flex-start; flex-direction: column; }
  .search { width: 100%; }
  .filters { width: 100%; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; transition: none !important; } }
"""


def _localize_static_html(template: str, translator: Any) -> str:
    """Localize trusted framework copy before project data is inserted."""

    locale = _text(getattr(translator, "locale", "en"), "en")
    replacements = {
        '<html lang="en">': f'<html lang="{escape(locale, quote=True)}">',
        "IPD Agent Workflow Framework": _t(
            translator,
            "dashboard.framework",
            "IPD Agent Workflow Framework",
        ),
        "IPD Dashboard · __PROJECT_TITLE__": _t(
            translator,
            "dashboard.page_title",
            "IPD Dashboard · {project}",
            project="__PROJECT_TITLE__",
        ),
        "Dashboard metadata": _t(translator, "dashboard.metadata", "Dashboard metadata"),
        "State revision": _t(translator, "dashboard.state_revision", "State revision"),
        "Process schema": _t(translator, "dashboard.process_schema", "Process schema"),
        "Workflow step": _t(translator, "dashboard.workflow_step", "Workflow step"),
        "Repository state": _t(translator, "dashboard.repository_state", "Repository state"),
        "Project summary": _t(translator, "dashboard.project_summary", "Project summary"),
        "Current phase": _t(translator, "dashboard.current_phase", "Current phase"),
        "Current TR": _t(translator, "dashboard.current_tr", "Current TR"),
        "Current DCP / Gate": _t(translator, "dashboard.current_dcp_gate", "Current DCP / Gate"),
        "Current review subject": _t(
            translator,
            "dashboard.current_iteration_subject",
            "Current review subject",
        ),
        "Progress": _t(translator, "dashboard.progress", "Progress"),
        "Accepted": _t(translator, "dashboard.accepted", "Accepted"),
        "Review queue": _t(translator, "dashboard.review_queue", "Review queue"),
        "Refinement due": _t(
            translator, "dashboard.refinement_due", "Refinement due"
        ),
        "Waiting on prerequisites": _t(
            translator,
            "dashboard.waiting_on_dependencies",
            "Waiting on prerequisites",
        ),
        "Explicit blockers": _t(
            translator, "dashboard.explicit_blockers", "Explicit blockers"
        ),
        "Governance blockers": _t(
            translator, "dashboard.governance_blockers", "Governance blockers"
        ),
        "Next available task": _t(translator, "dashboard.next_task", "Next available task"),
        "Open details": _t(translator, "dashboard.open_details", "Open details"),
        "Project phases": _t(translator, "dashboard.project_phases", "Project phases"),
        "IPD process flow diagram": _t(translator, "dashboard.process_diagram", "IPD process flow diagram"),
        "IPD process flow": _t(translator, "dashboard.process_flow", "IPD process flow"),
        "Phases, technical reviews, decision checkpoints, gates, and current position.": _t(
            translator,
            "dashboard.process_flow_description",
            "Phases, technical reviews, decision checkpoints, gates, and current position.",
        ),
        "Current work and deliverable dependencies": _t(
            translator,
            "dashboard.current_work",
            "Current work and deliverable dependencies",
        ),
        "Active checkpoint path and actionable deliverable relationships.": _t(
            translator,
            "dashboard.current_work_description",
            "Active checkpoint path and actionable deliverable relationships.",
        ),
        "Current status flow": _t(translator, "dashboard.current_status_diagram", "Current status flow"),
        "Current status": _t(translator, "dashboard.current_status", "Current status"),
        "Phase view": _t(translator, "dashboard.phase_view", "Phase view"),
        "Phase deliverable dependency diagram": _t(translator, "dashboard.phase_diagram", "Phase deliverable dependency diagram"),
        "Current deliverable dependency graph": _t(translator, "dashboard.dependency_diagram", "Current deliverable dependency graph"),
        "Deliverable dependency graph": _t(translator, "dashboard.deliverable_dependency_graph", "Deliverable dependency graph"),
        "Gate, TR, and DCP matrix": _t(translator, "dashboard.gate_matrix", "Gate, TR, and DCP matrix"),
        "Readiness, approval, evidence, and blocker status.": _t(translator, "dashboard.gate_matrix_description", "Readiness, approval, evidence, and blocker status."),
        "Deliverable matrix": _t(translator, "dashboard.deliverable_matrix", "Deliverable matrix"),
        "Ownership, lifecycle status, dependencies, evidence, and review history.": _t(translator, "dashboard.deliverable_matrix_description", "Ownership, lifecycle status, dependencies, evidence, and review history."),
        "Open full matrix": _t(translator, "dashboard.open_full_matrix", "Open full matrix"),
        "Search checkpoints": _t(translator, "dashboard.search_checkpoints", "Search checkpoints"),
        "Checkpoint type": _t(translator, "dashboard.checkpoint_type", "Checkpoint type"),
        "All types": _t(translator, "dashboard.all_types", "All types"),
        "Search deliverables": _t(translator, "dashboard.search_deliverables", "Search deliverables"),
        "Deliverable status": _t(translator, "dashboard.deliverable_status", "Deliverable status"),
        "All statuses": _t(translator, "dashboard.all_statuses", "All statuses"),
        "Back to dashboard": _t(translator, "matrix.back_to_dashboard", "Back to dashboard"),
        "Search ID, title, owner, or dependency": _t(
            translator,
            "matrix.search_deliverables_placeholder",
            "Search ID, title, owner, or dependency",
        ),
        "Search checkpoint ID, phase, or approval": _t(
            translator,
            "matrix.search_checkpoints_placeholder",
            "Search checkpoint ID, phase, or approval",
        ),
        "All phases": _t(translator, "matrix.all_phases", "All phases"),
        "ID / Deliverable": _t(translator, "field.id_deliverable", "ID / Deliverable"),
        "Node details": _t(translator, "dashboard.details", "Node details"),
        "Details": _t(translator, "dashboard.details", "Details"),
        "Select a node": _t(translator, "dashboard.select_node", "Select a node"),
        "Close details": _t(translator, "dashboard.close_details", "Close details"),
        "Zoom current status out": _t(translator, "dashboard.zoom_current_out", "Zoom current status out"),
        "Zoom current status in": _t(translator, "dashboard.zoom_current_in", "Zoom current status in"),
        "Zoom phase diagram out": _t(translator, "dashboard.zoom_phase_out", "Zoom phase diagram out"),
        "Zoom phase diagram in": _t(translator, "dashboard.zoom_phase_in", "Zoom phase diagram in"),
        "Zoom dependency graph out": _t(translator, "dashboard.zoom_dependency_out", "Zoom dependency graph out"),
        "Zoom dependency graph in": _t(translator, "dashboard.zoom_dependency_in", "Zoom dependency graph in"),
        "Zoom out": _t(translator, "dashboard.zoom_out", "Zoom out"),
        "Zoom in": _t(translator, "dashboard.zoom_in", "Zoom in"),
        "Readiness": _t(translator, "field.readiness", "Readiness"),
        "Approval": _t(translator, "field.approval", "Approval"),
        "Blockers": _t(translator, "field.blockers", "Blockers"),
        "Dependencies": _t(translator, "field.dependencies", "Dependencies"),
        "Evidence": _t(translator, "field.evidence", "Evidence"),
        "Reviews": _t(translator, "field.reviews", "Reviews"),
        "Owner": _t(translator, "field.owner", "Owner"),
        "Status": _t(translator, "field.status", "Status"),
        "Phase": _t(translator, "field.phase", "Phase"),
        "Type": _t(translator, "field.type", "Type"),
        "Input evidence": _t(translator, "detail.input_evidence", "Input evidence"),
        "Output deliverables": _t(translator, "detail.output_deliverables", "Output deliverables"),
        "Review history": _t(translator, "detail.review_history", "Review history"),
        "Provenance layer": _t(translator, "detail.provenance_layer", "Provenance layer"),
        "Provenance source": _t(translator, "detail.provenance_source", "Provenance source"),
        "Maturity": _t(translator, "detail.maturity", "Maturity"),
        "Review criteria": _t(translator, "detail.criteria", "Review criteria"),
        "Replaced by": _t(translator, "detail.replaced_by", "Replaced by"),
        "Blocker": _t(translator, "detail.blocker", "Blocker"),
        "Actionability": _t(translator, "detail.actionability", "Actionability"),
        "Binding readiness": _binding_text(translator, "readiness"),
        "Binding blockers": _binding_text(translator, "blockers"),
        "Unmet prerequisites": _t(
            translator,
            "detail.unmet_dependencies",
            "Unmet prerequisites",
        ),
        "No evidence recorded.": _t(translator, "detail.no_evidence", "No evidence recorded."),
        "No review history recorded.": _t(translator, "detail.no_review_history", "No review history recorded."),
        "No input evidence recorded.": _t(translator, "detail.no_input_evidence", "No input evidence recorded."),
        "No output deliverables recorded.": _t(translator, "detail.no_output_deliverables", "No output deliverables recorded."),
        "No open blockers.": _t(translator, "detail.no_blockers", "No open blockers."),
        "Human authorization recorded": _t(translator, "common.human_authorization_recorded", "Human authorization recorded"),
        "Unassigned": _t(translator, "common.unassigned", "Unassigned"),
        "Unknown reviewer": _t(translator, "common.reviewer", "Unknown reviewer"),
        "Recorded": _t(translator, "common.recorded", "Recorded"),
        "Pending": _t(translator, "common.pending", "Pending"),
        "Blocked": _t(translator, "common.blocked", "Blocked"),
        "Item": _t(translator, "common.item", "Item"),
        "None": _t(translator, "common.none", "None"),
        ">Planned<": ">" + _status_label("planned", translator) + "<",
        ">In progress<": ">" + _status_label("in_progress", translator) + "<",
        ">Ready for review<": ">" + _status_label("ready_for_review", translator) + "<",
        ">In review<": ">" + _status_label("in_review", translator) + "<",
        ">Accepted<": ">" + _status_label("accepted", translator) + "<",
        ">Rejected<": ">" + _status_label("rejected", translator) + "<",
        ">Blocked<": ">" + _status_label("blocked", translator) + "<",
        ">Superseded<": ">" + _status_label("superseded", translator) + "<",
    }
    # Static copy may be translated by trusted substring replacement, but
    # JavaScript identifiers and lookup keys must remain language-neutral.
    # Runtime-visible script copy is localized through the embedded i18n map.
    fragments = re.split(r"(<script\b[^>]*>.*?</script>)", template, flags=re.I | re.S)
    rendered: list[str] = []
    for fragment in fragments:
        if re.match(r"<script\b", fragment, flags=re.I):
            rendered.append(fragment)
            continue
        for source in sorted(replacements, key=len, reverse=True):
            fragment = fragment.replace(source, replacements[source])
        rendered.append(fragment)
    return "".join(rendered)


def _badge(status: Any, translator: Any) -> str:
    label = _status_label(status, translator)
    return f'<span class="badge status-{_status_class(status)}">{escape(label)}</span>'


def _phase_cards(phases: list[Mapping[str, Any]], translator: Any) -> str:
    rows: list[str] = []
    for phase in phases:
        phase_id = _text(phase.get("id"), "phase")
        current = bool(phase.get("current"))
        accepted = _count(phase.get("accepted_count", 0))
        total = _count(phase.get("deliverable_count", 0))
        sequence_label = _t(
            translator,
            "dashboard.phase_number",
            "Phase {sequence}",
            sequence=_text(phase.get("sequence"), "—"),
        )
        count_label = _t(
            translator,
            "dashboard.accepted_count",
            "{accepted} of {total} accepted",
            accepted=accepted,
            total=total,
        )
        rows.append(
            '<button type="button" class="phase-card{}" data-phase="{}" '
            'aria-pressed="{}"><span class="phase-sequence">{}</span>'
            '<span class="phase-title">{}</span><span class="phase-count">{} · {}</span></button>'.format(
                " active" if current else "",
                escape(phase_id, quote=True),
                "true" if current else "false",
                escape(sequence_label),
                _h(phase.get("display_label") or phase.get("title"), phase_id.title()),
                escape(count_label),
                _badge(phase.get("status"), translator),
            )
        )
    rendered = "".join(rows)
    if not rendered:
        return f'<div class="empty">{escape(_t(translator, "dashboard.no_phase_data", "No phase data is available."))}</div>'
    return rendered


def _gate_rows(
    checkpoints: list[Mapping[str, Any]],
    translator: Any,
    *,
    link_prefix: str = "",
) -> str:
    rows: list[str] = []
    for checkpoint in checkpoints:
        node_type = _text(checkpoint.get("type"), "gate").lower()
        node_id = _text(checkpoint.get("id"), "unknown")
        blockers = checkpoint.get("blockers")
        blocker_count = len(blockers) if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes)) else 0
        readiness = checkpoint.get("readiness") if isinstance(checkpoint.get("readiness"), Mapping) else {}
        approval = checkpoint.get("approval") if isinstance(checkpoint.get("approval"), Mapping) else {}
        href = f'{link_prefix}#node={node_type}:{node_id}'
        rows.append(
            '<tr data-node="{}:{}" data-kind="{}" data-status="{}" tabindex="0">'
            '<td><a class="row-link" href="{}">{}</a></td><td>{}</td><td>{}</td>'
            '<td>{} / {}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                escape(node_type, quote=True), escape(node_id, quote=True),
                escape(node_type, quote=True), escape(_status_class(checkpoint.get("status")), quote=True),
                escape(href, quote=True), _h(node_id), escape(
                    _t(translator, f"node_type.{node_type}", node_type.upper())
                ),
                _h(_phase_label(checkpoint.get("phase"), translator)), _count(readiness.get("accepted", 0)),
                _count(readiness.get("required", len(_strings(checkpoint.get("required_deliverables"))))),
                _badge(checkpoint.get("display_status", checkpoint.get("status")), translator),
                escape(_status_label(approval.get("status", "pending"), translator)), str(blocker_count),
            )
        )
    return "".join(rows) or (
        '<tr><td colspan="7" class="empty">'
        + escape(_t(translator, "dashboard.no_checkpoints", "No checkpoints are available."))
        + "</td></tr>"
    )


def _deliverable_rows(
    deliverables: list[Mapping[str, Any]],
    translator: Any,
    *,
    link_prefix: str = "",
) -> str:
    rows: list[str] = []
    for item in deliverables:
        item_id = _text(item.get("id"), "unknown")
        status = item.get("display_status", item.get("status"))
        dependencies = _strings(item.get("depends_on"))
        evidence = _strings(item.get("evidence"))
        reviews = _items(item.get("reviews"))
        actionability = (
            item.get("actionability")
            if isinstance(item.get("actionability"), Mapping)
            else {}
        )
        binding_ready = actionability.get("binding_ready")
        binding_badge = (
            '<span class="badge status-{}">{}</span>'.format(
                "ready" if binding_ready is True else "blocked",
                escape(
                    _binding_text(
                        translator,
                        "ready" if binding_ready is True else "not_ready",
                    )
                ),
            )
            if isinstance(binding_ready, bool)
            else '<span class="muted">—</span>'
        )
        href = f'{link_prefix}#node=deliverable:{item_id}'
        rows.append(
            '<tr data-node="deliverable:{}" data-phase="{}" data-status="{}" tabindex="0">'
            '<td><a class="row-link" href="{}">{}</a><div class="muted">{}</div></td>'
            '<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                escape(item_id, quote=True), escape(_text(item.get("phase"), "unknown"), quote=True),
                escape(_status_class(status), quote=True), escape(href, quote=True), _h(item_id),
                _h(item.get("display_label") or item.get("title"), _t(translator, "dashboard.untitled_deliverable", "Untitled deliverable")), _h(_phase_label(item.get("phase"), translator)),
                _h(item.get("owner"), _t(translator, "common.unassigned", "Unassigned")), _badge(status, translator), binding_badge,
                _h(", ".join(dependencies), _t(translator, "common.none", "None")), str(len(evidence)), str(len(reviews)),
            )
        )
    return "".join(rows) or (
        '<tr><td colspan="8" class="empty">'
        + escape(_t(translator, "dashboard.no_deliverables", "No deliverables are available."))
        + "</td></tr>"
    )


def render_index(
    state_data: Mapping[str, Any],
    graph_data: Mapping[str, Any],
    phase_files: Mapping[str, str],
    *,
    translator: Any | None = None,
    locale: str = "en",
    diagrams: Mapping[str, str] | None = None,
) -> str:
    """Render the interactive dashboard landing page."""

    translator = _translator(translator, locale)
    project = state_data.get("project") if isinstance(state_data.get("project"), Mapping) else {}
    summary = state_data.get("summary") if isinstance(state_data.get("summary"), Mapping) else {}
    current = project.get("current") if isinstance(project.get("current"), Mapping) else {}
    repository = project.get("repository") if isinstance(project.get("repository"), Mapping) else {}
    phases = _items(state_data.get("phases"))
    checkpoints = _items(state_data.get("checkpoints"))
    deliverables = _items(state_data.get("deliverables"))
    available = _items(state_data.get("available_tasks"))
    refinement_due = _items(state_data.get("refinement_due"))
    refinement_due_count = summary.get("refinement_due", len(refinement_due))
    waiting_count = summary.get("waiting_on_dependencies", 0)
    explicit_blockers = summary.get("explicit_blockers")
    if explicit_blockers is None:
        explicit_blockers = summary.get("explicitly_blocked")
    if explicit_blockers is None:
        explicit_blockers = sum(
            item.get("status") == "blocked"
            and (
                not current.get("phase")
                or item.get("phase") in {None, current.get("phase")}
            )
            for item in deliverables
        )
    governance_blockers = summary.get("governance_blockers", 0)
    progress = summary.get("progress_percent", 0)
    try:
        progress_number = max(0.0, min(100.0, float(progress)))
    except (TypeError, ValueError):
        progress_number = 0.0

    first_task = available[0] if available else {}
    task_id = _text(
        first_task.get("id"),
        _t(translator, "dashboard.no_task_available", "No task is currently available"),
    )
    task_title = _text(
        first_task.get("display_label") or first_task.get("title"),
        _t(
            translator,
            "dashboard.resolve_dependencies",
            "Resolve dependencies or complete the active review.",
        ),
    )
    task_meta = " · ".join(
        part
        for part in (
            _phase_label(first_task.get("phase"), translator),
            _text(first_task.get("owner"), ""),
        )
        if part
    ) or _t(translator, "dashboard.state_synchronized", "Workflow state is synchronized")

    phase_options = "".join(
        '<option value="{}" data-src="{}"{}>{}</option>'.format(
            escape(_text(phase_id), quote=True), escape(_text(path), quote=True),
            " selected" if _text(phase_id) == _text(current.get("phase"), "") else "",
            _h(next((p.get("display_label") or p.get("title") for p in phases if _text(p.get("id")) == _text(phase_id)), phase_id)),
        )
        for phase_id, path in phase_files.items()
    )
    default_phase_src = ""
    current_phase = _text(current.get("phase"), "")
    if current_phase in phase_files:
        default_phase_src = _text(phase_files[current_phase], "")
    elif phase_files:
        default_phase_src = _text(next(iter(phase_files.values())), "")

    repository_kind = _text(repository.get("kind"), "").lower()
    repository_label = " · ".join(
        part
        for part in (
            repository_kind.upper() if repository_kind not in {"", "none"} else "",
            _text(repository.get("branch"), ""),
            _text(repository.get("revision"), ""),
        )
        if part
    ) or _t(translator, "common.not_detected", "Not detected")
    if repository.get("dirty") is True:
        repository_label += " · " + _t(translator, "common.modified", "Modified")

    refinement_alert = ""
    if refinement_due:
        first_due = refinement_due[0]
        due_id = _text(first_due.get("id"))
        due_title = _text(
            first_due.get("display_label") or first_due.get("title"), due_id
        )
        refinement_alert = (
            '<section class="refinement-alert" aria-label="'
            + escape(
                _t(translator, "dashboard.refinement_due", "Refinement due"),
                quote=True,
            )
            + '"><span class="kicker">'
            + escape(_t(translator, "dashboard.refinement_due", "Refinement due"))
            + "</span><div><strong>"
            + escape(f"{due_id} · {due_title}")
            + "</strong><div>"
            + escape(
                _t(
                    translator,
                    "dashboard.refinement_due_description",
                    "A required process definition must be refined before governed work can continue.",
                )
            )
            + '</div></div><a class="btn" href="#node=deliverable:'
            + escape(due_id, quote=True)
            + '">'
            + escape(_t(translator, "dashboard.open_details", "Open details"))
            + "</a></section>"
        )

    html = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>IPD Dashboard · __PROJECT_TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div><p class="eyebrow">IPD Agent Workflow Framework</p><h1>__PROJECT_NAME__</h1></div>
    <div class="top-meta" aria-label="Dashboard metadata">
      <div><span>State revision</span><strong>__STATE_REVISION__</strong></div>
      <div><span>Process schema</span><strong>__PROCESS_SCHEMA__</strong></div>
      <div><span>Workflow step</span><strong>__WORKFLOW_STEP__</strong></div>
      <div><span>Repository state</span><strong>__REPOSITORY_STATE__</strong></div>
    </div>
  </header>

  <section class="summary-strip" aria-label="Project summary">
    <div class="metric"><span class="metric-label">Current phase</span><strong class="metric-value">__CURRENT_PHASE__</strong></div>
    <div class="metric"><span class="metric-label">Current TR</span><strong class="metric-value">__CURRENT_TR__</strong></div>
    <div class="metric"><span class="metric-label">Current DCP / Gate</span><strong class="metric-value">__CURRENT_GATE__</strong></div>
    <div class="metric"><span class="metric-label">Current review subject</span><strong class="metric-value">__CURRENT_ITERATION_SUBJECT__</strong></div>
    <div class="metric"><span class="metric-label">Progress</span><strong class="metric-value">__PROGRESS__%</strong><div class="progress" aria-hidden="true"><span style="width:__PROGRESS__%"></span></div></div>
    <div class="metric"><span class="metric-label">Accepted</span><strong class="metric-value">__ACCEPTED__ / __TOTAL__</strong></div>
    <div class="metric"><span class="metric-label">Review queue</span><strong class="metric-value">__REVIEW_QUEUE__</strong></div>
    <div class="metric"><span class="metric-label">Waiting on prerequisites</span><strong class="metric-value">__WAITING__</strong></div>
    <div class="metric"><span class="metric-label">Refinement due</span><strong class="metric-value__REFINEMENT_ALERT_CLASS__">__REFINEMENT_DUE__</strong></div>
    <div class="metric"><span class="metric-label">Explicit blockers</span><strong class="metric-value__BLOCKER_ALERT__">__BLOCKERS__</strong></div>
    <div class="metric"><span class="metric-label">Governance blockers</span><strong class="metric-value__GOVERNANCE_ALERT__">__GOVERNANCE_BLOCKERS__</strong></div>
  </section>

  __REFINEMENT_ALERT__

  <section class="next-task" aria-label="Next available task">
    <span class="kicker">Next available task</span>
    <div><strong>__TASK_ID__ · __TASK_TITLE__</strong><div class="task-meta">__TASK_META__</div></div>
    <a class="btn" href="__TASK_LINK__">Open details</a>
  </section>

  <nav class="phase-rail" aria-label="Project phases">__PHASE_CARDS__</nav>

  <div class="workspace detail-closed" id="workspace">
    <main class="main">
      <section class="panel" id="process-flow">
        <div class="panel-head"><div><h2>IPD process flow</h2><p>Phases, technical reviews, decision checkpoints, gates, and current position.</p></div><div class="tools" data-zoom-for="overview"><button class="btn" type="button" data-zoom="out" aria-label="Zoom out">−</button><button class="btn" type="button" data-zoom="reset">100%</button><button class="btn" type="button" data-zoom="in" aria-label="Zoom in">+</button></div></div>
        <div class="panel-body"><div class="diagram-frame" id="overview"><object type="image/svg+xml" data="assets/ipd_flow.svg" aria-label="IPD process flow diagram"></object></div></div>
      </section>

      <section class="panel" id="current-deliverables">
        <div class="panel-head"><div><h2>Current work and deliverable dependencies</h2><p>Active checkpoint path and actionable deliverable relationships.</p></div></div>
        <div class="panel-body diagram-pair">
          __RELATION_CONTROLS__
          <div><div class="tools" data-zoom-for="status-flow"><strong>Current status</strong><button class="btn" type="button" data-zoom="out" aria-label="Zoom current status out">−</button><button class="btn" type="button" data-zoom="reset">100%</button><button class="btn" type="button" data-zoom="in" aria-label="Zoom current status in">+</button></div><div class="diagram-frame compact" id="status-flow"><object type="image/svg+xml" data="assets/current_status_flow.svg" aria-label="Current status flow"></object></div></div>
          <div><div class="tools"><label for="phase-view"><strong>Phase view</strong></label><select class="select" id="phase-view">__PHASE_OPTIONS__</select><span data-zoom-for="phase-diagram"><button class="btn" type="button" data-zoom="out" aria-label="Zoom phase diagram out">−</button><button class="btn" type="button" data-zoom="reset">100%</button><button class="btn" type="button" data-zoom="in" aria-label="Zoom phase diagram in">+</button></span></div><div class="diagram-frame compact" id="phase-diagram"><object type="image/svg+xml" data="__DEFAULT_PHASE_SRC__" aria-label="Phase deliverable dependency diagram"></object></div></div>
        </div>
        <div class="panel-body"><div class="tools" data-zoom-for="dependency-flow"><strong>Deliverable dependency graph</strong><button class="btn" type="button" data-zoom="out" aria-label="Zoom dependency graph out">−</button><button class="btn" type="button" data-zoom="reset">100%</button><button class="btn" type="button" data-zoom="in" aria-label="Zoom dependency graph in">+</button></div><div class="diagram-frame compact" id="dependency-flow"><object type="image/svg+xml" data="assets/deliverable_dependency.svg" aria-label="Current deliverable dependency graph"></object></div></div>
      </section>

      <section class="panel" id="gate-matrix">
        <div class="panel-head"><div><h2>Gate, TR, and DCP matrix</h2><p>Readiness, approval, evidence, and blocker status.</p></div><div class="filters"><a class="btn" href="matrices/gate_matrix.html">Open full matrix</a><label class="sr-only" for="gate-search">Search checkpoints</label><input class="search" id="gate-search" type="search" placeholder="Search checkpoints"><label class="sr-only" for="gate-type">Checkpoint type</label><select class="select" id="gate-type"><option value="">All types</option><option value="tr">TR</option><option value="dcp">DCP</option><option value="gate">Gate</option></select></div></div>
        <div class="table-scroll"><table><thead><tr><th>ID</th><th>Type</th><th>Phase</th><th>Readiness</th><th>Status</th><th>Approval</th><th>Blockers</th></tr></thead><tbody id="gate-rows">__GATE_ROWS__</tbody></table></div>
      </section>

      <section class="panel" id="deliverable-matrix">
        <div class="panel-head"><div><h2>Deliverable matrix</h2><p>Ownership, lifecycle status, dependencies, evidence, and review history.</p></div><div class="filters"><a class="btn" href="matrices/deliverable_matrix.html">Open full matrix</a><label class="sr-only" for="deliverable-search">Search deliverables</label><input class="search" id="deliverable-search" type="search" placeholder="Search deliverables"><label class="sr-only" for="deliverable-status">Deliverable status</label><select class="select" id="deliverable-status"><option value="">All statuses</option><option value="planned">Planned</option><option value="in_progress">In progress</option><option value="ready_for_review">Ready for review</option><option value="in_review">In review</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="blocked">Blocked</option><option value="superseded">Superseded</option></select></div></div>
        <div class="table-scroll"><table><thead><tr><th>ID / Deliverable</th><th>Phase</th><th>Owner</th><th>Status</th><th>Binding readiness</th><th>Dependencies</th><th>Evidence</th><th>Reviews</th></tr></thead><tbody id="deliverable-rows">__DELIVERABLE_ROWS__</tbody></table></div>
      </section>
    </main>

    <aside class="details" id="details" aria-live="polite" aria-label="Node details" hidden>
      <div class="details-head"><div><p class="eyebrow" id="detail-kind">Details</p><h2 id="detail-title">Select a node</h2></div><button class="details-close" id="details-close" type="button" aria-label="Close details">×</button></div>
      <div class="details-body" id="detail-body"></div>
    </aside>
  </div>
</div>

__SVG_TEMPLATES__
<script id="ipd-state" type="application/json">__STATE_JSON__</script>
<script id="ipd-graph" type="application/json">__GRAPH_JSON__</script>
<script id="ipd-i18n" type="application/json">__I18N_JSON__</script>
<script>
(() => {
  'use strict';
  const state = JSON.parse(document.getElementById('ipd-state').textContent);
  const graph = JSON.parse(document.getElementById('ipd-graph').textContent);
  const i18n = JSON.parse(document.getElementById('ipd-i18n').textContent);
  const workspace = document.getElementById('workspace');
  const details = document.getElementById('details');
  const label = (group, key, fallback) => (i18n[group] && i18n[group][key]) || fallback;
  const ui = (key, fallback) => label('ui', key, fallback);
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const values = value => Array.isArray(value) ? value : [];
  const list = (value, empty = null) => {
    const items = values(value);
    return items.length ? `<ul class="detail-list">${items.map(item => `<li>${esc(typeof item === 'object' ? (item.id || item.path || JSON.stringify(item)) : item)}</li>`).join('')}</ul>` : `<p class="muted">${esc(empty || ui('none', 'None'))}</p>`;
  };
  const section = (title, content) => `<section class="detail-section"><h3>${esc(title)}</h3>${content}</section>`;
  const checkpoint = (kind, id) => values(state.checkpoints).find(item => String(item.type || '').toLowerCase() === kind && String(item.id) === id);
  const deliverable = id => values(state.deliverables).find(item => String(item.id) === id);
  const activity = id => values(state.activities).find(item => String(item.id) === id);
  const phase = id => values(state.phases).find(item => String(item.id) === id);

  const fileList = records => values(records).length ? `<ul class="detail-list">${values(records).map(record => {
    const href = String(record.href || '');
    const safe = /^(https?:\/\/|\.\.\/\.\.\/)/i.test(href);
    return `<li><code class="file-path">${esc(record.path)}</code>${record.exists === false ? ` <span class="muted">${esc(ui('missing_file', 'Not generated or unavailable'))}</span>` : ''}<div class="file-actions">${safe ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(ui('open_file', 'Open file'))}</a>` : ''}<button class="btn" type="button" data-copy-path="${esc(record.path)}">${esc(ui('copy_path', 'Copy path'))}</button></div></li>`;
  }).join('')}</ul>` : `<p class="muted">${esc(ui('no_files', 'No files recorded.'))}</p>`;
  document.getElementById('detail-body').addEventListener('click', async event => {
    const button = event.target.closest('[data-copy-path]'); if (!button) return;
    const path = button.dataset.copyPath;
    try { await navigator.clipboard.writeText(path); button.textContent = ui('copied', 'Copied'); }
    catch (_) { const input = document.createElement('textarea'); input.value = path; button.parentElement.append(input); input.select(); const copied = document.execCommand('copy'); input.remove(); button.textContent = copied ? ui('copied', 'Copied') : ui('copy_failed', 'Select and copy the path'); }
  });

  function showDetails(kind, id) {
    const item = kind === 'deliverable' ? deliverable(id) : kind === 'activity' ? activity(id) : kind === 'phase' ? phase(id) : checkpoint(kind, id);
    if (!item) return;
    document.getElementById('detail-kind').textContent = label('nodeTypes', kind, kind === 'deliverable' ? 'Deliverable' : kind.toUpperCase());
    document.getElementById('detail-title').textContent = `${item.id || id} · ${item.display_label || item.title || label('common', 'untitled', 'Untitled')}`;
    const status = item.display_status || item.status || 'unknown';
    const statusKey = String(status).toLowerCase().replaceAll(' ', '_');
    let body = section(ui('status', 'Status'), `<p><span class="badge status-${esc(statusKey)}">${esc(label('statuses', statusKey, String(status).replaceAll('_', ' ')))}</span></p>`);
    const provenance = item.provenance || {};
    if (provenance.layer) body += section(ui('provenance_layer', 'Provenance layer'), `<p>${esc(provenance.layer)}</p>`);
    if (provenance.source_id) body += section(ui('provenance_source', 'Provenance source'), `<p>${esc(provenance.source_id)}</p>`);
    if (item.maturity) body += section(ui('maturity', 'Maturity'), `<p>${esc(item.maturity)}</p>`);
    if (kind === 'deliverable') {
      body += section(ui('id', 'ID'), `<p>${esc(item.id)}</p>`);
      body += section(ui('owner', 'Owner'), `<p>${esc(item.owner || ui('unassigned', 'Unassigned'))}</p>`);
      body += section(ui('dependencies', 'Dependencies'), list(item.depends_on));
      body += section(ui('definition_state', 'Definition state'), `<p>${esc(label('definitions', item.definition_state || 'concrete', item.definition_state || 'concrete'))}</p>`);
      body += section(ui('refines', 'Refines'), list(item.refines));
      body += section(ui('refined_by', 'Refined by'), list(item.refined_by));
      body += section(ui('refinement_trigger', 'Refinement trigger'), item.refinement_trigger ? `<p><code>${esc(JSON.stringify(item.refinement_trigger))}</code></p>` : `<p class="muted">${esc(ui('none', 'None'))}</p>`);
      body += section(ui('refinement_status', 'Refinement status'), `<p><span class="badge status-${esc(item.refinement_status || 'not_required')}">${esc(label('refinementStatuses', item.refinement_status || 'not_required', item.refinement_status || 'not required'))}</span></p>`);
      body += section(ui('concrete_leaf_closure', 'Concrete leaf closure'), list(item.concrete_leaf_closure));
      const bindingImpact = item.binding_impact || (item.actionability && item.actionability.binding_impact);
      if (bindingImpact) body += section(ui('binding_impact', 'Binding impact'), `<p><code>${esc(JSON.stringify(bindingImpact))}</code></p>`);
      if (item.actionability && item.actionability.state) {
        const actionabilityKey = String(item.actionability.state).toLowerCase();
        body += section(ui('actionability', 'Actionability'), `<p>${esc(label('actionability', actionabilityKey, actionabilityKey.replaceAll('_', ' ')))}</p>`);
        body += section(ui('unmet_dependencies', 'Unmet prerequisites'), list(item.actionability.unmet_dependencies));
        if (typeof item.actionability.binding_ready === 'boolean') {
          const readinessKey = item.actionability.binding_ready ? 'ready' : 'not_ready';
          body += section(label('binding', 'readiness', 'Binding readiness'), `<p>${esc(label('binding', readinessKey, readinessKey.replaceAll('_', ' ')))}</p>`);
          body += section(label('binding', 'blockers', 'Binding blockers'), list(item.actionability.binding_blockers, label('binding', 'no_blockers', 'No binding blockers')));
        }
      }
      body += section(ui('owned_files', 'Deliverable files'), fileList(item.owned_files));
      body += section(ui('shared_files', 'Shared evidence files'), fileList(item.shared_files));
      body += section(ui('binding_rules', 'File binding rules'), list(values(item.file_binding_rules).map(rule => `${rule.id} · ${rule.role} · ${values(rule.patterns).join(', ')}`)));
      body += section(ui('evidence', 'Evidence'), fileList(item.evidence_files || values(item.evidence).map(path => ({path}))));
      const history = values(item.reviews).map(review => typeof review === 'object' ? [review.decision || review.result || review.status || ui('recorded', 'Recorded'), review.reviewer || review.actor || ui('unknown_reviewer', 'Unknown reviewer'), review.evidence || review.comment || review.notes || ''].filter(Boolean).join(' · ') : review);
      body += section(ui('review_history', 'Review history'), list(history, ui('no_review_history', 'No review history recorded.')));
      if (values(item.replacements).length) body += section(ui('replaced_by', 'Replaced by'), list(item.replacements));
      if (item.blocker) body += section(ui('blocker', 'Blocker'), `<p>${esc(typeof item.blocker === 'object' ? (item.blocker.reason || item.blocker.id || JSON.stringify(item.blocker)) : item.blocker)}</p>`);
    } else if (kind === 'activity') {
      body += section(ui('definition_state', 'Definition state'), `<p>${esc(label('definitions', item.definition_state || 'concrete', item.definition_state || 'concrete'))}</p>`);
      body += section(ui('refines', 'Refines'), list(item.refines));
      body += section(ui('refined_by', 'Refined by'), list(item.refined_by));
      body += section(ui('refinement_trigger', 'Refinement trigger'), item.refinement_trigger ? `<p><code>${esc(JSON.stringify(item.refinement_trigger))}</code></p>` : `<p class="muted">${esc(ui('none', 'None'))}</p>`);
      body += section(ui('output_deliverables', 'Output deliverables'), list(item.deliverables, ui('no_output_deliverables', 'No output deliverables recorded.')));
    } else if (kind !== 'phase') {
      const criteria = values(item.criteria).map(criterion => typeof criterion === 'object' ? `${criterion.id || label('common', 'criterion', 'criterion')} · ${criterion.description || ''}${criterion.evidence_required ? ` · ${label('common', 'evidence_required', 'Evidence required')}` : ''}` : criterion);
      if (criteria.length) body += section(ui('criteria', 'Review criteria'), list(criteria));
      body += section(ui('input_evidence', 'Input evidence'), list(item.input_evidence || item.evidence, ui('no_input_evidence', 'No input evidence recorded.')));
      body += section(ui('output_deliverables', 'Output deliverables'), list(item.output_deliverables || item.required_deliverables, ui('no_output_deliverables', 'No output deliverables recorded.')));
      const blockers = values(item.blockers).map(blocker => typeof blocker === 'object' ? `${blocker.deliverable || blocker.id || ui('item', 'Item')} · ${blocker.status || blocker.reason || ui('blocked', 'Blocked')}` : blocker);
      body += section(ui('blockers', 'Blockers'), list(blockers, ui('no_blockers', 'No open blockers.')));
      const approval = item.approval || {};
      const approvalStatus = String(approval.status || 'pending');
      body += section(ui('approval', 'Approval'), `<p>${esc(label('statuses', approvalStatus, approvalStatus))}${approval.authorized_human ? ` · ${esc(ui('human_authorization_recorded', 'Human authorization recorded'))}` : ''}</p>`);
    }
    document.getElementById('detail-body').innerHTML = body;
    details.hidden = false;
    workspace.classList.remove('detail-closed');
    details.scrollTop = 0;
  }

  function route() {
    const match = location.hash.match(/^#node=(phase|activity|tr|dcp|gate|deliverable):(.+)$/i);
    if (match) showDetails(match[1].toLowerCase(), decodeURIComponent(match[2]));
  }
  window.addEventListener('hashchange', route);
  route();
  document.getElementById('details-close').addEventListener('click', () => {
    details.hidden = true;
    workspace.classList.add('detail-closed');
    history.replaceState(null, '', location.pathname + location.search);
  });

  document.querySelectorAll('tr[data-node]').forEach(row => {
    row.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); location.hash = `node=${row.dataset.node}`; }
    });
    row.addEventListener('click', event => { if (!event.target.closest('a')) location.hash = `node=${row.dataset.node}`; });
  });

  const phaseSelect = document.getElementById('phase-view');
  const phaseFrame = document.getElementById('phase-diagram');
  const phaseObject = phaseFrame.querySelector('object');
  const relationInputs = [...document.querySelectorAll('[data-relation-toggle]')];
  function filterRelations() {
    const selected = new Set(relationInputs.filter(input => input.checked).map(input => input.value));
    document.querySelectorAll('.relation-filtered').forEach(svg => {
      const edges = [...svg.querySelectorAll('.edge[data-relation]')];
      edges.forEach(edge => { edge.style.display = selected.has(edge.dataset.relation) ? '' : 'none'; if (selected.has(edge.dataset.relation)) edge.style.display = 'inline'; });
      const frame = svg.closest('.diagram-frame');
      let count = frame.querySelector('.relation-count');
      if (!count) { count = document.createElement('p'); count.className = 'relation-count muted'; count.setAttribute('aria-live', 'polite'); frame.prepend(count); }
      count.textContent = `${ui('visible_edges', 'Visible relationships')}: ${edges.filter(edge => selected.has(edge.dataset.relation)).length} / ${edges.length}`;
    });
  }
  relationInputs.forEach(input => input.addEventListener('change', filterRelations));
  document.querySelectorAll('[data-relations-action]').forEach(button => button.addEventListener('click', () => {
    relationInputs.forEach(input => { input.checked = button.dataset.relationsAction === 'all' || input.value === 'depends_on'; }); filterRelations();
  }));
  filterRelations();
  function selectPhase(phase) {
    const option = [...phaseSelect.options].find(item => item.value === phase);
    if (option) {
      phaseSelect.value = phase;
      const template = [...document.querySelectorAll('template[data-svg-src]')].find(t => t.dataset.svgSrc === option.dataset.src);
      if (template) { phaseFrame.replaceChildren(template.content.cloneNode(true)); filterRelations(); const svg = phaseFrame.querySelector('svg'); if (svg) svg.style.transform = `scale(${scales.get('phase-diagram') || 1})`; }
      else if (phaseObject) phaseObject.data = option.dataset.src;
    }
    document.querySelectorAll('.phase-card').forEach(card => {
      const active = card.dataset.phase === phase;
      card.classList.toggle('active', active); card.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    filterDeliverables();
  }
  phaseSelect.addEventListener('change', () => selectPhase(phaseSelect.value));
  document.querySelectorAll('.phase-card').forEach(card => card.addEventListener('click', () => selectPhase(card.dataset.phase)));

  const scales = new Map();
  document.querySelectorAll('[data-zoom-for]').forEach(toolbar => toolbar.addEventListener('click', event => {
    const control = event.target.closest('[data-zoom]'); if (!control) return;
    const target = document.querySelector(`#${toolbar.dataset.zoomFor} > svg, #${toolbar.dataset.zoomFor} object`); if (!target) return;
    const key = toolbar.dataset.zoomFor; let scale = scales.get(key) || 1;
    scale = control.dataset.zoom === 'in' ? Math.min(2, scale + .15) : control.dataset.zoom === 'out' ? Math.max(.55, scale - .15) : 1;
    scales.set(key, scale); target.style.transform = `scale(${scale})`;
    const reset = toolbar.querySelector('[data-zoom="reset"]'); if (reset) reset.textContent = `${Math.round(scale * 100)}%`;
  }));

  const gateSearch = document.getElementById('gate-search');
  const gateType = document.getElementById('gate-type');
  function filterGates() {
    const query = gateSearch.value.trim().toLowerCase();
    document.querySelectorAll('#gate-rows tr[data-node]').forEach(row => { row.hidden = !((!query || row.textContent.toLowerCase().includes(query)) && (!gateType.value || row.dataset.kind === gateType.value)); });
  }
  gateSearch.addEventListener('input', filterGates); gateType.addEventListener('change', filterGates);
  const deliverableSearch = document.getElementById('deliverable-search');
  const deliverableStatus = document.getElementById('deliverable-status');
  function filterDeliverables() {
    const query = deliverableSearch.value.trim().toLowerCase(); const status = deliverableStatus.value; const phase = phaseSelect.value;
    document.querySelectorAll('#deliverable-rows tr[data-node]').forEach(row => { row.hidden = !((!query || row.textContent.toLowerCase().includes(query)) && (!status || row.dataset.status === status) && (!phase || row.dataset.phase === phase)); });
  }
  deliverableSearch.addEventListener('input', filterDeliverables); deliverableStatus.addEventListener('change', filterDeliverables);

  // SVG anchors target the parent page.  This listener adds keyboard/click
  // support when a browser exposes a same-origin SVG document.
  document.querySelectorAll('object[type="image/svg+xml"]').forEach(object => object.addEventListener('load', () => {
    try { object.contentDocument.querySelectorAll('[data-node-id]').forEach(node => node.setAttribute('tabindex', '0')); } catch (_) { /* Local-file isolation still leaves SVG anchor navigation intact. */ }
  }));
  document.querySelectorAll('.diagram-frame').forEach(frame => {
    frame.querySelectorAll('[data-node-id]').forEach(node => node.setAttribute('tabindex', '0'));
    frame.addEventListener('keydown', event => {
      const node = event.target.closest('[data-node-id]');
      if (node && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); location.hash = `node=${String(node.dataset.nodeType).toLowerCase()}:${encodeURIComponent(node.dataset.nodeId)}`; }
    });
  });
  void graph;
})();
</script>
</body>
</html>'''
    html = _localize_static_html(html, translator)
    task_link = "#current-deliverables"
    if first_task.get("id"):
        task_link = f"#node=deliverable:{_text(first_task.get('id'))}"
    gate_or_dcp = _text(current.get("dcp"), "") or _text(current.get("gate"), "—")
    replacements = {
        "__PROJECT_TITLE__": _h(project.get("name"), "IPD Project"),
        "__PROJECT_NAME__": _h(project.get("name"), "IPD Project"),
        "__STATE_REVISION__": _h(project.get("state_revision"), "—"),
        "__PROCESS_SCHEMA__": _h(project.get("process_schema_version"), "—"),
        "__WORKFLOW_STEP__": _h(
            _t(
                translator,
                f"workflow_step.{_text(project.get('workflow_step'), 'context')}",
                _text(project.get("workflow_step"), "context").replace("_", " ").title(),
            )
        ),
        "__REPOSITORY_STATE__": escape(repository_label),
        "__CURRENT_PHASE__": _h(
            _phase_label(current.get("phase"), translator),
            _t(translator, "common.not_started", "Not started"),
        ),
        "__CURRENT_TR__": _h(current.get("tr")),
        "__CURRENT_GATE__": escape(gate_or_dcp),
        "__CURRENT_ITERATION_SUBJECT__": _h(
            project.get("current_iteration_subject"), "—"
        ),
        "__PROGRESS__": f"{progress_number:g}",
        "__ACCEPTED__": _count(summary.get("accepted_deliverables", 0)),
        "__TOTAL__": _count(summary.get("total_deliverables", len(deliverables))),
        "__REVIEW_QUEUE__": _count(summary.get("review_queue", 0)),
        "__WAITING__": _count(waiting_count),
        "__REFINEMENT_DUE__": _count(refinement_due_count),
        "__REFINEMENT_ALERT_CLASS__": " alert" if refinement_due_count else "",
        "__REFINEMENT_ALERT__": refinement_alert,
        "__BLOCKERS__": _count(explicit_blockers),
        "__BLOCKER_ALERT__": " alert" if explicit_blockers else "",
        "__GOVERNANCE_BLOCKERS__": _count(governance_blockers),
        "__GOVERNANCE_ALERT__": " alert" if governance_blockers else "",
        "__TASK_ID__": _h(task_id),
        "__TASK_TITLE__": _h(task_title),
        "__TASK_META__": _h(task_meta),
        "__TASK_LINK__": escape(task_link, quote=True),
        "__PHASE_CARDS__": _phase_cards(phases, translator),
        "__PHASE_OPTIONS__": phase_options,
        "__DEFAULT_PHASE_SRC__": escape(default_phase_src, quote=True),
        "__GATE_ROWS__": _gate_rows(checkpoints, translator),
        "__DELIVERABLE_ROWS__": _deliverable_rows(deliverables, translator),
        "__STATE_JSON__": _json_script(state_data),
        "__GRAPH_JSON__": _json_script(graph_data),
        "__I18N_JSON__": _json_script(
            {
                "statuses": {
                    status: _status_label(status, translator)
                    for status in (
                        "planned",
                        "not_started",
                        "in_progress",
                        "ready_for_review",
                        "in_review",
                        "accepted",
                        "approved",
                        "rejected",
                        "blocked",
                        "superseded",
                        "ready",
                        "pending",
                        "unknown",
                    )
                },
                "nodeTypes": {
                    item: _t(translator, f"node_type.{item}", item.upper() if item in {"tr", "dcp"} else item.title())
                    for item in ("phase", "activity", "tr", "dcp", "gate", "deliverable")
                },
                "actionability": {
                    item: _t(
                        translator,
                        f"actionability.{item}",
                        (
                            _binding_text(translator, "waiting_on_bindings")
                            if item == "waiting_on_bindings"
                            else item.replace("_", " ").title()
                        ),
                    )
                    for item in (
                        "actionable",
                        "waiting_on_dependencies",
                        "waiting_on_bindings",
                        "waiting_on_refinement",
                        "waiting_on_protocol",
                        "claimed",
                        "inactive",
                    )
                },
                "binding": {
                    item: _binding_text(translator, item)
                    for item in (
                        "readiness",
                        "blockers",
                        "ready",
                        "not_ready",
                        "no_blockers",
                    )
                },
                "definitions": {
                    item: _t(
                        translator,
                        f"definition_state.{item}",
                        item.replace("_", " ").title(),
                    )
                    for item in ("abstract", "placeholder", "concrete")
                },
                "refinementStatuses": {
                    item: _t(
                        translator,
                        f"refinement_status.{item}",
                        item.replace("_", " ").title(),
                    )
                    for item in ("not_required", "pending", "due", "resolved")
                },
                "common": {
                    "untitled": _t(translator, "common.unknown", "Untitled"),
                    "criterion": _t(translator, "common.criterion", "criterion"),
                    "evidence_required": _t(
                        translator,
                        "detail.evidence_required",
                        "Evidence required",
                    ),
                },
                "ui": {
                    "status": _t(translator, "field.status", "Status"),
                    "id": _t(translator, "field.id", "ID"),
                    "owner": _t(translator, "field.owner", "Owner"),
                    "dependencies": _t(translator, "field.dependencies", "Dependencies"),
                    "definition_state": _t(translator, "detail.definition_state", "Definition state"),
                    "refines": _t(translator, "detail.refines", "Refines"),
                    "refined_by": _t(translator, "detail.refined_by", "Refined by"),
                    "refinement_trigger": _t(translator, "detail.refinement_trigger", "Refinement trigger"),
                    "refinement_status": _t(translator, "detail.refinement_status", "Refinement status"),
                    "concrete_leaf_closure": _t(translator, "detail.concrete_leaf_closure", "Concrete leaf closure"),
                    "binding_impact": _t(translator, "detail.binding_impact", "Binding impact"),
                    "evidence": _t(translator, "field.evidence", "Evidence"),
                    "approval": _t(translator, "field.approval", "Approval"),
                    "blockers": _t(translator, "field.blockers", "Blockers"),
                    "review_history": _t(translator, "detail.review_history", "Review history"),
                    "provenance_layer": _t(translator, "detail.provenance_layer", "Provenance layer"),
                    "provenance_source": _t(translator, "detail.provenance_source", "Provenance source"),
                    "maturity": _t(translator, "detail.maturity", "Maturity"),
                    "criteria": _t(translator, "detail.criteria", "Review criteria"),
                    "replaced_by": _t(translator, "detail.replaced_by", "Replaced by"),
                    "blocker": _t(translator, "detail.blocker", "Blocker"),
                    "actionability": _t(translator, "detail.actionability", "Actionability"),
                    "unmet_dependencies": _t(translator, "detail.unmet_dependencies", "Unmet prerequisites"),
                    "input_evidence": _t(translator, "detail.input_evidence", "Input evidence"),
                    "output_deliverables": _t(translator, "detail.output_deliverables", "Output deliverables"),
                    "no_evidence": _t(translator, "detail.no_evidence", "No evidence recorded."),
                    "no_review_history": _t(translator, "detail.no_review_history", "No review history recorded."),
                    "no_input_evidence": _t(translator, "detail.no_input_evidence", "No input evidence recorded."),
                    "no_output_deliverables": _t(translator, "detail.no_output_deliverables", "No output deliverables recorded."),
                    "no_blockers": _t(translator, "detail.no_blockers", "No open blockers."),
                    "human_authorization_recorded": _t(translator, "common.human_authorization_recorded", "Human authorization recorded"),
                    "unassigned": _t(translator, "common.unassigned", "Unassigned"),
                    "unknown_reviewer": _t(translator, "common.reviewer", "Unknown reviewer"),
                    "recorded": _t(translator, "common.recorded", "Recorded"),
                    **{key: translator.text("navigation." + key) for key in ("owned_files", "shared_files", "binding_rules", "missing_file", "open_file", "copy_path", "copied", "copy_failed", "no_files", "visible_edges")},
                    "item": _t(translator, "common.item", "Item"),
                    "blocked": _t(translator, "common.blocked", "Blocked"),
                    "none": _t(translator, "common.none", "None"),
                },
            }
        ),
        "__CSS__": _BASE_CSS,
    }
    for marker, value in replacements.items():
        html = html.replace(marker, value)
    relations = ("depends_on", "supports", "verifies", "supersedes", "refines")
    controls = '<fieldset class="relation-tools"><legend>' + escape(translator.text("navigation.relations")) + '</legend>'
    controls += "".join('<label><input type="checkbox" data-relation-toggle value="' + relation + '"' + (' checked' if relation == "depends_on" else '') + '>' + escape(translator.text("navigation.depends_on") if relation == "depends_on" else translator.text("relation." + relation)) + '</label>' for relation in relations)
    controls += '<button class="btn" type="button" data-relations-action="all">' + escape(translator.text("navigation.show_all")) + '</button><button class="btn" type="button" data-relations-action="default">' + escape(translator.text("navigation.restore_default")) + '</button></fieldset>'
    html = html.replace("__RELATION_CONTROLS__", controls)
    templates = []
    if diagrams:
        def inline_svg(source: str, prefix: str) -> str:
            svg = re.sub(r'<\?xml[^>]*\?>', '', source)
            ids = re.findall(r'(?<![-\w])id="([^"]+)"', svg)
            for identifier in ids:
                scoped = prefix + identifier
                svg = re.sub(r'(?<![-\w])id="' + re.escape(identifier) + '"',
                             lambda _: 'id="' + scoped + '"', svg)
                svg = svg.replace('url(#' + identifier + ')', 'url(#' + scoped + ')')
            svg = svg.replace('aria-labelledby="svg-title svg-desc"', 'aria-labelledby="' + prefix + 'svg-title ' + prefix + 'svg-desc"')
            svg = svg.replace('../index.html#node=', '#node=')
            svg = re.sub(r'(<g class="node [^"]+")', r'\1 tabindex="0"', svg)
            if prefix != 'overview-': svg = svg.replace('<svg ', '<svg class="relation-filtered" ', 1)
            return svg
        def embed(match: Any) -> str:
            source = match.group(1)
            if source not in diagrams: return match.group(0)
            prefix = 'overview-' if source == 'assets/ipd_flow.svg' else 'view-' + re.sub(r'[^a-zA-Z0-9]', '-', source) + '-'
            return inline_svg(diagrams[source], prefix)
        html = re.sub(r'<object type="image/svg\+xml" data="([^"]+)"[^>]*></object>', embed, html)
        for phase, source in phase_files.items():
            if source in diagrams:
                templates.append('<template data-svg-src="' + escape(source, quote=True) + '">' + inline_svg(diagrams[source], 'phase-' + phase + '-') + '</template>')
    return html.replace("__SVG_TEMPLATES__", "".join(templates))


def _matrix_shell(
    title: str,
    subtitle: str,
    body: str,
    data: Any,
    script: str,
    translator: Any,
) -> str:
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title><style>__CSS__
.matrix-shell{width:min(1500px,calc(100% - 32px));margin:16px auto 48px}.matrix-head{padding:20px 22px;color:#fff;background:#101828}.matrix-head h1{margin:0;font-size:24px}.matrix-head p{margin:5px 0 0;color:#D0D5DD}.matrix-tools{display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px;background:#fff;border:1px solid var(--line);border-top:0}.matrix-tools .search{flex:1;min-width:220px}.matrix-panel{background:#fff;border:1px solid var(--line);border-top:0}.matrix-panel .table-scroll{max-height:none}tbody tr:target{background:var(--blue-soft)}
</style></head><body><main class="matrix-shell"><header class="matrix-head"><p class="eyebrow">IPD Agent Workflow Framework</p><h1>__TITLE__</h1><p>__SUBTITLE__</p></header>__BODY__</main><script id="matrix-data" type="application/json">__DATA__</script><script>__SCRIPT__</script></body></html>'''
    template = _localize_static_html(template, translator)
    return (template.replace("__TITLE__", escape(title)).replace("__SUBTITLE__", escape(subtitle))
            .replace("__CSS__", _BASE_CSS).replace("__BODY__", body)
            .replace("__DATA__", _json_script(data)).replace("__SCRIPT__", script))


def render_deliverable_matrix(
    state_data: Mapping[str, Any],
    *,
    translator: Any | None = None,
    locale: str = "en",
) -> str:
    """Render a standalone searchable deliverable matrix."""

    translator = _translator(translator, locale)
    deliverables = _items(state_data.get("deliverables"))
    phases = sorted({_text(item.get("phase")) for item in deliverables})
    phase_by_id = {
        _text(item.get("id"), ""): _text(item.get("display_label") or item.get("title"), "")
        for item in _items(state_data.get("phases"))
    }
    phase_options = "".join(
        f'<option value="{escape(item, quote=True)}">{escape(phase_by_id.get(item) or item)}</option>'
        for item in phases
    )
    body = '''<div class="matrix-tools"><a class="btn" href="../index.html#deliverable-matrix">Back to dashboard</a><label class="sr-only" for="search">Search deliverables</label><input class="search" id="search" type="search" placeholder="Search ID, title, owner, or dependency"><label class="sr-only" for="phase">Phase</label><select class="select" id="phase"><option value="">All phases</option>{}</select><label class="sr-only" for="status">Status</label><select class="select" id="status"><option value="">All statuses</option><option value="planned">Planned</option><option value="in_progress">In progress</option><option value="ready_for_review">Ready for review</option><option value="in_review">In review</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="blocked">Blocked</option><option value="superseded">Superseded</option></select></div><section class="matrix-panel"><div class="table-scroll"><table><thead><tr><th>ID / Deliverable</th><th>Phase</th><th>Owner</th><th>Status</th><th>Binding readiness</th><th>Dependencies</th><th>Evidence</th><th>Reviews</th></tr></thead><tbody id="rows">{}</tbody></table></div></section>'''.format(phase_options, _deliverable_rows(deliverables, translator, link_prefix="../index.html"))
    script = r'''(() => {'use strict'; const q=document.getElementById('search'),p=document.getElementById('phase'),s=document.getElementById('status'); function filter(){const text=q.value.trim().toLowerCase();document.querySelectorAll('#rows tr[data-node]').forEach(row=>{row.hidden=!((!text||row.textContent.toLowerCase().includes(text))&&(!p.value||row.dataset.phase===p.value)&&(!s.value||row.dataset.status===s.value));});}q.addEventListener('input',filter);p.addEventListener('change',filter);s.addEventListener('change',filter);})();'''
    body = _localize_static_html(body, translator)
    return _matrix_shell(
        _t(translator, "dashboard.deliverable_matrix", "Deliverable Matrix"),
        _t(translator, "matrix.deliverable_subtitle", "Ownership, status, dependencies, evidence, and review history."),
        body,
        deliverables,
        script,
        translator,
    )


def render_gate_matrix(
    state_data: Mapping[str, Any],
    *,
    translator: Any | None = None,
    locale: str = "en",
) -> str:
    """Render a standalone searchable Gate/TR/DCP matrix."""

    translator = _translator(translator, locale)
    checkpoints = _items(state_data.get("checkpoints"))
    body = '''<div class="matrix-tools"><a class="btn" href="../index.html#gate-matrix">Back to dashboard</a><label class="sr-only" for="search">Search checkpoints</label><input class="search" id="search" type="search" placeholder="Search checkpoint ID, phase, or approval"><label class="sr-only" for="kind">Checkpoint type</label><select class="select" id="kind"><option value="">All types</option><option value="tr">TR</option><option value="dcp">DCP</option><option value="gate">Gate</option></select></div><section class="matrix-panel"><div class="table-scroll"><table><thead><tr><th>ID</th><th>Type</th><th>Phase</th><th>Readiness</th><th>Status</th><th>Approval</th><th>Blockers</th></tr></thead><tbody id="rows">{}</tbody></table></div></section>'''.format(_gate_rows(checkpoints, translator, link_prefix="../index.html"))
    script = r'''(() => {'use strict';const q=document.getElementById('search'),k=document.getElementById('kind');function filter(){const text=q.value.trim().toLowerCase();document.querySelectorAll('#rows tr[data-node]').forEach(row=>{row.hidden=!((!text||row.textContent.toLowerCase().includes(text))&&(!k.value||row.dataset.kind===k.value));});}q.addEventListener('input',filter);k.addEventListener('change',filter);})();'''
    body = _localize_static_html(body, translator)
    return _matrix_shell(
        _t(translator, "dashboard.gate_matrix", "Gate Matrix"),
        _t(translator, "matrix.gate_subtitle", "Technical review, decision checkpoint, and gate readiness."),
        body,
        checkpoints,
        script,
        translator,
    )


__all__ = ["render_index", "render_deliverable_matrix", "render_gate_matrix"]

"""Versioned numbering and per-parent work products, within core governance.

Plans allocate facts, never claims or approvals. Narrative edges are distinct
from core execution dependencies. All writes use requirements' existing journal.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

from .documents import RequirementError, safe_path
from .requirement_contract import STAGE_UNIT, STAGE_PLAN, ORGANIZATION, ID, validate
from .template_publications import live_instances

STAGES = ("TR1", "TR2", "TR3", "TR4")
PHASES = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
TYPES = {"TR1": ("tr1_requirements_feasibility", "ir_spec"),
         "TR2": ("ir_decomposition", "sr_spec"),
         "TR3": ("sr_decomposition", "ar_spec"),
         "TR4": ("delivery_conclusion", "ar_spec")}
NEW_TYPES = {"stage_index", "ir_decomposition", "sr_decomposition", "delivery_conclusion", "hardware_selection"}


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        self.values.extend(value for key, value in attrs if key in {"id", "name"} and value is not None)


def reference(record):
    return record["id"] + "@" + str(record["version"])


def organization(registry):
    if not registry or "organization" not in registry:
        raise RequirementError("ORGANIZATION_REQUIRED: adopt the 0.5.4 organization contract first")
    return registry["organization"]


def codes(registry):
    return {x["requirement"]: x["code"] for x in registry.get("organization", {}).get("codes", [])}


def assign_code(registry, record, *, allocate_id=False, enforce_new=False):
    org = organization(registry)
    value = deepcopy(record)
    mapping = codes(registry)
    if value["kind"] == "IR":
        prefix = "ir-"
    elif value["derived"] and value["parent"] is None:
        prefix = value["kind"].lower() + "-d-"
    else:
        parent = mapping.get(value["parent"])
        if not parent:
            raise RequirementError("NUMBER_PARENT: number the exact parent first")
        prefix = value["kind"].lower() + "-" + parent.split("-", 1)[1] + "-"
    prior = [x for x in org["codes"] if x["requirement"].rsplit("@", 1)[0] == value.get("id")]
    reusable = [x["code"] for x in prior if re.fullmatch(re.escape(prefix) + r"[0-9]+", x["code"])]
    used = [int(x["code"][len(prefix):]) for x in org["codes"]
            if re.fullmatch(re.escape(prefix) + r"[0-9]+", x["code"])]
    code = reusable[-1] if reusable else prefix + str(max(used, default=0) + 1).zfill(3)
    identities = {r["id"] for r in registry["requirements"]}
    if allocate_id and not value.get("id"):
        while code in identities:
            code = prefix + str(int(code[len(prefix):]) + 1).zfill(3)
        value["id"] = code
    elif enforce_new and value.get("id") not in identities and value.get("id") != code:
        raise RequirementError("NUMBER_PARENT: new identities must use the allocated hierarchical number")
    exact = reference(value)
    if exact in mapping:
        raise RequirementError("NUMBER_DUPLICATE: exact requirement already numbered")
    org["codes"].append({"requirement": exact, "code": code})
    return value


def adopt(registry, required_stages, adoption):
    if "organization" in registry:
        raise RequirementError("ORGANIZATION_ENABLED: already adopted")
    validate(required_stages, ORGANIZATION["properties"]["required_stages"])
    if len(set(required_stages)) != len(required_stages):
        raise RequirementError("STAGE_CONTRACT: select distinct supported stages")
    registry.update(schema_version="1.1", contract="0.5.4")
    registry["organization"] = {"policy": "hierarchical-v1", "required_stages": list(required_stages),
                                "codes": [], "plans": [], "units": [], "adoption": adoption}
    for item in sorted(registry["requirements"], key=lambda r: ({"IR": 0, "SR": 1, "AR": 2}[r["kind"]], r["id"], r["version"])):
        assign_code(registry, item)


def stage_phase(registry, state, stage):
    phases = [g["phase"] for g in state["gates"] if registry["stage_map"].get(g["id"]) == stage]
    if not phases:
        raise RequirementError("STAGE_MAP: selected stage has no canonical Gate")
    return min(phases, key=PHASES.index)


def groups(registry, stage):
    current = next(i for i in registry["increments"] if i["id"] == registry["active_increment"])
    scope = {s["requirement"] for s in current["scope"]}
    records = {reference(r): r for r in registry["requirements"]}
    if stage == "TR1":
        return [("ir", [], sorted(r for r in scope if records[r]["kind"] == "IR"))]
    if stage in {"TR2", "TR3"}:
        kind = "IR" if stage == "TR2" else "SR"
        return [(r, [r], sorted(c for c in scope if records[c]["parent"] == r))
                for r in sorted(scope) if records[r]["kind"] == kind]
    parents = sorted({records[r]["parent"] or r for r in scope if records[r]["kind"] == "AR"})
    return [(p, sorted(r for r in scope if records[r]["kind"] == "AR" and (records[r]["parent"] or r) == p), []) for p in parents]


def plan_stage(registry, state, stage, owner, locale):
    org = organization(registry)
    validate(stage, STAGE_PLAN["properties"]["stage"])
    validate(locale, STAGE_PLAN["properties"]["locale"])
    validate(owner, ID)
    if stage not in org["required_stages"] or locale not in {"en", "zh-CN"}:
        raise RequirementError("STAGE_CONTRACT: unknown stage or locale")
    subject = next((d for d in state["deliverables"] if d["id"] == owner), None)
    if not subject or subject["phase"] != stage_phase(registry, state, stage):
        raise RequirementError("STAGE_OWNER: choose an existing Owner in the stage Phase")
    if subject["status"] in {"accepted", "superseded"}:
        raise RequirementError("STAGE_GOVERNED: cannot change an accepted Owner")
    if PHASES.index(subject["phase"]) < PHASES.index(state["project"]["phase"]):
        raise RequirementError("STAGE_GOVERNED: cannot add facts to a closed Phase")
    inc = registry["active_increment"]
    prior = next((p for p in org["plans"] if p["increment"] == inc and p["stage"] == stage), None)
    if prior and (prior["owner"] != owner or prior["locale"] != locale):
        raise RequirementError("STAGE_PLAN_EXISTS: preserve the stage Owner and locale")
    prefix = inc + "-" + stage.lower()
    if prior is None:
        org["plans"].append({"increment": inc, "stage": stage, "owner": owner, "locale": locale, "index": prefix + "-index"})
    for key, inputs, outputs in groups(registry, stage):
        identifier = prefix + "-" + key.replace("@", "-v")
        if any(u["id"] == identifier for u in org["units"]):
            continue  # Extend new parent branches, never overwrite existing work.
        org["units"].append({"id": identifier, "increment": inc, "stage": stage, "owner": owner,
            "locale": locale, "inputs": inputs, "outputs": outputs, "supports": [], "arguments": [],
            "conclusion": identifier + "-conclusion", "register": identifier + "-register" if TYPES[stage][1] else None,
            "finalized": False, "rationale": "Planned from the explicit increment scope"})


def support_path(root, registry, support):
    if support["kind"] == "instance":
        item = next((i for i in registry["instances"] if i["id"] == support["target"]), None)
        if not item or item["owner"] != support["owner"]:
            raise RequirementError("SUPPORT_REFERENCE: missing live instance or different Owner")
        return item["path"]
    safe_path(root, support["target"])
    return support["target"]


def update_unit(root, registry, state, unit, owner_check):
    org = organization(registry)
    validate(unit, STAGE_UNIT)
    old = next((u for u in org["units"] if u["id"] == unit["id"]), None)
    if not old or any(unit[k] != old[k] for k in ("increment", "stage", "owner", "locale")) or unit["increment"] != registry["active_increment"]:
        raise RequirementError("STAGE_UNIT: update a planned current unit without changing its identity")
    subject = next(d for d in state["deliverables"] if d["id"] == unit["owner"])
    if subject["status"] in {"accepted", "superseded"}:
        raise RequirementError("STAGE_GOVERNED: accepted work needs a new increment")
    if PHASES.index(subject["phase"]) < PHASES.index(state["project"]["phase"]):
        raise RequirementError("STAGE_GOVERNED: cannot reinterpret a closed Phase")
    for support in unit["supports"]:
        if support["kind"] == "instance" and support["target"] not in {i["id"] for i in live_instances(registry)}:
            raise RequirementError("SUPPORT_REFERENCE: select a live instance")
        relative = support_path(root, registry, support)
        owner_check(root, state, relative, support["owner"])
        if support["required"] and support["owner"] != unit["owner"]:
            by_id = {d["id"]: d for d in state["deliverables"]}
            pending, seen = list(subject["depends_on"]), set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(by_id[current]["depends_on"])
            if by_id[support["owner"]]["status"] != "accepted" and support["owner"] not in seen:
                raise RequirementError("SUPPORT_DEPENDENCY: configure the explicit core prerequisite before requiring another Owner's work")
        path = safe_path(root, relative)
        # Hashes come from the current bytes, never from a caller assertion.
        support["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    org["units"][org["units"].index(old)] = deepcopy(unit)
    if unit["finalized"]:
        issues = unit_issues(root, registry, state, unit)
        if issues:
            raise RequirementError("STAGE_NOT_READY: " + ", ".join(issues))


def validate_organization(registry):
    if "organization" not in registry:
        return
    org = registry["organization"]
    records = {reference(r): r for r in registry["requirements"]}
    mapping = codes(registry)
    if set(mapping) != set(records) or len(mapping) != len(org["codes"]):
        raise RequirementError("NUMBER_COVERAGE: each exact requirement needs one readable code")
    owners = {}
    for r, code in mapping.items():
        identity = records[r]["id"]
        if code in owners and owners[code] != identity:
            raise RequirementError("NUMBER_DUPLICATE: a historical code belongs to another identity")
        owners[code] = identity
        item = records[r]
        prefix = item["kind"].lower() + "-"
        if item["parent"]:
            prefix += mapping[item["parent"]].split("-", 1)[1] + "-"
        elif item["derived"]:
            prefix += "d-"
        if not re.fullmatch(re.escape(prefix) + r"[0-9]{3,}", code):
            raise RequirementError("NUMBER_PARENT: code must match the exact parent code")
    keys = [(p["increment"], p["stage"]) for p in org["plans"]]
    if len(keys) != len(set(keys)) or len({u["id"] for u in org["units"]}) != len(org["units"]):
        raise RequirementError("STAGE_DUPLICATE: duplicate stage plan or unit")
    increments = {i["id"] for i in registry["increments"]}
    for unit in org["units"]:
        if unit["increment"] not in increments or (unit["increment"], unit["stage"]) not in keys:
            raise RequirementError("STAGE_UNIT: unknown increment or unplanned stage")
        for field in ("inputs", "outputs"):
            if len(unit[field]) != len(set(unit[field])) or not set(unit[field]) <= set(records):
                raise RequirementError("STAGE_REFERENCE: duplicate or dangling requirement")
        inputs, outputs = unit["inputs"], unit["outputs"]
        arguments = [a["requirement"] for a in unit["arguments"]]
        if len(arguments) != len(set(arguments)) or len({a["anchor"] for a in unit["arguments"]}) != len(arguments) or not set(arguments) <= set(outputs):
            raise RequirementError("STAGE_ARGUMENT: each argument must identify a distinct output")
        if unit["stage"] == "TR1" and (inputs or any(records[r]["kind"] != "IR" for r in outputs)):
            raise RequirementError("STAGE_PARENT: TR1 produces IR requirements")
        if unit["stage"] in {"TR2", "TR3"}:
            kind = "IR" if unit["stage"] == "TR2" else "SR"
            if len(inputs) != 1 or records[inputs[0]]["kind"] != kind or any(records[r]["parent"] != inputs[0] for r in outputs):
                raise RequirementError("STAGE_PARENT: exactly one parent and only its direct children")
        if unit["stage"] == "TR4" and (outputs or any(records[r]["kind"] != "AR" for r in inputs)):
            raise RequirementError("STAGE_PARENT: TR4 consumes AR without a fourth requirement layer")
        support_keys = [(s["kind"], s["target"]) for s in unit["supports"]]
        if len(support_keys) != len(set(support_keys)) or any(s["kind"] == "instance" and s["target"] in {unit["conclusion"], unit["register"]} for s in unit["supports"]):
            raise RequirementError("SUPPORT_CYCLE: duplicate or self-supporting conclusion")
    terminals = {(u["increment"], target): u["id"] for u in org["units"] for target in (u["conclusion"], u["register"]) if target}
    graph = {u["id"]: {terminals[(u["increment"], s["target"])] for s in u["supports"]
                       if s["required"] and s["kind"] == "instance" and (u["increment"], s["target"]) in terminals} for u in org["units"]}
    def visit(node, path, done):
        if node in path:
            raise RequirementError("SUPPORT_CYCLE: required conclusions cannot depend on each other cyclically")
        if node not in done:
            for child in graph[node]:
                visit(child, path | {node}, done)
            done.add(node)
    done = set()
    for node in graph:
        visit(node, set(), done)


def referenced_paths(root, registry, *, references=None):
    """Only explicit active references; never enumerate an unrelated file tree."""
    if "organization" not in registry:
        return {}
    result = {}
    for unit in registry["organization"]["units"]:
        if unit["increment"] != registry["active_increment"] or (references is not None and not set(unit["inputs"] + unit["outputs"]) & set(references)):
            continue
        for support in unit["supports"]:
            relative = support_path(root, registry, support)
            if relative in result:
                continue
            path = safe_path(root, relative)
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def unit_issues(root, registry, state, unit, *, check_owner=True, documents=None):
    issues = []
    instances = {i["id"]: i for i in live_instances(registry) if i["increment"] == unit["increment"]}
    records = {reference(r): r for r in registry["requirements"]}
    if documents is None:
        from .documents import lint_instances
        documents = lint_instances(root, [instances[k] for k in (unit["conclusion"], unit["register"]) if k in instances], records)
    scope = {s["requirement"] for i in registry["increments"] if i["id"] == unit["increment"] for s in i["scope"]}
    if not set(unit["inputs"] + unit["outputs"]) <= scope:
        issues.append("STAGE_SCOPE")
    expected = next((o for key, ins, o in groups(registry, unit["stage"]) if ins == unit["inputs"]), None)
    if expected is None or set(expected) != set(unit["outputs"]) or (unit["stage"] != "TR4" and not unit["outputs"]) or (unit["stage"] == "TR4" and not unit["inputs"]):
        issues.append("STAGE_OUTPUTS")
    for field, dtype in zip(("conclusion", "register"), TYPES[unit["stage"]]):
        if dtype is None:
            continue
        item = instances.get(unit[field])
        desired = set(unit["outputs"] if field == "register" and unit["stage"] != "TR4" else unit["inputs"] + unit["outputs"])
        if not item or item["owner"] != unit["owner"] or item["document_type"] != dtype or set(item["requirements"]) != desired:
            issues.append("STAGE_DOCUMENT:" + field)
        elif documents.get(item["id"]):
            issues.extend("STAGE_DOCUMENT_INVALID:" + field + ":" + i for i in documents[item["id"]])
    arguments = {a["requirement"]: a["anchor"] for a in unit["arguments"]}
    if set(arguments) != set(unit["outputs"]):
        issues.append("STAGE_ARGUMENTS")
    conclusion = instances.get(unit["conclusion"])
    if conclusion and arguments:
        try:
            text = safe_path(root, conclusion["path"]).read_text(encoding="utf-8")
            text = re.sub(r'\A---\r?\n.*?\r?\n---(?:\r?\n|\Z)', '', text, flags=re.S)
            parsed = _Anchors()
            parsed.feed(re.sub(r'```.*?```|~~~.*?~~~|<!--.*?-->', '', text, flags=re.S))
            anchors = parsed.values
            for exact_ref, target in arguments.items():
                if anchors.count(target) != 1:
                    issues.append("STAGE_ARGUMENT_ANCHOR:" + exact_ref)
        except (ValueError, OSError):
            issues.append("STAGE_ARGUMENT_DOCUMENT")
    state_owners = {d["id"]: d for d in state["deliverables"]}
    for support in unit["supports"]:
        if not support["required"]:
            continue
        try:
            if support["kind"] == "instance" and support["target"] not in {i["id"] for i in live_instances(registry)}:
                issues.append("SUPPORT_SUPERSEDED:" + support["target"])
            relative = support_path(root, registry, support)
            path = safe_path(root, relative)
            if not path.is_file():
                issues.append("SUPPORT_MISSING:" + support["target"])
            elif not support["sha256"] or hashlib.sha256(path.read_bytes()).hexdigest() != support["sha256"]:
                issues.append("SUPPORT_STALE:" + support["target"])
            if check_owner and support["owner"] != unit["owner"] and state_owners.get(support["owner"], {}).get("status") != "accepted":
                issues.append("SUPPORT_UNACCEPTED:" + support["target"])
            from .requirements import _owner
            _owner(root, state, relative, support["owner"])
        except (ValueError, OSError) as exc:
            issues.append("SUPPORT_INVALID:" + support["target"] + ":" + str(exc))
    if not unit["finalized"]:
        issues.append("STAGE_DRAFT")
    return sorted(set(issues))


def readiness(root, registry, state, *, stage, owner=None, phase=None, documents=None):
    if "organization" not in registry:
        return []
    org = registry["organization"]
    cutoff = PHASES.index(phase or state["project"]["phase"])
    inc = registry["active_increment"]
    plans = [p for p in org["plans"] if p["increment"] == inc]
    issues = []
    instances = {i["id"]: i for i in live_instances(registry) if i["increment"] == inc}
    for current in org["required_stages"]:
        if STAGES.index(current) > STAGES.index(stage) or PHASES.index(stage_phase(registry, state, current)) > cutoff:
            continue
        plan = next((p for p in plans if p["stage"] == current), None)
        if owner is not None and (not plan or plan["owner"] != owner):
            continue
        if not plan:
            issues.append("STAGE_PLAN_MISSING:" + current)
            continue
        index = instances.get(plan["index"])
        if not index or index["document_type"] != "stage_index" or index["owner"] != plan["owner"]:
            issues.append("STAGE_INDEX_MISSING:" + current)
        units = [u for u in org["units"] if u["increment"] == inc and u["stage"] == current]
        expected = {tuple(ins) for key, ins, out in groups(registry, current)}
        actual = [tuple(u["inputs"]) for u in units]
        if set(actual) != expected or len(actual) != len(set(actual)) or not units:
            issues.append("STAGE_COVERAGE:" + current)
        for unit in units:
            issues.extend(i + ":" + unit["id"] for i in unit_issues(root, registry, state, unit, documents=documents))
    return sorted(set(issues))


def blueprints(registry):
    """Proposed files are editable plans, not inferred artifact permissions."""
    if "organization" not in registry or not registry["active_increment"]:
        return []
    org, inc, mapping = registry["organization"], registry["active_increment"], codes(registry)
    records = {reference(r): r for r in registry["requirements"]}
    result = []
    for plan in org["plans"]:
        if plan["increment"] != inc:
            continue
        base = "docs/increments/" + inc + "/" + plan["stage"].lower()
        result.append({"id": plan["index"], "key": plan["stage"].lower() + "-index", "owner": plan["owner"], "locale": plan["locale"],
                       "document_type": "stage_index", "path": base + "/index.md", "requirements": [],
                       "title": plan["stage"], "scope": "Explicit stage scope and cross-branch checks"})
        for unit in org["units"]:
            if unit["increment"] != inc or unit["stage"] != plan["stage"]:
                continue
            lineage = []
            cursor = (unit["inputs"] or unit["outputs"] or [None])[0]
            while cursor:
                item = records[cursor]
                if item["kind"] != "AR" or item["parent"] is None:
                    lineage.append(mapping[cursor])
                cursor = item["parent"]
            path = base + ("/" + "/".join(reversed(lineage)) if lineage and unit["stage"] != "TR1" else "")
            for field, dtype in zip(("conclusion", "register"), TYPES[unit["stage"]]):
                if dtype is None:
                    continue
                result.append({"id": unit[field], "key": unit["stage"].lower() + "-" + field, "owner": unit["owner"], "locale": unit["locale"],
                    "document_type": dtype, "path": path + "/" + dtype + ".md",
                    "requirements": unit["outputs"] if field == "register" and unit["stage"] != "TR4" else sorted(set(unit["inputs"] + unit["outputs"])),
                    "title": unit["id"], "scope": unit["rationale"]})
    return result


def context(root, registry, reference):
    if "organization" not in registry:
        return None
    related = {reference}
    while True:
        old = set(related)
        related.update(reference_of for r in registry["requirements"] if r["parent"] in related for reference_of in [r["id"] + "@" + str(r["version"])])
        if old == related:
            break
    units = [u for u in registry["organization"]["units"] if u["increment"] == registry["active_increment"] and set(u["inputs"] + u["outputs"]) & related]
    # Exclude increment/unit IDs, preserving the existing explicit reuse rules.
    semantic = [{k: v for k, v in u.items() if k not in {"id", "increment", "finalized"}} for u in units]
    return {"units": semantic, "support_files": referenced_paths(root, registry, references=related)}

"""Opt-in IR/SR/AR, serial increments and immutable delivery snapshots.

The registry is an additional project fact, never a remote coordination service.
Every mutation is reviewed as a fingerprinted plan and shares the core mutex and
rollback journal. Historical facts live in content-addressed snapshots.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from .documents import RequirementError, digest, instantiate, lint, load_pack, safe_path, template
from .requirement_contract import (CHANGE, ID, LINK, OBLIGATION, REQUIREMENT, SCOPE, STAGE_UNIT,
                                   VERIFICATION, validate)
from .runtime import bind_increment, create_runtime_state, load_runtime, record_event, save_runtime, utc_now, _parse_time
from .state import create_initial_state, load_state, resolve_state_path, write_state
from .transaction import project_mutation_guard
from .requirement_verification import active_changes, verification_context, verification_issue
from .template_publications import live_instances, require_published, read_record, transition


REGISTRY = ".ipd/requirements.yaml"


def ref(record: dict) -> str:
    return f"{record['id']}@{record['version']}"


def registry_path(root: Path) -> Path:
    return safe_path(root, REGISTRY)


def read_registry(root: Path) -> dict | None:
    path = registry_path(root)
    if not path.is_file():
        return None
    value = load_state(path)
    validate(value)
    check_relations(value)
    return value


def active(registry: dict) -> dict:
    result = next((i for i in registry["increments"] if i["id"] == registry["active_increment"]), None)
    if result is None:
        raise RequirementError("INCREMENT_REQUIRED: no active increment")
    return result


def check_relations(registry: dict) -> None:
    requirements = {ref(r): r for r in registry["requirements"]}
    if len(requirements) != len(registry["requirements"]):
        raise RequirementError("REQUIREMENT_DUPLICATE: duplicate exact version")
    kinds = {}
    for r in requirements.values():
        if r["id"] in kinds and kinds[r["id"]] != r["kind"]:
            raise RequirementError("REQUIREMENT_KIND: stable ID cannot change kind")
        kinds[r["id"]] = r["kind"]
        parent = requirements.get(r["parent"])
        expected = {"IR": None, "SR": "IR", "AR": "SR"}[r["kind"]]
        if r["kind"] == "IR" and (r["parent"] is not None or r["derived"]):
            raise RequirementError("REQUIREMENT_PARENT: IR cannot have a parent")
        if r["kind"] != "IR" and not (r["derived"] and r["parent"] is None):
            if not parent or parent["kind"] != expected:
                raise RequirementError("REQUIREMENT_PARENT: invalid or dangling exact parent version")
        if len({a["id"] for a in r["acceptance"]}) != len(r["acceptance"]):
            raise RequirementError("CRITERION_DUPLICATE: duplicate acceptance criterion")
        visited = {ref(r)}
        while parent:
            if ref(parent) in visited:
                raise RequirementError("REQUIREMENT_CYCLE: decomposition cycle")
            visited.add(ref(parent))
            parent = requirements.get(parent["parent"])
    increment_ids = [i["id"] for i in registry["increments"]]
    if len(increment_ids) != len(set(increment_ids)):
        raise RequirementError("INCREMENT_DUPLICATE: duplicate increment")
    running = [i["id"] for i in registry["increments"] if i["status"] == "active"]
    if running != ([registry["active_increment"]] if registry["active_increment"] else []):
        raise RequirementError("INCREMENT_CONFLICT: one active increment is required")
    accepted = {i["id"] for i in registry["increments"] if i["status"] == "accepted"}
    if accepted != {b["increment"] for b in registry["baselines"]} or len({b["id"] for b in registry["baselines"]}) != len(registry["baselines"]):
        raise RequirementError("BASELINE_REFERENCE: accepted increments require unique frozen baselines")
    for identifier in kinds:
        versions = sorted(r["version"] for r in requirements.values() if r["id"] == identifier)
        if versions != list(range(1, len(versions) + 1)):
            raise RequirementError("REQUIREMENT_VERSION: content version history has gaps")
    for increment in registry["increments"]:
        seen = set()
        for item in increment["scope"]:
            r = requirements.get(item["requirement"])
            if not r or item["requirement"] in seen or len(item["criteria"]) != len(set(item["criteria"])) or not set(item["criteria"]) <= {a["id"] for a in r["acceptance"]}:
                raise RequirementError("SCOPE_INVALID: duplicate, dangling or unknown criterion")
            seen.add(item["requirement"])
    for collection in ("instances", "obligations", "verifications"):
        items = registry[collection]
        if len({i["id"] for i in items}) != len(items):
            raise RequirementError("RECORD_DUPLICATE: duplicate " + collection + " ID")
        for item in items:
            if item["increment"] not in increment_ids:
                raise RequirementError("INCREMENT_REFERENCE: unknown increment")
    paths = [i["path"].casefold() for i in registry["instances"]]
    if len(paths) != len(set(paths)):
        raise RequirementError("INSTANCE_PATH: duplicate or case-colliding path")
    for item in registry["instances"]:
        if item.get("supersedes"):
            prior = next((i for i in registry["instances"] if i["id"] == item["supersedes"]), None)
            if not prior or prior["increment"] != item["increment"] or prior["owner"] != item["owner"] or registry["instances"].index(prior) >= registry["instances"].index(item):
                raise RequirementError("INSTANCE_REPLACEMENT: invalid superseded instance")
        if len(item["requirements"]) != len(set(item["requirements"])) or not set(item["requirements"]) <= set(requirements):
            raise RequirementError("INSTANCE_REFERENCE: invalid requirement reference")
    replaced = [i["supersedes"] for i in registry["instances"] if i.get("supersedes")]
    if len(set(replaced)) != len(replaced):
        raise RequirementError("INSTANCE_REPLACEMENT: duplicate replacement branch")
    records = registry.get("template_records", [])
    if len({r["id"] for r in records}) != len(records):
        raise RequirementError("TEMPLATE_RECORD_EXISTS: duplicate QA record ID")
    for collection in ("links", "obligations", "verifications"):
        for item in registry[collection]:
            if item["requirement"] not in requirements:
                raise RequirementError("REQUIREMENT_REFERENCE: dangling exact version")
    for item in registry["verifications"]:
        criteria = {a["id"]: a for a in requirements[item["requirement"]]["acceptance"]}
        if item["criterion"] not in criteria or item["method"] != criteria[item["criterion"]]["method"]:
            raise RequirementError("VERIFICATION_METHOD: unknown criterion or different method")
    from .stage_organization import validate_organization
    validate_organization(registry)


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def input_snapshot(root: Path, registry: dict | None = None) -> dict:
    registry = read_registry(root) if registry is None else registry
    result = {}
    for relative in (REGISTRY, ".ipd/project_state.yaml", ".ipd/agent_runtime.yaml",
                     ".ipd/tailored_process.yaml", ".ipd/task_profile.yaml",
                     ".ipd/process_extensions.yaml", ".ipd/artifact_bindings.yaml"):
        result[relative] = file_hash(safe_path(root, relative))
    if registry:
        from .stage_organization import referenced_paths
        result.update(referenced_paths(root, registry))
        if "organization" in registry:
            adopted = registry["organization"]["adoption"]
            result[adopted["path"]] = file_hash(safe_path(root, adopted["path"]))
            if result[adopted["path"]] != adopted["sha256"]:
                raise RequirementError("HISTORY_TAMPERED: organization adoption snapshot changed")
        for record in registry.get("template_records", []):
            read_record(root, record)
            result[record["path"]] = record["sha256"]
        pin = active(registry)["pack"] if registry["active_increment"] else registry["template_pack"]
        manifest, _ = load_pack(root, pin)
        result["template_pack"] = digest(manifest)
        for item in registry["instances"] + registry["verifications"]:
            if item["increment"] == registry["active_increment"]:
                path = item.get("path", item.get("evidence"))
                result[path] = file_hash(safe_path(root, path))
        for item in [registry["migration"], *registry["baselines"]]:
            result[item["path"]] = file_hash(safe_path(root, item["path"]))
            if result[item["path"]] != item["sha256"]:
                raise RequirementError("HISTORY_TAMPERED: immutable snapshot missing or changed")
    return result


def source_snapshot(root: Path, registry: dict | None = None) -> dict:
    """Exclude control files that Verify itself changes after fingerprinting."""
    result = input_snapshot(root, registry)
    result.pop(".ipd/project_state.yaml", None)
    result.pop(".ipd/agent_runtime.yaml", None)
    return result


def impact(registry: dict, changed: str) -> list[str]:
    affected = {changed}
    while True:
        before = len(affected)
        affected.update(ref(r) for r in registry["requirements"] if r["parent"] in affected)
        for edge in registry["links"]:
            if edge["relation"] == "shared_constraint" and edge["target"] in affected:
                affected.add(edge["requirement"])
        if len(affected) == before:
            break
    # Ancestors require explicit applicability assessment as well.
    rmap = {ref(r): r for r in registry["requirements"]}
    current = rmap[changed].get("parent")
    while current:
        affected.add(current)
        current = rmap[current].get("parent")
    for item in registry["instances"]:
        if set(item["requirements"]) & affected:
            affected.add("instance:" + item["id"])
    for link in registry["links"]:
        if link["requirement"] in affected:
            affected.add(link["target"])
    for unit in registry.get("organization", {}).get("units", []):
        if set(unit["inputs"] + unit["outputs"]) & affected:
            affected.add("unit:" + unit["id"])
            affected.update("instance:" + i for i in (unit["conclusion"], unit["register"]) if i)
    return sorted(affected)


def _snapshot(root: Path, state: dict, runtime: dict, registry: dict | None) -> str:
    files = {}
    paths = {".ipd/tailored_process.yaml", ".ipd/task_profile.yaml",
             ".ipd/process_extensions.yaml", ".ipd/artifact_bindings.yaml"}
    if registry:
        from .stage_organization import referenced_paths
        paths.update(p for p, sha in referenced_paths(root, registry).items() if sha is not None)
        if "organization" in registry:
            paths.add(registry["organization"]["adoption"]["path"])
        paths.update(i["path"] for i in registry["instances"] if i["increment"] == registry["active_increment"])
        paths.update(i["evidence"] for i in registry["verifications"] if i["increment"] == registry["active_increment"])
    for item in state["deliverables"] + state["gates"]:
        references = list(item.get("evidence", [])) + [r["evidence"] for r in item.get("reviews", []) if r.get("evidence")]
        if registry and any(":" in e for e in references):
            raise RequirementError("SNAPSHOT_EXTERNAL: delivery snapshots require resolvable local evidence")
        paths.update(e for e in item.get("evidence", []) if "://" not in e and ":" not in e)
        paths.update(r["evidence"] for r in item.get("reviews", []) if r.get("evidence") and ":" not in r["evidence"])
    total = 0
    for relative in sorted(paths):
        path = safe_path(root, relative)
        if not path.is_file():
            raise RequirementError("SNAPSHOT_EVIDENCE: missing local evidence " + relative)
        total += path.stat().st_size
        if path.stat().st_size > 16 * 1024 * 1024 or total > 100 * 1024 * 1024:
            raise RequirementError("SNAPSHOT_SIZE: evidence snapshot budget exceeded")
        files[relative] = base64.b64encode(path.read_bytes()).decode("ascii")
    if registry:
        for record in registry.get("template_records", []):
            read_record(root, record)
            path = safe_path(root, record["path"])
            files[record["path"]] = base64.b64encode(path.read_bytes()).decode("ascii")
    pack = None
    if registry:
        pin = active(registry)["pack"]
        manifest, directory = load_pack(root, pin)
        pack = {"manifest": manifest, "files": {
            r["path"]: safe_path(directory, r["path"]).read_text(encoding="utf-8")
            for r in manifest["templates"]}}
    return json.dumps({"schema_version": "1.0", "state": state, "runtime": runtime,
                       "registry": registry, "files": files, "template_pack": pack},
                      ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _fields(request: dict, required: set[str]) -> None:
    common = {"request_id", "operation", "reason"}
    if set(request) != common | required or any(not request.get(k) for k in common):
        raise RequirementError("REQUEST_CONTRACT: missing or unknown operation fields")
    validate(request["request_id"], ID)


def _owner(root: Path, state: dict, path: str, owner: str) -> None:
    from .reconcile import load_artifact_bindings, map_paths_to_deliverables
    if owner not in {i["id"] for i in state["deliverables"]}:
        raise RequirementError("INSTANCE_OWNER: unknown core Deliverable")
    binding = load_artifact_bindings(root / ".ipd/artifact_bindings.yaml")
    mapping = map_paths_to_deliverables([path], binding)
    owners = {d for rule in mapping["paths"].get(path, []) for d in rule["owner_deliverable_ids"]}
    if owners != {owner}:
        raise RequirementError("INSTANCE_OWNER: path must have exactly the declared Owner")


def _accepted_source(root: Path, source: dict) -> None:
    validate(source, {"type": "object", "properties": {k: {"type": "string", "minLength": 1}
             for k in ("backend", "repository", "revision", "path")},
             "required": ["backend", "repository", "revision", "path"], "additionalProperties": False})
    from urllib.parse import urlsplit
    if urlsplit(source["repository"]).password:
        raise RequirementError("BASELINE_SOURCE: credentials cannot be stored in project facts")
    if source["path"] != ".":
        safe_path(root, source["path"])
    paths = {REGISTRY, ".ipd/project_state.yaml", ".ipd/agent_runtime.yaml",
             ".ipd/tailored_process.yaml", ".ipd/artifact_bindings.yaml",
             ".ipd/task_profile.yaml", ".ipd/process_extensions.yaml"}
    registry = read_registry(root)
    if registry:
        paths.update(b["path"] for b in [registry["migration"], *registry["baselines"]])
        paths.update(r["path"] for r in registry.get("template_records", []))
        paths.update(i["path"] for i in registry["instances"] if i["increment"] == registry["active_increment"])
        paths.update(v["evidence"] for v in registry["verifications"] if v["increment"] == registry["active_increment"])
        pin = active(registry)["pack"]
        if pin["path"]:
            manifest, _ = load_pack(root, pin)
            paths.add(pin["path"] + "/manifest.json")
            paths.update(pin["path"] + "/" + r["path"] for r in manifest["templates"])
    state = load_state(resolve_state_path(root))
    for item in state["deliverables"] + state["gates"]:
        paths.update(e for e in item.get("evidence", []) if ":" not in e)
        paths.update(r["evidence"] for r in item.get("reviews", []) if r.get("evidence") and ":" not in r["evidence"])
    def run(args: list[str]) -> bytes:
        try:
            completed = subprocess.run(args, cwd=root, capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RequirementError("BASELINE_SOURCE: repository client unavailable or timed out") from exc
        if completed.returncode:
            raise RequirementError("BASELINE_SOURCE: cannot resolve repository source")
        return completed.stdout
    def equal(relative: str, data: bytes) -> bool:
        local = safe_path(root, relative).read_bytes()
        if relative == ".ipd/agent_runtime.yaml":
            import yaml
            def authority(content: bytes) -> dict:
                runtime = yaml.safe_load(content)
                return {"active_claims": runtime["active_claims"], "events": [e for e in runtime["events"]
                    if e["action"] not in {"verify", "refresh", "lifecycle_complete"}]}
            return authority(data) == authority(local)
        return data.replace(b"\r\n", b"\n") == local.replace(b"\r\n", b"\n")
    # No fetch/update/commit: repository access here is strictly read-only.
    if source["backend"] == "git":
        if not __import__("re").fullmatch(r"[0-9a-f]{40,64}", source["revision"]):
            raise RequirementError("BASELINE_SOURCE: use a full immutable Git commit ID")
        run(["git", "cat-file", "-e", source["revision"] + "^{commit}"])
        url = run(["git", "config", "--get", "remote.origin.url"]).decode().strip()
        if url != source["repository"]:
            raise RequirementError("BASELINE_SOURCE: repository URL differs")
        # The accepted source must contain the exact governance inputs. The
        # snapshot itself is subsequently committed through normal Git flow.
        for relative in sorted(paths):
            prefix = "" if source["path"] == "." else source["path"].strip("/") + "/"
            data = run(["git", "show", source["revision"] + ":" + prefix + relative])
            if not equal(relative, data):
                raise RequirementError("BASELINE_SOURCE: working facts differ from source commit")
    elif source["backend"] == "svn":
        if not source["revision"].isdigit():
            raise RequirementError("BASELINE_SOURCE: use a numeric SVN revision")
        for relative in sorted(paths):
            prefix = "" if source["path"] == "." else source["path"] + "/"
            url = source["repository"].rstrip("/") + "/" + prefix + relative
            data = run(["svn", "cat", "--non-interactive", "-r", source["revision"], url + "@" + source["revision"]])
            if not equal(relative, data):
                raise RequirementError("BASELINE_SOURCE: working facts differ from SVN source")
    else:
        raise RequirementError("BASELINE_SOURCE: supported backends are Git and SVN")


def _create_instance(root: Path, registry: dict, state: dict, runtime: dict, item: dict,
                     files: dict, *, supersedes: str | None = None) -> None:
    increment = active(registry)
    allowed = {"id", "key", "requirements", "owner", "document_type", "path", "title", "scope", "locale"}
    if set(item) != allowed:
        raise RequirementError("INSTANCE_CONTRACT: missing or unknown instance fields")
    path = safe_path(root, item["path"])
    if not item["path"].startswith("docs/") or path.exists():
        raise RequirementError("INSTANCE_PATH: require a new path under docs/")
    from .stage_organization import NEW_TYPES
    if item["document_type"] in NEW_TYPES and "organization" not in registry:
        raise RequirementError("ORGANIZATION_REQUIRED: adopt stage organization before creating this type")
    if not item["requirements"] and not ("organization" in registry and item["document_type"] in {"stage_index", "tr1_requirements_feasibility"}):
        raise RequirementError("INSTANCE_SCOPE: only stage indexes or initial TR1 analysis can omit requirement references")
    _owner(root, state, item["path"], item["owner"])
    lease = runtime["active_claims"].get(item["owner"])
    if not lease or _parse_time(lease["expires_at"]) <= utc_now() or state["project"]["workflow_step"] != "work":
        raise RequirementError("INSTANCE_CLAIM: an unexpired Owner Claim is required")
    require_published(root, registry, increment["pack"])
    record, text = template(root, increment["pack"], item["document_type"], item["locale"])
    import re
    if not re.fullmatch(record["filename_pattern"], path.name):
        raise RequirementError("TEMPLATE_NAMING: filename does not follow the pinned QA naming rule")
    kinds = {r["kind"] for r in registry["requirements"] if ref(r) in item["requirements"]}
    if not kinds <= set(record["requirement_kinds"]) or state["project"]["phase"] not in record["phases"]:
        raise RequirementError("TEMPLATE_APPLICABILITY: template does not apply to this requirement or Phase")
    if not set(item["requirements"]) <= {s["requirement"] for s in increment["scope"]}:
        raise RequirementError("INSTANCE_SCOPE: all requirements must be in the active scope")
    item.update(increment=increment["id"], pack=deepcopy(increment["pack"]),
                template_id=record["id"], template_version=record["version"], template_sha256=record["sha256"])
    if supersedes:
        item["supersedes"] = supersedes
    for existing in live_instances(registry):
        if existing["id"] == supersedes:
            continue
        if existing["increment"] == item["increment"] and existing["key"] == item["key"] and existing["document_type"] == item["document_type"] and set(existing["requirements"]) & set(item["requirements"]):
            raise RequirementError("INSTANCE_KEY: duplicate requirement/type/key")
    registry["instances"].append(item)
    files[item["path"]] = instantiate(text, item)


def _simulate(root: Path, request: dict) -> tuple[dict, dict, dict, dict[str, str]]:
    registry = read_registry(root)
    state = load_state(resolve_state_path(root))
    from .validation import validate_state
    state_issues = validate_state(state)
    if state_issues:
        raise RequirementError("REQUIREMENT_STATE: invalid core state: " + str(state_issues[0]))
    runtime = load_runtime(root)
    files: dict[str, str] = {}
    op = request.get("operation")
    from .stage_organization import CLAIM_EDITS, authorize_claim_edit
    stage_edit = (registry is not None and 'organization' in registry and op in CLAIM_EDITS
                  and bool(runtime['active_claims']) and state['project']['workflow_step']=='work')
    claim_operation = op in {"instantiate", "replace_templates", "revise_instance"} or (
        op == "stage_unit" and runtime["active_claims"] and state["project"]["workflow_step"] == "work") or (
        op in {"verification", "draft_templates", "review_templates", "publish_templates"}
        and runtime["active_claims"] and state["project"]["workflow_step"] == "work") or stage_edit
    if not claim_operation and (runtime["active_claims"] or state["project"]["workflow_step"] in {"work", "close", "review"}):
        raise RequirementError("GOVERNANCE_ACTIVE: finish the active Claim or Review first")
    if op == "enable":
        _fields(request, {"increment", "product_version"})
        if registry is not None:
            raise RequirementError("REQUIREMENTS_ENABLED: model is already enabled")
        validate(request["increment"], ID)
        manifest, _ = load_pack(root)
        pin = {k: manifest[k] for k in ("id", "version", "layer")}
        pin.update(path="", sha256=digest(manifest))
        snapshot = _snapshot(root, state, runtime, None)
        relative = ".ipd/requirement_history/migration.json"
        files[relative] = snapshot
        process = load_state(root / ".ipd/tailored_process.yaml")
        stages = {"concept": "TR1", "plan": "TR2", "develop": "TR3", "qualify": "TR4",
                  "launch": "TR4", "lifecycle": "TR4"}
        registry = {"schema_version": "1.0", "contract": "0.5.3", "product_state": "active",
            "template_pack": pin, "stage_map": {g["id"]: stages[g["phase"]] for g in process["gates"]},
            "active_increment": request["increment"], "requirements": [], "increments": [{
                "id": request["increment"], "product_version": request["product_version"],
                "base_baseline": None, "scope": [], "status": "active", "pack": pin}],
            "instances": [], "obligations": [], "links": [], "verifications": [],
            "baselines": [], "changes": [], "events": [],
            "migration": {"path": relative, "sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
                          "unmapped": [d["id"] for d in state["deliverables"]]}}
    elif registry is None:
        raise RequirementError("REQUIREMENTS_DISABLED: explicitly enable the model first")
    elif registry["product_state"] == "retired":
        raise RequirementError("PRODUCT_RETIRED: product is read-only")
    elif op == "adopt_organization":
        _fields(request, {"required_stages"})
        active(registry)
        if any(g["status"] == "approved" for g in state["gates"]) or any(d["status"] == "accepted" for d in state["deliverables"]):
            raise RequirementError("STAGE_GOVERNED: adopt in a new increment before Gate approvals")
        from .stage_organization import adopt
        snapshot = _snapshot(root, state, runtime, registry)
        relative = ".ipd/requirement_history/organization-" + request["request_id"] + ".json"
        files[relative] = snapshot
        adopt(registry, request["required_stages"], {"path": relative, "sha256": hashlib.sha256(snapshot.encode()).hexdigest()})
    elif op == "stage_plan":
        _fields(request, {"stage", "owner", "locale"})
        from .stage_organization import plan_stage
        plan_stage(registry, state, request["stage"], request["owner"], request["locale"])
    elif op == "stage_unit":
        _fields(request, {"unit"})
        from .stage_organization import update_unit
        unit = deepcopy(request["unit"])
        validate(unit, STAGE_UNIT)
        if claim_operation:
            lease = runtime["active_claims"].get(unit.get("owner"))
            if not lease or _parse_time(lease["expires_at"]) <= utc_now():
                raise RequirementError("INSTANCE_CLAIM: hold the unit Owner Claim")
        update_unit(root, registry, state, unit, _owner)
    elif op in {"requirement", "numbered_requirement"}:
        _fields(request, {"requirement"})
        active(registry)
        value = deepcopy(request["requirement"])
        if not isinstance(value, dict):
            raise RequirementError("REQUEST_CONTRACT: requirement must be an object")
        validate({**value, "id": value.get("id", "pending")} if op == "numbered_requirement" else value, REQUIREMENT)
        if stage_edit:
            authorize_claim_edit(registry,state,runtime,op,request)
        if "organization" in registry:
            from .stage_organization import assign_code
            value = assign_code(registry, value, allocate_id=op == "numbered_requirement", enforce_new=True)
        elif op == "numbered_requirement":
            raise RequirementError("ORGANIZATION_REQUIRED: adopt before allocating numbers")
        validate(value, REQUIREMENT)
        prior = [r for r in registry["requirements"] if r["id"] == value["id"]]
        if value["version"] != max([r["version"] for r in prior], default=0) + 1:
            raise RequirementError("REQUIREMENT_VERSION: versions must append consecutively")
        if prior:
            old = ref(max(prior, key=lambda r: r["version"]))
            targets = impact(registry, old)
            targets.extend("gate:" + g["id"] for g in state["gates"])
            registry["changes"].append({"request_id": request["request_id"], "old": old,
                "new": ref(value), "affected": sorted(set(targets)), "assessments": []})
        registry["requirements"].append(deepcopy(value))
    elif op == "scope":
        _fields(request, {"scope"})
        validate(request["scope"], SCOPE)
        if stage_edit:
            authorize_claim_edit(registry,state,runtime,op,request)
        increment = active(registry)
        if any(g["status"] == "approved" for g in state["gates"]):
            old = {(s["requirement"], c) for s in increment["scope"] for c in s["criteria"]}
            new = {(s["requirement"], c) for s in request["scope"] for c in s["criteria"]}
            if not old <= new:
                raise RequirementError("SCOPE_GOVERNED: accepted scope cannot be silently reduced")
        increment["scope"] = deepcopy(request["scope"])
    elif op == "decomposition":
        _fields(request, {"requirement", "status"})
        value = next((r for r in registry["requirements"] if ref(r) == request["requirement"]), None)
        if not value or value["kind"] == "AR" or request["status"] not in {"open", "complete"}:
            raise RequirementError("DECOMPOSITION_INVALID: use an existing IR/SR and an explicit status")
        if stage_edit:
            authorize_claim_edit(registry,state,runtime,op,request)
        value["decomposition"] = request["status"]
    elif op == "stage_map":
        _fields(request, {"stage_map"})
        if any(g["status"] == "approved" for g in state["gates"]):
            raise RequirementError("STAGE_GOVERNED: cannot reinterpret an approved Gate")
        if set(request["stage_map"]) != {g["id"] for g in state["gates"]}:
            raise RequirementError("STAGE_MAP: map every canonical Gate explicitly")
        registry["stage_map"] = deepcopy(request["stage_map"])
    elif op == "obligation":
        _fields(request, {"obligation"})
        item = {**request["obligation"], "increment": active(registry)["id"]}
        validate(item, OBLIGATION)
        if item["requirement"] not in {s["requirement"] for s in active(registry)["scope"]} or item["owner"] not in {d["id"] for d in state["deliverables"]}:
            raise RequirementError("INSTANCE_SCOPE: obligation needs a scoped requirement and an existing Owner")
        if len(item["keys"]) != len(set(item["keys"])):
            raise RequirementError("INSTANCE_KEY: duplicate obligation key")
        registry["obligations"].append(item)
    elif op == "link":
        _fields(request, {"link"})
        item = {**request["link"], "increment": active(registry)["id"]}
        validate(item, LINK)
        if stage_edit:
            authorize_claim_edit(registry,state,runtime,op,request)
        targets = {i["id"] for i in state["deliverables"]}
        if item["relation"] == "shared_constraint":
            targets = {ref(r) for r in registry["requirements"]}
        if item["target"] not in targets or item in registry["links"]:
            raise RequirementError("LINK_ENDPOINT: invalid or duplicate typed relation")
        registry["links"].append(item)
        registry["migration"]["unmapped"] = [d for d in registry["migration"]["unmapped"] if d != item["target"]]
    elif op == "verification":
        _fields(request, {"verification"})
        item = {**request["verification"], "increment": active(registry)["id"]}
        if any(key in item for key in ("source_baseline", "source_result", "context_sha256")):
            raise RequirementError("VERIFICATION_SOURCE: historical source and context fields are managed by the Skill")
        item.update(source_baseline=None, source_result=None)
        evidence = safe_path(root, item.get("evidence", ""))
        item["sha256"] = file_hash(evidence)
        validate(item, VERIFICATION)
        if item["requirement"] not in {s["requirement"] for s in active(registry)["scope"]}:
            raise RequirementError("VERIFICATION_SCOPE: result is outside the current scope")
        item["context_sha256"] = verification_context(root, registry, item["requirement"])
        registry["verifications"].append(item)
    elif op == "reuse_verification":
        _fields(request, {"baseline", "result", "id"})
        increment = active(registry)
        baseline = next((b for b in registry["baselines"] if b["id"] == request["baseline"]), None)
        if not baseline or file_hash(safe_path(root, baseline["path"])) != baseline["sha256"]:
            raise RequirementError("REUSE_BASELINE: immutable baseline cannot be resolved")
        snapshot = json.loads(safe_path(root, baseline["path"]).read_text(encoding="utf-8"))
        result = next((r for r in snapshot["registry"]["verifications"] if r["id"] == request["result"]), None)
        if not result or result["result"] != "passed" or result["requirement"] not in {s["requirement"] for s in increment["scope"]}:
            raise RequirementError("REUSE_VERSION: only an unchanged scoped requirement with a passed result can be reused")
        if result.get("context_sha256") != verification_context(root, registry, result["requirement"]):
            raise RequirementError("REUSE_CONTEXT: historical inputs or re-verification context differ")
        encoded = snapshot["files"].get(result["evidence"])
        if not encoded:
            raise RequirementError("REUSE_EVIDENCE: snapshot has no resolvable evidence")
        content = base64.b64decode(encoded, validate=True)
        if hashlib.sha256(content).hexdigest() != result["sha256"]:
            raise RequirementError("REUSE_EVIDENCE: content digest differs")
        # Materialized UTF-8 evidence remains portable and is covered by the
        # transaction. Binary evidence is retained in the baseline snapshot.
        relative = ".ipd/requirement_history/reuse-" + request["id"] + ".txt"
        files[relative] = content.decode("utf-8")
        item = {**result, "id": request["id"], "increment": increment["id"],
                "evidence": relative, "source_baseline": baseline["id"], "source_result": result["id"]}
        registry["verifications"].append(item)
    elif op == "assess":
        _fields(request, {"change", "assessments"})
        validate(request["assessments"], CHANGE["properties"]["assessments"])
        change = next((c for c in registry["changes"] if c["request_id"] == request["change"]), None)
        if not change or len(request["assessments"]) != len(change["affected"]) or {a["target"] for a in request["assessments"]} != set(change["affected"]):
            raise RequirementError("IMPACT_UNKNOWN: assess every affected object explicitly")
        change["assessments"] = deepcopy(request["assessments"])
        change["assessment_revision"] = state["revision"] + 1
    elif op in {"draft_templates", "review_templates", "publish_templates"}:
        extra = {"path"} if op == "draft_templates" else {"source"}
        if op == "review_templates":
            extra.add("decision")
        _fields(request, {"id", "actor", "actor_type"} | extra)
        relative, text = transition(root, registry, request, state["revision"] + 1)
        files[relative] = text
    elif op == "pin_templates":
        _fields(request, {"path"})
        manifest, _ = load_pack(root, None if request["path"] == "" else {"path": request["path"]})
        # External packs are loaded and validated independently before pinning.
        pin = {k: manifest[k] for k in ("id", "version", "layer")}
        pin.update(path=request["path"], sha256=digest(manifest))
        require_published(root, registry, pin)
        for prior in [registry["template_pack"], *[i["pack"] for i in registry["increments"]]]:
            if (prior["id"], prior["version"]) == (pin["id"], pin["version"]) and prior["sha256"] != pin["sha256"]:
                raise RequirementError("TEMPLATE_TAMPERED: a published pack version is immutable")
        if any(i["increment"] == registry["active_increment"] for i in registry["instances"]):
            raise RequirementError("TEMPLATE_IN_USE: select a new pack in a new increment")
        registry["template_pack"] = pin
        active(registry)["pack"] = pin
    elif op == "replace_templates":
        _fields(request, {"path", "replacements"})
        from .template_publications import pack_pin
        increment = active(registry)
        pin = pack_pin(root, request["path"])
        require_published(root, registry, pin)
        current = [i for i in live_instances(registry) if i["increment"] == increment["id"]]
        replacements = request["replacements"]
        if not isinstance(replacements, list) or not replacements or any(not isinstance(r, dict) or set(r) != {"old", "instance"} for r in replacements):
            raise RequirementError("INSTANCE_REPLACEMENT: explicit old IDs and new instances required")
        if len({r["old"] for r in replacements}) != len(replacements) or {r["old"] for r in replacements} != {i["id"] for i in current}:
            raise RequirementError("INSTANCE_REPLACEMENT: replace every active instance atomically")
        owners = {i["owner"] for i in current}
        if len(owners) != 1:
            raise RequirementError("INSTANCE_REPLACEMENT: multiple Owners require a new increment")
        registry["template_pack"] = pin
        increment["pack"] = pin
        for replacement in replacements:
            prior = next(i for i in current if i["id"] == replacement["old"])
            item = deepcopy(replacement["instance"])
            if any(item.get(k) != prior[k] for k in ("owner", "key", "document_type", "requirements", "locale")):
                raise RequirementError("INSTANCE_REPLACEMENT: preserve Owner, key, type, requirements and locale")
            _create_instance(root, registry, state, runtime, item, files, supersedes=prior["id"])
    elif op == "instantiate":
        _fields(request, {"instance"})
        _create_instance(root, registry, state, runtime, deepcopy(request["instance"]), files)
    elif op == "revise_instance":
        _fields(request, {"old", "instance"})
        from .stage_organization import organization
        organization(registry)
        old = next((i for i in live_instances(registry) if i["id"] == request["old"] and i["increment"] == registry["active_increment"]), None)
        item = deepcopy(request["instance"])
        if not old or any(item.get(k) != old[k] for k in ("owner", "key", "document_type", "locale")):
            raise RequirementError("INSTANCE_REPLACEMENT: preserve current Owner, key, type and locale")
        _create_instance(root, registry, state, runtime, item, files, supersedes=old["id"])
    elif op == "baseline":
        _fields(request, {"id", "source"})
        validate(request["id"], ID)
        increment = active(registry)
        issues = readiness(root, registry, state, stage="TR4", all_documents=True)
        issues.extend(i["code"] for i in validation_issues(root, state))
        if issues or not state["gates"] or any(g["status"] != "approved" for g in state["gates"]):
            raise RequirementError("BASELINE_NOT_READY: " + ", ".join(issues or ["unapproved Gates"]))
        if state["project"]["phase"] != "lifecycle" or state["project"]["workflow_step"] != "verify":
            raise RequirementError("BASELINE_NOT_READY: finish the complete governed lifecycle")
        verification = runtime.get("last_verification") or {}
        from .project import verification_input_fingerprint
        if verification.get("status") != "passed" or verification.get("input_fingerprint") != verification_input_fingerprint(root, state=state, runtime=runtime):
            raise RequirementError("BASELINE_VERIFICATION: current successful Verify required")
        _accepted_source(root, request["source"])
        relative = ".ipd/requirement_history/" + request["id"] + ".json"
        files[relative] = _snapshot(root, state, runtime, registry)
        registry["baselines"].append({"id": request["id"], "increment": increment["id"], "path": relative,
            "sha256": hashlib.sha256(files[relative].encode()).hexdigest(), "source": request["source"]})
        increment["status"] = "accepted"
        registry["active_increment"] = None
    elif op == "begin":
        _fields(request, {"increment", "product_version", "base_baseline", "scope"})
        if registry["active_increment"]:
            raise RequirementError("INCREMENT_CONFLICT: finish the active increment first")
        baseline = next((b for b in registry["baselines"] if b["id"] == request["base_baseline"]), None)
        if baseline is None or baseline != registry["baselines"][-1]:
            raise RequirementError("INCREMENT_BASE: explicitly use the latest accepted baseline")
        from .project import sync_state_with_process
        process = load_state(root / ".ipd/tailored_process.yaml")
        initial = create_initial_state(state["project"]["name"], state["project"]["task_types"])
        initial["revision"] = state["revision"]
        state = sync_state_with_process(initial, process)
        runtime = create_runtime_state()
        registry["active_increment"] = request["increment"]
        registry["increments"].append({"id": request["increment"], "product_version": request["product_version"],
            "base_baseline": baseline["id"], "scope": deepcopy(request["scope"]),
            "status": "active", "pack": deepcopy(registry["template_pack"])})
    elif op == "retire":
        _fields(request, set())
        if registry["active_increment"]:
            raise RequirementError("PRODUCT_ACTIVE: finish the increment before retirement")
        registry["product_state"] = "retired"
    else:
        raise RequirementError("REQUEST_OPERATION: unknown operation")
    validate(registry)
    check_relations(registry)
    for relative in files:
        if safe_path(root, relative).exists():
            raise RequirementError("OUTPUT_EXISTS: immutable output already exists")
    state["revision"] += 1
    if not claim_operation:
        state["project"]["workflow_step"] = "refresh"
    return registry, state, runtime, files


def preview(root: Path, request: dict) -> dict:
    root = root.resolve()
    base = input_snapshot(root)
    registry, state, _, files = _simulate(root, request)
    result = {"schema_version": "1.0", "command": "requirements", "request": request,
            "base_revision": load_state(resolve_state_path(root))["revision"], "base_sha256": digest(base),
            "result_sha256": digest(registry), "result_revision": state["revision"],
            "outputs": {p: hashlib.sha256(t.encode()).hexdigest() for p, t in files.items()},
            "impact": next((c for c in reversed(registry["changes"]) if c["request_id"] == request["request_id"]), None)
                      if request["operation"] in {"requirement", "numbered_requirement"} else None,
            "unmapped": registry["migration"]["unmapped"],
            "documents": files if request["operation"] in {"instantiate", "revise_instance"} else {}}
    if "organization" in registry:
        from .stage_organization import blueprints
        result["numbering"] = registry["organization"]["codes"]
        result["stage_plan"] = {"instances": blueprints(registry), "binding_issues": []}
        for item in result["stage_plan"]["instances"]:
            try:
                _owner(root, state, item["path"], item["owner"])
                if safe_path(root, item["path"]).exists():
                    result["stage_plan"]["binding_issues"].append("OUTPUT_EXISTS:" + item["path"])
            except (ValueError, OSError) as exc:
                result["stage_plan"]["binding_issues"].append(str(exc) + ":" + item["path"])
    return result


def apply_plan(root: Path, plan: dict, *, actor: str, authorized: bool) -> dict:
    if not authorized or not actor.strip():
        raise RequirementError("AUTHORIZATION_REQUIRED: explicit human authorization and actor required")
    root = root.resolve()
    request = plan.get("request", {})
    # The outer mutex must include preflight. The inner journal declares paths
    # only after recomputing the complete output set from validated input.
    from .transaction import project_access_guard
    with project_access_guard(root):
        existing = read_registry(root)
        prior = next((e for e in (existing or {}).get("events", []) if e["request_id"] == request.get("request_id")), None)
        if prior:
            if prior["plan_sha256"] != digest(plan):
                raise RequirementError("REQUEST_REPLAY_CONFLICT: request ID already used with different input")
            for relative, expected in plan["outputs"].items():
                if file_hash(safe_path(root, relative)) != expected:
                    raise RequirementError("REQUEST_REPLAY_CONFLICT: previous output changed")
            return {"status": "already_applied", "revision": prior["result_revision"]}
        current = preview(root, request)
        if current != plan:
            raise RequirementError("PLAN_STALE: preview no longer matches project inputs")
        registry, state, runtime, files = _simulate(root, request)
        operation = request["operation"]
        from .stage_organization import CLAIM_EDITS
        if operation in CLAIM_EDITS and runtime['active_claims'] and next(iter(runtime['active_claims'].values()))['actor'] != actor:
            raise RequirementError('INSTANCE_CLAIM: actor does not hold the stage Owner Claim')
        if operation in {"draft_templates", "review_templates", "publish_templates"} and request["actor"] != actor:
            raise RequirementError("TEMPLATE_ACTOR: applying actor must match the human declaration")
        if request["operation"] in {"instantiate", "revise_instance"} and runtime["active_claims"][request["instance"]["owner"]]["actor"] != actor:
            raise RequirementError("INSTANCE_CLAIM: actor does not hold the Owner Claim")
        if operation == "stage_unit" and runtime["active_claims"] and runtime["active_claims"].get(request["unit"]["owner"], {}).get("actor") != actor:
            raise RequirementError("INSTANCE_CLAIM: actor does not hold the unit Owner Claim")
        if operation == "replace_templates" and any(runtime["active_claims"][r["instance"]["owner"]]["actor"] != actor for r in request["replacements"]):
            raise RequirementError("INSTANCE_CLAIM: actor does not hold the Owner Claim")
        if operation == "verification" and runtime["active_claims"] and actor not in {c["actor"] for c in runtime["active_claims"].values()}:
            raise RequirementError("INSTANCE_CLAIM: verification actor must hold the active Claim")
        context_registry = registry
        if operation == "baseline":
            context_registry = deepcopy(registry)
            context_registry["active_increment"] = registry["baselines"][-1]["increment"]
        runtime = bind_increment(runtime, context_registry)
        registry["events"].append({"request_id": request["request_id"], "operation": request["operation"],
            "reason": request["reason"], "actor": actor, "base_revision": plan["base_revision"],
            "request_sha256": digest(request), "plan_sha256": digest(plan), "result_revision": state["revision"],
            "increment_context": deepcopy(runtime["increment_context"])})
        runtime = record_event(runtime, "requirements_" + request["operation"], details={
            "increment": runtime["increment_context"]["increment"], "request_id": request["request_id"],
            "state_revision": state["revision"], "actor": actor, "authorized": True})
        extras = [registry_path(root), *[safe_path(root, p) for p in files]]
        with project_mutation_guard(root, extra_files=extras):
            for relative, text in files.items():
                path = safe_path(root, relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8", newline="\n") as handle:
                    handle.write(text)
            write_state(registry_path(root), registry)
            write_state(resolve_state_path(root), state)
            save_runtime(root, runtime)
        return {"status": "applied", "revision": state["revision"], "outputs": list(files)}


def readiness(root: Path, registry: dict, state: dict, *, stage: str,
              owner: str | None = None, all_documents: bool = False, phase: str | None = None) -> list[str]:
    increment = active(registry)
    requirements = {ref(r): r for r in registry["requirements"]}
    scope = {s["requirement"]: s["criteria"] for s in increment["scope"]}
    issues = []
    level = int(stage[-1])
    if not scope and owner is None:
        issues.append("REQUIREMENT_SCOPE_EMPTY")
    instances = [i for i in live_instances(registry) if i["increment"] == increment["id"]]
    if instances:
        try:
            require_published(root, registry, increment["pack"])
        except RequirementError as exc:
            issues.append(str(exc))
    phase_order = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
    cutoff = phase_order.index(phase or state["project"]["phase"])
    due_owners = {d["id"] for d in state["deliverables"] if phase_order.index(d["phase"]) <= cutoff}
    if owner is None and not all_documents:
        instances = [i for i in instances if i["owner"] in due_owners]
    if owner is not None:
        instances = [i for i in instances if i["owner"] == owner]
    from .documents import lint_instances
    document_issues = lint_instances(root, instances, requirements)
    for item in instances:
        try:
            _owner(root, state, item["path"], item["owner"])
            issues.extend(i + ":" + item["id"] for i in document_issues[item["id"]])
        except (ValueError, OSError) as exc:
            issues.append("DOCUMENT_INVALID:" + item["id"] + ":" + str(exc))
    for obligation in registry["obligations"]:
        if obligation["increment"] != increment["id"] or (owner is not None and obligation["owner"] != owner):
            continue
        if owner is None and not all_documents and obligation["owner"] not in due_owners:
            continue
        actual = [i["key"] for i in instances if obligation["requirement"] in i["requirements"] and i["document_type"] == obligation["document_type"] and i["owner"] == obligation["owner"]]
        if sorted(actual) != sorted(obligation["keys"]):
            issues.append("DOCUMENT_CARDINALITY:" + obligation["id"])
    if owner is not None and not all_documents:
        from .stage_organization import readiness as stage_readiness
        issues.extend(stage_readiness(root, registry, state, stage=stage, owner=owner, phase=phase, documents=document_issues))
        return sorted(set(issues))
    for reference, criteria in scope.items():
        r = requirements[reference]
        due = {"IR": 1, "SR": 2, "AR": 3}[r["kind"]]
        if due > level:
            continue
        if r["maturity"] != "defined":
            issues.append("REQUIREMENT_DRAFT:" + reference)
        if r["kind"] != "AR" and due < level:
            children = [ref(child) for child in requirements.values() if child["parent"] == reference and ref(child) in scope]
            if r["decomposition"] != "complete" or not children:
                issues.append("DECOMPOSITION_OPEN:" + reference)
        if due > 1 and not r["derived"] and r["parent"] not in scope:
            issues.append("PARENT_OUT_OF_SCOPE:" + reference)
        if level >= 3 and not any(l["increment"] == increment["id"] and l["requirement"] == reference and l["relation"] in {"allocated_to", "satisfied_by"} for l in registry["links"]):
            issues.append("IMPLEMENTATION_UNLINKED:" + reference)
        if level == 4:
            for criterion in criteria:
                results = [v for v in registry["verifications"] if v["increment"] == increment["id"] and v["requirement"] == reference and v["criterion"] == criterion]
                result = results[-1] if results else None
                if not result or result["result"] != "passed":
                    issues.append("VERIFICATION_NOT_PASSED:" + reference + ":" + criterion)
                elif issue := verification_issue(root, registry, result):
                    issues.append(issue)
    for change in active_changes(registry):
        if ({a["target"] for a in change["assessments"]} != set(change["affected"]) or any(a["action"] == "defer" for a in change["assessments"])):
            issues.append("IMPACT_UNKNOWN:" + change["request_id"])
    from .stage_organization import readiness as stage_readiness
    issues.extend(stage_readiness(root, registry, state, stage=stage, owner=owner, phase=phase, documents=document_issues))
    return sorted(set(issues))


def enforce(root: Path, state: dict, subject: str, kind: str) -> None:
    registry = read_registry(root)
    if not registry:
        return
    input_snapshot(root, registry)
    if not registry["active_increment"]:
        raise RequirementError("INCREMENT_REQUIRED: start a new increment before writing core facts")
    stage = registry["stage_map"].get(subject, "TR4")
    phase = next((g["phase"] for g in state["gates"] if g["id"] == subject), None)
    issues = readiness(root, registry, state, stage=stage, owner=subject if kind == "deliverable" else None, phase=phase)
    if issues:
        raise RequirementError("REQUIREMENT_NOT_READY: " + ", ".join(issues))


def assert_writable(root: Path) -> None:
    registry = read_registry(root)
    if registry:
        input_snapshot(root, registry)
        if not registry["active_increment"] or registry["product_state"] != "active":
            raise RequirementError("INCREMENT_REQUIRED: start an increment before changing core facts")


def projection(root: Path) -> dict | None:
    registry = read_registry(root)
    if not registry:
        return None
    result = deepcopy(registry)
    state = load_state(resolve_state_path(root))
    result["diagnostics"] = readiness(root, registry, state, stage="TR4", all_documents=True) if registry["active_increment"] else []
    result["input_sha256"] = digest(source_snapshot(root, registry))
    result["coverage"] = []
    result["verification_diagnostics"] = {}
    accepted_increments = {i["id"] for i in registry["increments"] if i["status"] == "accepted"}
    for requirement in registry["requirements"]:
        reference = ref(requirement)
        criteria = {c["id"] for c in requirement["acceptance"]}
        accepted = set()
        for increment in registry["increments"]:
            if increment["id"] not in accepted_increments:
                continue
            scoped = {c for s in increment["scope"] if s["requirement"] == reference for c in s["criteria"]}
            latest = {v["criterion"]: v for v in registry["verifications"]
                      if v["increment"] == increment["id"] and v["requirement"] == reference}
            accepted.update(c for c in scoped if c in latest and latest[c]["result"] == "passed")
        latest = {v["criterion"]: v for v in registry["verifications"]
                  if v["increment"] == registry["active_increment"] and v["requirement"] == reference}
        effective = {}
        for criterion, outcome in latest.items():
            issue = verification_issue(root, registry, outcome)
            if issue:
                result["verification_diagnostics"][outcome["id"]] = issue
            effective[criterion] = "unknown" if issue else outcome["result"]
        implementation = [l["target"] for l in registry["links"] if l["increment"] == registry["active_increment"]
                          and l["requirement"] == reference and l["relation"] == "satisfied_by"]
        accepted_outputs = {d["id"] for d in state["deliverables"] if d["status"] == "accepted"}
        result["coverage"].append({"requirement": reference, "definition": requirement["maturity"],
            "decomposition": requirement["decomposition"], "accepted_criteria": sorted(accepted),
            "all_criteria": sorted(criteria), "fulfillment": "full" if accepted == criteria else "partial" if accepted else "none",
            "implementation": "accepted" if implementation and set(implementation) <= accepted_outputs else "unknown",
            "verification": {status: sum(v == status for v in effective.values()) for status in ("passed", "failed", "skipped", "unknown")},
            "unverified_criteria": sorted(criteria - set(latest))})
    if "organization" in registry:
        from .stage_flow import projection as flow_projection
        result["flow"] = flow_projection(root, registry, state)
    return result


def validation_issues(root: Path, state: dict) -> list[dict]:
    try:
        registry = read_registry(root)
        if not registry:
            return []
        input_snapshot(root, registry)
        messages = []
        if registry["active_increment"]:
            for item in state["deliverables"]:
                if item["status"] in {"ready_for_review", "in_review", "accepted"}:
                    messages.extend(readiness(root, registry, state, stage="TR4", owner=item["id"]))
                    if item["status"] == "accepted":
                        approval = next((event for event in reversed(load_runtime(root)["events"])
                                         if event.get("action") == "approve" and event.get("subject") == item["id"]), {})
                        if approval.get("requirements_sha256") and approval["requirements_sha256"] != decision_manifest(root, state, item["id"], "deliverable"):
                            messages.append("DELIVERABLE_REQUIREMENTS_CHANGED:" + item["id"])
            for gate in state["gates"]:
                if gate["status"] == "approved":
                    approval = next((event for event in reversed(load_runtime(root)["events"])
                                     if event.get("action") == "approve" and event.get("subject") == gate["id"]), {})
                    if approval.get("requirements_sha256"):
                        messages.extend(readiness(root, registry, state, stage=registry["stage_map"].get(gate["id"], "TR4"), phase=gate["phase"]))
                        if approval["requirements_sha256"] != decision_manifest(root, state, gate["id"], "gate"):
                            messages.append("GATE_REQUIREMENTS_CHANGED:" + gate["id"])
        return [{"path": "$.requirements", "code": m.split(":")[0], "message": m} for m in sorted(set(messages))]
    except (ValueError, OSError) as exc:
        return [{"path": "$.requirements", "code": "REQUIREMENT_INVALID", "message": str(exc)}]


def decision_manifest(root: Path, state: dict, subject: str, kind: str) -> str | None:
    registry = read_registry(root)
    if not registry or not registry["active_increment"]:
        return None
    increment = active(registry)
    scoped = {s["requirement"]: s for s in increment["scope"]}
    if kind == "gate":
        level = int(registry["stage_map"].get(subject, "TR4")[-1])
    else:
        phase = next(d["phase"] for d in state["deliverables"] if d["id"] == subject)
        level = {"concept": 1, "plan": 2, "develop": 3}.get(phase, 4)
    instances = [i for i in live_instances(registry) if i["increment"] == increment["id"] and (kind == "gate" or i["owner"] == subject)]
    if kind == "gate":
        phase_order = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
        gate_phase = next(g["phase"] for g in state["gates"] if g["id"] == subject)
        owners = {d["id"] for d in state["deliverables"] if phase_order.index(d["phase"]) <= phase_order.index(gate_phase)}
        instances = [i for i in instances if i["owner"] in owners]
    else:
        owners = {subject}
    selected = {v for i in instances for v in i["requirements"]}
    if kind == "gate":
        selected = {ref(r) for r in registry["requirements"] if ref(r) in scoped and {"IR": 1, "SR": 2, "AR": 3}[r["kind"]] <= level}
    records = []
    for requirement in registry["requirements"]:
        if ref(requirement) in selected:
            value = deepcopy(requirement)
            if {"IR": 1, "SR": 2, "AR": 3}[value["kind"]] >= level:
                value.pop("decomposition")
            records.append(value)
    results = [v for v in registry["verifications"] if v["increment"] == increment["id"] and v["requirement"] in selected] if level == 4 else []
    manifest = {"increment": increment["id"], "requirements": records,
        "scope": [s for r, s in scoped.items() if r in selected], "instances": instances,
        "obligations": [o for o in registry["obligations"] if o["increment"] == increment["id"] and o["owner"] in owners],
        "links": [l for l in registry["links"] if l["increment"] == increment["id"] and l["requirement"] in selected
                  and (level >= 3 or l["relation"] == "shared_constraint")],
        "files": {i["path"]: file_hash(safe_path(root, i["path"])) for i in instances},
        "verifications": results, "evidence": {v["evidence"]: file_hash(safe_path(root, v["evidence"])) for v in results},
        "pack": increment["pack"]}
    if "organization" in registry:
        org = registry["organization"]
        units = [u for u in org["units"] if u["increment"] == increment["id"] and u["owner"] in owners and int(u["stage"][-1]) <= level]
        from .stage_organization import referenced_paths
        manifest["organization"] = {"policy": org["policy"], "codes": [c for c in org["codes"] if c["requirement"] in selected],
            "plans": [p for p in org["plans"] if p["increment"] == increment["id"] and p["owner"] in owners and int(p["stage"][-1]) <= level],
            "units": units, "support_files": referenced_paths(root, {**registry, "organization": {**org, "units": units}})}
    return digest(manifest)

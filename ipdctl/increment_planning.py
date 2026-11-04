"""Advisory increment plans with stable identities and audited transitions."""

from __future__ import annotations

from pathlib import Path

from .documents import RequirementError, digest, safe_path
from .requirement_contract import HASH, ID, S, arr, enum, obj, validate
from .requirements import read_registry
from .state import load_state, write_state
from .transaction import project_access_guard


PATH = ".ipd/increment_plan.yaml"
STATES = enum("candidate", "merged", "linked")
OPERATIONS = {
    "add": {"id": ID, "title": S},
    "reorder": {"order": arr(ID)},
    "merge": {"ids": {**arr(ID), "minItems": 1}, "increment": ID},
    "link": {"id": ID, "increment": ID},
}
RECORD = obj({"id": ID, "title": S, "status": STATES, "increment": {"oneOf": [ID, {"type": "null"}]}})
REQUESTS = {operation: obj({"request_id": ID, "reason": S, "operation": enum(operation), **fields})
            for operation, fields in OPERATIONS.items()}
PLAN_STORE = obj({
    "schema_version": enum("1.0"), "candidates": arr(RECORD),
    "events": arr(obj({"request": {"oneOf": list(REQUESTS.values())}, "actor": S, "plan_sha256": HASH})),
})


def read(root: Path) -> dict:
    path = safe_path(root, PATH)
    if not path.exists():
        return {"schema_version": "1.0", "candidates": [], "events": []}
    data = load_state(path)
    validate(data, PLAN_STORE)
    ids = [item["id"] for item in data["candidates"]]
    if len(ids) != len(set(ids)):
        raise RequirementError("INCREMENT_PLAN_ID: duplicate candidate ID")
    for item in data["candidates"]:
        validate(item["increment"], {"type": "null"} if item["status"] == "candidate" else ID)
    requests = [event["request"]["request_id"] for event in data["events"]]
    if len(requests) != len(set(requests)):
        raise RequirementError("INCREMENT_PLAN_ID: duplicate request ID")
    return data


def display(data: dict) -> list[dict]:
    order = 0
    records = []
    for item in data["candidates"]:
        if item["status"] == "candidate":
            order += 1
        records.append({**item, "display_order": order if item["status"] == "candidate" else None})
    return records


def _prepare(root: Path, request: dict) -> tuple[dict, dict]:
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise RequirementError("INCREMENT_PLAN_OPERATION: expected add, reorder, merge or link")
    validate(request, REQUESTS[operation])
    registry = read_registry(root)
    if registry is None or registry["product_state"] != "active":
        raise RequirementError("INCREMENT_PLAN_PROJECT: an enabled, active product is required")
    data = read(root)
    base = digest({"planning": data, "requirements": registry})
    candidates = {item["id"]: item for item in data["candidates"]}
    increments = {item["id"]: item for item in registry["increments"]}
    pending = {key for key, item in candidates.items() if item["status"] == "candidate"}
    if operation == "add":
        key = request["id"]
        if key in candidates or key in increments:
            raise RequirementError("INCREMENT_PLAN_ID: ID already exists")
        data["candidates"].append({"id": key, "title": request["title"], "status": "candidate", "increment": None})
    elif operation == "reorder":
        order = request["order"]
        if len(order) != len(pending) or set(order) != pending:
            raise RequirementError("INCREMENT_PLAN_ORDER: list every pending candidate exactly once")
        ordered = iter(order)
        data["candidates"] = [candidates[next(ordered)] if item["status"] == "candidate" else item
                              for item in data["candidates"]]
    else:
        keys = request["ids"] if operation == "merge" else [request["id"]]
        target = request["increment"]
        if len(keys) != len(set(keys)) or not set(keys) <= pending or target not in increments:
            raise RequirementError("INCREMENT_PLAN_TARGET: pending candidates and an existing increment are required")
        if operation == "merge" and target != registry["active_increment"]:
            raise RequirementError("INCREMENT_PLAN_TARGET: merge into the active increment")
        if operation == "link" and any(i["increment"] == target and i["status"] == "linked" for i in candidates.values()):
            raise RequirementError("INCREMENT_PLAN_TARGET: increment already linked to a candidate")
        for key in keys:
            candidates[key].update(status="merged" if operation == "merge" else "linked", increment=target)
    plan = {"schema_version": "1.0", "command": "increment-plan", "request": request, "base_sha256": base,
            "candidates": display(data), "canonical_scope_changed": False}
    return plan, data


def preview(root: Path, request: dict) -> dict:
    return _prepare(root, request)[0]


def apply(root: Path, plan: dict, *, actor: str, authorized: bool) -> dict:
    if not authorized or not actor.strip():
        raise RequirementError("AUTHORIZATION_REQUIRED: explicit human authorization and actor required")
    request = plan.get("request", {})
    with project_access_guard(root):
        prior = next((event for event in read(root)["events"]
                      if event["request"]["request_id"] == request.get("request_id")), None)
        fingerprint = digest(plan)
        if prior:
            if prior["plan_sha256"] != fingerprint or prior["actor"] != actor:
                raise RequirementError("REQUEST_REPLAY_CONFLICT: request ID already used")
            return {"status": "already_applied"}
        current, data = _prepare(root, request)
        if current != plan:
            raise RequirementError("PLAN_STALE: preview no longer matches project inputs")
        data["events"].append({"request": request, "actor": actor, "plan_sha256": fingerprint})
        write_state(safe_path(root, PATH), data)
        return {"status": "applied", "candidates": display(data)}

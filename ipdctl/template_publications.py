"""Project-local QA declarations, immutable review and publication records.

Actors are explicit human assertions, not authenticated platform identities.
The request transaction owns creation and rollback of every record file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .documents import RequirementError, digest, load_pack, safe_path
from .requirement_contract import ID, PUBLICATION, validate


def pack_pin(root: Path, path: str) -> dict:
    manifest, _ = load_pack(root, None if path == "" else {"path": path})
    return {**{k: manifest[k] for k in ("id", "version", "layer")},
            "path": path, "sha256": digest(manifest)}


def read_record(root: Path, reference: dict) -> dict:
    path = safe_path(root, reference["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference["sha256"]:
        raise RequirementError("TEMPLATE_HISTORY_TAMPERED: missing or changed QA record")
    record = json.loads(path.read_text(encoding="utf-8"))
    validate(record, PUBLICATION)
    for key in ("id", "stage", "pack"):
        if record[key] != reference[key]:
            raise RequirementError("TEMPLATE_HISTORY_TAMPERED: QA record reference differs")
    return record


def published(root: Path, registry: dict, pin: dict) -> bool:
    records = registry.get("template_records", [])
    reviews = [r for r in records if r["stage"] == "reviewed" and r["pack"] == pin]
    if not reviews or read_record(root, reviews[-1])["decision"] != "approved":
        return False
    return any(r["stage"] == "published" and r["pack"] == pin and
               read_record(root, r)["source"] == reviews[-1]
               for r in records)


def require_published(root: Path, registry: dict, pin: dict) -> None:
    load_pack(root, pin)
    if not published(root, registry, pin):
        raise RequirementError("TEMPLATE_UNPUBLISHED: draft, human review and authorized publication required")


def transition(root: Path, registry: dict, request: dict, revision: int) -> tuple[str, str]:
    stage = {"draft_templates": "draft", "review_templates": "reviewed",
             "publish_templates": "published"}[request["operation"]]
    validate(request["id"], ID)
    if request["actor_type"] != "human" or not request["actor"].strip():
        raise RequirementError("TEMPLATE_HUMAN_REQUIRED: explicit human declaration required")
    records = registry.setdefault("template_records", [])
    if any(r["id"] == request["id"] for r in records):
        raise RequirementError("TEMPLATE_RECORD_EXISTS: immutable QA ID already used")
    parent = None
    if stage == "draft":
        pin = pack_pin(root, request["path"])
        author, reviewer, decision = request["actor"], None, "pending"
    else:
        parent = next((r for r in records if r["id"] == request["source"]), None)
        expected = "draft" if stage == "reviewed" else "reviewed"
        if not parent or parent["stage"] != expected:
            raise RequirementError("TEMPLATE_REVIEW_SOURCE: incorrect review stage")
        previous = read_record(root, parent)
        pin = previous["pack"]
        load_pack(root, pin)
        author = previous["author"]
        reviewer = request["actor"] if stage == "reviewed" else previous["reviewer"]
        if stage == "reviewed":
            decision = request["decision"]
            if decision not in {"approved", "rejected"} or reviewer == author:
                raise RequirementError("TEMPLATE_REVIEW_DECISION: independent reviewer and explicit decision required")
        else:
            decision = previous["decision"]
            if decision != "approved":
                raise RequirementError("TEMPLATE_REVIEW_REJECTED: cannot publish a rejected pack")
            # An earlier approval cannot override a subsequent rejection.
            reviews = [read_record(root, r) for r in records
                       if r["stage"] == "reviewed" and r["pack"] == pin]
            if reviews[-1]["id"] != parent["id"]:
                raise RequirementError("TEMPLATE_REVIEW_STALE: use the latest review")
    for prior in records:
        if (prior["pack"]["id"], prior["pack"]["version"]) == (pin["id"], pin["version"]) and prior["pack"]["sha256"] != pin["sha256"]:
            raise RequirementError("TEMPLATE_TAMPERED: version already declared with different content")
    record = {"schema_version": "1.0", "id": request["id"], "stage": stage,
              "pack": pin, "author": author, "reviewer": reviewer,
              "publisher": request["actor"] if stage == "published" else None,
              "actor": request["actor"], "actor_type": "human", "authorized": True,
              "identity_source": "explicit-local-declaration", "decision": decision,
              "reason": request["reason"], "result_revision": revision,
              "source": parent, "request_id": request["request_id"]}
    validate(record, PUBLICATION)
    text = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path = ".ipd/template_publications/" + request["id"] + ".json"
    records.append({"id": record["id"], "stage": stage, "pack": pin, "path": path,
                    "sha256": hashlib.sha256(text.encode()).hexdigest()})
    return path, text


def live_instances(registry: dict) -> list[dict]:
    superseded = {i["supersedes"] for i in registry["instances"] if i.get("supersedes")}
    return [i for i in registry["instances"] if i["id"] not in superseded]

"""Bind results to direct inputs and explicit re-verification obligations.

Increment IDs and result/evidence records are excluded from the semantic input
digest so an unchanged, explicitly selected historical result can be reused.
An accepted re-verification assessment contributes its monotonic revision;
copying a result from before that assessment cannot satisfy the obligation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .documents import digest, safe_path
from .template_publications import live_instances


def active_changes(registry: dict) -> list[dict]:
    increment = next(i for i in registry["increments"] if i["id"] == registry["active_increment"])
    versions = {}
    for item in increment["scope"]:
        identifier, version = item["requirement"].rsplit("@", 1)
        versions[identifier] = max(versions.get(identifier, 0), int(version))
    return [c for c in registry["changes"]
            if versions.get(c["new"].rsplit("@", 1)[0], 0) >= int(c["new"].rsplit("@", 1)[1])]


def _target_references(registry: dict, target: str) -> set[str]:
    increment = next(i for i in registry["increments"] if i["id"] == registry["active_increment"])
    scope = {s["requirement"] for s in increment["scope"]}
    records = {f"{r['id']}@{r['version']}": r for r in registry["requirements"]}
    if target in records:
        return {r for r in scope if records[r]["id"] == records[target]["id"]}
    if target.startswith("gate:"):
        stage = int(registry["stage_map"].get(target[5:], "TR4")[-1])
        return {r for r in scope if {"IR": 1, "SR": 2, "AR": 3}[records[r]["kind"]] <= stage}
    if target.startswith("instance:"):
        instance = next((i for i in registry["instances"] if i["id"] == target[9:]), None)
        identifiers = {records[r]["id"] for r in instance["requirements"]} if instance else set()
        return {r for r in scope if records[r]["id"] in identifiers}
    # A core Deliverable can implement several requirements or own shared files.
    references = {l["requirement"] for l in registry["links"]
                  if l["increment"] == increment["id"] and l["relation"] != "shared_constraint"
                  and l["target"] == target}
    references.update(r for i in registry["instances"]
                      if i["increment"] == increment["id"] and i["owner"] == target
                      for r in i["requirements"])
    return references & scope


def verification_context(root: Path, registry: dict, reference: str) -> str:
    increment = next(i for i in registry["increments"] if i["id"] == registry["active_increment"])
    records = {f"{r['id']}@{r['version']}": r for r in registry["requirements"]}
    scoped = next(s for s in increment["scope"] if s["requirement"] == reference)
    links = [{k: v for k, v in l.items() if k != "increment"} for l in registry["links"]
             if l["increment"] == increment["id"] and l["requirement"] == reference]
    instances = [{k: v for k, v in i.items() if k != "increment"} for i in live_instances(registry)
                 if i["increment"] == increment["id"] and reference in i["requirements"]]
    epochs = []
    for change in active_changes(registry):
        targets = sorted(a["target"] for a in change["assessments"]
                         if a["action"] == "reverify" and reference in _target_references(registry, a["target"]))
        if targets:
            epochs.append({"change": change["request_id"], "revision": change.get("assessment_revision", 0),
                           "targets": targets})
    files = {}
    for instance in instances:
        path = safe_path(root, instance["path"])
        files[instance["path"]] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return digest({"requirement": records[reference], "criteria": sorted(scoped["criteria"]),
        "pack": increment["pack"], "links": sorted(links, key=digest),
        "shared_constraints": {l["target"]: records[l["target"]] for l in links if l["relation"] == "shared_constraint"},
        "instances": sorted(instances, key=lambda i: i["id"]), "files": files,
        "reverification": sorted(epochs, key=lambda e: e["change"])})


def verification_issue(root: Path, registry: dict, result: dict) -> str | None:
    increment = next(i for i in registry["increments"] if i["id"] == registry["active_increment"])
    if result["requirement"] not in {s["requirement"] for s in increment["scope"]}:
        return "VERIFICATION_OUT_OF_SCOPE:" + result["id"]
    if not result.get("context_sha256"):
        return "VERIFICATION_CONTEXT_UNKNOWN:" + result["id"]
    if result["context_sha256"] != verification_context(root, registry, result["requirement"]):
        return "VERIFICATION_CONTEXT_STALE:" + result["id"]
    path = safe_path(root, result["evidence"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != result["sha256"]:
        return "VERIFICATION_STALE:" + result["id"]
    return None

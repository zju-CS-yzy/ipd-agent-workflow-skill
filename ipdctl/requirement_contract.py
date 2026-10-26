"""Strict, published JSON contracts for opt-in incremental requirements."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .documents import RequirementError


def obj(properties: dict, required: list | None = None) -> dict:
    return {"type": "object", "properties": properties, "additionalProperties": False,
            "required": list(properties) if required is None else required}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


S = {"type": "string", "minLength": 1}
ID = {**S, "pattern": r"^[a-z0-9][a-z0-9._-]*$"}
REF = {**S, "pattern": r"^[a-z0-9][a-z0-9._-]*@[1-9][0-9]*$"}
HASH = {**S, "pattern": r"^[a-f0-9]{64}$"}
INT = {"type": "integer", "minimum": 1}
NULL = {"type": "null"}


def enum(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


CRITERION = obj({"id": ID, "criterion": S,
                 "method": enum("test", "analysis", "inspection", "demonstration")})
REQUIREMENT = obj({"id": ID, "version": INT, "kind": enum("IR", "SR", "AR"),
    "title": S, "statement": S, "source": S, "rationale": S, "priority": S,
    "owner": S, "module": S, "parent": {"oneOf": [REF, NULL]},
    "derived": {"type": "boolean"}, "acceptance": {**arr(CRITERION), "minItems": 1},
    "maturity": enum("draft", "defined"), "decomposition": enum("open", "complete")})
SCOPE = arr(obj({"requirement": REF, "criteria": {**arr(ID), "minItems": 1}}))
PIN = obj({"id": ID, "version": S, "sha256": HASH, "path": {"type": "string"},
           "layer": enum("core", "organization", "project")})
TEMPLATE_PACK = {"$schema": "https://json-schema.org/draft/2020-12/schema", **obj({
    "schema_version": enum("1.0"), "id": ID, "version": S, "contract": enum("0.5.3", "0.5.4"),
    "layer": enum("core", "organization", "project"),
    "templates": {**arr(obj({"document_type": ID, "id": ID, "version": S,
        "locale": enum("en", "zh-CN"), "path": S, "sections": {**arr(ID), "minItems": 1},
        "filename_pattern": S, "sha256": HASH,
        "requirement_kinds": {**arr(enum("IR", "SR", "AR")), "minItems": 1},
        "phases": {**arr(enum("concept", "plan", "develop", "qualify", "launch", "lifecycle")), "minItems": 1}})), "minItems": 1}})}
INSTANCE = obj({"id": ID, "key": ID, "increment": ID, "requirements": {**arr(REF), "minItems": 1},
    "owner": ID, "document_type": ID, "path": S, "title": S, "scope": S,
    "locale": enum("en", "zh-CN"), "template_id": ID, "template_version": S,
    "template_sha256": HASH, "pack": PIN})
INSTANCE["properties"]["supersedes"] = ID
TEMPLATE_RECORD = obj({"id": ID, "stage": enum("draft", "reviewed", "published"),
                       "pack": PIN, "path": S, "sha256": HASH})
PUBLICATION = obj({"schema_version": enum("1.0"), "id": ID,
    "stage": enum("draft", "reviewed", "published"), "pack": PIN,
    "author": S, "reviewer": {"oneOf": [S, NULL]}, "publisher": {"oneOf": [S, NULL]},
    "actor": S, "actor_type": enum("human"), "authorized": {"type": "boolean", "enum": [True]},
    "identity_source": enum("explicit-local-declaration"), "decision": enum("pending", "approved", "rejected"),
    "reason": S, "result_revision": INT, "source": {"oneOf": [TEMPLATE_RECORD, NULL]},
    "request_id": ID})
CONTEXT = obj({"increment": {"oneOf": [ID, NULL]},
               "base_baseline": {"oneOf": [ID, NULL]}, "scope_sha256": HASH})
OBLIGATION = obj({"id": ID, "increment": ID, "requirement": REF, "owner": ID,
                   "document_type": ID, "keys": {**arr(ID), "minItems": 1}})
LINK = obj({"increment": ID, "requirement": REF,
            "relation": enum("allocated_to", "satisfied_by", "shared_constraint"),
            "target": S, "rationale": S})
VERIFICATION = obj({"id": ID, "increment": ID, "requirement": REF, "criterion": ID,
    "method": enum("test", "analysis", "inspection", "demonstration"),
    "case": S, "environment": S, "result": enum("passed", "failed", "skipped", "unknown"),
    "evidence": S, "sha256": HASH, "source_baseline": {"oneOf": [ID, NULL]},
    "source_result": {"oneOf": [ID, NULL]}, "context_sha256": HASH},
    required=["id", "increment", "requirement", "criterion", "method", "case", "environment",
              "result", "evidence", "sha256", "source_baseline", "source_result"])
INCREMENT = obj({"id": ID, "product_version": S, "base_baseline": {"oneOf": [ID, NULL]},
                 "scope": SCOPE, "status": enum("active", "accepted"), "pack": PIN})
BASELINE = obj({"id": ID, "increment": ID, "path": S, "sha256": HASH,
               "source": obj({"backend": enum("git", "svn"), "repository": S,
                              "revision": S, "path": S})})
CHANGE = obj({"request_id": ID, "old": REF, "new": REF, "affected": arr(S),
              "assessments": arr(obj({"target": S, "action": enum("reverify", "unaffected", "defer"),
                                      "rationale": S})), "assessment_revision": INT},
             required=["request_id", "old", "new", "affected", "assessments"])
EVENT = obj({"request_id": ID, "operation": S, "actor": S, "reason": S,
             "base_revision": {"type": "integer", "minimum": 0}, "request_sha256": HASH,
             "result_revision": INT, "plan_sha256": HASH})
EVENT["properties"]["increment_context"] = CONTEXT
SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Incremental requirement registry 1.0", **obj({
    "schema_version": enum("1.0"), "contract": enum("0.5.3"),
    "product_state": enum("active", "retired"), "active_increment": {"oneOf": [ID, NULL]},
    "template_pack": PIN, "stage_map": {"type": "object", "additionalProperties": enum("TR1", "TR2", "TR3", "TR4")},
    "requirements": arr(REQUIREMENT), "increments": arr(INCREMENT),
    "instances": arr(INSTANCE), "obligations": arr(OBLIGATION), "links": arr(LINK),
    "verifications": arr(VERIFICATION), "baselines": arr(BASELINE), "changes": arr(CHANGE),
    "events": arr(EVENT), "migration": obj({"path": S, "sha256": HASH, "unmapped": arr(ID)})})}
SCHEMA["properties"]["template_records"] = arr(TEMPLATE_RECORD)

# Keep 1.0 readable verbatim. New organizational facts require a new contract,
# so published 0.5.3 clients reject them rather than dropping unknown fields.
LEGACY_SCHEMA = SCHEMA
SUPPORT = obj({"kind": enum("instance", "artifact"), "target": S, "owner": ID,
               "required": {"type": "boolean"}, "rationale": S,
               "anchor": {"type": "string"}, "sha256": {"oneOf": [HASH, NULL]}})
STAGE_UNIT = obj({"id": ID, "increment": ID, "stage": enum("TR1", "TR2", "TR3", "TR4"),
                  "owner": ID, "locale": enum("en", "zh-CN"), "inputs": arr(REF),
                  "outputs": arr(REF), "supports": arr(SUPPORT), "conclusion": ID,
                  "arguments": arr(obj({"requirement": REF, "anchor": ID})),
                  "register": {"oneOf": [ID, NULL]}, "finalized": {"type": "boolean"}, "rationale": S})
STAGE_PLAN = obj({"increment": ID, "stage": enum("TR1", "TR2", "TR3", "TR4"),
                  "owner": ID, "locale": enum("en", "zh-CN"), "index": ID})
ORGANIZATION = obj({"policy": enum("hierarchical-v1"),
    "required_stages": {**arr(enum("TR1", "TR2", "TR3", "TR4")), "minItems": 1},
    "codes": arr(obj({"requirement": REF, "code": ID})),
    "plans": arr(STAGE_PLAN), "units": arr(STAGE_UNIT),
    "adoption": obj({"path": S, "sha256": HASH})})
ORGANIZED_SCHEMA = deepcopy(LEGACY_SCHEMA)
ORGANIZED_SCHEMA["title"] = "Incremental requirement registry 1.1"
ORGANIZED_SCHEMA["properties"].update(schema_version=enum("1.1"), contract=enum("0.5.4"), organization=ORGANIZATION)
ORGANIZED_SCHEMA["required"] = [*ORGANIZED_SCHEMA["required"], "organization"]
ORGANIZED_SCHEMA["properties"]["instances"]["items"]["properties"]["requirements"] = arr(REF)
SUPPORT_V2 = deepcopy(SUPPORT)
SUPPORT_V2['properties']['usage'] = enum('deliverable', 'attachment', 'reference')
STAGE_UNIT_V2 = deepcopy(STAGE_UNIT)
STAGE_UNIT_V2['properties']['supports'] = arr(SUPPORT_V2)
WORK_SCHEMA = deepcopy(ORGANIZED_SCHEMA)
WORK_SCHEMA['title'] = 'Incremental requirement registry 1.2'
WORK_SCHEMA['properties'].update(schema_version=enum('1.2'), contract=enum('0.5.5'))
WORK_SCHEMA['properties']['organization']['properties']['units'] = arr(STAGE_UNIT_V2)
WORK_SCHEMA['properties']['organization']['properties']['work_adoption'] = obj({'path': S, 'sha256': HASH})
WORK_SCHEMA['properties']['organization']['required'].append('work_adoption')
SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema",
          "title": "Incremental requirement registries", "oneOf": [LEGACY_SCHEMA, ORGANIZED_SCHEMA, WORK_SCHEMA]}


def unit_contract(registry):
    return STAGE_UNIT_V2 if registry['schema_version'] == '1.2' else STAGE_UNIT


def validate(value: Any, schema: dict = SCHEMA, path: str = "$") -> None:
    """Validate the subset used by our published schemas without optional deps."""
    if "oneOf" in schema:
        matches = 0
        for option in schema["oneOf"]:
            try:
                validate(value, option, path)
                matches += 1
            except RequirementError:
                pass
        if matches != 1:
            raise RequirementError("REQUIREMENT_CONTRACT: invalid value at " + path)
        return
    kind = schema.get("type")
    expected = {"object": dict, "array": list, "string": str, "integer": int,
                "boolean": bool, "null": type(None)}.get(kind)
    if expected and type(value) is not expected:
        raise RequirementError("REQUIREMENT_CONTRACT: invalid type at " + path)
    if "enum" in schema and value not in schema["enum"]:
        raise RequirementError("REQUIREMENT_CONTRACT: invalid enum at " + path)
    if kind == "object":
        properties = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            raise RequirementError("REQUIREMENT_CONTRACT: required field missing at " + path)
        for key, item in value.items():
            rule = properties.get(key, schema.get("additionalProperties", True))
            if rule is False:
                raise RequirementError("REQUIREMENT_CONTRACT: unknown field " + path + "." + key)
            if isinstance(rule, dict):
                validate(item, rule, path + "." + key)
    if kind == "array":
        if len(value) < schema.get("minItems", 0):
            raise RequirementError("REQUIREMENT_CONTRACT: empty list at " + path)
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    if kind == "string" and (len(value.strip()) < schema.get("minLength", 0) or
                             ("pattern" in schema and not re.fullmatch(schema["pattern"], value))):
        raise RequirementError("REQUIREMENT_CONTRACT: invalid text at " + path)
    if kind == "integer" and value < schema.get("minimum", value):
        raise RequirementError("REQUIREMENT_CONTRACT: invalid integer at " + path)

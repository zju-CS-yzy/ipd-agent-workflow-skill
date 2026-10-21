from __future__ import annotations

import json
import shutil
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from tests import test_requirements as fixtures
from ipdctl.documents import RequirementError, load_pack
from ipdctl.requirements import apply_plan, preview, read_registry, readiness
from ipdctl.runtime import load_runtime, record_event, save_runtime, validate_runtime
from ipdctl.state import write_state
from ipdctl.template_publications import live_instances, published


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RequirementTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_preview_draft_review_rejection_and_authorization(self):
        f = self.f
        f.execute("enable", increment="mvp", product_version="0.1")
        before = f.bytes()
        request = f.request("draft_templates", id="draft", path="", actor="author", actor_type="human")
        plan = preview(f.root, request)
        self.assertEqual(before, f.bytes())
        for actor, authorized in [("author", False), ("impersonator", True)]:
            with self.assertRaisesRegex(RequirementError, "AUTHORIZATION_REQUIRED|TEMPLATE_ACTOR"):
                apply_plan(f.root, plan, actor=actor, authorized=authorized)
            self.assertEqual(before, f.bytes())
        apply_plan(f.root, plan, actor="author", authorized=True)
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_UNPUBLISHED"):
            preview(f.root, f.request("pin_templates", path=""))
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_REVIEW_DECISION"):
            f.execute("review_templates", actor="author", id="self", source="draft", decision="approved", actor_type="human")
        f.execute("review_templates", actor="reviewer", id="rejected", source="draft", decision="rejected", actor_type="human")
        before = f.bytes()
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_REVIEW_REJECTED"):
            f.execute("publish_templates", actor="publisher", id="pub", source="rejected", actor_type="human")
        self.assertEqual(before, f.bytes())

    def test_published_digest_retry_history_and_rollback(self):
        f = self.f
        f.enable()
        registry = read_registry(f.root)
        self.assertTrue(published(f.root, registry, registry["template_pack"]))
        plan = f.execute("pin_templates", path="")
        before = f.bytes()
        self.assertEqual(apply_plan(f.root, plan, actor="human", authorized=True)["status"], "already_applied")
        self.assertEqual(before, f.bytes())
        draft = preview(f.root, f.request("draft_templates", id="rollback", path="", actor="author", actor_type="human"))
        with patch("ipdctl.requirements.save_runtime", side_effect=OSError("injected write failure")):
            with self.assertRaises(OSError):
                apply_plan(f.root, draft, actor="author", authorized=True)
        self.assertEqual(before, f.bytes())
        apply_plan(f.root, draft, actor="author", authorized=True)
        record = read_registry(f.root)["template_records"][-1]
        (f.root / record["path"]).write_text("{}", encoding="utf-8")
        before = f.bytes()
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_HISTORY_TAMPERED"):
            preview(f.root, f.request("pin_templates", path=""))
        self.assertEqual(before, f.bytes())

    def test_review_is_bound_to_exact_pack_and_latest_decision(self):
        f = self.f
        f.enable()
        f.execute("draft_templates", actor="author", id="draft", path="", actor_type="human")
        f.execute("review_templates", actor="reviewer", id="yes", source="draft", decision="approved", actor_type="human")
        stale = preview(f.root, f.request("publish_templates", id="pub", source="yes", actor="publisher", actor_type="human"))
        f.execute("review_templates", actor="reviewer", id="no", source="draft", decision="rejected", actor_type="human")
        before = f.bytes()
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_REVIEW_STALE"):
            apply_plan(f.root, stale, actor="publisher", authorized=True)
        self.assertEqual(before, f.bytes())

    def test_legacy_instance_replacement_is_explicit_new_file_and_owner_claim(self):
        f = self.f
        f.basic_scope()
        _, directory = load_pack(f.root)
        legacy = directory / "archives/ipd-starter-1.0.0"
        shutil.copytree(legacy, f.root / "legacy-pack")
        f.publish_pack("legacy-pack")
        f.execute("pin_templates", path="legacy-pack")
        old = f.prepare_instance()
        f.execute("instantiate", actor="agent", instance=old)
        old_bytes = (f.root / old["path"]).read_bytes()
        new = {**old, "id": "converted", "path": "docs/converted.md"}
        request = f.request("replace_templates", path="", replacements=[{"old": old["id"], "instance": new}])
        before = f.bytes()
        plan = preview(f.root, request)
        self.assertEqual(before, f.bytes())
        with self.assertRaisesRegex(RequirementError, "INSTANCE_CLAIM"):
            apply_plan(f.root, plan, actor="wrong", authorized=True)
        self.assertEqual(before, f.bytes())
        apply_plan(f.root, plan, actor="agent", authorized=True)
        registry = read_registry(f.root)
        self.assertEqual((f.root / old["path"]).read_bytes(), old_bytes)
        self.assertEqual([i["id"] for i in live_instances(registry)], ["converted"])
        self.assertEqual(registry["instances"][-1]["supersedes"], old["id"])
        self.assertTrue((f.root / new["path"]).is_file())
        self.assertTrue(any("DOCUMENT_PLACEHOLDERS:converted" == i for i in readiness(f.root, registry, f.state(), stage="TR1", owner=old["owner"])))

    def test_new_events_bind_scope_without_backfilling_history(self):
        f = self.f
        legacy = record_event(load_runtime(f.root), "legacy-example")
        save_runtime(f.root, legacy)
        f.enable()
        f.execute("requirement", requirement=fixtures.requirement())
        f.execute("scope", scope=[{"requirement": "ir-1@1", "criteria": ["response"]}])
        runtime = load_runtime(f.root)
        self.assertEqual(runtime["events"][0], legacy["events"][0])
        self.assertNotIn("increment_context", runtime["events"][0])
        current = record_event(runtime, "verify", details={"status": "passed"})
        self.assertEqual(current["events"][-1]["increment_context"]["increment"], "mvp")
        self.assertEqual(current["schema_version"], "1.1")
        self.assertEqual(validate_runtime(current), [])
        missing = deepcopy(current)
        missing["events"][-1].pop("increment_context")
        self.assertTrue(validate_runtime(missing))
        current["events"][-1]["increment_context"]["scope_sha256"] = "invalid"
        self.assertTrue(validate_runtime(current))

    def test_early_gate_ignores_future_allocation_but_binds_shared_constraints(self):
        from ipdctl.requirements import decision_manifest
        f = self.f
        f.basic_scope()
        gate = f.state()["gates"][0]["id"]
        before = decision_manifest(f.root, f.state(), gate, "gate")
        f.execute("link", link={"requirement": "ir-1@1", "relation": "satisfied_by",
            "target": f.state()["deliverables"][0]["id"], "rationale": "Future implementation allocation"})
        self.assertEqual(before, decision_manifest(f.root, f.state(), gate, "gate"))
        f.execute("requirement", requirement=fixtures.requirement("ir-2"))
        f.execute("link", link={"requirement": "ir-1@1", "relation": "shared_constraint",
            "target": "ir-2@1", "rationale": "Changed input constraint"})
        self.assertNotEqual(before, decision_manifest(f.root, f.state(), gate, "gate"))

    def test_claim_holder_can_record_after_writing_but_other_actor_cannot(self):
        f = self.f
        f.basic_scope()
        item = f.prepare_instance()
        f.execute("instantiate", actor="agent", instance=item)
        evidence = f.root / "observed.txt"
        evidence.write_text("Actual synthetic observation\n", encoding="utf-8")
        req = f.request("verification", verification={"id": "observed", "requirement": "ir-1@1",
            "criterion": "response", "method": "test", "case": "case@1", "environment": "fixture",
            "result": "passed", "evidence": "observed.txt"})
        plan = preview(f.root, req)
        before = f.bytes()
        with self.assertRaisesRegex(RequirementError, "INSTANCE_CLAIM"):
            apply_plan(f.root, plan, actor="other", authorized=True)
        self.assertEqual(before, f.bytes())
        apply_plan(f.root, plan, actor="agent", authorized=True)
        self.assertEqual(f.state()["project"]["workflow_step"], "work")
        self.assertEqual(load_runtime(f.root)["active_claims"][item["owner"]]["actor"], "agent")

    def test_publication_recovers_after_process_exit_between_authority_writes(self):
        import subprocess
        import sys
        f = self.f
        f.enable()
        request = f.request("draft_templates", id="crash-draft", path="", actor="author", actor_type="human")
        plan = preview(f.root, request)
        saved = f.root / "crash-plan.json"
        saved.write_text(json.dumps(plan), encoding="utf-8")
        script = (
            "import os,json,sys; from pathlib import Path; from unittest.mock import patch; "
            "from ipdctl.requirements import apply_plan; "
            "p=Path(sys.argv[1]); plan=json.loads((p/'crash-plan.json').read_text()); "
            "guard=patch('ipdctl.requirements.save_runtime',side_effect=lambda *a: os._exit(73)); "
            "guard.start(); apply_plan(p,plan,actor='author',authorized=True)"
        )
        child = subprocess.run([sys.executable, "-B", "-c", script, str(f.root)],
                               cwd=Path(__file__).resolve().parents[1], capture_output=True)
        self.assertEqual(child.returncode, 73, child.stderr.decode(errors="replace"))
        self.assertTrue((f.root / ".ipd/template_publications/crash-draft.json").is_file())
        self.assertEqual(apply_plan(f.root, plan, actor="author", authorized=True)["status"], "applied")
        registry = read_registry(f.root)
        self.assertEqual(sum(r["id"] == "crash-draft" for r in registry["template_records"]), 1)
        self.assertEqual(sum(e.get("request_id") == request["request_id"] for e in load_runtime(f.root)["events"]), 1)
        self.assertEqual(apply_plan(f.root, plan, actor="author", authorized=True)["status"], "already_applied")

    def test_unpublished_rejection_is_bilingual_and_readonly(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from ipdctl.cli import main
        f = self.f
        f.execute("enable", increment="mvp", product_version="0.1")
        request = f.root / "pin-request.json"
        request.write_text(json.dumps(f.request("pin_templates", path="")), encoding="utf-8")
        before = f.bytes()
        for locale, expected in (("en", "TEMPLATE_UNPUBLISHED"), ("zh-CN", "模板包尚未完成")):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = main(["requirements", str(f.root), "--request", str(request), "--locale", locale])
            self.assertEqual(status, 1)
            self.assertIn(expected, out.getvalue() + err.getvalue())
            self.assertEqual(before, f.bytes())

    def test_early_sr_format_converts_to_a_valid_canonical_parent_table(self):
        import yaml
        from tests import test_document_tables
        from ipdctl.documents import metadata
        from ipdctl.runtime import claim
        f = self.f
        f.basic_scope()
        f.execute("requirement", requirement=fixtures.requirement("sr-1", "SR", "ir-1@1"))
        f.execute("scope", scope=[{"requirement": r, "criteria": ["response"]} for r in ("ir-1@1", "sr-1@1")])
        _, directory = load_pack(f.root)
        shutil.copytree(directory / "archives/ipd-starter-1.0.0", f.root / "legacy-pack")
        f.publish_pack("legacy-pack")
        f.execute("pin_templates", path="legacy-pack")
        state = f.state()
        legacy_registry = read_registry(f.root)
        legacy_registry["template_records"] = [r for r in legacy_registry["template_records"] if r["pack"]["path"] == "legacy-pack"]
        write_state(f.root / ".ipd/requirements.yaml", legacy_registry)
        owner = next(d["id"] for d in state["deliverables"] if d["phase"] == "plan")
        bindings = fixtures.load_state(f.root / ".ipd/artifact_bindings.yaml")
        bindings["bindings"].append({"id": "sr-owner", "glob": "docs/**", "deliverable": owner, "role": "owner", "critical": True})
        write_state(f.root / ".ipd/artifact_bindings.yaml", bindings)
        state["project"].update(phase="plan", workflow_step="work")
        next(d for d in state["deliverables"] if d["id"] == owner)["status"] = "in_progress"
        write_state(f.root / ".ipd/project_state.yaml", state)
        save_runtime(f.root, claim(load_runtime(f.root), owner, actor="agent", state_revision=state["revision"]))
        old = {"id": "early-sr", "key": "system", "requirements": ["sr-1@1"], "owner": owner,
               "document_type": "sr_spec", "path": "docs/early-sr.md", "title": "System specification",
               "scope": "Synthetic conversion", "locale": "en"}
        f.execute("instantiate", actor="agent", instance=old)
        original = (f.root / old["path"]).read_bytes()
        self.assertIn("DOCUMENT_PARENT_COLUMN:early-sr", readiness(f.root, read_registry(f.root), f.state(), stage="TR2", owner=owner))
        new = {**old, "id": "current-sr", "path": "docs/current-sr.md"}
        before = f.bytes()
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_UNPUBLISHED"):
            preview(f.root, f.request("replace_templates", path="", replacements=[{"old": old["id"], "instance": new}]))
        self.assertEqual(before, f.bytes())
        # QA can publish a target while the old Owner Claim remains open;
        # it changes no effective pack, file, Claim or Review decision.
        f.publish_pack("")
        self.assertEqual(f.state()["project"]["workflow_step"], "work")
        self.assertEqual(load_runtime(f.root)["active_claims"][owner]["actor"], "agent")
        f.execute("replace_templates", actor="agent", path="", replacements=[{"old": old["id"], "instance": new}])
        recorded = read_registry(f.root)["instances"][-1]
        text = test_document_tables.DocumentTableTests().filled("sr_spec", "en", 1)[0]
        body = text.split("---", 2)[2].lstrip().replace("ir-parent@1", "ir-1@1")
        text = "---\n" + yaml.safe_dump(metadata(recorded), sort_keys=False) + "---\n\n" + body
        (f.root / new["path"]).write_text(text, encoding="utf-8")
        self.assertEqual(readiness(f.root, read_registry(f.root), f.state(), stage="TR2", owner=owner), [])
        self.assertEqual((f.root / old["path"]).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

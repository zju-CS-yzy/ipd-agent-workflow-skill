from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from ipdctl.cli import main
from ipdctl.documents import RequirementError, digest, instantiate, lint, load_pack, safe_path, template
from ipdctl.project import initialize_project, sync_state_with_process, verification_input_snapshot
from ipdctl.requirement_contract import SCHEMA, validate
from ipdctl.requirements import (REGISTRY, apply_plan, check_relations, enforce, preview, projection,
                                 read_registry, readiness, ref)
from ipdctl.runtime import load_runtime, save_runtime, claim
from ipdctl.state import load_state, write_state
from ipdctl.tailoring import load_profile, tailor_profile


def requirement(identifier="ir-1", kind="IR", parent=None, version=1):
    return {"id": identifier, "version": version, "kind": kind, "title": "Portable sensor",
            "statement": "The product shall report a measurement within two seconds.",
            "source": "customer-interview-1", "rationale": "Timely field decisions",
            "priority": "high", "owner": "systems-team", "module": "sensor",
            "parent": parent, "derived": False, "acceptance": [
                {"id": "response", "criterion": "Elapsed time <= 2 s at 20 C",
                 "method": "test"}], "maturity": "defined", "decomposition": "open"}


class RequirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize_project(self.root, name="Synthetic incremental project", task_types=["software"])
        process = tailor_profile(load_profile(self.root / ".ipd/task_profile.yaml"))
        write_state(self.root / ".ipd/tailored_process.yaml", process)
        state = sync_state_with_process(load_state(self.root / ".ipd/project_state.yaml"), process)
        write_state(self.root / ".ipd/project_state.yaml", state)
        self.counter = 0

    def request(self, op, **fields):
        self.counter += 1
        return {"operation": op, "request_id": f"request-{self.counter}", "reason": "Synthetic acceptance fixture", **fields}

    def execute(self, op, actor="human", **fields):
        if op in {"draft_templates", "review_templates", "publish_templates"}:
            fields["actor"] = actor
        plan = preview(self.root, self.request(op, **fields))
        apply_plan(self.root, plan, actor=actor, authorized=True)
        return plan

    def enable(self):
        plan = self.execute("enable", increment="mvp", product_version="0.1")
        self.publish_pack("")
        return plan

    def publish_pack(self, path):
        suffix = str(self.counter)
        self.execute("draft_templates", actor="qa-author", id="draft-" + suffix,
                     path=path, actor_type="human")
        self.execute("review_templates", actor="qa-reviewer", id="review-" + suffix,
                     source="draft-" + suffix, decision="approved", actor_type="human")
        self.execute("publish_templates", actor="qa-publisher", id="publish-" + suffix,
                     source="review-" + suffix, actor_type="human")

    def state(self):
        return load_state(self.root / ".ipd/project_state.yaml")

    def bytes(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def basic_scope(self):
        self.enable()
        self.execute("requirement", requirement=requirement())
        self.execute("scope", scope=[{"requirement": "ir-1@1", "criteria": ["response"]}])

    def prepare_instance(self, locale="en", key="northbound"):
        registry = read_registry(self.root)
        state = self.state()
        owner = state["deliverables"][0]["id"]
        bindings = load_state(self.root / ".ipd/artifact_bindings.yaml")
        bindings["bindings"].append({"id": "document-owner", "glob": "docs/**", "deliverable": owner,
                                      "role": "owner", "critical": True})
        write_state(self.root / ".ipd/artifact_bindings.yaml", bindings)
        state["project"]["workflow_step"] = "work"
        state["deliverables"][0]["status"] = "in_progress"
        write_state(self.root / ".ipd/project_state.yaml", state)
        save_runtime(self.root, claim(load_runtime(self.root), owner, actor="agent", state_revision=state["revision"]))
        return {"id": "interface-" + key, "key": key, "requirements": ["ir-1@1"], "owner": owner,
                "document_type": "interface_spec", "path": "docs/" + key + ".md", "title": "Sensor interface",
                "scope": "Synthetic MVP", "locale": locale}

    def test_legacy_is_opt_in_and_template_preview_has_no_writes(self):
        before = self.bytes()
        self.assertIsNone(read_registry(self.root))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["templates", str(self.root), "--type", "sr_spec", "--locale", "zh-CN"]), 0)
        self.assertIn("系统验证方法与判据", output.getvalue())
        self.assertEqual(before, self.bytes())
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            main(["templates", "--locale", "zh-CN", "--help"])
        self.assertIn("中英文 Markdown", output.getvalue())

    def test_enable_preview_authorization_and_exact_retry(self):
        before = self.bytes()
        plan = preview(self.root, self.request("enable", increment="mvp", product_version="0.1"))
        self.assertEqual(before, self.bytes())
        with self.assertRaisesRegex(RequirementError, "AUTHORIZATION_REQUIRED"):
            apply_plan(self.root, plan, actor="human", authorized=False)
        self.assertEqual(before, self.bytes())
        apply_plan(self.root, plan, actor="human", authorized=True)
        applied = self.bytes()
        self.assertEqual(apply_plan(self.root, plan, actor="human", authorized=True)["status"], "already_applied")
        self.assertEqual(applied, self.bytes())
        self.assertEqual(read_registry(self.root)["migration"]["unmapped"], [i["id"] for i in self.state()["deliverables"]])

    def test_stale_plan_and_changed_replay_rejected(self):
        self.enable()
        plan = preview(self.root, self.request("requirement", requirement=requirement()))
        self.execute("requirement", requirement=requirement("ir-2"))
        before = self.bytes()
        with self.assertRaises(RequirementError):
            apply_plan(self.root, plan, actor="human", authorized=True)
        self.assertEqual(before, self.bytes())

    def test_progressive_gate_deadlines_are_independent(self):
        self.basic_scope()
        registry = read_registry(self.root)
        self.assertEqual(readiness(self.root, registry, self.state(), stage="TR1"), [])
        self.assertIn("DECOMPOSITION_OPEN:ir-1@1", readiness(self.root, registry, self.state(), stage="TR2"))
        self.assertIn("VERIFICATION_NOT_PASSED:ir-1@1:response", readiness(self.root, registry, self.state(), stage="TR4"))

    def test_exact_parent_type_versions_and_cycle_rejected(self):
        self.basic_scope()
        for parent, kind in [("missing@1", "SR"), ("ir-1@2", "SR"), ("ir-1@1", "AR")]:
            with self.assertRaisesRegex(RequirementError, "REQUIREMENT_PARENT"):
                preview(self.root, self.request("requirement", requirement=requirement("child", kind, parent)))
        self.execute("requirement", requirement=requirement("sr-1", "SR", "ir-1@1"))
        self.execute("requirement", requirement=requirement("ar-1", "AR", "sr-1@1"))
        self.assertEqual(len(read_registry(self.root)["requirements"]), 3)

    def test_requirement_version_change_preserves_history_and_lists_impact(self):
        self.basic_scope()
        self.execute("requirement", requirement=requirement("sr-1", "SR", "ir-1@1"))
        self.execute("requirement", requirement=requirement("ar-1", "AR", "sr-1@1"))
        before = deepcopy(read_registry(self.root)["requirements"])
        plan = self.execute("requirement", requirement=requirement(version=2))
        self.assertEqual(read_registry(self.root)["requirements"][:3], before)
        self.assertTrue({"ir-1@1", "sr-1@1", "ar-1@1"} <= set(plan["impact"]["affected"]))

    def test_multi_instance_bilingual_templates_and_cardinality(self):
        self.basic_scope()
        self.execute("requirement", requirement=requirement("sr-1", "SR", "ir-1@1"))
        self.execute("requirement", requirement=requirement("ar-1", "AR", "sr-1@1"))
        self.execute("scope", scope=[{"requirement": r, "criteria": ["response"]} for r in ("ir-1@1", "sr-1@1", "ar-1@1")])
        item = self.prepare_instance("zh-CN")
        item["requirements"] = ["ar-1@1", "sr-1@1"]
        self.execute("instantiate", actor="agent", instance=item)
        self.execute_instance_second(item)
        registry = read_registry(self.root)
        state = self.state()
        registry["obligations"].append({"id": "two-interfaces", "increment": "mvp", "requirement": "ar-1@1",
            "owner": item["owner"], "document_type": "interface_spec", "keys": ["northbound", "southbound"]})
        checks = readiness(self.root, registry, state, stage="TR1", owner=item["owner"])
        self.assertFalse(any("CARDINALITY" in c for c in checks))
        self.assertTrue(any("PLACEHOLDERS" in c for c in checks))
        self.assertEqual(registry["instances"][0]["requirements"], ["ar-1@1", "sr-1@1"])
        self.assertEqual({i["template_version"] for i in registry["instances"]}, {"1.0.0"})
        registry["instances"].pop()
        self.assertIn("DOCUMENT_CARDINALITY:two-interfaces", readiness(self.root, registry, state, stage="TR1", owner=item["owner"]))
        self.assertIn("接口标识与两端角色", (self.root / "docs/northbound.md").read_text(encoding="utf-8"))

    def execute_instance_second(self, original):
        item = {**original, "id": "interface-southbound", "key": "southbound", "path": "docs/southbound.md", "locale": "en"}
        self.execute("instantiate", actor="agent", instance=item)

    def test_multi_requirement_register_is_created_and_checked_as_one_document(self):
        self.basic_scope()
        self.execute("requirement", requirement=requirement("ir-2"))
        self.execute("scope", scope=[{"requirement": r, "criteria": ["response"]} for r in ("ir-1@1", "ir-2@1")])
        item = self.prepare_instance("zh-CN", "all-ir")
        item.update(document_type="ir_spec", requirements=["ir-1@1", "ir-2@1"])
        self.execute("instantiate", actor="agent", instance=item)
        registry = read_registry(self.root)
        instance = registry["instances"][0]
        path = self.root / item["path"]
        text = path.read_text(encoding="utf-8")
        text = text.replace("[[TODO: requirement_1]]", "ir-1@1").replace("[[TODO: requirement_2]]", "ir-2@1")
        text = re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic content and source@1", text)
        path.write_text(text, encoding="utf-8")
        self.assertEqual(instance["template_version"], "1.1.1")
        self.assertEqual(readiness(self.root, registry, self.state(), stage="TR1", owner=item["owner"]), [])
        path.write_text(text.replace("ir-2@1</td>", "ir-1@1</td>"), encoding="utf-8")
        self.assertTrue(any("DOCUMENT_REQUIREMENT_ROWS" in c for c in readiness(self.root, registry, self.state(), stage="TR1", owner=item["owner"])))

    def test_template_lint_detects_empty_sections_columns_metadata(self):
        self.basic_scope()
        item = self.prepare_instance()
        self.execute("instantiate", actor="agent", instance=item)
        actual = read_registry(self.root)["instances"][0]
        record, source = template(self.root, actual["pack"], "interface_spec", "en")
        text = (self.root / actual["path"]).read_text(encoding="utf-8")
        filled = re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic fixture content", text)
        self.assertEqual(lint(filled, actual, source, record["sections"]), [])
        stripped = re.sub(r"\[\[TODO:[^\]]+\]\]", "", text)
        self.assertTrue(any(i.startswith("DOCUMENT_UNFILLED") for i in lint(stripped, actual, source, record["sections"])))
        self.assertIn("DOCUMENT_METADATA", lint(filled.replace("instance_id:", "forged_id:"), actual, source, record["sections"]))
        self.assertIn("DOCUMENT_COLUMNS", lint(filled.replace("| ID / version |", "| Changed |"), actual, source, record["sections"]))
        punctuation = {**actual, "scope": "MVP---version-1"}
        json_example = re.sub(r"\[\[TODO:[^\]]+\]\]", '{"actual":{"elapsed_s":1.5}}', instantiate(source, punctuation))
        self.assertEqual(lint(json_example, punctuation, source, record["sections"]), [])

    def test_parent_reference_errors_block_registered_document_and_gate_without_writes(self):
        self.basic_scope()
        for identifier in ("sr-1", "sr-2"):
            self.execute("requirement", requirement=requirement(identifier, "SR", "ir-1@1"))
        self.execute("scope", scope=[{"requirement": r, "criteria": ["response"]}
            for r in ("ir-1@1", "sr-1@1", "sr-2@1")])
        item = self.prepare_instance("zh-CN", "system-register")
        item.update(document_type="sr_spec", requirements=["sr-1@1", "sr-2@1"])
        self.execute("instantiate", actor="agent", instance=item)
        path = self.root / item["path"]
        text = path.read_text(encoding="utf-8").replace("[[TODO: requirement_1]]", "sr-1@1").replace("[[TODO: requirement_2]]", "sr-2@1")
        text = text.replace("[[TODO: parent_shared]]", "ir-1@1")
        text = re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic requirement facts", text)
        path.write_text(text, encoding="utf-8")
        self.assertEqual(readiness(self.root, read_registry(self.root), self.state(), stage="TR1", owner=item["owner"]), [])
        path.write_text(text.replace("ir-1@1</td>", "missing-ir@999</td>"), encoding="utf-8")
        gate = next(g for g, stage in read_registry(self.root)["stage_map"].items() if stage == "TR1")
        before = self.bytes()
        with self.assertRaisesRegex(RequirementError, "DOCUMENT_PARENT_REFERENCE"):
            enforce(self.root, self.state(), gate, "gate")
        self.assertEqual(before, self.bytes())

    def test_template_tamper_missing_locale_and_unknown_variable(self):
        manifest, directory = load_pack(self.root)
        local = self.root / "private-pack"
        import shutil
        shutil.copytree(directory, local)
        template_path = local / "en/interface_spec.md"
        template_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_TAMPERED"):
            load_pack(self.root, {"path": "private-pack"})
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_VARIABLE"):
            instantiate("{{unsafe}}", {})

    def test_safe_paths_reject_escape_windows_names_and_case_collision(self):
        for name in ("../escape", "docs/../escape", "D:/escape", "docs\\file", "/tmp/file", "docs/NUL.md", "docs/file. ", "docs//file"):
            with self.assertRaises(RequirementError, msg=name):
                safe_path(self.root, name)

    def test_partial_write_failure_rolls_back_files_state_registry_runtime(self):
        self.basic_scope()
        item = self.prepare_instance()
        plan = preview(self.root, self.request("instantiate", instance=item))
        before = self.bytes()
        with patch("ipdctl.requirements.save_runtime", side_effect=OSError("injected write failure")):
            with self.assertRaises(OSError):
                apply_plan(self.root, plan, actor="agent", authorized=True)
        self.assertEqual(before, self.bytes())
        self.assertFalse((self.root / item["path"]).exists())

    def test_wrong_actor_and_existing_file_do_not_write(self):
        self.basic_scope()
        item = self.prepare_instance()
        plan = preview(self.root, self.request("instantiate", instance=item))
        before = self.bytes()
        with self.assertRaisesRegex(RequirementError, "INSTANCE_CLAIM"):
            apply_plan(self.root, plan, actor="other", authorized=True)
        self.assertEqual(before, self.bytes())
        (self.root / item["path"]).write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(RequirementError, "INSTANCE_PATH"):
            preview(self.root, self.request("instantiate", instance=item))

    def test_requirement_evidence_changes_verification_fingerprint(self):
        self.basic_scope()
        first = verification_input_snapshot(self.root)
        self.execute("requirement", requirement=requirement("ir-2"))
        self.assertNotEqual(first["files"]["incremental_requirements"], verification_input_snapshot(self.root)["files"]["incremental_requirements"])

    def test_ar_success_does_not_imply_ir_acceptance(self):
        self.basic_scope()
        self.execute("requirement", requirement=requirement("sr-1", "SR", "ir-1@1"))
        self.execute("requirement", requirement=requirement("ar-1", "AR", "sr-1@1"))
        self.execute("scope", scope=[{"requirement": r, "criteria": ["response"]} for r in ("ir-1@1", "sr-1@1", "ar-1@1")])
        evidence = self.root / "test-evidence.md"
        evidence.write_text("Synthetic measured elapsed time: 1.5 s at 20 C", encoding="utf-8")
        self.execute("verification", verification={"id": "case-ar", "requirement": "ar-1@1", "criterion": "response",
            "method": "test", "case": "module-test@1", "environment": "synthetic-v1", "result": "passed", "evidence": evidence.name})
        issues = readiness(self.root, read_registry(self.root), self.state(), stage="TR4")
        self.assertIn("VERIFICATION_NOT_PASSED:ir-1@1:response", issues)
        self.assertIn("VERIFICATION_NOT_PASSED:sr-1@1:response", issues)
        self.assertNotIn("VERIFICATION_NOT_PASSED:ar-1@1:response", issues)
        evidence.write_text("Evidence changed", encoding="utf-8")
        self.assertIn("VERIFICATION_STALE:case-ar", readiness(self.root, read_registry(self.root), self.state(), stage="TR4"))

    def test_strict_schema_and_pack_locale_parity(self):
        self.enable()
        registry = read_registry(self.root)
        registry["invented"] = True
        with self.assertRaisesRegex(RequirementError, "REQUIREMENT_CONTRACT"):
            validate(registry)
        manifest, _ = load_pack(self.root)
        self.assertEqual(len(manifest["templates"]), 46)
        en = {t["document_type"]: t for t in manifest["templates"] if t["locale"] == "en"}
        zh = {t["document_type"]: t for t in manifest["templates"] if t["locale"] == "zh-CN"}
        self.assertEqual(set(en), set(zh))
        for name in en:
            self.assertEqual(en[name]["sections"], zh[name]["sections"])
            self.assertEqual(en[name]["version"], zh[name]["version"])

    def test_core_review_cannot_approve_ir_at_tr4_without_evidence(self):
        self.basic_scope()
        from ipdctl.requirements import enforce
        gate = next(k for k, v in read_registry(self.root)["stage_map"].items() if v == "TR4")
        with self.assertRaisesRegex(RequirementError, "VERIFICATION_NOT_PASSED"):
            enforce(self.root, self.state(), gate, "gate")

    def test_future_document_obligation_does_not_block_tr1(self):
        self.basic_scope()
        future = next(d["id"] for d in self.state()["deliverables"] if d["phase"] == "plan")
        self.execute("obligation", obligation={"id": "future-interfaces", "requirement": "ir-1@1",
            "owner": future, "document_type": "interface_spec", "keys": ["northbound", "southbound"]})
        registry = read_registry(self.root)
        self.assertEqual(readiness(self.root, registry, self.state(), stage="TR1"), [])
        self.assertIn("DOCUMENT_CARDINALITY:future-interfaces", readiness(self.root, registry, self.state(), stage="TR2", phase="plan"))

    def test_git_source_checks_accepted_evidence_bytes_without_writes(self):
        import subprocess
        from ipdctl.requirements import _accepted_source
        self.basic_scope()
        evidence = self.root / "verification.txt"
        evidence.write_text("Synthetic actual measurement: 1.5 seconds\n", encoding="utf-8")
        self.execute("verification", verification={"id": "source-result", "requirement": "ir-1@1", "criterion": "response", "method": "test", "case": "case@1", "environment": "fixture-v1", "result": "passed", "evidence": evidence.name})
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()
        git("init", "-b", "main")
        git("config", "user.name", "Synthetic source fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("remote", "add", "origin", "https://example.invalid/source.git")
        git("add", ".")
        git("commit", "-m", "Accept synthetic source and evidence")
        source = {"backend": "git", "repository": "https://example.invalid/source.git", "revision": git("rev-parse", "HEAD"), "path": "."}
        before = self.bytes()
        _accepted_source(self.root, source)
        self.assertEqual(before, self.bytes())
        evidence.write_text("Unaccepted working result\n", encoding="utf-8")
        with self.assertRaisesRegex(RequirementError, "BASELINE_SOURCE"):
            _accepted_source(self.root, source)

    def test_svn_source_uses_only_revision_pinned_read_commands(self):
        import subprocess
        from ipdctl.requirements import _accepted_source
        self.basic_scope()
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            relative = args[-1].split("/trunk/", 1)[1].rsplit("@", 1)[0]
            return subprocess.CompletedProcess(args, 0, (self.root / relative).read_bytes(), b"")
        before = self.bytes()
        with patch("ipdctl.requirements.subprocess.run", side_effect=run):
            _accepted_source(self.root, {"backend": "svn", "repository": "https://example.invalid/repo", "revision": "42", "path": "trunk"})
        self.assertEqual(before, self.bytes())
        self.assertTrue(calls)
        self.assertTrue(all(c[:5] == ["svn", "cat", "--non-interactive", "-r", "42"] and c[-1].endswith("@42") for c in calls))

    def test_review_rejects_changed_document_bytes_without_state_writes(self):
        self.basic_scope()
        item = self.prepare_instance()
        self.execute("instantiate", actor="agent", instance=item)
        path = self.root / item["path"]
        path.write_text(re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic fixture content", path.read_text(encoding="utf-8")), encoding="utf-8")
        def invoke(*args):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(list(args))
            return result, stdout.getvalue() + stderr.getvalue()
        self.assertEqual(invoke("close", item["owner"], "--project-root", str(self.root), "--actor", "agent", "--evidence", item["path"])[0], 0)
        self.assertEqual(invoke("review", item["owner"], "--project-root", str(self.root), "--reviewer", "review-agent")[0], 0)
        path.write_text(path.read_text(encoding="utf-8") + "\nChanged evidence content.\n", encoding="utf-8")
        before = self.bytes()
        code, output = invoke("approve", item["owner"], "--project-root", str(self.root), "--reviewer", "human", "--actor-type", "human", "--authorized", "--evidence", item["path"])
        self.assertEqual(code, 1)
        self.assertIn("REVIEW_INPUTS_CHANGED", output)
        self.assertEqual(before, self.bytes())

    def test_dashboard_is_readonly_and_displays_independent_dimensions(self):
        self.basic_scope()
        from ipdctl.project import render_project_dashboard
        before = {k: v for k, v in self.bytes().items() if not k.startswith(".ipd/dashboard/")}
        render_project_dashboard(self.root)
        self.assertEqual(before, {k: v for k, v in self.bytes().items() if not k.startswith(".ipd/dashboard/")})
        index = (self.root / ".ipd/dashboard/index.html").read_text(encoding="utf-8")
        self.assertIn("ipd-requirement-filter", index)
        self.assertIn("ir-1@1", index)
        self.assertIn("VERIFICATION_NOT_PASSED", index)

    def test_two_governed_increments_preserve_baselines_partial_ir_and_exact_reuse(self):
        import subprocess
        def invoke(*args):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(list(args))
            self.assertEqual(code, 0, stdout.getvalue() + stderr.getvalue())
        def git(*args):
            result = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        git("init", "-b", "main")
        git("config", "user.name", "Synthetic acceptance fixture")
        git("config", "user.email", "fixture@example.invalid")
        git("remote", "add", "origin", "https://example.invalid/synthetic.git")
        (self.root / ".gitignore").write_text(".ipd/dashboard/\n.ipd/verify_report.json\n.ipd/reconcile_report.json\n", encoding="utf-8")
        invoke("tailor", str(self.root))
        git("add", ".")
        git("commit", "-m", "Create synthetic project baseline")
        self.enable()
        ir = requirement()
        ir["acceptance"].append({"id": "future", "criterion": "Future scope explicitly deferred", "method": "inspection"})
        self.execute("requirement", requirement=ir)
        self.execute("requirement", requirement=requirement("sr-1", "SR", "ir-1@1"))
        self.execute("requirement", requirement=requirement("ar-1", "AR", "sr-1@1"))
        for reference in ("ir-1@1", "sr-1@1"):
            self.execute("decomposition", requirement=reference, status="complete")
        scoped = [{"requirement": r, "criteria": ["response"]} for r in ("ir-1@1", "sr-1@1", "ar-1@1")]
        self.execute("scope", scope=scoped)
        owner = self.state()["deliverables"][0]["id"]
        for reference in ("ir-1@1", "sr-1@1", "ar-1@1"):
            self.execute("link", link={"requirement": reference, "relation": "satisfied_by", "target": owner, "rationale": "Synthetic allocated implementation"})
            path = "evidence/requirements/" + reference + ".txt"
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text("Synthetic measured elapsed time: 1.5 s at 20 C\n", encoding="utf-8")
            self.execute("verification", verification={"id": "result-" + reference.split("@")[0], "requirement": reference,
                "criterion": "response", "method": "test", "case": "response-case@1", "environment": "synthetic-fixture-v1", "result": "passed", "evidence": path})
        def refresh_verify():
            invoke("refresh", str(self.root))
            invoke("verify", str(self.root), "--json")
        invoke("adopt-baseline", str(self.root), "--actor", "human", "--actor-type", "human", "--authorized", "--reason", "Accept synthetic initial files")
        refresh_verify()
        phases = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")
        for phase in phases:
            for deliverable in [d for d in self.state()["deliverables"] if d["phase"] == phase]:
                identifier = deliverable["id"]
                path = "evidence/" + identifier + ".md"
                invoke("claim", identifier, "--project-root", str(self.root), "--actor", "agent")
                (self.root / path).write_text("Synthetic completed deliverable\n", encoding="utf-8")
                invoke("close", identifier, "--project-root", str(self.root), "--actor", "agent", "--evidence", path)
                invoke("review", identifier, "--project-root", str(self.root), "--reviewer", "review-agent")
                invoke("approve", identifier, "--project-root", str(self.root), "--reviewer", "human", "--actor-type", "human", "--authorized", "--evidence", path)
                refresh_verify()
            while True:
                state = self.state()
                identifier = state["project"]["current_gate"]
                if identifier is None:
                    break
                path = "evidence/gates/" + identifier + ".md"
                (self.root / path).parent.mkdir(parents=True, exist_ok=True)
                invoke("review", identifier, "--project-root", str(self.root), "--reviewer", "review-agent")
                (self.root / path).write_text("Synthetic authorized Gate approval\n", encoding="utf-8")
                invoke("approve", identifier, "--project-root", str(self.root), "--reviewer", "human", "--actor-type", "human", "--authorized", "--evidence", path)
                refresh_verify()
            if phase != "lifecycle":
                invoke("advance-phase", str(self.root))
                refresh_verify()
        git("add", ".")
        git("commit", "-m", "Accept synthetic MVP facts")
        invoke("render-dashboard", str(self.root))
        invoke("verify", str(self.root), "--json")
        source = {"backend": "git", "repository": "https://example.invalid/synthetic.git", "revision": git("rev-parse", "HEAD"), "path": "."}
        self.execute("baseline", id="b1", source=source)
        registry = read_registry(self.root)
        baseline = registry["baselines"][0]
        frozen = (self.root / baseline["path"]).read_bytes()
        prior_revision = self.state()["revision"]
        self.execute("begin", increment="extension", product_version="0.2", base_baseline="b1", scope=scoped)
        self.assertGreater(self.state()["revision"], prior_revision)
        self.assertEqual(self.state()["project"]["phase"], "concept")
        self.assertTrue(all(g["status"] == "planned" for g in self.state()["gates"]))
        self.assertEqual((self.root / baseline["path"]).read_bytes(), frozen)
        for reference in ("ir-1@1", "sr-1@1", "ar-1@1"):
            self.execute("link", link={"requirement": reference, "relation": "satisfied_by", "target": owner,
                "rationale": "Synthetic allocated implementation"})
        (self.root / "evidence/requirements/ir-1@1.txt").write_text("Changed current file\n", encoding="utf-8")
        self.execute("reuse_verification", baseline="b1", result="result-ir-1", id="reuse-ir")
        result = read_registry(self.root)["verifications"][-1]
        self.assertEqual(result["source_baseline"], "b1")
        self.assertIn("1.5 s", (self.root / result["evidence"]).read_text(encoding="utf-8"))
        coverage = next(c for c in projection(self.root)["coverage"] if c["requirement"] == "ir-1@1")
        self.assertEqual(coverage["fulfillment"], "partial")
        self.assertEqual(coverage["accepted_criteria"], ["response"])
        self.assertEqual((self.root / baseline["path"]).read_bytes(), frozen)

        # A later explicit IR re-verification cannot copy the old B1 result.
        self.execute("requirement", requirement=requirement("ar-1", "AR", "sr-1@1", version=2))
        changed_scope = deepcopy(scoped)
        changed_scope[-1]["requirement"] = "ar-1@2"
        self.execute("scope", scope=changed_scope)
        change = read_registry(self.root)["changes"][-1]
        self.execute("assess", change=change["request_id"], assessments=[
            {"target": t, "action": "reverify" if t == "ir-1@1" else "unaffected",
             "rationale": "Synthetic change applicability"} for t in change["affected"]])
        zero = self.bytes()
        with self.assertRaisesRegex(RequirementError, "REUSE_CONTEXT"):
            preview(self.root, self.request("reuse_verification", baseline="b1", result="result-ir-1", id="blocked-reuse"))
        self.assertEqual(zero, self.bytes())
        self.assertEqual((self.root / baseline["path"]).read_bytes(), frozen)


if __name__ == "__main__":
    unittest.main()

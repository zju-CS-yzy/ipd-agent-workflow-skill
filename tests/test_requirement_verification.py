"""Independent negative expectations for re-verification and parent references."""

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

from tests import test_requirements as fixtures
from ipdctl.documents import RequirementError, lint, load_pack, template
from ipdctl.requirement_contract import SCHEMA
from ipdctl.requirements import apply_plan, enforce, preview, projection, read_registry, readiness, ref
from ipdctl.runtime import load_runtime, save_runtime
from ipdctl.state import write_state


ROOT = Path(__file__).resolve().parents[1]


class ReverificationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RequirementTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.basic_scope()
        for identifier, kind, parent in (("sr-1", "SR", "ir-1@1"), ("ar-1", "AR", "sr-1@1")):
            self.f.execute("requirement", requirement=fixtures.requirement(identifier, kind, parent))
        for reference in ("ir-1@1", "sr-1@1"):
            self.f.execute("decomposition", requirement=reference, status="complete")
        self.scope("ar-1@1")
        self.owner = self.f.state()["deliverables"][0]["id"]
        for reference in ("ir-1@1", "sr-1@1", "ar-1@1"):
            self.link(reference)
        self.sequence = 0

    def scope(self, ar):
        self.f.execute("scope", scope=[{"requirement": r, "criteria": ["response"]}
            for r in ("ir-1@1", "sr-1@1", ar)])

    def link(self, reference):
        self.f.execute("link", link={"requirement": reference, "relation": "satisfied_by",
            "target": self.owner, "rationale": "Synthetic current implementation"})

    def record(self, reference, identifier=None, result="passed"):
        self.sequence += 1
        identifier = identifier or f"result-{self.sequence}"
        path = self.f.root / (identifier + ".txt")
        path.write_text("Synthetic observation: 1.5 seconds\n", encoding="utf-8")
        self.last_result_plan = self.f.execute("verification", verification={"id": identifier, "requirement": reference,
            "criterion": "response", "method": "test", "case": "response@1",
            "environment": "synthetic-v1", "result": result, "evidence": path.name})
        return identifier

    def initial_results(self):
        for r in ("ir-1@1", "sr-1@1", "ar-1@1"):
            self.record(r, "old-" + r.split("@")[0])
        self.assertEqual(self.issues(), [])

    def change(self, version=2):
        self.f.execute("requirement", requirement=fixtures.requirement("ar-1", "AR", "sr-1@1", version))
        self.scope(f"ar-1@{version}")
        self.link(f"ar-1@{version}")
        return read_registry(self.f.root)["changes"][-1]

    def assess(self, change, targets):
        self.f.execute("assess", change=change["request_id"], assessments=[
            {"target": t, "action": "reverify" if t in targets else "unaffected",
             "rationale": "Explicit synthetic applicability decision"} for t in change["affected"]])

    def issues(self):
        return readiness(self.f.root, read_registry(self.f.root), self.f.state(), stage="TR4")

    def test_old_and_preassessment_results_cannot_satisfy_reverify_or_gate(self):
        self.initial_results()
        change = self.change()
        self.record("ar-1@2", "new-ar")
        self.record("ir-1@1", "premature-ir")
        self.assess(change, {"ir-1@1"})
        self.assertIn("VERIFICATION_CONTEXT_STALE:premature-ir", self.issues())
        gate = next(g for g, stage in read_registry(self.f.root)["stage_map"].items() if stage == "TR4")
        before = self.f.bytes()
        with self.assertRaisesRegex(RequirementError, "VERIFICATION_CONTEXT_STALE"):
            enforce(self.f.root, self.f.state(), gate, "gate")
        self.assertEqual(self.f.bytes(), before)
        coverage = next(c for c in projection(self.f.root)["coverage"] if c["requirement"] == "ir-1@1")
        self.assertEqual(coverage["verification"]["passed"], 0)
        self.assertEqual(coverage["verification"]["unknown"], 1)
        self.record("ir-1@1", "fresh-ir")
        self.assertEqual(self.issues(), [])
        enforce(self.f.root, self.f.state(), gate, "gate")

    def test_reassessment_requires_another_result_and_failure_does_not_release(self):
        self.initial_results()
        change = self.change()
        self.assess(change, {"ir-1@1"})
        self.record("ar-1@2")
        self.record("ir-1@1", "fresh-once")
        self.assertEqual(self.issues(), [])
        self.assess(change, {"ir-1@1"})
        self.assertIn("VERIFICATION_CONTEXT_STALE:fresh-once", self.issues())
        self.record("ir-1@1", result="failed")
        self.assertIn("VERIFICATION_NOT_PASSED:ir-1@1:response", self.issues())
        self.record("ir-1@1")
        self.assertEqual(self.issues(), [])

    def test_exact_replay_does_not_create_a_fresh_verification(self):
        self.initial_results()
        self.record("ir-1@1", "retried-ir")
        old_plan = self.last_result_plan
        change = self.change()
        self.assess(change, {"ir-1@1"})
        self.record("ar-1@2")
        before = self.f.bytes()
        result = apply_plan(self.f.root, old_plan, actor="human", authorized=True)
        self.assertEqual(result["status"], "already_applied")
        self.assertEqual(self.f.bytes(), before)
        self.assertIn("VERIFICATION_CONTEXT_STALE:retried-ir", self.issues())

    def test_core_deliverable_and_gate_targets_require_fresh_results(self):
        self.initial_results()
        change = self.change()
        gate = next(g for g, stage in read_registry(self.f.root)["stage_map"].items() if stage == "TR4")
        for target in (self.owner, "gate:" + gate):
            with self.subTest(target=target):
                self.assess(change, {target})
                self.record("ar-1@2")
                self.assertTrue(any(i.startswith("VERIFICATION_CONTEXT_STALE:") for i in self.issues()))
                for r in ("ir-1@1", "sr-1@1"):
                    self.record(r)
                self.assertEqual(self.issues(), [])

    def test_future_candidate_does_not_invalidate_current_scope(self):
        self.initial_results()
        self.f.execute("requirement", requirement=fixtures.requirement("ar-1", "AR", "sr-1@1", 2))
        self.assertEqual(self.issues(), [])

    def test_shared_document_assessment_and_content_change_invalidate_context(self):
        item = self.f.prepare_instance("en", "shared")
        self.f.execute("instantiate", actor="agent", instance=item)
        path = self.f.root / item["path"]
        path.write_text(re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic completed design", path.read_text(encoding="utf-8")), encoding="utf-8")
        # Complete isolated fixture setup. Claim/review lifecycle is covered
        # separately; this case tests verification applicability.
        runtime = load_runtime(self.f.root)
        runtime["active_claims"] = {}
        save_runtime(self.f.root, runtime)
        state = self.f.state()
        state["project"]["workflow_step"] = "refresh"
        write_state(self.f.root / ".ipd/project_state.yaml", state)
        self.initial_results()
        change = self.change()
        self.assess(change, {"instance:" + item["id"]})
        self.record("ar-1@2")
        self.assertIn("VERIFICATION_CONTEXT_STALE:old-ir-1", self.issues())
        self.record("ir-1@1", "fresh-design-result")
        self.assertEqual(self.issues(), [])
        path.write_text(path.read_text(encoding="utf-8") + "\nUpdated design decision\n", encoding="utf-8")
        self.assertIn("VERIFICATION_CONTEXT_STALE:fresh-design-result", self.issues())

    def test_superseding_ar_does_not_drop_an_earlier_reverification(self):
        self.initial_results()
        first = self.change()
        self.assess(first, {"ir-1@1"})
        second = self.change(3)
        self.assess(second, set())
        self.record("ar-1@3")
        self.assertIn("VERIFICATION_CONTEXT_STALE:old-ir-1", self.issues())
        self.record("ir-1@1")
        self.assertEqual(self.issues(), [])

    def test_legacy_unbound_result_is_readable_but_not_current_proof(self):
        self.initial_results()
        registry = read_registry(self.f.root)
        registry["verifications"][0].pop("context_sha256")
        write_state(self.f.root / ".ipd/requirements.yaml", registry)
        before = self.f.bytes()
        self.assertIn("VERIFICATION_CONTEXT_UNKNOWN:old-ir-1", self.issues())
        self.assertEqual(self.f.bytes(), before)

    def test_explicit_pack_change_invalidates_previous_result_context(self):
        import shutil
        self.initial_results()
        pack, directory = load_pack(self.f.root)
        private = self.f.root / "private-pack"
        shutil.copytree(directory, private)
        pack.update(id="synthetic-pack", version="1.0.0", layer="project")
        (private / "manifest.json").write_text(json.dumps(pack), encoding="utf-8")
        self.f.publish_pack("private-pack")
        self.f.execute("pin_templates", path="private-pack")
        self.assertIn("VERIFICATION_CONTEXT_STALE:old-ir-1", self.issues())

    def test_caller_cannot_stamp_context_or_duplicate_assessment_targets(self):
        before = self.f.bytes()
        evidence = self.f.root / "observation.txt"
        evidence.write_text("Synthetic observation\n", encoding="utf-8")
        before = self.f.bytes()
        with self.assertRaisesRegex(RequirementError, "VERIFICATION_SOURCE"):
            preview(self.f.root, self.f.request("verification", verification={"context_sha256": "0" * 64}))
        self.assertEqual(self.f.bytes(), before)
        change = self.change()
        assessments = [{"target": t, "action": "unaffected", "rationale": "Synthetic decision"} for t in change["affected"]]
        before = self.f.bytes()
        with self.assertRaisesRegex(RequirementError, "IMPACT_UNKNOWN"):
            preview(self.f.root, self.f.request("assess", change=change["request_id"], assessments=assessments + [assessments[0]]))
        self.assertEqual(self.f.bytes(), before)


class RegisterReferenceTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / "docs/worked-projects/room-booking"
        self.model = json.loads((self.base / "document-instances.json").read_text(encoding="utf-8"))
        catalog = json.loads((self.base / "catalog.json").read_text(encoding="utf-8"))
        self.canonical = {r["ref"]: r for r in catalog["requirements"]}

    def documents(self):
        for locale in ("en", "zh-CN"):
            for filename in ("SR-TR2.md", "AR-TR3.md"):
                d = next(d for d in self.model["documents"] if d["path"] == locale + "/" + filename)
                instance = d["instance"]
                record, source = template(ROOT, d["pack"], instance["document_type"], locale)
                text = (self.base / d["path"]).read_text(encoding="utf-8")
                yield instance, source, record, text

    def test_parent_references_reject_missing_wrong_kind_and_wrong_exact_version(self):
        for instance, source, record, text in self.documents():
            child = instance["requirements"][0]
            parent = self.canonical[child]["parent"]
            canonical = deepcopy(self.canonical)
            parent2 = parent.rsplit("@", 1)[0] + "@2"
            canonical[parent2] = {**canonical[parent], "version": 2}
            self.assertEqual(lint(text, instance, source, record["sections"], canonical=canonical), [])
            for replacement, code in (("missing-parent@999", "DOCUMENT_PARENT_REFERENCE"),
                                      (child, "DOCUMENT_PARENT_KIND"),
                                      (parent2, "DOCUMENT_PARENT_MISMATCH"),
                                      ("N/A: ignored", "DOCUMENT_PARENT_FORMAT")):
                with self.subTest(locale=instance["locale"], kind=instance["document_type"], replacement=replacement):
                    issues = lint(text.replace(parent, replacement), instance, source, record["sections"], canonical=canonical)
                    self.assertTrue(any(i.startswith(code + ":") for i in issues), issues)

    def test_missing_reference_context_fails_closed(self):
        for instance, source, record, text in self.documents():
            self.assertIn("DOCUMENT_REFERENCE_CONTEXT", lint(text, instance, source, record["sections"]))

    def test_shared_cell_cannot_hide_different_canonical_parents_or_child_kind(self):
        for instance, source, record, text in self.documents():
            canonical = deepcopy(self.canonical)
            second = instance["requirements"][1]
            canonical[second]["parent"] = "ir-02@1" if instance["document_type"] == "sr_spec" else "sr-02@1"
            self.assertIn("DOCUMENT_PARENT_MISMATCH:" + second,
                lint(text, instance, source, record["sections"], canonical=canonical))
            first = instance["requirements"][0]
            canonical[first]["kind"] = "IR"
            self.assertIn("DOCUMENT_REQUIREMENT_KIND:" + first,
                lint(text, instance, source, record["sections"], canonical=canonical))

    def test_private_or_legacy_format_cannot_omit_the_parent_column(self):
        for instance, source, record, text in self.documents():
            without_parent = source.replace('data-ipd-column="parent"', 'data-ipd-column="prose"')
            self.assertIn("DOCUMENT_PARENT_COLUMN",
                lint(text, instance, without_parent, record["sections"], canonical=self.canonical))

    def test_shared_parent_cell_can_only_waive_explicitly_derived_rows(self):
        for instance, source, record, text in self.documents():
            parent = self.canonical[instance["requirements"][0]]["parent"]
            canonical = deepcopy(self.canonical)
            derived = text.replace(parent, "derived: independent safety constraint")
            self.assertTrue(any(i.startswith("DOCUMENT_PARENT_FORMAT") for i in lint(derived, instance, source, record["sections"], canonical=canonical)))
            for requirement in canonical.values():
                if requirement["parent"] == parent:
                    requirement.update(parent=None, derived=True)
            self.assertEqual(lint(derived, instance, source, record["sections"], canonical=canonical), [])
            self.assertTrue(any(i.startswith("DOCUMENT_DERIVED_REASON") for i in lint(text, instance, source, record["sections"], canonical=canonical)))

    def test_published_schema_keeps_legacy_fields_and_current_fingerprint(self):
        schema = json.loads((ROOT / "schemas/requirements.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema, SCHEMA)

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from ipdctl.cli import main
from ipdctl.documents import RequirementError
from ipdctl.increment_planning import apply, display, preview, read
from ipdctl.project import render_project_dashboard
from ipdctl.stage_flow import anchor
from ipdctl.state import write_state
from ipdctl.version_context import inventory
import test_requirements


class IncrementPlanningTests(unittest.TestCase):
    def setUp(self):
        self.project = test_requirements.RequirementTests()
        self.project.setUp()
        self.addCleanup(self.project.doCleanups)
        self.root = self.project.root
        self.project.basic_scope()

    def test_planning_merge_renumbers_display_and_preserves_execution_facts(self):
        facts = self.project.bytes()
        for number in range(1, 5):
            request = self.project.request("add", id=f"inc-{number:02}", title=f"Feature {number}")
            source = self.root / "request.yaml"
            write_state(source, request)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["increment-plan", str(self.root), "--request", str(source)]), 0)
            plan = json.loads(output.getvalue())
            self.assertEqual(plan["candidates"][-1]["display_order"], number)
            apply(self.root, plan, actor="planner", authorized=True)
        self.assertEqual(display(read(self.root))[2]["id"], "inc-03")
        request = self.project.request("merge", ids=["inc-01", "inc-02"], increment="mvp")
        before = self.project.bytes()
        plan = preview(self.root, request)
        self.assertEqual(before, self.project.bytes())
        with self.assertRaisesRegex(RequirementError, "AUTHORIZATION_REQUIRED"):
            apply(self.root, plan, actor="planner", authorized=False)
        apply(self.root, plan, actor="planner", authorized=True)
        self.assertEqual(apply(self.root, plan, actor="planner", authorized=True)["status"], "already_applied")
        records = display(read(self.root))
        self.assertEqual([(r["id"], r["status"], r["display_order"], r["increment"]) for r in records],
                         [("inc-01", "merged", None, "mvp"), ("inc-02", "merged", None, "mvp"),
                          ("inc-03", "candidate", 1, None), ("inc-04", "candidate", 2, None)])
        for path, content in facts.items():
            self.assertEqual((self.root / path).read_bytes(), content, path)
        render_project_dashboard(self.root)
        html = (self.root / ".ipd/dashboard/index.html").read_text(encoding="utf-8")
        self.assertIn('id="' + anchor("candidate-", "inc-01") + '"', html)
        self.assertIn("Increment 1 · Feature 3", html)
        self.assertIn("Increment 2 · Feature 4", html)

    def test_reorder_rejects_stale_or_duplicate_plans(self):
        plans = [preview(self.root, self.project.request("add", id=key, title=key))
                 for key in ("future-a", "future-b")]
        apply(self.root, plans[0], actor="planner", authorized=True)
        with self.assertRaisesRegex(RequirementError, "PLAN_STALE"):
            apply(self.root, plans[1], actor="planner", authorized=True)
        with self.assertRaisesRegex(RequirementError, "INCREMENT_PLAN_ORDER"):
            preview(self.root, self.project.request("reorder", order=["future-a", "future-a"]))

    def test_old_pin_remains_distinct_from_shipped_and_active_pack(self):
        from ipdctl.documents import digest, load_pack
        from ipdctl.requirements import read_registry

        registry = read_registry(self.root)
        pin = {"id": "ipd-starter", "version": "1.2.1", "path": "", "layer": "core"}
        old_pack, _ = load_pack(self.root, pin)
        pin["sha256"] = digest(old_pack)
        registry["template_pack"] = pin
        old = self.project.bytes()
        versions = inventory(self.root, registry, process_schema="2.0", runtime_schema="1.1")
        self.assertEqual(versions["templates"]["project_pin"]["version"], "1.2.1")
        self.assertEqual(versions["templates"]["active_increment_pin"]["version"], "1.3.0")
        self.assertEqual(versions["templates"]["shipped"]["version"], "1.3.0")
        self.assertTrue(versions["upgrade_preview"]["project_pin_differs_from_shipped"])
        self.assertEqual(old, self.project.bytes())

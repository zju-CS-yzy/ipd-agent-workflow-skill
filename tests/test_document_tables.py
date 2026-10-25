"""Multi-row specifications and immutable starter-pack compatibility."""

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from ipdctl.document_tables import lint_tables
from ipdctl.documents import RequirementError, digest, instantiate, lint, load_pack, template


ROOT = Path(__file__).resolve().parents[1]


class DocumentTableTests(unittest.TestCase):
    def filled(self, kind="ir_spec", locale="zh-CN", count=2):
        pack, _ = load_pack(ROOT)
        record, source = template(ROOT, {}, kind, locale)
        instance = {"id": "requirements-register", "increment": "mvp", "owner": "concept.scope",
                    "requirements": [f"{kind[:2]}-{n}@1" for n in range(1, count + 1)],
                    "document_type": kind, "template_id": record["id"], "template_version": record["version"],
                    "template_sha256": record["sha256"], "locale": locale, "scope": "Synthetic increment",
                    "title": "Synthetic multi-requirement fixture"}
        text = instantiate(source, instance)
        match = re.search(r'<table data-ipd-table="requirements">.*?</table>', text, re.S)
        tree = ET.fromstring(match[0])
        body = tree.find("tbody")
        first = deepcopy(body[0])
        body.clear()
        for n in range(1, count + 1):
            row = deepcopy(first)
            row[0].text = instance["requirements"][n - 1]
            for cell in list(row):
                if "rowspan" in cell.attrib:
                    if n == 1:
                        cell.set("rowspan", str(count))
                    else:
                        row.remove(cell)
            body.append(row)
        text = text[:match.start()] + ET.tostring(tree, encoding="unicode") + text[match.end():]
        text = re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic facts and source@1", text)
        if kind in {"sr_spec", "ar_spec"}:
            parent = "ir-parent@1" if kind == "sr_spec" else "sr-parent@1"
            # These cells represent exact machine references, not prose.
            text = re.sub(r'(<td rowspan="[0-9]+">)Synthetic facts and source@1', r'\g<1>' + parent, text, count=1)
        return text, instance, source, record

    def canonical(self, instance):
        kind = instance["document_type"][:2].upper()
        parent = {"SR": "ir-parent@1", "AR": "sr-parent@1"}.get(kind)
        result = {r: {"kind": kind, "parent": parent, "derived": False} for r in instance["requirements"]}
        if parent:
            result[parent] = {"kind": "IR" if kind == "SR" else "SR", "parent": None}
        return result

    def test_all_registers_support_one_two_and_many_rows_in_both_locales(self):
        for kind in ("ir_spec", "sr_spec", "ar_spec"):
            for locale in ("en", "zh-CN"):
                for count in (1, 2, 12):
                    with self.subTest(kind=kind, locale=locale, count=count):
                        text, instance, source, record = self.filled(kind, locale, count)
                        self.assertEqual(lint(text, instance, source, record["sections"], canonical=self.canonical(instance)), [])

    def test_exact_row_manifest_rejects_missing_duplicate_and_extra_requirements(self):
        text, instance, source, _ = self.filled()
        for changed in (text.replace("ir-2@1</td>", "ir-1@1</td>"),
                        text.replace("ir-2@1</td>", "ir-3@1</td>"),
                        text.replace("ir-2@1</td>", "ir-2@2</td>")):
            self.assertIn("DOCUMENT_REQUIREMENT_ROWS", lint_tables(changed, source, instance["requirements"]))
        self.assertIn("DOCUMENT_REQUIREMENT_ROWS", lint_tables(text, source, instance["requirements"] + ["ir-3@1"]))

    def test_identity_cannot_be_merged_even_when_span_geometry_is_valid(self):
        text, instance, source, _ = self.filled()
        changed = text.replace("<td>ir-1@1</td>", '<td rowspan="2">ir-1@1</td>').replace("<td>ir-2@1</td>", "")
        self.assertIn("DOCUMENT_REQUIREMENT_ID_MERGED", lint_tables(changed, source, instance["requirements"]))

    def test_invalid_spans_and_blank_cells_are_not_completed_content(self):
        text, instance, source, _ = self.filled()
        for span in ('"0"', '"3"', '"two"', '"-1"', '"2.0"'):
            with self.subTest(span=span):
                changed = text.replace('rowspan="2"', 'rowspan=' + span, 1)
                self.assertIn("DOCUMENT_TABLE_SPANS", lint_tables(changed, source, instance["requirements"]))
        self.assertIn("DOCUMENT_TABLE_SPANS", lint_tables(text.replace('rowspan="2"', 'rowspan', 1), source, instance["requirements"]))
        blank = text.replace("Synthetic facts and source@1</td>", "</td>", 1)
        self.assertIn("DOCUMENT_FIELDS", lint_tables(blank, source, instance["requirements"]))
        bare_na = text.replace("Synthetic facts and source@1</td>", "不适用</td>", 1)
        self.assertIn("DOCUMENT_NA_REASON", lint_tables(bare_na, source, instance["requirements"]))

    def test_missing_columns_tables_or_broken_markup_fail_closed(self):
        text, instance, source, _ = self.filled()
        self.assertIn("DOCUMENT_COLUMNS", lint_tables(text.replace('data-ipd-column="owner"', 'data-ipd-column="other"'), source, instance["requirements"]))
        self.assertIn("DOCUMENT_TABLES", lint_tables(text.replace('data-ipd-table="requirements"', 'data-ipd-table="other"'), source, instance["requirements"]))
        self.assertIn("DOCUMENT_TABLE_SPANS", lint_tables(text.replace('<td>ir-2@1</td>', ''), source, instance["requirements"]))
        for changed in (text.replace("</table>", ""), text.replace("<tbody>", '<tbody><script>untrusted()</script>'),
                        text.replace("<tbody>", '<tbody onclick="untrusted()">')):
            self.assertIn("DOCUMENT_TABLE_MARKUP", lint_tables(changed, source, instance["requirements"]))

    def test_previous_pin_loads_original_bytes_not_new_register(self):
        previous = ROOT / "ipdctl/document_templates/archives/ipd-starter-1.0.0"
        old = json.loads((previous / "manifest.json").read_text(encoding="utf-8"))
        pin = {"id": "ipd-starter", "version": "1.0.0", "sha256": digest(old)}
        manifest, directory = load_pack(ROOT, pin)
        self.assertEqual(directory, previous)
        self.assertEqual(len(manifest["templates"]), 28)
        _, source = template(ROOT, pin, "ir_spec", "zh-CN")
        self.assertIn("## 用户场景与范围", source)
        self.assertNotIn('data-ipd-table="requirements"', source)
        with self.assertRaisesRegex(RequirementError, "TEMPLATE_PIN"):
            load_pack(ROOT, {**pin, "sha256": "0" * 64})

    def test_stage_drafts_are_bilingual_and_do_not_fake_completed_results(self):
        pack, directory = load_pack(ROOT)
        self.assertEqual(pack["version"], "1.3.0")
        for stage_type in ("tr1_requirements_feasibility", "tr2_scenarios_allocation",
                           "tr3_high_level_design", "tr4_detail_implementation_test"):
            for locale in ("en", "zh-CN"):
                record, source = template(ROOT, {}, stage_type, locale)
                self.assertEqual(record["version"], "0.2.1")
                self.assertIn("[[TODO:", source)
                self.assertTrue("讨论稿" in source if locale == "zh-CN" else "Discussion draft" in source)
                instance = {"id": "stage-overview", "increment": "mvp", "owner": "concept.scope",
                            "requirements": ["ir-1@1"], "document_type": stage_type,
                            "template_id": record["id"], "template_version": record["version"],
                            "template_sha256": record["sha256"], "locale": locale,
                            "scope": "Synthetic stage", "title": "Synthetic stage overview"}
                filled = re.sub(r"\[\[TODO:[^\]]+\]\]", "Synthetic facts and source@1", instantiate(source, instance))
                self.assertEqual(lint(filled, instance, source, record["sections"]), [])

    def test_previous_stage_pack_keeps_its_original_sections_and_bytes(self):
        for version, stage_version in (("1.1.0", "0.1.0"), ("1.2.0", "0.2.0")):
            previous = ROOT / ("ipdctl/document_templates/archives/ipd-starter-" + version)
            old = json.loads((previous / "manifest.json").read_text(encoding="utf-8"))
            pin = {"id": old["id"], "version": old["version"], "sha256": digest(old)}
            manifest, directory = load_pack(ROOT, pin)
            self.assertEqual(directory, previous)
            self.assertEqual(len(manifest["templates"]), 36)
            for locale in ("en", "zh-CN"):
                for kind in ("tr2_scenarios_allocation", "tr3_high_level_design"):
                    old_record, old_source = template(ROOT, pin, kind, locale)
                    self.assertEqual(old_record["version"], stage_version)
                    self.assertEqual(old_source, (previous / old_record["path"]).read_text(encoding="utf-8"))
                    new_record, new_source = template(ROOT, {}, kind, locale)
                    self.assertNotEqual(new_record["sha256"], old_record["sha256"])
                    if version == "1.1.0":
                        self.assertNotIn("decomposition", old_record["sections"])
                        self.assertNotEqual(new_record["sections"], old_record["sections"])
                    else:
                        self.assertEqual(new_record["sections"], old_record["sections"])


if __name__ == "__main__":
    unittest.main()

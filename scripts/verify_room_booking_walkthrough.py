#!/usr/bin/env python3
"""Check the public synthetic worked documents; never writes project facts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ipdctl.documents import lint, template


def check(root: Path, execute: bool = False) -> dict:
    project = root / "docs/worked-projects/room-booking"
    catalog = json.loads((project / "catalog.json").read_text(encoding="utf-8"))
    requirements = {item["ref"]: item for item in catalog["requirements"]}
    assert len(requirements) == 21, "duplicate or missing requirements"
    groups = {kind: {ref for ref, item in requirements.items() if item["kind"] == kind}
              for kind in ("IR", "SR", "AR")}
    assert {kind: len(refs) for kind, refs in groups.items()} == {"IR": 3, "SR": 6, "AR": 12}
    for ref, item in requirements.items():
        parent = item["parent"]
        if item["kind"] == "IR":
            assert parent is None
        else:
            assert parent in requirements, ref
            assert requirements[parent]["kind"] == {"SR": "IR", "AR": "SR"}[item["kind"]]
        for field in ("statement", "argument", "choice"):
            assert set(item[field]) == {"en", "zh-CN"} and all(item[field].values()), (ref, field)
    for kind in ("IR", "SR"):
        assert all(any(item["parent"] == ref for item in requirements.values()) for ref in groups[kind])

    model = json.loads((project / "document-instances.json").read_text(encoding="utf-8"))
    assert len(model["documents"]) == 16
    expectations = {"TR1.md": groups["IR"], "TR2.md": groups["IR"] | groups["SR"],
                    "TR3.md": groups["SR"] | groups["AR"], "TR4.md": set(requirements),
                    "IR-TR1.md": groups["IR"], "SR-TR2.md": groups["SR"],
                    "AR-TR3.md": groups["AR"], "AR-TR4.md": groups["AR"]}
    for document in model["documents"]:
        path = project / document["path"]
        text = path.read_text(encoding="utf-8")
        instance = document["instance"]
        record, source = template(root, document["pack"], instance["document_type"], instance["locale"])
        assert not lint(text, instance, source, record["sections"], canonical=requirements), document["path"]
        assert set(instance["requirements"]) == expectations[path.name], document["path"]

    for locale in ("zh-CN", "en"):
        texts = {name: (project / locale / name).read_text(encoding="utf-8") for name in expectations}
        for kind, name in (("IR", "TR1.md"), ("SR", "TR2.md"), ("AR", "TR3.md")):
            for ref in groups[kind]:
                identifier = requirements[ref]["record"]
                assert texts[name].count('<a id="' + identifier + '"></a>') == 1, (locale, ref)
                assert requirements[ref]["statement"][locale] in texts[name], (locale, ref)
        assert not re.search(r"sr-\d+@\d+|ar-\d+@\d+", texts["IR-TR1.md"])
        assert not re.search(r"ar-\d+@\d+", texts["SR-TR2.md"])
        assert "verification.json" not in texts["AR-TR3.md"], "future evidence leaked into TR3"
        assert "verification.json" in texts["AR-TR4.md"]
        for ref in groups["AR"]:
            assert texts["TR4.md"].count('<a id="impl-' + requirements[ref]["id"] + '"></a>') == 1

    link_count = 0
    for path in project.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\[\[TODO:|\{\{", text), path.name
        links = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'<a href="([^"]+)"', text)
        for href in links:
            href = html.unescape(href)
            if href.startswith(("https:", "http:")):
                continue
            relative, _, fragment = href.partition("#")
            target = (path.parent / relative).resolve() if relative else path.resolve()
            assert target.is_relative_to(root.resolve()), (path, href)
            assert target.is_file(), (path, href)
            if fragment:
                target_text = target.read_text(encoding="utf-8")
                assert 'id="' + fragment + '"' in target_text, (path, href)
            link_count += 1

    evidence = json.loads((project / "evidence/verification.json").read_text(encoding="utf-8"))
    assert evidence["total"] == evidence["passed"] == 21
    assert evidence["human_acceptance"] == "not_performed"
    assert evidence["governance_approval"] == "not_granted"
    for name, value in evidence["source_sha256"].items():
        assert hashlib.sha256((project / "implementation" / name).read_bytes()).hexdigest() == value, name
    results = {row["requirement"]: row for row in evidence["cases"]}
    assert set(results) == set(requirements)
    for ref, row in results.items():
        assert row["criterion"] == requirements[ref]["criterion"]
        assert row["id"] == requirements[ref]["case"]
        assert row["result"] == "passed" and row["actual"] == row["expected"]

    source = ast.parse((project / "implementation/booking.py").read_text(encoding="utf-8"))
    symbols = {node.name for node in source.body if isinstance(node, ast.FunctionDef)}
    for node in source.body:
        if isinstance(node, ast.ClassDef):
            symbols.update(node.name + "." + method.name for method in node.body if isinstance(method, ast.FunctionDef))
    for item in requirements.values():
        owner = ""
        for symbol in item["code"].split("/"):
            if "." in symbol:
                owner = symbol.rsplit(".", 1)[0] + "."
            elif owner:
                symbol = owner + symbol
            assert symbol in symbols, (item["ref"], symbol)
    if execute:
        run = subprocess.run([sys.executable, str(project / "implementation/verify_demo.py")],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        fresh = json.loads(run.stdout)
        assert fresh["cases"] == evidence["cases"], "fresh execution differs from saved case evidence"
        assert fresh["source_sha256"] == evidence["source_sha256"]
    return {"result": "passed", "documents": 16, "requirements": {k: len(v) for k, v in groups.items()},
            "derivations_per_locale": 21, "local_links": link_count, "software_cases": 21,
            "fresh_execution": execute, "human_approval": "not_granted"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--execute", action="store_true", help="rerun the synthetic software cases")
    args = parser.parse_args()
    print(json.dumps(check(args.root, args.execute), ensure_ascii=False, indent=2))

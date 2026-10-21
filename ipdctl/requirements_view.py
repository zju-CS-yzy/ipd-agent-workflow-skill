"""Escaped, read-only requirement navigation inside the existing Dashboard."""

from __future__ import annotations

import html
from pathlib import Path

from .requirements import projection, ref


def panel(root: Path, locale: str) -> tuple[dict | None, str]:
    data = projection(root)
    if data is None:
        return None, ""
    zh = locale == "zh-CN"
    esc = lambda value: html.escape(str(value), quote=True)
    title = "渐进需求、增量与交付件" if zh else "Progressive requirements, increments and documents"
    hint = "此视图只读；定义、分解、文档、实现和验证分别展示。未知与跳过均不代表通过。" if zh else "Read-only view. Definition, decomposition, documents, implementation and verification are separate. Unknown and skipped results are not passes."
    rows = []
    for r in sorted(data["requirements"], key=lambda r: ({"IR": 0, "SR": 1, "AR": 2}[r["kind"]], r["id"], r["version"])):
        reference = ref(r)
        instances = [i for i in data["instances"] if reference in i["requirements"]]
        results = [v for v in data["verifications"] if v["requirement"] == reference]
        members = [i["id"] for i in data["increments"] if any(s["requirement"] == reference for s in i["scope"])]
        outputs = []
        for instance in instances:
            baseline = next((b for b in data["baselines"] if b["increment"] == instance["increment"]), None)
            link = "../requirement_history/" + Path(baseline["path"]).name if baseline else "../../" + instance["path"]
            outputs.append('<a href="' + esc(link) + '">' + esc(instance["id"]) + '</a> (' + esc(instance["key"]) + '; ' + esc(instance["template_id"] + "@" + instance["template_version"]) + ")")
        outputs = "<br>".join(outputs)
        outcomes = "; ".join(v["criterion"] + ":" +
            ("unknown [" + data["verification_diagnostics"][v["id"]] + "]"
             if v["id"] in data["verification_diagnostics"] else v["result"]) +
            " (" + v["increment"] + ")" for v in results) or "unknown"
        coverage = next(c for c in data["coverage"] if c["requirement"] == reference)
        fields = [reference, r["kind"], r["title"], r["parent"] or "—", ", ".join(members) or "future",
                  r["module"], r["owner"], r["priority"], r["maturity"], r["decomposition"]]
        button = '<button type="button" data-requirement-toggle="' + esc(reference) + '" aria-expanded="true">−</button> '
        cells = '<td>' + button + esc(reference) + '</td>' + "".join("<td>" + esc(v) + "</td>" for v in fields[1:])
        rows.append('<tr data-requirement-ref="' + esc(reference) + '" data-requirement-parent="' + esc(r["parent"] or "") + '" data-ipd-requirement="' + esc(" ".join(map(str, fields)) + " " + outcomes) + '">' + cells + "<td>" + outputs + "</td><td>" + esc(coverage["implementation"]) + "</td><td>" + esc(outcomes) + "</td><td>" + esc(coverage["fulfillment"]) + "</td></tr>")
    headings = (["需求版本", "层级", "标题", "上层版本", "增量", "模块", "责任", "优先级", "定义", "分解", "交付件 / 模板", "实现", "验证（分层独立）", "全量满足"] if zh else
                ["Requirement", "Kind", "Title", "Parent version", "Increment", "Module", "Owner", "Priority", "Definition", "Decomposition", "Documents / templates", "Implementation", "Verification (independent levels)", "Full-scope fulfillment"])
    issues = "".join("<li>" + esc(d) + "</li>" for d in data["diagnostics"])
    changes = "".join("<li>" + esc(c["old"] + " → " + c["new"] + ": " + ", ".join(c["affected"])) + "</li>" for c in data["changes"])
    baselines = "".join('<li><a href="../requirement_history/' + esc(Path(b["path"]).name) + '">' + esc(b["id"]) + "</a> " + esc(b["sha256"]) + "</li>" for b in data["baselines"])
    # One search accepts any combination of increment, version, module, owner,
    # priority, maturity and result; all inserted values are escaped text.
    content = '<section id="ipd-requirements"><h2>' + title + "</h2><p>" + hint + '</p><label>' + ("筛选" if zh else "Filter") + ' <input id="ipd-requirement-filter" type="search"></label><div style="overflow:auto"><table><thead><tr>' + "".join("<th>" + h + "</th>" for h in headings) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div><ul>" + issues + "</ul><ul>" + changes + "</ul><ul>" + baselines + "</ul></section>"
    content += r'''<script>(()=>{const input=document.getElementById('ipd-requirement-filter'),rows=[...document.querySelectorAll('[data-ipd-requirement]')],collapsed=new Set(),parents=new Map(rows.map(row=>[row.dataset.requirementRef,row.dataset.requirementParent]));function update(){const words=input.value.toLowerCase().split(/\s+/).filter(Boolean);rows.forEach(row=>{let parent=row.dataset.requirementParent,hidden=false;const seen=new Set();while(parent&&!seen.has(parent)){seen.add(parent);hidden=hidden||collapsed.has(parent);parent=parents.get(parent);}row.hidden=hidden||!words.every(word=>row.dataset.ipdRequirement.toLowerCase().includes(word));});}input.addEventListener('input',update);document.querySelectorAll('[data-requirement-toggle]').forEach(button=>button.addEventListener('click',()=>{const ref=button.dataset.requirementToggle;if(collapsed.has(ref)){collapsed.delete(ref);button.textContent='−';button.setAttribute('aria-expanded','true');}else{collapsed.add(ref);button.textContent='+';button.setAttribute('aria-expanded','false');}update();}));})();</script>'''
    return data, content

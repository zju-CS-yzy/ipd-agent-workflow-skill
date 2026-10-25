"""Derived work-product graph; narrative edges never mutate execution facts."""
from __future__ import annotations

import hashlib
import html
import json
import re
from urllib.parse import quote
from .documents import safe_path
from .stage_organization import codes, unit_issues


def anchor(prefix, value):
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:16]


def ordered_requirements(registry):
    mapping, children = codes(registry), {}
    records = {r["id"] + "@" + str(r["version"]): r for r in registry["requirements"]}
    for exact, r in records.items():
        children.setdefault(r["parent"] if r["parent"] in records else None, []).append(exact)
    def key(exact):
        return tuple((1, int(x)) if x.isdigit() else (0, x) for x in re.split(r"(\d+)", mapping.get(exact, exact)))
    def walk(parent, depth):
        for exact in sorted(children.get(parent, []), key=key):
            yield records[exact], depth
            yield from walk(exact, depth + 1)
    return list(walk(None, 0))


def projection(root, registry, state):
    org, mapping = registry["organization"], codes(registry)
    records = {r["id"] + "@" + str(r["version"]): r for r in registry["requirements"]}
    instances = {i["id"]: i for i in registry["instances"]}
    from .documents import lint_instances
    from .template_publications import live_instances
    documents = lint_instances(root, [i for i in live_instances(registry) if i["increment"] == registry["active_increment"]], records)
    core = {d["id"]: d for d in state["deliverables"]}
    nodes, edges, units, reverse = {}, set(), [], {}
    historical_states = {}
    verification_diagnostics = {}
    def add(key, kind, label, **fields):
        nodes.setdefault(key, {"id": key, "type": kind, "label": label, **fields})
        return key
    def req(exact):
        return add("requirement:" + exact, "Requirement", mapping.get(exact, exact), reference=exact,
                   href="#" + anchor("rq-", exact), title=records[exact]["title"])
    def document(unit, target, support=None):
        artifact = support and support["kind"] == "artifact"
        item = instances.get(target) if not artifact else None
        path_text = target if artifact else item["path"] if item else None
        owner = support["owner"] if support else item["owner"] if item else unit["owner"]
        expected = support["sha256"] if support else None
        baseline = next((b for b in registry["baselines"] if b["increment"] == unit["increment"]), None)
        href, status = None, "planned"
        if baseline:
            href, status = "../requirement_history/" + quote(baseline["path"].rsplit("/", 1)[1]), "historical"
        elif path_text:
            try:
                path = safe_path(root, path_text)
                if path.is_file():
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    status = "stale" if support and actual != expected else "current"
                    href = "../../" + quote(path_text, safe="/")
                    if support and support["anchor"]:
                        href += "#" + quote(support["anchor"], safe="")
                else:
                    status = "missing"
            except (ValueError, OSError):
                status = "invalid"
        token = ("artifact:" if artifact else "instance:") + target
        key = unit["increment"] + ":" + token + (":" + str(expected) if support else "")
        add(key, "Artifact" if artifact else "DocumentInstance", target, path=path_text,
            owner=owner, href=href, availability=status, sha256=expected, reverse_key=token,
            template=(item["template_id"] + "@" + item["template_version"]) if item else None)
        owner_state = core
        if baseline:
            if baseline["id"] not in historical_states:
                snapshot = json.loads(safe_path(root, baseline["path"]).read_text(encoding="utf-8"))
                historical_states[baseline["id"]] = {d["id"]: d for d in snapshot["state"]["deliverables"]}
            owner_state = historical_states[baseline["id"]]
        owner_key = add("owner:" + unit["increment"] + ":" + owner, "Deliverable", owner, core_id=owner,
                        increment=unit["increment"], status=owner_state.get(owner, {}).get("status", "unknown"),
                        href=href if baseline else "#deliverable-matrix")
        edges.add((key, owner_key, "owned_by"))
        record = reverse.setdefault(token, {"units": [], "requirements": [], "increments": [], "baselines": []})
        for field, values in (("units", [unit["id"]]), ("requirements", unit["inputs"] + unit["outputs"]),
                              ("increments", [unit["increment"]]), ("baselines", [baseline["id"]] if baseline else [])):
            record[field] = sorted(set(record[field]) | set(values))
        return key
    for unit in org["units"]:
        inputs, outputs = [req(r) for r in unit["inputs"]], [req(r) for r in unit["outputs"]]
        materials = [document(unit, s["target"], s) for s in unit["supports"]]
        conclusions = [document(unit, key) for key in (unit["conclusion"], unit["register"]) if key]
        results = []
        if unit["stage"] == "TR4":
            relatives = set(unit["inputs"])
            for exact in list(relatives):
                parent = records[exact]["parent"]
                while parent:
                    relatives.add(parent)
                    parent = records[parent]["parent"]
            for result in registry["verifications"]:
                if result["increment"] != unit["increment"] or result["requirement"] not in relatives:
                    continue
                issue = None
                if unit["increment"] == registry["active_increment"]:
                    if result["id"] not in verification_diagnostics:
                        from .requirement_verification import verification_issue
                        verification_diagnostics[result["id"]] = verification_issue(root, registry, result)
                    issue = verification_diagnostics[result["id"]]
                baseline = next((b for b in registry["baselines"] if b["increment"] == unit["increment"]), None)
                href = "../requirement_history/" + quote(baseline["path"].rsplit("/", 1)[1]) if baseline else "../../" + quote(result["evidence"], safe="/")
                node = add("verification:" + result["id"], "Verification", result["criterion"],
                           reference=result["requirement"], status="unknown" if issue else result["result"],
                           diagnostic=issue, sha256=result["sha256"], href=href)
                results.append(node)
                edges.add((node, req(result["requirement"]), "verifies"))
        for target in conclusions:
            edges.update((source, target, "input") for source in inputs)
            edges.update((source, target, "supports") for source in materials)
            edges.update((target, child, "produces") for child in outputs)
        edges.update((source, material, "analyzes") for source in inputs for material in materials)
        cursor = (unit["inputs"] or unit["outputs"] or [None])[0]
        while cursor and records[cursor]["parent"]:
            cursor = records[cursor]["parent"]
        historical = unit["increment"] != registry["active_increment"]
        problems = [] if historical else unit_issues(root, registry, state, unit, documents=documents)
        units.append({"id": unit["id"], "stage": unit["stage"], "increment": unit["increment"],
            "root": mapping.get(cursor, "derived"), "owner": unit["owner"], "inputs": inputs,
            "supports": materials, "conclusions": conclusions, "outputs": outputs, "results": results, "issues": problems,
            "arguments": [{**a, "href": (nodes[conclusions[0]].get("href") or "") + ("#" + quote(a["anchor"], safe="") if not historical and nodes[conclusions[0]].get("href") else "")}
                          for a in unit["arguments"]],
            "status": "historical" if historical else "incomplete" if problems else "structurally_ready"})
    indexes = [{"stage": p["stage"], "increment": p["increment"], "node": document(
        {**p, "id": p["index"], "inputs": [], "outputs": []}, p["index"])} for p in org["plans"]]
    linked = {u["owner"] for u in org["units"] if u["increment"] == registry["active_increment"]}
    linked.update(s["owner"] for u in org["units"] if u["increment"] == registry["active_increment"] for s in u["supports"])
    return {"schema_version": "1.0", "edge_semantics": "work-product trace; not execution dependencies",
            "active_increment": registry["active_increment"], "nodes": list(nodes.values()),
            "edges": [{"source": s, "target": t, "relation": r} for s, t, r in sorted(edges)],
            "units": units, "indexes": indexes, "reverse": reverse,
            "unassociated_deliverables": sorted(set(core) - linked)}


def panel(flow, locale):
    zh = locale == "zh-CN"
    esc = lambda x: html.escape(str(x), quote=True)
    nodes, units = {n["id"]: n for n in flow["nodes"]}, flow["units"]
    labels = {"planned": "计划", "missing": "缺失", "current": "当前", "stale": "已失效",
              "historical": "历史快照", "invalid": "无效", "incomplete": "未就绪", "structurally_ready": "结构就绪",
              "passed": "通过", "failed": "失败", "unknown": "未知", "skipped": "跳过"}
    def jump(unit):
        return '<a data-flow-open="' + esc(unit["id"]) + '" href="#' + anchor("su-", unit["id"]) + '">' + esc(unit["stage"] + " · " + unit["id"]) + '</a>'
    def card(key, unit=None):
        node = nodes[key]
        text = esc(node["label"])
        if node.get("href"):
            text = '<a href="' + esc(node["href"]) + '">' + text + '</a>'
        detail = " · ".join(labels.get(str(node[k]), str(node[k])) if zh else str(node[k]) for k in ("reference", "path", "availability", "status", "template") if node.get(k))
        if unit and node.get("reference"):
            argument = next((a for a in unit["arguments"] if a["requirement"] == node["reference"]), None)
            if argument and argument["href"]:
                text += ' <a data-flow-argument href="' + esc(argument["href"]) + '">' + ("分解论证" if zh else "Derivation") + '</a>'
        if node.get("owner"):
            text += ' <button type="button" data-flow-owner="' + esc(node["owner"]) + '">' + ("流程交付件" if zh else "Core deliverable") + '</button>'
        consumers = [u for u in units if key in u["inputs"]]
        if node.get("reverse_key"):
            consumers = [u for u in units if u["id"] in flow["reverse"][node["reverse_key"]]["units"]]
        links = '<br>' + ("使用位置：" if zh else "Used by: ") + " · ".join(jump(u) for u in consumers) if consumers else ""
        return '<li data-flow-node="' + esc(key) + '">' + text + '<br><small>' + esc(detail) + '</small>' + links + '</li>'
    headings = ["上层输入", "支撑材料", "阶段结论 / 需求表", "下层输出"] if zh else ["Parent inputs", "Supporting work", "Conclusions / registers", "Child outputs"]
    content = '<section id="ipd-stage-flow"><h2>' + ("需求与阶段成果" if zh else "Requirements and stage work products") + '</h2><p>'
    content += ("各列表示分析、支撑和产出；执行先后由流程依赖决定。结构就绪不等于人类批准。" if zh else "Columns show analysis, support and output. Core dependencies control execution. Structural readiness is not human approval.") + '</p>'
    content += '<label>' + ("阶段" if zh else "Stage") + ' <select id="ipd-flow-stage"><option value="">' + ("全部" if zh else "All") + '</option>' + ''.join('<option>' + s + '</option>' for s in ("TR1", "TR2", "TR3", "TR4")) + '</select></label> '
    content += '<label>' + ("增量" if zh else "Increment") + ' <select id="ipd-flow-increment"><option value="">' + ("全部" if zh else "All") + '</option>'
    content += ''.join('<option' + (' selected' if i == flow["active_increment"] else '') + '>' + esc(i) + '</option>' for i in sorted({u["increment"] for u in units})) + '</select></label> '
    content += '<label>' + ("筛选需求或材料" if zh else "Find requirements or work") + ' <input id="ipd-flow-search" type="search"></label>'
    for group in sorted({u["root"] for u in units}):
        content += '<div data-flow-group><h3>' + esc(group) + '</h3>'
        for unit in [u for u in units if u["root"] == group]:
            search = " ".join([unit["id"], unit["owner"], unit["status"], *unit["issues"], *[nodes[k]["label"] + " " + nodes[k].get("status", "") for field in ("inputs", "supports", "conclusions", "outputs", "results") for k in unit[field]]])
            content += '<details id="' + anchor("su-", unit["id"]) + '" data-flow-unit="' + esc(unit["id"]) + '" data-stage="' + unit["stage"] + '" data-increment="' + esc(unit["increment"]) + '" data-search="' + esc(search.lower()) + '"><summary>' + esc(unit["stage"] + " · " + unit["id"] + " · " + (labels[unit["status"]] if zh else unit["status"])) + '</summary><div class="ipd-work-columns">'
            current_headings = headings if unit["stage"] != "TR4" else (["AR 输入", "设计、实现与执行证据", "交付结论 / AR 表", "AR/SR/IR 验证"] if zh else ["AR inputs", "Design, implementation and evidence", "Delivery / AR register", "AR/SR/IR verification"])
            for title, field in zip(current_headings, ("inputs", "supports", "conclusions", "outputs" if unit["stage"] != "TR4" else "results")):
                content += '<div><strong>' + title + '</strong><ul>' + ''.join(card(k,unit) for k in unit[field]) + '</ul></div>'
            content += '</div><ul>' + ''.join('<li>' + esc(i) + '</li>' for i in unit["issues"]) + '</ul></details>'
        content += '</div>'
    content += '<h3>' + ("阶段索引" if zh else "Stage indexes") + '</h3><ul>' + ''.join(card(i["node"]) for i in flow["indexes"]) + '</ul>'
    content += '<p>' + ("尚未关联的流程交付件：" if zh else "Unassociated core deliverables: ") + esc(", ".join(flow["unassociated_deliverables"])) + '</p></section>'
    content += '''<style>.ipd-work-columns{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:12px;overflow:auto}.ipd-work-columns>div{border:1px solid #8899ab;padding:12px}.ipd-work-columns small{overflow-wrap:anywhere}#ipd-stage-flow{padding:24px}#ipd-stage-flow details{padding:8px}</style>
<script>(()=>{const stage=document.getElementById('ipd-flow-stage'),inc=document.getElementById('ipd-flow-increment'),search=document.getElementById('ipd-flow-search'),units=[...document.querySelectorAll('[data-flow-unit]')];function update(){const words=search.value.toLowerCase().split(/\\s+/).filter(Boolean);units.forEach(u=>{u.hidden=!!((stage.value&&u.dataset.stage!==stage.value)||(inc.value&&u.dataset.increment!==inc.value)||!words.every(w=>u.dataset.search.includes(w)));});document.querySelectorAll('[data-flow-group]').forEach(g=>g.hidden=[...g.querySelectorAll('[data-flow-unit]')].every(u=>u.hidden));}stage.addEventListener('change',update);inc.addEventListener('change',update);search.addEventListener('input',update);document.querySelectorAll('[data-flow-open]').forEach(a=>a.addEventListener('click',()=>{const target=units.find(u=>u.dataset.flowUnit===a.dataset.flowOpen);if(target){stage.value=target.dataset.stage;inc.value=target.dataset.increment;search.value='';update();target.open=true;}}));document.querySelectorAll('[data-flow-owner]').forEach(b=>b.addEventListener('click',()=>{const input=document.getElementById('deliverable-search');const status=document.getElementById('deliverable-status');if(status){status.value='';status.dispatchEvent(new Event('change'));}if(input){input.value=b.dataset.flowOwner;input.dispatchEvent(new Event('input'));}location.hash='deliverable-matrix';}));document.querySelectorAll('a[href^="#rq-"]').forEach(a=>a.addEventListener('click',()=>{const target=document.getElementById(a.hash.slice(1));if(target){const filter=document.getElementById('ipd-requirement-filter');if(filter){filter.value='';filter.dispatchEvent(new Event('input'));}document.querySelectorAll('[data-requirement-toggle][aria-expanded="false"]').forEach(b=>b.click());}}));update();})();</script>'''
    return content

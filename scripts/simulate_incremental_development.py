#!/usr/bin/env python3
"""Run two fully governed delivery increments from the bilingual worked project.

All identities and acceptance decisions are synthetic test declarations. This
does not claim real QA acceptance, production testing, or remote integration.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ipdctl.cli import main
from ipdctl.documents import lint, metadata, template
from ipdctl.requirements import apply_plan, preview, read_registry, projection
from ipdctl.runtime import load_runtime
from ipdctl.state import load_state, write_state
import yaml

DEMO = ROOT / "docs/worked-projects/room-booking"
PHASES = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")


def run(locale: str, project: Path, *, organized: bool = False) -> dict:
    started = time.monotonic()
    project.mkdir(parents=True)
    count = 0
    def invoke(*args):
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = main([*map(str, args)])
        except SystemExit as exc:
            raise RuntimeError(out.getvalue() + err.getvalue()) from exc
        if code:
            raise RuntimeError(f"{args}: {out.getvalue()}{err.getvalue()}")
        return out.getvalue()
    def git(*args):
        return subprocess.run(["git", *args], cwd=project, text=True, encoding="utf-8",
                              capture_output=True, check=True).stdout.strip()
    def state():
        return load_state(project / ".ipd/project_state.yaml")
    def request(operation, actor="fixture-maintainer", **fields):
        nonlocal count
        count += 1
        req = {"request_id": f"fixture-{count}", "operation": operation,
               "reason": "Synthetic complete development qualification", **fields}
        if operation in {"draft_templates", "review_templates", "publish_templates"}:
            req.update(actor=actor, actor_type="human")
        plan = preview(project, req)
        return apply_plan(project, plan, actor=actor, authorized=True)
    def verify():
        invoke("refresh", project)
        report = json.loads(invoke("verify", project, "--json"))
        return report
    git("init", "-b", "main")
    git("config", "user.name", "Synthetic lifecycle fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("remote", "add", "origin", "https://example.invalid/room-booking.git")
    (project / ".gitignore").write_text(".ipd/dashboard/\n.ipd/verify_report.json\n.ipd/reconcile_report.json\n", encoding="utf-8")
    invoke("init", project, "--name", "Synthetic governed room booking", "--task-type", "software", "--locale", locale)
    invoke("tailor", project)
    # Explicit Owner bindings for each phase's companion documents, retained
    # for both increments. No direct edits of canonical state or approvals.
    bindings_path = project / ".ipd/artifact_bindings.yaml"
    bindings = load_state(bindings_path)
    phase_owner = {phase: next(d["id"] for d in state()["deliverables"] if d["phase"] == phase) for phase in PHASES}
    for phase in PHASES:
        bindings["bindings"].append({"id": "docs-" + phase, "glob": f"docs/*/{phase}/**",
            "deliverable": phase_owner[phase], "role": "owner", "critical": True})
        if organized and phase in {"concept", "plan", "develop", "qualify"}:
            stage_code={"concept":"tr1","plan":"tr2","develop":"tr3","qualify":"tr4"}[phase]
            bindings["bindings"].append({"id":"stage-"+phase,"glob":f"docs/increments/*/{stage_code}/**",
                "deliverable":phase_owner[phase],"role":"owner","critical":True})
    if organized:
        for identifier,pattern,owner in (("shared-source","docs/shared/**",phase_owner['concept']),
            ("case-results","evidence/*/cases.json",phase_owner['qualify']),
            ("extended-results","evidence/*/extended.txt",phase_owner['qualify'])):
            bindings['bindings'].append({'id':identifier,'glob':pattern,'deliverable':owner,'role':'owner','critical':True})
    bindings["bindings"].append({"id": "implementation", "glob": "implementation/**",
        "deliverable": phase_owner["develop"], "role": "owner", "critical": True})
    write_state(bindings_path, bindings)
    git("add", ".")
    git("commit", "-m", "Initialize isolated synthetic project")
    request("enable", increment="mvp", product_version="0.1")
    request("draft_templates", actor="fixture-qa-author", id="draft", path="")
    request("review_templates", actor="fixture-qa-reviewer", id="review", source="draft", decision="approved")
    request("publish_templates", actor="fixture-publisher", id="published", source="review")
    request("pin_templates", path="")
    if organized:
        request("adopt_organization",required_stages=["TR1","TR2","TR3","TR4"])
    catalog = json.loads((DEMO / "catalog.json").read_text(encoding="utf-8"))["requirements"]
    if organized:
        from stage_development_support import numbered_catalog
        catalog=numbered_catalog(catalog)
    extension_ref=next(r['ref'] for r in catalog if r.get('legacy_id',r['id'])=='ir-03')
    docs = [d for d in json.loads((DEMO / "document-instances.json").read_text(encoding="utf-8"))["documents"] if d["instance"]["locale"] == locale]
    def destination(document, increment):
        name = Path(document["path"]).stem
        phase = next(p for stage, p in (("TR1", "concept"), ("TR2", "plan"), ("TR3", "develop"), ("TR4", "qualify")) if name.endswith(stage))
        return project / f"docs/{increment}/{phase}" / Path(document["path"]).name
    def filled_body(document, increment, output):
        original = DEMO / document["path"]
        body = original.read_text(encoding="utf-8").split("---", 2)[2].lstrip("\r\n")
        mapping = {(DEMO / d["path"]).resolve(): destination(d, increment) for d in docs}
        def target(link):
            path, separator, anchor = link.partition("#")
            if not path or ":" in path:
                return link
            absolute = (original.parent / unquote(path)).resolve()
            relative = absolute.relative_to(DEMO.resolve())
            if absolute in mapping:
                resolved = mapping[absolute]
            elif relative.parts[0] == "implementation":
                resolved = project / "implementation" / increment / Path(*relative.parts[1:])
            else:
                resolved = project / "reference" / increment / relative
            return os.path.relpath(resolved, output.parent).replace("\\", "/") + (separator + anchor if separator else "")
        body = re.sub(r'(?<=href=")([^"]+)(?=")', lambda m: target(m[0]), body)
        return re.sub(r'(?<=\]\()([^\s)]+)(?=\))', lambda m: target(m[0]), body)
    scope = []
    frozen = {}
    counts = {"documents": 0, "deliverable_approvals": 0, "gate_approvals": 0, "cases": 0}
    for cycle, increment in enumerate(("mvp", "extension")):
        print(f"{locale}: starting {increment}", flush=True)
        if cycle:
            scope = [{**s, "criteria": [*s["criteria"], "extended-cases"] if s["requirement"] == extension_ref else s["criteria"]} for s in scope]
            request("begin", increment=increment, product_version="0.2", base_baseline="b1", scope=scope)
        shutil.copytree(DEMO, project / "reference" / increment)
        for phase in PHASES:
            kind = {"concept": "IR", "plan": "SR", "develop": "AR"}.get(phase)
            if kind and not cycle:
                for r in [r for r in catalog if r["kind"] == kind]:
                    criteria = [{"id": r["criterion"].lower(), "criterion": r["statement"][locale], "method": "test"}]
                    if r.get('legacy_id',r['id']) == "ir-03":
                        criteria.append({"id": "extended-cases", "criterion": "1000 serial book/cancel cycles preserve zero occupied minutes", "method": "test"})
                    request("requirement", requirement={"id": r["id"], "version": 1, "kind": kind,
                        "title": r["id"], "statement": r["statement"][locale], "source": "worked-brief@1",
                        "rationale": r["argument"][locale], "priority": "high", "owner": "fixture-team",
                        "module": r["module"], "parent": r["parent"], "derived": False,
                        "acceptance": criteria, "maturity": "defined", "decomposition": "open"})
                    scope.append({"requirement": r["ref"], "criteria": [r["criterion"].lower()]})
                request("scope", scope=scope)
                parent_kind = {"SR": "IR", "AR": "SR"}.get(kind)
                for r in [r for r in catalog if r["kind"] == parent_kind]:
                    request("decomposition", requirement=r["ref"], status="complete")
            if phase == "develop":
                for r in catalog:
                    request("link", link={"requirement": r["ref"], "relation": "satisfied_by",
                        "target": phase_owner[phase], "rationale": "Worked implementation symbol " + r["code"]})
            stage = {"concept": "TR1", "plan": "TR2", "develop": "TR3", "qualify": "TR4"}.get(phase)
            stage_docs = [d for d in docs if stage and Path(d["path"]).stem.endswith(stage)]
            if organized:
                stage_docs=[]
                if stage:
                    request('stage_plan',stage=stage,owner=phase_owner[phase],locale=locale)
            for document in stage_docs:
                instance = document["instance"]
                request("obligation", obligation={"id": f"ob-{increment}-{Path(document['path']).stem.lower()}",
                    "requirement": instance["requirements"][0], "owner": phase_owner[phase],
                    "document_type": instance["document_type"], "keys": [stage.lower()]})
            invoke("adopt-baseline", project, "--actor", "fixture-maintainer", "--actor-type", "human",
                   "--authorized", "--reason", "Accept explicit synthetic inputs for current stage")
            verify()
            for deliverable in [d for d in state()["deliverables"] if d["phase"] == phase]:
                owner = deliverable["id"]
                invoke("claim", owner, "--project-root", project, "--actor", "fixture-agent")
                evidence = f"evidence/{increment}/{owner}.md"
                (project / evidence).parent.mkdir(parents=True, exist_ok=True)
                (project / evidence).write_text(f"Synthetic {increment} {phase} work and review evidence\n", encoding="utf-8")
                if owner == phase_owner[phase]:
                    for document in stage_docs:
                        raw = document["instance"]
                        item = {"id": increment + "-" + Path(document["path"]).stem.lower(), "key": stage.lower(),
                            "requirements": raw["requirements"], "owner": owner, "document_type": raw["document_type"],
                            "path": f"docs/{increment}/{phase}/" + Path(document["path"]).name,
                            "title": raw["title"], "scope": "Synthetic governed qualification " + increment, "locale": locale}
                        request("instantiate", actor="fixture-agent", instance=item)
                        recorded = read_registry(project)["instances"][-1]
                        body = filled_body(document, increment, project / item["path"])
                        text = "---\n" + yaml.safe_dump(metadata(recorded), allow_unicode=True, sort_keys=False) + "---\n\n" + body
                        (project / item["path"]).write_text(text, encoding="utf-8")
                        record, source = template(project, recorded["pack"], recorded["document_type"], locale)
                        canonical = {f"{r['id']}@{r['version']}": r for r in read_registry(project)["requirements"]}
                        issues = lint(text, recorded, source, record["sections"], canonical=canonical)
                        if issues:
                            raise RuntimeError(str(issues))
                        counts["documents"] += 1
                    if phase == "develop":
                        shutil.copytree(DEMO / "implementation", project / f"implementation/{increment}")
                    if organized and stage and phase!='qualify':
                        from stage_development_support import write_stage
                        write_stage(project,stage,locale,request,counts,phase_owner)
                    if phase == "qualify":
                        code = project / f"implementation/{increment}"
                        result = subprocess.run([sys.executable, "-B", "verify_demo.py"], cwd=code,
                            capture_output=True, text=True, encoding="utf-8", check=True)
                        measured = json.loads(result.stdout)
                        if measured["passed"] != measured["total"]:
                            raise RuntimeError("Worked implementation test failed")
                        output = f"evidence/{increment}/cases.json"
                        (project / output).write_text(result.stdout, encoding="utf-8")
                        counts["cases"] += measured["total"]
                        if cycle:
                            extra = subprocess.run([sys.executable, "-B", "-c",
                                "from booking import Calendar; c=Calendar(); "
                                "exec('for i in range(1000):\\n b=c.book(\"08:00\",\"08:15\"); c.cancel(b[\"id\"])'); "
                                "assert c.summary()['occupied_min']==0; print('1000 serial cycles passed')"],
                                cwd=code, capture_output=True, text=True, encoding="utf-8", check=True)
                            (project / f"evidence/{increment}/extended.txt").write_text(extra.stdout, encoding="utf-8")
                            counts["cases"] += 1
                        if organized:
                            from stage_development_support import write_stage
                            write_stage(project,stage,locale,request,counts,phase_owner)
                        for s in scope:
                            for criterion in s["criteria"]:
                                request("verification", actor="fixture-agent", verification={
                                    "id": f"{increment}-{s['requirement'].split('@')[0]}-{criterion}",
                                    "requirement": s["requirement"], "criterion": criterion, "method": "test",
                                    "case": criterion + "@1", "environment": "synthetic-python-" + sys.version.split()[0],
                                    "result": "passed", "evidence": f"evidence/{increment}/extended.txt" if criterion == "extended-cases" else output})
                close_args = ["close", owner, "--project-root", project, "--actor", "fixture-agent", "--evidence", evidence]
                if phase == "develop" and owner == phase_owner[phase]:
                    for filename in ("booking.py", "verify_demo.py"):
                        close_args.extend(["--evidence", f"implementation/{increment}/{filename}"])
                invoke(*close_args)
                invoke("review", owner, "--project-root", project, "--reviewer", "fixture-review-agent")
                invoke("approve", owner, "--project-root", project, "--reviewer", "fixture-human", "--actor-type", "human", "--authorized", "--evidence", evidence)
                counts["deliverable_approvals"] += 1
                verify()
            while state()["project"]["current_gate"]:
                gate = state()["project"]["current_gate"]
                evidence = f"evidence/{increment}/gates/{gate}.md"
                invoke("review", gate, "--project-root", project, "--reviewer", "fixture-review-agent")
                (project / evidence).parent.mkdir(parents=True, exist_ok=True)
                (project / evidence).write_text("Synthetic explicit Gate decision\n", encoding="utf-8")
                invoke("approve", gate, "--project-root", project, "--reviewer", "fixture-human", "--actor-type", "human", "--authorized", "--evidence", evidence)
                counts["gate_approvals"] += 1
                verify()
            if phase != "lifecycle":
                invoke("advance-phase", project)
                verify()
            print(f"{locale}: {increment} {phase} passed", flush=True)
        git("add", ".")
        git("commit", "-m", "Accept synthetic " + increment + " facts")
        invoke("render-dashboard", project)
        invoke("verify", project, "--json")
        request("baseline", id=f"b{cycle+1}", source={"backend": "git", "repository": "https://example.invalid/room-booking.git", "revision": git("rev-parse", "HEAD"), "path": "."})
        registry = read_registry(project)
        event = registry["events"][-1]
        if event["increment_context"]["increment"] != increment:
            raise RuntimeError("Delivery acceptance lost increment context")
        runtime = load_runtime(project)
        if any(e.get("increment_context", {}).get("increment") != increment for e in runtime["events"][runtime["increment_context_start"]:]):
            raise RuntimeError("New lifecycle event lacks exact increment context")
        for b in registry["baselines"]:
            content = (project / b["path"]).read_bytes()
            if b["id"] in frozen and frozen[b["id"]] != content:
                raise RuntimeError("Earlier baseline changed")
            frozen[b["id"]] = content
        if not cycle:
            ir = next(r for r in projection(project)["coverage"] if r["requirement"] == extension_ref)
            if ir["fulfillment"] != "partial":
                raise RuntimeError("MVP falsely claims future criterion accepted")
    registry = projection(project)
    if any(c["fulfillment"] != "full" for c in registry["coverage"]):
        raise RuntimeError("Final increment did not accept every criterion")
    request("retire")
    if read_registry(project)["product_state"] != "retired":
        raise RuntimeError("Explicit retirement failed")
    verify()
    stage_outcomes=None
    if organized:
        from stage_development_support import check_stage_outcomes
        stage_outcomes=check_stage_outcomes(project)
    return {"status": "passed", "locale": locale, "increments": 2, "baselines": 2,
        "stage_organization":organized,
        "stage_outcomes":stage_outcomes,
        "requirements": len(catalog), "counts": counts, "history_preserved": True,
        "runtime_schema": "1.1", "synthetic_human_decisions": True,
        "seconds": round(time.monotonic()-started, 3)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", choices=("en", "zh-CN"), default="en")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--organized",action="store_true",help="Qualify 0.5.4 per-parent organization and work-product graphs")
    parser.add_argument("--project", type=Path, help="Keep an isolated project; target must not exist")
    args = parser.parse_args()
    if args.project:
        result = run(args.locale, args.project, organized=args.organized)
    else:
        with tempfile.TemporaryDirectory(prefix="ipd-increment-") as temp:
            result = run(args.locale, Path(temp) / "project", organized=args.organized)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)

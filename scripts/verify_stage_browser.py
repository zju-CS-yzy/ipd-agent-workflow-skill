#!/usr/bin/env python3
"""Real-browser stage navigation. Synthetic work state; no acceptance claim."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def fixture(destination,locale):
    from tests.test_stage_organization import StageOrganizationTests
    from ipdctl.dashboard import render_dashboard
    from ipdctl.stage_organization import blueprints
    from ipdctl.state import load_state
    from ipdctl.runtime import load_runtime
    case=StageOrganizationTests('runTest');case.setUp()
    try:
        case.tree();case.plan('TR2',locale);case.plan('TR3',locale)
        owner=case.owner('plan')
        case.f.execute('adopt_work_products',roles=[])
        from ipdctl.work_planning import preview as work_preview
        from ipdctl.cli import main
        from ipdctl.state import write_state
        from contextlib import redirect_stdout
        import io
        candidate=work_preview(case.root,{'request_id':'browser-material','reason':'Synthetic independent supporting work',
            'stage':'TR2','consumer':owner,'materials':[{'id':'plan.selection','title':'Shared selection analysis',
            'path':'docs/shared 资料 #&.txt','usage':'deliverable','required':True,
            'rationale':'Shared timing budget','execution_dependency':True}]})
        assert candidate['ready_for_authoring']
        write_state(case.root/'.ipd/process_extensions.yaml',candidate['candidate_process_extensions'])
        write_state(case.root/'.ipd/artifact_bindings.yaml',candidate['candidate_artifact_bindings'])
        with redirect_stdout(io.StringIO()): assert main(['tailor',str(case.root)])==0
        case.bindings(owner,'docs/increments/**')
        material='docs/shared 资料 #&.txt'
        path=case.root/material;path.parent.mkdir(exist_ok=True);path.write_text('Synthetic shared selection evidence',encoding='utf-8')
        for unit in list(case.registry()['organization']['units']):
            if unit['stage']=='TR2':
                unit['supports']=[{'kind':'artifact','target':material,'owner':'plan.selection','usage':'deliverable','required':True,'rationale':'Synthetic shared constraint','anchor':'','sha256':None}]
                case.f.execute('stage_unit',unit=unit)
        case.work(owner)
        for item in [x for x in blueprints(case.registry()) if x['owner']==owner]:
            case.f.execute('instantiate',actor='agent',instance=item);case.fill(item)
        for unit in list(case.registry()['organization']['units']):
            if unit['stage']=='TR2':
                # Deliberately unaccepted support: display an incomplete draft,
                # never bypass the independent support acceptance guard.
                unit['finalized']=False
                unit['arguments']=[{'requirement':r,'anchor':'derive-'+r.split('@')[0]} for r in unit['outputs']]
                case.f.execute('stage_unit',actor='agent',unit=unit)
        shutil.copytree(case.root,destination)
        render_dashboard(destination,load_state(destination/'.ipd/tailored_process.yaml'),load_state(destination/'.ipd/project_state.yaml'),
                         runtime=load_runtime(destination),locale=locale,bindings=load_state(destination/'.ipd/artifact_bindings.yaml'))
        return destination
    finally:
        case.doCleanups()


def run(output,channels):
    from playwright.sync_api import sync_playwright
    output=output.resolve()
    if output==ROOT or ROOT in output.parents:raise ValueError('Browser results must be outside the checkout')
    output.mkdir(parents=True,exist_ok=True)
    projects={loc:fixture(output/loc,loc) for loc in ('en','zh-CN')};results=[]
    def facts(project):
        return {p.relative_to(project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in project.rglob('*') if p.is_file() and '.ipd/dashboard/' not in p.relative_to(project).as_posix()}
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    with sync_playwright() as playwright:
        for channel in channels:
            browser=playwright.chromium.launch(channel=None if channel=='chromium' else channel)
            for locale,project in projects.items():
                server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(project)))
                threading.Thread(target=server.serve_forever,daemon=True).start()
                try:
                    for protocol in ('file','http'):
                        before=facts(project);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        address=(project/'.ipd/dashboard/index.html').as_uri() if protocol=='file' else f'http://127.0.0.1:{server.server_port}/.ipd/dashboard/index.html'
                        page.goto(address);page.locator('#ipd-stage-flow').wait_for()
                        assert page.locator('[data-flow-unit]').count()==6
                        page.locator('[data-flow-group]').evaluate_all('(xs)=>xs.forEach(x=>x.open=true)')
                        assert page.locator('#deliverable-matrix').count()==1
                        assert not page.locator('#ipd-requirement-filter').count()
                        assert page.locator('#ipd-stage-flow').evaluate('(e)=>e.closest("main")!==null')
                        assert page.locator('#dependency-flow').evaluate('(e)=>e.compareDocumentPosition(document.getElementById("ipd-stage-flow")) & Node.DOCUMENT_POSITION_FOLLOWING')
                        page.locator('#ipd-flow-stage').select_option('TR2')
                        assert page.locator('[data-flow-unit]:visible').count()==2
                        first=page.locator('[data-flow-unit]:visible').first
                        first.evaluate('(e)=>{e.closest("[data-flow-group]").open=true;e.open=true}')
                        assert first.locator('svg[data-work-diagram]').count()==1
                        assert first.locator('svg .edge[data-relation="supports"]').count()>=1
                        support=first.locator('g[data-work-key="deliverable:plan.selection"]')
                        assert support.count()==1
                        main_node=page.locator('#dependency-flow g[data-work-key="deliverable:plan.selection"]')
                        assert main_node.count()==1
                        assert support.locator('rect').last.get_attribute('rx')==main_node.locator('rect').last.get_attribute('rx')
                        support.click(); assert 'plan.selection' in page.locator('#detail-title').inner_text()
                        assert page.locator('.work-selected[data-work-key="deliverable:plan.selection"]').count()>=3
                        assert page.locator('#detail-body [data-work-unit]').count()==2
                        page.locator('#detail-body [data-work-unit]').last.click()
                        assert page.locator('[data-flow-unit][open]:visible').count()>=1
                        page.locator('#deliverable-search').fill('shared 资料')
                        material=page.locator('#deliverable-rows tr[data-kind="Material"]:visible').first
                        assert material.count()==1
                        material.click();link=page.locator('#detail-body a').first
                        href=link.get_attribute('href');assert '%20' in href and '%23' in href and '%26' in href
                        assert ('no independent approval' if locale=='en' else '没有独立审批状态') in page.locator('#detail-body').inner_text()
                        assert page.locator('#detail-body [data-work-unit]').count()==2
                        page.locator('#deliverable-search').fill('impossible-branch')
                        assert page.locator('[data-flow-unit]:visible').count()==0
                        page.locator('#deliverable-search').fill('');page.locator('#ipd-flow-stage').select_option('TR2')
                        page.locator('#details-close').click()
                        page.locator('#ipd-stage-flow').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'{channel}-{locale}-{protocol}.png'))
                        zoom=first.locator('[data-zoom="in"]');zoom.click()
                        assert 'scale(' in first.locator('svg').get_attribute('style')
                        page.set_viewport_size({'width':390,'height':844})
                        page.locator('#ipd-stage-flow').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'{channel}-{locale}-{protocol}-mobile.png'))
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                        page.set_viewport_size({'width':1440,'height':1000})
                        # Phase switching reuses SVGs without duplicate IDs.
                        page.locator('#work-phase').select_option('plan')
                        assert page.locator('#dependency-flow g[data-work-key="deliverable:plan.selection"]').count()==1
                        page.locator('#work-phase').select_option('')
                        duplicates=page.locator('[id]').evaluate_all('(xs)=>{const ids=xs.map(x=>x.id);return ids.filter((x,i)=>ids.indexOf(x)!==i)}')
                        assert not duplicates and not errors,(duplicates,errors)
                        assert before==facts(project)
                        results.append({'channel':channel,'locale':locale,'protocol':protocol,'passed':True,'stage_jump':True,'reverse_consumers':2,'facts_unchanged':True})
                        page.close()
                finally:
                    server.shutdown();server.server_close()
            browser.close()
    report={'status':'passed','cases':len(results),'results':results,'fixture':'synthetic work state; no human acceptance'}
    (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--channel',action='append',default=[]);args=parser.parse_args()
    print(json.dumps(run(args.output,args.channel or ['chromium']),indent=2))

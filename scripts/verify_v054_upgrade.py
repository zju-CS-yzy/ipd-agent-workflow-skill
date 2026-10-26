#!/usr/bin/env python3
"""Qualify actual published 0.5.4 source against explicit 0.5.5 work-role adoption."""
from pathlib import Path
import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ipdctl.documents import digest
from ipdctl.requirements import apply_plan,preview,read_registry


def run():
    with tempfile.TemporaryDirectory(prefix='ipd-v054-') as temp:
        work=Path(temp);old=work/'old';old.mkdir();project=work/'project'
        raw=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=zip','v0.5.4-beta'],cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(raw)) as handle:handle.extractall(old)
        env=dict(os.environ,PYTHONPATH=str(old),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',GIT_CEILING_DIRECTORIES=str(work))
        def invoke(*args,passed=True):
            result=subprocess.run([sys.executable,'-B','-m','ipdctl',*map(str,args)],cwd=work,env=env,capture_output=True,text=True,encoding='utf-8')
            assert (result.returncode==0)==passed,(args,result.stdout,result.stderr)
            return result
        assert '0.5.4-beta' in invoke('--version').stdout
        invoke('init',project,'--name','Synthetic real-tag adoption','--locale','en');invoke('tailor',project)
        req={'operation':'enable','request_id':'legacy-enable','reason':'Synthetic published-source fixture','increment':'mvp','product_version':'0.1'}
        path=work/'request.json';path.write_text(json.dumps(req),encoding='utf-8')
        result=json.loads(invoke('requirements',project,'--request',path,'--json').stdout)
        plan=work/'plan.json';plan.write_text(json.dumps(result),encoding='utf-8')
        invoke('requirements',project,'--apply',plan,'--actor','synthetic-maintainer','--authorized')
        req={'operation':'adopt_organization','request_id':'legacy-organize','reason':'Synthetic published-source fixture','required_stages':['TR1','TR2','TR3','TR4']}
        path.write_text(json.dumps(req),encoding='utf-8')
        result=json.loads(invoke('requirements',project,'--request',path,'--json').stdout)
        plan.write_text(json.dumps(result),encoding='utf-8')
        invoke('requirements',project,'--apply',plan,'--actor','synthetic-maintainer','--authorized')
        # A new renderer upgrades only derived views on old facts.
        from ipdctl.cli import main
        from contextlib import redirect_stdout
        facts=lambda:{p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file() and '.ipd/dashboard/' not in p.relative_to(project).as_posix()}
        prior=facts()
        with redirect_stdout(io.StringIO()): assert main(['render-dashboard',str(project)])==0
        assert facts()==prior
        legacy=read_registry(project)
        assert legacy['schema_version']=='1.1' and legacy['contract']=='0.5.4'
        before={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
        request={'operation':'adopt_work_products','request_id':'adopt-v055','reason':'Explicit synthetic work-role upgrade','roles':[]}
        candidate=preview(project,request)
        assert before=={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
        apply_plan(project,candidate,actor='synthetic-maintainer',authorized=True)
        adopted=read_registry(project)
        snapshot=json.loads((project/adopted['organization']['work_adoption']['path']).read_text(encoding='utf-8'))
        assert snapshot['registry']==legacy and adopted['requirements']==legacy['requirements']
        for path_key,content in before.items():
            if path_key.startswith('.ipd/requirement_history/'):
                assert (project/path_key).read_bytes()==content
        stable={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
        invoke('requirements',project,'--request',path,'--json',passed=False)
        assert stable=={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
        # Core refresh also writes state/runtime, so checking only the registry
        # command would leave an important old-client path unqualified.
        invoke('refresh',project,passed=False)
        assert stable=={p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
        return {'status':'passed','source_tag':'v0.5.4-beta','target_contract':'0.5.5','readonly_redraw_preserves_v054_facts':True,
                'preview_zero_write':True,'prior_registry_sha256':digest(legacy),
                'historical_bytes_preserved':True,'old_client_rejected_without_writes':True,
                'old_core_refresh_rejected_without_writes':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=run();text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    print(text)

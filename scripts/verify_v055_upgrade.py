#!/usr/bin/env python3
"""Qualify explicit product-governance adoption from published v0.5.5."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ipdctl.cli import main
from ipdctl.requirements import apply_plan, preview, read_registry
from ipdctl.state import load_state


def run():
    with tempfile.TemporaryDirectory(prefix='ipd-v055-products-') as directory:
        work = Path(directory)
        old = work / 'old'
        old.mkdir()
        archive = subprocess.check_output(
            ['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', 'v0.5.5-beta'], cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(archive)) as handle:
            handle.extractall(old)
        env = dict(os.environ, PYTHONPATH=str(old), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        reports = []
        for locale in ('en', 'zh-CN'):
            project = work / locale
            def legacy(*arguments, passed=True):
                result = subprocess.run([sys.executable, '-B', '-m', 'ipdctl', *map(str, arguments)],
                                        cwd=work, env=env, capture_output=True, text=True, encoding='utf-8')
                assert (result.returncode == 0) == passed, (arguments, result.stdout, result.stderr)
                return result.stdout
            def facts():
                return {path.relative_to(project).as_posix(): path.read_bytes() for path in project.rglob('*')
                        if path.is_file() and '.ipd/dashboard/' not in path.relative_to(project).as_posix()}
            legacy('init', project, '--name', 'Published-source adoption fixture', '--locale', locale)
            legacy('tailor', project)
            for index, (operation, fields) in enumerate([
                ('enable', {'increment': 'mvp', 'product_version': '0.1'}),
                ('adopt_organization', {'required_stages': ['TR1']}),
                ('adopt_work_products', {'roles': []}),
            ]):
                request = {'request_id': 'legacy-' + str(index), 'operation': operation,
                           'reason': 'Public synthetic old-source setup', **fields}
                request_file = work / 'request.json'
                request_file.write_text(json.dumps(request), encoding='utf-8')
                plan_file = work / 'plan.json'
                plan_file.write_text(legacy('requirements', project, '--request', request_file), encoding='utf-8')
                legacy('requirements', project, '--apply', plan_file, '--actor', 'fixture-human', '--authorized')
            before = facts()
            with redirect_stdout(io.StringIO()):
                assert main(['render-dashboard', str(project)]) == 0
            assert facts() == before
            prior_registry = read_registry(project)
            request = {'request_id': 'adopt-products', 'operation': 'adopt_product_governance',
                       'reason': 'Explicit enabling-product governance'}
            before = facts()
            plan = preview(project, request)
            assert facts() == before
            apply_plan(project, plan, actor='fixture-human', authorized=True)
            registry = read_registry(project)
            snapshot = json.loads((project / registry['components']['adoption']['path']).read_text(encoding='utf-8'))
            assert snapshot['registry'] == prior_registry
            current_state = load_state(project / '.ipd/project_state.yaml')
            assert current_state['deliverables'] == snapshot['state']['deliverables']
            assert current_state['gates'] == snapshot['state']['gates']
            prior_events = snapshot['runtime']['events']
            assert load_state(project / '.ipd/agent_runtime.yaml')['events'][:len(prior_events)] == prior_events
            assert all((project / path).read_bytes() == content for path, content in before.items()
                       if path not in {'.ipd/requirements.yaml', '.ipd/project_state.yaml', '.ipd/agent_runtime.yaml'})
            after = facts()
            legacy('requirements', project, '--json', passed=False)
            assert facts() == after
            assert apply_plan(project, plan, actor='fixture-human', authorized=True)['status'] == 'already_applied'
            reports.append({'locale': locale, 'preview_zero_write': True, 'old_client_rejected_without_writes': True,
                            'prior_registry_preserved': True, 'contract': registry['contract']})
        return {'status': 'passed', 'source_tag': 'v0.5.5-beta', 'results': reports}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))

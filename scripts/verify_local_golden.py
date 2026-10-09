#!/usr/bin/env python3
"""Qualify a frozen external project without modifying the supplied fixture.

All project data and detailed reports stay in the caller's external output
directory. No project-specific paths, names, or expected failures live here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]


def copy_fixture(source: Path, target: Path) -> Path:
    # Windows CopyFile may need the extended path prefix for long Git refs.
    prefix = '\\\\?\\' if os.name == 'nt' else ''
    shutil.copytree(prefix + str(source.resolve()), prefix + str(target.resolve()))
    return target


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def issues(report: dict) -> list[tuple[str, str]]:
    return sorted((item.get('path', ''), item.get('code', item.get('message', '')))
                  for item in report.get('issues', []))


def run(fixture: Path, baseline_source: Path, output: Path) -> dict:
    fixture, output = fixture.resolve(), output.resolve()
    if fixture == output or fixture in output.parents or output == ROOT or ROOT in output.parents:
        raise ValueError('Output must be outside the fixture and the Skill checkout')
    if fixture == ROOT or ROOT in fixture.parents:
        raise ValueError('Real project fixtures must remain outside the Skill checkout')
    if any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 1024
           for p in fixture.rglob('*')):
        raise ValueError('Fixture must not contain filesystem links or reparse points')
    before = hashes(fixture)
    output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='golden-', dir=output))
    baseline = copy_fixture(fixture, work / 'baseline')
    upgrade = copy_fixture(fixture, work / 'upgrade')
    commands = []

    def cli(source: Path, project: Path, *args: str, success: bool | None = True):
        env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
        result = subprocess.run([sys.executable, '-B', '-m', 'ipdctl', *args], cwd=project,
                                env=env, capture_output=True, text=True, encoding='utf-8', timeout=240)
        commands.append({'args': list(args), 'returncode': result.returncode,
                         'stdout': result.stdout, 'stderr': result.stderr})
        if success is not None and (result.returncode == 0) != success:
            raise AssertionError(commands[-1])
        return result

    stored = json.loads((fixture / '.ipd/verify_report.json').read_text(encoding='utf-8'))
    old = json.loads(cli(baseline_source, baseline, 'verify', str(baseline), '--json', success=None).stdout)
    assert old['status'] == stored['status'] and issues(old) == issues(stored), 'Baseline not reproduced'
    initial_state = yaml.safe_load((upgrade / '.ipd/project_state.yaml').read_text(encoding='utf-8'))
    subjects = [x['id'] for x in initial_state['deliverables'] if x['status'] == 'in_review']
    recovered = None
    if initial_state['project'].get('workflow_step') == 'review' and not initial_state['project'].get('current_iteration_subject'):
        assert len(subjects) == 1, 'Fixture needs an explicit, unambiguous review recovery case'
        zero = hashes(upgrade)
        cli(ROOT, upgrade, 'review', subjects[0], '--project-root', str(upgrade),
            '--reviewer', 'golden-simulated-human', '--actor-type', 'human', '--recover-subject',
            '--reason', 'Isolated regression test; no actual project decision', success=False)
        assert hashes(upgrade) == zero, 'Unauthorized recovery wrote files'
        cli(ROOT, upgrade, 'review', subjects[0], '--project-root', str(upgrade),
            '--reviewer', 'golden-simulated-human', '--actor-type', 'human', '--authorized',
            '--recover-subject', '--reason', 'Isolated regression test; no actual project decision')
        recovered = yaml.safe_load((upgrade / '.ipd/project_state.yaml').read_text(encoding='utf-8'))
        normalized = deepcopy(recovered)
        normalized['revision'] = initial_state['revision']
        normalized['project'].pop('current_iteration_subject', None)
        assert normalized == initial_state, 'Recovery changed unrelated facts'
        other = next(x['id'] for x in initial_state['deliverables'] if x['id'] != subjects[0])
        zero = hashes(upgrade)
        cli(ROOT, upgrade, 'review', other, '--project-root', str(upgrade), '--reviewer', 'golden-agent', success=False)
        assert hashes(upgrade) == zero, 'Cross-subject review wrote files'
    yaml_before = {p.name: p.read_bytes() for p in (upgrade / '.ipd').glob('*.yaml')}
    cli(ROOT, upgrade, 'render-dashboard', str(upgrade))
    assert all((upgrade / '.ipd' / n).read_bytes() == b for n, b in yaml_before.items()), 'Rendering wrote facts'
    first = hashes(upgrade / '.ipd/dashboard')
    cli(ROOT, upgrade, 'render-dashboard', str(upgrade))
    assert hashes(upgrade / '.ipd/dashboard') == first, 'Non-deterministic rendering'
    manifest = json.loads((upgrade / '.ipd/dashboard/manifest.json').read_text(encoding='utf-8'))
    assert manifest['schema_version'] == '2.2' and len(manifest['files']) == 16
    cli(ROOT, upgrade, 'validate', str(upgrade), '--json')
    refresh_before = hashes(upgrade)
    cli(ROOT, upgrade, 'refresh', str(upgrade), success=False if recovered else True)
    if recovered:
        assert hashes(upgrade) == refresh_before, 'Review-step refresh was not zero-write'
    current = json.loads(cli(ROOT, upgrade, 'verify', str(upgrade), '--json', success=None).stdout)
    assert current['status'] == old['status'] and issues(current) == issues(old), 'Verification regression'
    locale_projects = {}
    for locale in ('en', 'zh-CN'):
        project = copy_fixture(upgrade, work / locale)
        profile = project / '.ipd/task_profile.yaml'
        value = yaml.safe_load(profile.read_text(encoding='utf-8'))
        value.setdefault('presentation', {})['locale'] = locale
        profile.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding='utf-8')
        source = {p.name: p.read_bytes() for p in (project / '.ipd').glob('*.yaml')}
        cli(ROOT, project, 'render-dashboard', str(project))
        assert all((project / '.ipd' / n).read_bytes() == b for n,b in source.items())
        m = json.loads((project / '.ipd/dashboard/manifest.json').read_text(encoding='utf-8'))
        assert m['locale'] == locale
        locale_projects[locale] = str(project)
    report = {'passed': hashes(fixture) == before, 'fixture_unchanged': hashes(fixture) == before,
              'baseline_status': old['status'], 'preserved_issue_count': len(old.get('issues', [])),
              'review_recovered_in_copy': recovered is not None, 'locale_projects': locale_projects,
              'commands': commands}
    (output / 'qualification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert report['passed'], 'Frozen fixture changed'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--baseline-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.fixture, args.baseline_source, args.output)
    print(json.dumps({k:v for k,v in report.items() if k != 'commands'}, ensure_ascii=False, indent=2))

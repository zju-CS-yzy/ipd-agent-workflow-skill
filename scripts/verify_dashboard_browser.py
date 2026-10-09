#!/usr/bin/env python3
"""Actual-browser checks for offline Dashboard filtering and file navigation.

Requires Playwright only in the test environment, never in the Skill runtime.
External project data and screenshots must be written outside the checkout.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import itertools
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def synthetic(root: Path, locale: str) -> Path:
    from ipdctl.dashboard import render_dashboard
    from ipdctl.state import create_initial_state
    from ipdctl.tailoring import tailor_profile
    root.mkdir(parents=True, exist_ok=True)
    process = tailor_profile({'schema_version': '1.0', 'project_name': 'browser-regression', 'task_types': ['software']})
    state = create_initial_state('browser-regression')
    ids = [x['id'] for x in process['deliverables'] if x['phase'] == 'concept']
    if len(ids) < 2:
        additional = deepcopy(next(x for x in process['deliverables'] if x['id'] == ids[0]))
        additional.update(id='concept.browser_example', title='Browser interaction example')
        process['deliverables'].append(additional)
        ids.append(additional['id'])
    state['traceability'] = [{'source': ids[1], 'target': ids[0], 'relation': relation}
                            for relation in ('depends_on', 'supports', 'verifies', 'supersedes', 'refines')]
    path = root / 'docs/中文 # & file.txt'
    path.parent.mkdir(exist_ok=True)
    path.write_text('browser file navigation fixture', encoding='utf-8')
    render_dashboard(root, process, state, locale=locale, bindings={'bindings': [
        {'id': 'owned', 'paths': ['docs/中文 # & file.txt', 'docs/future.txt'], 'deliverable': ids[0]}]})
    return root


def run(output: Path, channels: list[str], external: dict[str, str]) -> dict:
    from playwright.sync_api import sync_playwright
    output = output.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if output == checkout or checkout in output.parents:
        raise ValueError('Browser results and external project data must stay outside the checkout')
    output.mkdir(parents=True, exist_ok=True)
    cases = [('synthetic', locale, synthetic(output / ('fixture-' + locale), locale)) for locale in ('en', 'zh-CN')]
    cases += [('external', locale, Path(path).resolve()) for locale, path in external.items()]
    results = []
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    with sync_playwright() as playwright:
        for channel in channels:
            browser = playwright.chromium.launch(channel=channel if channel != 'chromium' else None)
            for kind, locale, project in cases:
                handler = partial(QuietHandler, directory=str(project))
                server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    for protocol in ('file', 'http'):
                        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        base = (project / '.ipd/dashboard/index.html').as_uri() if protocol == 'file' else f'http://127.0.0.1:{server.server_port}/.ipd/dashboard/index.html'
                        page.goto(base)
                        inputs = page.locator('[data-relation-toggle]')
                        assert inputs.count() == 5
                        assert page.locator('[data-relation-toggle]:checked').evaluate_all('(xs) => xs.map(x=>x.value)') == ['depends_on']
                        counts = page.locator('#status-flow .edge[data-relation]').evaluate_all('(xs) => [...new Set(xs.map(x=>x.dataset.relation))]')
                        if kind == 'synthetic': assert len(counts) == 5, counts
                        positions = page.locator('#status-flow [data-node-id]').evaluate_all('(xs)=>xs.map(x=>[x.dataset.nodeId,x.dataset.x,x.dataset.y])')
                        combinations = 0
                        for bits in itertools.product((False, True), repeat=5):
                            selected = []
                            for i, bit in enumerate(bits):
                                inputs.nth(i).set_checked(bit)
                                if bit: selected.append(inputs.nth(i).get_attribute('value'))
                            failures = page.locator('.relation-filtered .edge[data-relation]').evaluate_all('(xs, chosen) => xs.filter(x => (getComputedStyle(x).display !== "none") !== chosen.includes(x.dataset.relation)).map(x=>x.dataset.relation)', selected)
                            assert not failures, (selected, failures)
                            combinations += 1
                        assert page.locator('#status-flow [data-node-id]').evaluate_all('(xs)=>xs.map(x=>[x.dataset.nodeId,x.dataset.x,x.dataset.y])') == positions
                        page.locator('[data-relations-action="default"]').click()
                        page.locator('[data-relation-toggle][value="depends_on"]').uncheck()
                        page.locator('[data-relation-toggle][value="supports"]').check()
                        page.locator('[data-relation-toggle][value="verifies"]').check()
                        options = page.locator('#phase-view option').evaluate_all('(xs)=>xs.map(x=>x.value)')
                        page.locator('#phase-view').select_option(options[-1])
                        assert page.locator('[data-relation-toggle]:checked').evaluate_all('(xs)=>xs.map(x=>x.value)') == ['supports', 'verifies']
                        page.locator('#phase-view').select_option(options[0])
                        targets = page.evaluate('JSON.parse(document.getElementById("ipd-state").textContent).deliverables.filter(x=>x.owned_files?.some(f=>f.href)).map(x=>x.id)')
                        assert targets, 'No bound-file case in fixture'
                        target = next((x for x in targets if page.locator(f'#status-flow [data-node-id="{x}"]').count()), targets[0])
                        node = page.locator(f'#status-flow [data-node-id="{target}"]')
                        assert node.count() == 1, 'Canonical node identity lost in inline SVG'
                        node.click()
                        page.locator('#details').wait_for(state='visible')
                        assert page.locator('#details').is_visible()
                        assert target in page.locator('#detail-title').inner_text()
                        assert page.locator('#detail-body [data-copy-path]').count()
                        link = page.locator('#detail-body a').first
                        assert link.count() and link.get_attribute('href').startswith('../../')
                        if protocol == 'http': assert context.request.get(urljoin(base, link.get_attribute('href'))).ok
                        if kind == 'synthetic':
                            with page.expect_popup() as event: link.click()
                            popup = event.value
                            popup.wait_for_load_state()
                            assert 'browser file navigation fixture' in popup.locator('body').inner_text()
                            popup.close()
                            assert ('Not generated' if locale == 'en' else '尚未生成') in page.locator('#detail-body').inner_text()
                        copy = page.locator('#detail-body [data-copy-path]').first
                        copy.click()
                        page.wait_for_timeout(100)
                        assert copy.inner_text() in ('Copied', '已复制', 'Select and copy the path', '请选择并复制路径')
                        # Zoom remains functional for inline SVG.
                        page.locator('[data-zoom-for="status-flow"] [data-zoom="in"]').click()
                        assert 'scale(' in page.locator('#status-flow > svg').get_attribute('style')
                        page.locator('#details-close').click()
                        node.focus()
                        page.keyboard.press('Enter')
                        page.locator('#details').wait_for(state='visible')
                        assert page.locator('#details').is_visible()
                        duplicates = page.locator('[id]').evaluate_all('(xs)=>{const ids=xs.map(x=>x.id);return ids.filter((x,i)=>ids.indexOf(x)!==i)}')
                        assert not duplicates, duplicates
                        if locale == 'zh-CN' and protocol == 'file':
                            page.locator('#details-close').click()
                            page.locator('[data-relations-action="default"]').click()
                            page.locator('[data-zoom-for="status-flow"] [data-zoom="reset"]').click()
                            page.locator('#status-flow').screenshot(path=str(output / f'{channel}-{kind}-desktop.png'))
                            page.set_viewport_size({'width': 390, 'height': 844})
                            page.locator('.relation-tools').scroll_into_view_if_needed()
                            page.screenshot(path=str(output / f'{channel}-{kind}-mobile.png'))
                        assert not errors, errors
                        results.append({'channel': channel, 'kind': kind, 'locale': locale,
                                        'protocol': protocol, 'relation_combinations': combinations, 'passed': True})
                        context.close()
                finally:
                    server.shutdown()
                    server.server_close()
            browser.close()
    report = {'passed': all(x['passed'] for x in results), 'results': results}
    (output / 'qualification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--channel', action='append', default=[])
    parser.add_argument('--external-projects', type=Path, help='Local Golden qualification JSON')
    args = parser.parse_args()
    external = json.loads(args.external_projects.read_text(encoding='utf-8'))['locale_projects'] if args.external_projects else {}
    report = run(args.output, args.channel or ['chromium'], external)
    print(json.dumps(report, indent=2))

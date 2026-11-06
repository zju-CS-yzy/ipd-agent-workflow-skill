#!/usr/bin/env python3
"""Public synthetic browser qualification for product/adoption navigation."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ipdctl.project import render_project_dashboard
from ipdctl.state import load_state, write_state
from tests.test_product_governance import ProductGovernanceTests


def run(output, channels):
    from playwright.sync_api import sync_playwright
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    case = ProductGovernanceTests('runTest')
    case.setUp()
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    try:
        case.adopted_pair()
        with sync_playwright() as playwright:
            for locale in ('en', 'zh-CN'):
                profile = load_state(case.root / '.ipd/task_profile.yaml')
                profile['presentation']['locale'] = locale
                write_state(case.root / '.ipd/task_profile.yaml', profile)
                render_project_dashboard(case.root)
                facts = {path.name: path.read_bytes() for path in (case.root / '.ipd').glob('*.yaml')}
                server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(case.root)))
                threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    for channel in channels:
                        browser = playwright.chromium.launch(channel=None if channel == 'chromium' else channel)
                        try:
                            for protocol in ('file', 'http'):
                                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                                errors = []
                                page.on('pageerror', lambda error: errors.append(str(error)))
                                address = ((case.root / '.ipd/dashboard/index.html').as_uri() if protocol == 'file'
                                           else f'http://127.0.0.1:{server.server_port}/.ipd/dashboard/index.html')
                                page.goto(address)
                                page.locator('#dependency-flow g[data-work-key="product:adopt-1"]').click()
                                page.locator('#detail-body [data-copy-path]').first.wait_for()
                                assert 'Algorithm evaluation' in page.locator('#detail-body').inner_text()
                                assert ('Human approval' if locale == 'en' else '人工批准') in page.locator('#detail-body').inner_text()
                                page.locator('#details-close').click()
                                page.locator('#dependency-flow g[data-work-key="product:rec-1"]').click()
                                page.wait_for_function("document.getElementById('detail-body').textContent.includes('prior-reviewer')")
                                assert ('Historical approval declaration' if locale == 'en' else '历史批准声明') in page.locator('#detail-body').inner_text()
                                assert 'test-pc' in page.locator('#detail-body').inner_text()
                                page.locator('#details-close').click()
                                page.locator('#dependency-flow').screenshot(path=str(output / f'{locale}-{channel}-{protocol}.png'))
                                page.set_viewport_size({'width': 390, 'height': 844})
                                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                                page.goto(address.rsplit('/', 1)[0] + '/matrices/deliverable_matrix.html')
                                page.locator('#deliverable-search').fill('rec-1')
                                page.locator('tr[data-work-key="product:rec-1"]').click()
                                assert 'prior-reviewer' in page.locator('#detail-body').inner_text()
                                assert not errors, errors
                                assert all((case.root / '.ipd' / name).read_bytes() == content for name, content in facts.items())
                                results.append({'locale': locale, 'channel': channel, 'protocol': protocol,
                                                'passed': True, 'facts_unchanged': True})
                                page.close()
                        finally:
                            browser.close()
                finally:
                    server.shutdown()
                    server.server_close()
    finally:
        case.doCleanups()
    return {'status': 'passed', 'cases': len(results), 'results': results,
            'scope': 'public synthetic releases and governed target-environment adoption'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--channel', action='append')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.channel or ['chromium']), indent=2))

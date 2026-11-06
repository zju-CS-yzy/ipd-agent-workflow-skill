from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ipdctl.state import write_state
from scripts.stage_development_support import check_dashboard_inventory


class StageQualificationTests(unittest.TestCase):
    def test_exact_inventory_includes_historical_owner_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_state(root / '.ipd/project_state.yaml',
                        {'deliverables': [{'id': 'concept.source'}, {'id': 'plan.result'}]})
            registry = {
                'active_increment': None,
                'instances': [
                    {'id': 'conclusion', 'owner': 'plan.result'},
                    {'id': 'index', 'owner': 'plan.result'},
                ],
                'organization': {
                    'units': [{'increment': 'mvp', 'owner': 'plan.result',
                               'supports': [{'owner': 'concept.source'}],
                               'conclusion': 'conclusion', 'register': None}],
                    'plans': [{'increment': 'mvp', 'index': 'index'}],
                },
            }
            dashboard = root / '.ipd/dashboard'
            base = {
                'index.html', 'governance.md',
                'assets/ipd_flow.svg', 'assets/current_status_flow.svg', 'assets/deliverable_dependency.svg',
                'matrices/deliverable_matrix.html', 'matrices/gate_matrix.html',
                'data/state.json', 'data/graph.json', 'data/requirement_flow.json',
                'phases/concept.svg', 'phases/plan.svg', 'phases/develop.svg',
                'phases/qualify.svg', 'phases/launch.svg', 'phases/lifecycle.svg',
            }
            for relative in base:
                path = dashboard / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic output', encoding='utf-8')
            detail_keys = [
                'deliverable:concept.source', 'deliverable:plan.result',
                'historical:mvp:deliverable:concept.source', 'historical:mvp:deliverable:plan.result',
            ]
            for key in detail_keys:
                relative = 'assets/work/' + hashlib.sha256(key.encode()).hexdigest() + '.js'
                path = dashboard / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                item = {'id': key, 'kind': 'Deliverable'}
                path.write_text('window.ipdWorkDetails.set(' + json.dumps(key) + ',' + json.dumps(item) + ');\n',
                                encoding='utf-8')
                base.add(relative)
            manifest = {
                'files': sorted(base | {'manifest.json'}),
                'outputs': [{'path': '.ipd/dashboard/' + relative,
                             'sha256': hashlib.sha256((dashboard / relative).read_bytes()).hexdigest()}
                            for relative in sorted(base)],
            }
            (dashboard / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(check_dashboard_inventory(root, registry), 21)
            historical = dashboard / ('assets/work/' + hashlib.sha256(detail_keys[-1].encode()).hexdigest() + '.js')
            original = historical.read_bytes()
            historical.unlink()
            with self.assertRaisesRegex(AssertionError, 'missing'):
                check_dashboard_inventory(root, registry)
            historical.write_bytes(original + b'changed')
            with self.assertRaises(AssertionError):
                check_dashboard_inventory(root, registry)
            historical.write_bytes(original)
            (dashboard / 'stale.js').write_text('obsolete', encoding='utf-8')
            with self.assertRaisesRegex(AssertionError, 'unexpected'):
                check_dashboard_inventory(root, registry)

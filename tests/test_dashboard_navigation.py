"""File navigation and self-contained large-graph regression coverage."""
from copy import deepcopy
from itertools import combinations
import json
import re
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ipdctl.dashboard import render_dashboard
from ipdctl.dashboard_files import project_file_navigation
from ipdctl.dashboard_svg import render_svg
from ipdctl.state import create_initial_state
from ipdctl.tailoring import tailor_profile
from tests.test_dashboard import canonical_fixture, node_boxes


class DashboardNavigationTests(unittest.TestCase):
    def test_binding_expansion_missing_files_shared_evidence_and_escaping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'docs/中文 # & 空格.md'
            path.parent.mkdir()
            path.write_text('fixture', encoding='utf-8')
            items = [{'id': 'a', 'evidence': ['docs/中文 # & 空格.md', '../outside.md',
                                            'javascript:alert(1)', 'https://example.org/evidence']}]
            bindings = {'schema_version': '1.0', 'bindings': [
                {'id': 'owner', 'glob': 'docs/**', 'deliverable': 'a'},
                {'id': 'future', 'paths': ['future.md'], 'deliverable': 'a'},
                {'id': 'shared', 'glob': 'docs/**', 'role': 'shared_evidence',
                 'deliverables': ['a'], 'critical': False},
                {'id': 'empty', 'glob': 'unmatched/**', 'deliverable': 'a'}]}
            project_file_navigation(root, items, bindings)
            item = items[0]
            self.assertEqual([x['path'] for x in item['owned_files']],
                             ['docs/中文 # & 空格.md', 'future.md'])
            self.assertEqual(item['owned_files'][0]['href'],
                             '../../docs/%E4%B8%AD%E6%96%87%20%23%20%26%20%E7%A9%BA%E6%A0%BC.md')
            self.assertIsNone(item['owned_files'][1]['href'])
            self.assertEqual(len(item['shared_files']), 1)
            self.assertEqual(len(item['file_binding_rules']), 4)
            self.assertIsNone(item['evidence_files'][1]['href'])
            self.assertIsNone(item['evidence_files'][2]['href'])
            self.assertTrue(item['evidence_files'][3]['external'])

    def test_navigation_does_not_follow_links_or_include_managed_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.ipd/dashboard').mkdir(parents=True)
            (root / '.ipd/dashboard/index.html').write_text('generated')
            (root / 'real.txt').write_text('real')
            from unittest.mock import patch
            with patch('ipdctl.dashboard_files._reparse', side_effect=lambda p: p.name == 'real.txt'):
                items = [{'id': 'a'}]
                project_file_navigation(root, items, {'bindings': [
                    {'id': 'all', 'glob': '**', 'deliverable': 'a'}]})
            self.assertEqual(items[0]['owned_files'], [])

    def test_ignore_precedence_matches_binding_reconciliation_for_both_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'visible.txt').write_text('visible')
            (root / 'ignored.txt').write_text('ignored')
            items = [{'id': 'a', 'evidence': ['ignored.txt']}]
            project_file_navigation(root, items, {'ignore': ['ignored.txt', 'future.txt'], 'bindings': [
                {'id': 'owner', 'glob': '**', 'deliverable': 'a'},
                {'id': 'exact', 'paths': ['ignored.txt', 'future.txt'], 'deliverable': 'a'},
                {'id': 'shared', 'glob': '**', 'role': 'shared_evidence', 'deliverables': ['a'], 'critical': False}]})
            self.assertEqual([x['path'] for x in items[0]['owned_files']], ['visible.txt'])
            self.assertEqual([x['path'] for x in items[0]['shared_files']], ['visible.txt'])
            # Explicit recorded evidence remains inspectable independently of ownership.
            self.assertEqual(items[0]['evidence_files'][0]['path'], 'ignored.txt')
            self.assertTrue(items[0]['evidence_files'][0]['exists'])

    def test_all_six_task_types_have_bilingual_interactive_output_contract(self):
        for task_type in ('software', 'hardware', 'embedded', 'robotics', 'ai_system', 'material_change'):
            process = tailor_profile({'schema_version': '1.0', 'project_name': 'contract', 'task_types': [task_type]})
            state = create_initial_state('contract', [task_type])
            for locale in ('en', 'zh-CN'):
                with self.subTest(task_type=task_type, locale=locale), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    manifest = render_dashboard(root, process, state, locale=locale)
                    self.assertEqual(len(manifest['files']), 16)
                    self.assertEqual(manifest['locale'], locale)
                    html = (root / '.ipd/dashboard/index.html').read_text(encoding='utf-8')
                    self.assertEqual(html.count('data-relation-toggle value='), 5)
                    self.assertNotIn('__SVG_TEMPLATES__', html)
                    self.assertNotIn('<object ', html)

    def test_inline_graphs_have_scoped_ids_and_portable_navigation_in_both_locales(self):
        process, state = canonical_fixture()
        for locale in ('en', 'zh-CN'):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'output.txt').write_text('fixture')
                original = deepcopy((process, state))
                render_dashboard(root, process, state, locale=locale, bindings={
                    'bindings': [{'id': 'file', 'paths': ['output.txt'],
                                  'deliverable': state['deliverables'][0]['id']}]})
                dashboard = root / '.ipd/dashboard'
                html = (dashboard / 'index.html').read_text(encoding='utf-8')
                self.assertNotIn('<object ', html)
                self.assertIn('data-relations-action="default"', html)
                self.assertEqual(html.count('data-relation-toggle value='), 5)
                self.assertIn('value="depends_on" checked', html)
                self.assertIn('data-copy-path', html)
                self.assertNotIn(str(root), html)
                graph = json.loads((dashboard / 'data/graph.json').read_text(encoding='utf-8'))
                inline_ids = set(re.findall(r'data-node-id="([^"]+)"', html))
                self.assertTrue(inline_ids)
                self.assertLessEqual(inline_ids, {node['id'] for node in graph['nodes']})
                data = json.loads((dashboard / 'data/state.json').read_text(encoding='utf-8'))
                self.assertEqual(data['deliverables'][0]['owned_files'][0]['href'], '../../output.txt')
                self.assertEqual((process, state), original)
                first = {p.relative_to(dashboard): p.read_bytes() for p in dashboard.rglob('*') if p.is_file()}
                render_dashboard(root, process, state, locale=locale, bindings={
                    'bindings': [{'id': 'file', 'paths': ['output.txt'],
                                  'deliverable': state['deliverables'][0]['id']}]})
                self.assertEqual(first, {p.relative_to(dashboard): p.read_bytes() for p in dashboard.rglob('*') if p.is_file()})

    def test_large_graph_300_nodes_preserves_relations_direction_and_layout(self):
        graph = {'nodes': [{'id': f'd{i:03}', 'type': 'Deliverable', 'phase': 'concept',
                            'title': f'交付物 {i} / Long bilingual deliverable label',
                            'status': 'planned'} for i in range(300)], 'edges': []}
        relations = ('depends_on', 'supports', 'verifies', 'supersedes', 'refines')
        for i in range(1, 300):
            graph['edges'].append({'source': f'd{i:03}', 'target': f'd{(i-1)//3:03}',
                                   'relation': 'depends_on'})
            if i % 5 == 0:
                for relation in relations[1:]:
                    graph['edges'].append({'source': f'd{i:03}', 'target': 'd000', 'relation': relation})
        for locale in ('en', 'zh-CN'):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as directory:
                svg = render_svg(graph, title='Large graph regression', locale=locale)
                tree = ET.fromstring(svg)
                self.assertEqual(tree.attrib['data-node-count'], '300')
                ns = {'svg': 'http://www.w3.org/2000/svg'}
                edges = tree.findall('.//svg:path[@data-relation]', ns)
                self.assertEqual(len(edges), len(graph['edges']))
                self.assertEqual({e.attrib['data-relation'] for e in edges}, set(relations))
                for edge in edges:
                    if edge.attrib['data-relation'] == 'depends_on':
                        self.assertEqual(edge.attrib['data-visual-source'], edge.attrib['data-target'])
                        self.assertEqual(edge.attrib['data-visual-target'], edge.attrib['data-source'])
                path = Path(directory) / 'large.svg'
                path.write_text(svg, encoding='utf-8')
                for left, right in combinations(node_boxes(path), 2):
                    _, x, y, w, h = left
                    _, xx, yy, ww, hh = right
                    self.assertTrue(x+w <= xx or xx+ww <= x or y+h <= yy or yy+hh <= y)


if __name__ == '__main__':
    unittest.main()

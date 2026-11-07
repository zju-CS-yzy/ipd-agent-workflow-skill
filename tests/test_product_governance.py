from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
from contextlib import redirect_stdout, redirect_stderr
import unittest

from ipdctl.cli import main
from ipdctl.documents import RequirementError, digest
from ipdctl.product_governance import claim_issues, impact, issues, records
from ipdctl.requirement_contract import SCHEMA, validate
from ipdctl.requirements import apply_plan, preview, read_registry
from ipdctl.state import load_state, write_state
from ipdctl.tailoring import tailor_profile
from ipdctl.project import sync_state_with_process, render_project_dashboard
from tests import test_requirements as fixtures


class ProductGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RequirementTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        process = load_state(self.root / '.ipd/tailored_process.yaml')
        activity = process['deliverables'][0]['activity_id']
        extension = load_state(self.root / '.ipd/process_extensions.yaml')
        owners = ['recorder', 'dataset', 'check', 'check2', 'adopt', 'upgrade', 'consume']
        extension['deliverables'] = [
            {'id': 'concept.' + name, 'title': name, 'phase': 'concept', 'activity_id': activity,
             'review_required': True, 'depends_on': ['concept.adopt'] if name == 'consume' else []}
            for name in owners]
        write_state(self.root / '.ipd/process_extensions.yaml', extension)
        process = tailor_profile(load_state(self.root / '.ipd/task_profile.yaml'), extension)
        write_state(self.root / '.ipd/tailored_process.yaml', process)
        write_state(self.root / '.ipd/project_state.yaml',
                    sync_state_with_process(self.fixture.state(), process))
        bindings = load_state(self.root / '.ipd/artifact_bindings.yaml')
        bindings['bindings'].extend(
            {'id': name, 'glob': 'products/' + name + '/**', 'deliverable': 'concept.' + name, 'role': 'owner'}
            for name in owners)
        write_state(self.root / '.ipd/artifact_bindings.yaml', bindings)
        self.fixture.basic_scope()
        self.fixture.execute('adopt_product_governance')
        for name in ('recorder', 'replay'):
            self.fixture.execute('product_register', product={'id': name, 'title': name, 'scope': 'Enabling tool'})

    def invoke(self, *args, expected=0):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(map(str, args)))
        self.assertEqual(code, expected, out.getvalue() + err.getvalue())
        return out.getvalue()

    def proof(self, path, content='synthetic measured result'):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return {'path': path, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}

    def release(self, identifier, product='recorder', version='1.0', protocol='v1', path=None, content=None):
        artifact = self.proof(path or 'imports/' + identifier + '.txt', identifier if content is None else content)
        return {'id': identifier, 'product': product, 'version': version, 'scope': 'Synthetic capture or playback',
                'source': {'backend': 'content', 'repository': 'local-fixture',
                           'revision': digest([artifact]), 'path': '.'},
                'protocol': protocol, 'environments': ['dev-pc', 'test-pc'],
                'capabilities': ['capture' if product == 'recorder' else 'playback'],
                'requirements': ['ir-1@1'], 'artifacts': [artifact]}

    def imported(self, identifier, **fields):
        record = self.release(identifier, **fields)
        self.fixture.execute('product_import', **{'import': {
            'release': record, 'approver': 'prior-reviewer',
            'approval': self.proof('imports/' + identifier + '-approval.md', 'Old version approval'),
            'identity_source': 'historical-local-declaration'}})
        return record

    def start(self, owner):
        self.invoke('adopt-baseline', self.root, '--actor', 'fixture-human', '--actor-type', 'human',
                    '--authorized', '--reason', 'Accept synthetic project files')
        self.invoke('refresh', self.root)
        self.invoke('verify', self.root, '--json')
        self.invoke('claim', 'concept.' + owner, '--project-root', self.root, '--actor', 'fixture-agent')

    def work(self, kind, owner, record):
        return self.fixture.execute('product_work', actor='fixture-agent', kind=kind,
                                    owner='concept.' + owner, record=record)

    def finish(self, owner, record_id, evidence):
        identifier = 'concept.' + owner
        self.invoke('close', identifier, '--project-root', self.root, '--actor', 'fixture-agent',
                    '--evidence', evidence)
        self.invoke('review', identifier, '--project-root', self.root, '--reviewer', 'fixture-reviewer')
        self.invoke('approve', identifier, '--project-root', self.root, '--reviewer', 'fixture-human',
                    '--actor-type', 'human', '--authorized', '--evidence', evidence)
        self.fixture.execute('product_accept', work=record_id)

    def check(self, identifier='pair-1', environment='test-pc', datasets=None):
        return {'id': identifier, 'releases': ['rec-1', 'replay-1'], 'datasets': datasets or [],
                'protocol': 'v1', 'environment': environment, 'cases': [
                    {'id': 'roundtrip', 'criterion': 'Preserve sample count and time order',
                     'expected': '8 samples, ordered timestamps', 'observed': '8 samples, ordered timestamps',
                     'result': 'passed'}], 'evidence': self.proof('products/check/roundtrip.json')}

    def adopted_pair(self):
        self.imported('rec-1')
        self.imported('replay-1', product='replay')
        self.start('check')
        check = self.check()
        self.work('compatibility', 'check', check)
        self.finish('check', 'pair-1', check['evidence']['path'])
        self.start('adopt')
        adoption = {'id': 'adopt-1', 'key': 'algorithm-input', 'purpose': 'Algorithm evaluation',
                    'releases': ['rec-1', 'replay-1'], 'datasets': [], 'checks': ['pair-1'],
                    'protocol': 'v1', 'environment': 'test-pc', 'consumers': ['concept.consume'],
                    'evidence': self.proof('products/adopt/applicability.md'),
                    'prior': None, 'assessments': []}
        self.work('adoption', 'adopt', adoption)
        self.finish('adopt', 'adopt-1', adoption['evidence']['path'])
        return adoption

    def test_pinned_pair_requires_separate_adoption_and_rejects_changed_evidence(self):
        adoption = self.adopted_pair()
        registry = read_registry(self.root)
        self.assertEqual(set(records(registry, 'release')), {'rec-1', 'replay-1'})
        self.assertEqual(issues(self.root, registry, 'adoption', adoption), [])
        render_project_dashboard(self.root)
        graph = json.loads((self.root / '.ipd/dashboard/data/graph.json').read_text(encoding='utf-8'))
        self.assertTrue(any(edge['source'] == 'product:rec-1' and edge['target'] == 'product:adopt-1'
                            for edge in graph['edges']))
        self.imported('rec-2', version='2.0', protocol='v2')
        registry = read_registry(self.root)
        self.assertEqual(registry['components']['works'][-1]['record']['releases'], ['rec-1', 'replay-1'])
        before = self.fixture.bytes()
        report = impact(registry, 'rec-1', 'rec-2')
        self.assertIn('protocol', report['changed'])
        self.assertEqual(report['consumers'], ['concept.consume'])
        self.assertFalse(report['pins_changed'])
        self.assertEqual(before, self.fixture.bytes())
        self.proof('products/check/roundtrip.json', 'changed observations')
        self.assertTrue(claim_issues(self.root, read_registry(self.root), self.fixture.state(), 'concept.consume'))

    def test_new_recorder_release_uses_normal_review_without_ending_main_increment(self):
        self.imported('rec-1')
        self.start('recorder')
        record = self.release('rec-2', version='2.0', path='products/recorder/rec-2.txt')
        plan = self.work('release', 'recorder', record)
        before = self.fixture.bytes()
        with self.assertRaisesRegex(RequirementError, 'GOVERNANCE_ACTIVE'):
            self.fixture.execute('product_accept', work='rec-2')
        self.assertEqual(before, self.fixture.bytes())
        self.finish('recorder', 'rec-2', record['artifacts'][0]['path'])
        registry = read_registry(self.root)
        self.assertEqual(registry['active_increment'], 'mvp')
        self.assertEqual(set(records(registry, 'release')), {'rec-1', 'rec-2'})
        self.assertFalse(registry['baselines'])
        with self.assertRaisesRegex(RequirementError, 'SCOPE_GOVERNED'):
            self.fixture.execute('scope', scope=[])

    def test_unknown_test_environment_is_not_satisfied_by_developer_pc_results(self):
        self.imported('rec-1')
        self.imported('replay-1', product='replay')
        self.start('check')
        record = self.check(environment='dev-pc')
        record['cases'][0]['result'] = 'unknown'
        plan = self.work('compatibility', 'check', record)
        self.assertFalse(plan['ready_for_review'])
        self.invoke('close', 'concept.check', '--project-root', self.root, '--actor', 'fixture-agent',
                    '--evidence', record['evidence']['path'], expected=1)
        record['cases'][0]['result'] = 'passed'
        self.work('compatibility', 'check', record)
        self.finish('check', record['id'], record['evidence']['path'])
        self.start('adopt')
        adoption = {'id': 'test-adopt', 'key': 'algorithm-input', 'purpose': 'Target PC testing',
                    'releases': ['rec-1', 'replay-1'], 'datasets': [], 'checks': ['pair-1'],
                    'protocol': 'v1', 'environment': 'test-pc', 'consumers': ['concept.consume'],
                    'evidence': self.proof('products/adopt/applicability.md'), 'prior': None, 'assessments': []}
        self.work('adoption', 'adopt', adoption)
        self.assertIn('PRODUCT_COMPATIBILITY_UNKNOWN:test-adopt',
                      issues(self.root, read_registry(self.root), 'adoption', adoption))

    def test_adoption_preview_preserves_legacy_and_old_contract_rejects_new_facts(self):
        from ipdctl.requirement_contract import LEGACY_SCHEMA
        registry = read_registry(self.root)
        self.assertEqual(registry['contract'], '0.5.7')
        validate(registry, SCHEMA)
        with self.assertRaises(RequirementError):
            validate(registry, LEGACY_SCHEMA)
        adoption = registry['components']['adoption']
        snapshot = json.loads((self.root / adoption['path']).read_text(encoding='utf-8'))
        self.assertNotIn('components', snapshot['registry'])
        (self.root / adoption['path']).write_text('{}', encoding='utf-8')
        from ipdctl.requirements import input_snapshot
        with self.assertRaisesRegex(RequirementError, 'HISTORY_TAMPERED'):
            input_snapshot(self.root)

    def test_dataset_is_a_separate_reviewed_input_and_must_match_recorder_version(self):
        self.imported('rec-1')
        self.start('dataset')
        dataset = {
            'id': 'capture-1', 'recorder': 'rec-1', 'protocol': 'v1', 'environment': 'test-pc',
            'configuration': '8 samples at 100 Hz', 'calibration': 'Synthetic zero offset',
            'time_basis': 'Monotonic 10 ms steps',
            'files': [self.proof('products/dataset/data.json', '[0,1,2,3,4,5,6,7]')],
            'quality': {'cases': [{'id': 'count', 'criterion': 'Exactly 8 samples',
                                  'expected': '8', 'observed': '8', 'result': 'passed'}],
                        'evidence': self.proof('products/dataset/quality.json', '{"count":8}')},
        }
        self.work('dataset', 'dataset', dataset)
        self.assertNotIn('capture-1', records(read_registry(self.root), 'dataset'))
        self.finish('dataset', 'capture-1', dataset['quality']['evidence']['path'])
        self.imported('rec-2', version='2.0')
        registry = read_registry(self.root)
        check = self.check(datasets=['capture-1'])
        check['releases'] = ['rec-2']
        self.assertIn('PRODUCT_DATASET_CONTEXT:capture-1', issues(self.root, registry, 'compatibility', check))

    def test_withdrawal_suspends_selected_use_and_old_approval_remains_recorded(self):
        self.adopted_pair()
        before = deepcopy(read_registry(self.root)['components']['acceptances'])
        self.fixture.execute('product_withdraw', release='rec-1')
        registry = read_registry(self.root)
        self.assertEqual(registry['components']['acceptances'], before)
        self.assertIn('PRODUCT_WITHDRAWN:rec-1',
                      claim_issues(self.root, registry, self.fixture.state(), 'concept.consume'))
        self.invoke('refresh', self.root)
        self.invoke('verify', self.root, '--json')
        self.invoke('claim', 'concept.recorder', '--project-root', self.root, '--actor', 'fixture-agent')

    def test_stale_plan_and_transaction_failure_leave_no_product_history(self):
        from unittest.mock import patch
        record = self.release('rec-1')
        request = self.fixture.request('product_import', **{'import': {
            'release': record, 'approver': 'old-human', 'approval': self.proof('imports/approval.md'),
            'identity_source': 'historical-local-declaration'}})
        before = self.fixture.bytes()
        plan = preview(self.root, request)
        self.assertEqual(before, self.fixture.bytes())
        self.proof(record['artifacts'][0]['path'], 'modified artifact')
        with self.assertRaises(RequirementError):
            apply_plan(self.root, plan, actor='human', authorized=True)
        self.proof(record['artifacts'][0]['path'], 'rec-1')
        before = self.fixture.bytes()
        with patch('ipdctl.requirements.write_state', side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):
                apply_plan(self.root, plan, actor='human', authorized=True)
        self.assertEqual(before, self.fixture.bytes())

    def test_handoff_creates_bilingual_drafts_and_preserves_old_owner_and_source(self):
        self.start('recorder')
        record = self.release('rec-1', path='products/recorder/source.md')
        self.work('release', 'recorder', record)
        self.finish('recorder', 'rec-1', record['artifacts'][0]['path'])
        from ipdctl.product_governance import handoff_preview
        request = {'request_id': 'handoff-1', 'reason': 'Create maintained draft',
                   'source_owner': 'concept.recorder', 'target_owner': 'concept.adopt',
                   'files': [{'source': record['artifacts'][0]['path'], 'target': 'docs/en/interface.md'}]}
        before = self.fixture.bytes()
        planned = handoff_preview(self.root, request)
        self.assertEqual(before, self.fixture.bytes())
        self.assertEqual(planned['candidate_bindings'][0]['deliverable'], 'concept.adopt')
        bindings_path = self.root / '.ipd/artifact_bindings.yaml'
        original_bindings = bindings_path.read_bytes()
        ignored = load_state(bindings_path)
        ignored['ignore'].append('docs/en/**')
        write_state(bindings_path, ignored)
        ignored_plan = handoff_preview(self.root, request)
        self.assertIn('HANDOFF_IGNORED:docs/en/interface.md', ignored_plan['issues'])
        self.assertFalse(ignored_plan['ready_for_authoring'])
        self.assertEqual(ignored_plan['candidate_bindings'], [])
        bindings_path.write_bytes(original_bindings)
        bindings = load_state(self.root / '.ipd/artifact_bindings.yaml')
        bindings['bindings'].append({'id': 'handoff-docs', 'glob': 'docs/**',
                                     'deliverable': 'concept.adopt', 'role': 'owner'})
        write_state(self.root / '.ipd/artifact_bindings.yaml', bindings)
        self.start('adopt')
        old_owner = deepcopy(next(item for item in self.fixture.state()['deliverables'] if item['id'] == 'concept.recorder'))
        original = (self.root / record['artifacts'][0]['path']).read_bytes()
        for locale in ('en', 'zh-CN'):
            instance = {'id': 'draft-' + locale.lower(), 'key': locale.lower(), 'requirements': ['ir-1@1'],
                        'owner': 'concept.adopt', 'document_type': 'interface_spec',
                        'path': 'docs/' + locale + '/interface.md', 'title': 'Maintained interface',
                        'scope': 'Current tool', 'locale': locale}
            plan = self.fixture.execute('handoff_instance', actor='fixture-agent',
                                 source=record['artifacts'][0]['path'], source_owner='concept.recorder',
                                 sha256=record['artifacts'][0]['sha256'], editor='fixture-agent', instance=instance)
            self.assertIn(instance['path'], plan['documents'])
            text = (self.root / instance['path']).read_text(encoding='utf-8')
            self.assertIn('[[TODO:', text)
            self.assertIn('ipd-origin', text)
        self.assertEqual(original, (self.root / record['artifacts'][0]['path']).read_bytes())
        self.assertEqual(old_owner, next(item for item in self.fixture.state()['deliverables'] if item['id'] == 'concept.recorder'))
        self.proof(record['artifacts'][0]['path'], 'source changed after handoff')
        from ipdctl.requirements import readiness
        self.assertIn('HANDOFF_STALE:draft-en',
                      readiness(self.root, read_registry(self.root), self.fixture.state(),
                                stage='TR4', owner='concept.adopt'))

    def test_version_switch_invalidates_consumer_verification_only_after_accepted_adoption(self):
        from ipdctl.requirement_verification import verification_context
        from ipdctl.product_governance import selections
        self.adopted_pair()
        self.fixture.execute('link', link={'increment': 'mvp', 'requirement': 'ir-1@1',
            'relation': 'allocated_to', 'target': 'concept.consume', 'rationale': 'Evaluation consumes this adoption'})
        before = verification_context(self.root, read_registry(self.root), 'ir-1@1')
        self.imported('rec-2', version='2.0')
        self.assertEqual(before, verification_context(self.root, read_registry(self.root), 'ir-1@1'))
        self.start('check2')
        check = self.check('pair-2')
        check['releases'] = ['rec-2', 'replay-1']
        check['evidence'] = self.proof('products/check2/roundtrip.json')
        self.work('compatibility', 'check2', check)
        self.finish('check2', 'pair-2', check['evidence']['path'])
        extension = load_state(self.root / '.ipd/process_extensions.yaml')
        extension.setdefault('dependencies', []).append(
            {'source': 'concept.consume', 'target': 'concept.upgrade', 'relation': 'depends_on'})
        write_state(self.root / '.ipd/process_extensions.yaml', extension)
        self.invoke('tailor', self.root, '--preview', '--json')
        self.invoke('tailor', self.root)
        self.start('upgrade')
        adoption = deepcopy(records(read_registry(self.root), 'adoption')['adopt-1'])
        adoption.update(id='adopt-2', prior='adopt-1', releases=['rec-2', 'replay-1'], checks=['pair-2'],
                        evidence=self.proof('products/upgrade/applicability.md'),
                        assessments=[{'target': 'concept.consume', 'action': 'reverify', 'rationale': 'New capture binary'}])
        self.work('adoption', 'upgrade', adoption)
        self.assertEqual(selections(read_registry(self.root))[0]['id'], 'adopt-1')
        self.assertEqual(before, verification_context(self.root, read_registry(self.root), 'ir-1@1'))
        self.finish('upgrade', 'adopt-2', adoption['evidence']['path'])
        self.assertEqual(selections(read_registry(self.root))[0]['id'], 'adopt-2')
        self.assertNotEqual(before, verification_context(self.root, read_registry(self.root), 'ir-1@1'))

    def test_real_record_and_replay_data_reaches_the_main_consumer(self):
        import subprocess
        import sys
        recorder = ("import json,sys\nfrom pathlib import Path\n"
                    "data={'format':'frames-v1','frames':[{'t_ms':n*10,'value':n} for n in range(8)]}\n"
                    "Path(sys.argv[1]).write_text(json.dumps(data),encoding='utf-8')\n")
        replay = ("import json,sys\nfrom pathlib import Path\n"
                  "data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
                  "assert data['format']=='frames-v1'\nrows=data['frames']\n"
                  "assert len(rows)==8 and [row['t_ms'] for row in rows]==list(range(0,80,10))\n"
                  "print(json.dumps({'samples':len(rows),'last_ms':rows[-1]['t_ms'],'ordered':True}))\n")
        self.imported('rec-1')
        replay_release = self.imported('replay-1', product='replay', path='imports/replay.py', content=replay)
        self.start('recorder')
        record = self.release('rec-2', version='2.0', path='products/recorder/capture.py', content=recorder)
        self.work('release', 'recorder', record)
        self.finish('recorder', 'rec-2', record['artifacts'][0]['path'])
        self.start('dataset')
        data_path = self.root / 'products/dataset/frames.json'
        data_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, '-B', str(self.root / record['artifacts'][0]['path']), str(data_path)], check=True)
        def replay_result():
            return subprocess.check_output([sys.executable, '-B',
                str(self.root / replay_release['artifacts'][0]['path']), str(data_path)], text=True)
        observed = replay_result()
        self.assertEqual(json.loads(observed), {'samples': 8, 'last_ms': 70, 'ordered': True})
        case = {'id': 'roundtrip', 'criterion': 'Eight ordered 10 ms samples', 'expected': '8,70,true',
                'observed': observed.strip(), 'result': 'passed'}
        dataset = {'id': 'frames-2', 'recorder': 'rec-2', 'protocol': 'v1', 'environment': 'test-pc',
                   'configuration': '8 samples / 10 ms', 'calibration': 'Synthetic integer ramp',
                   'time_basis': 'Synthetic monotonic milliseconds',
                   'files': [{'path': 'products/dataset/frames.json', 'sha256': hashlib.sha256(data_path.read_bytes()).hexdigest()}],
                   'quality': {'cases': [case], 'evidence': self.proof('products/dataset/quality.json', observed)}}
        self.work('dataset', 'dataset', dataset)
        self.finish('dataset', 'frames-2', dataset['quality']['evidence']['path'])
        self.start('check')
        check = self.check(datasets=['frames-2'])
        check.update(releases=['rec-2', 'replay-1'], cases=[case],
                     evidence=self.proof('products/check/roundtrip.json', replay_result()))
        self.work('compatibility', 'check', check)
        self.finish('check', 'pair-1', check['evidence']['path'])
        self.start('adopt')
        adoption = {'id': 'data-adoption', 'key': 'algorithm-input', 'purpose': 'Synthetic algorithm evaluation',
                    'releases': ['rec-2', 'replay-1'], 'datasets': ['frames-2'], 'checks': ['pair-1'],
                    'protocol': 'v1', 'environment': 'test-pc', 'consumers': ['concept.consume'],
                    'prior': None, 'assessments': [], 'evidence': self.proof('products/adopt/applicability.md', observed)}
        self.work('adoption', 'adopt', adoption)
        self.finish('adopt', 'data-adoption', adoption['evidence']['path'])
        self.start('consume')
        self.assertEqual(json.loads(replay_result())['samples'], 8)

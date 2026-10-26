"""Independent entity, governance and current-vs-history expectations."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from ipdctl.dashboard import render_dashboard
from ipdctl.dashboard_model import build_dashboard_model
from ipdctl.dashboard_work import projection, enrich_graph, matrix, stage_panel
from ipdctl.documents import RequirementError
from ipdctl.requirement_contract import ORGANIZED_SCHEMA, validate
from ipdctl.requirements import preview, apply_plan, read_registry, input_snapshot
from ipdctl.state import load_state, write_state
from ipdctl.work_planning import preview as work_preview, check
from tests import test_stage_organization as stage_tests


class WorkProductTests(unittest.TestCase):
    def setUp(self):
        self.case = stage_tests.StageOrganizationTests('runTest'); self.case.setUp()
        self.addCleanup(self.case.doCleanups); self.root = self.case.root

    def prepare(self):
        self.case.tree(); self.case.plan('TR2')
        self.case.f.execute('adopt_work_products', roles=[])
        return self.case.owner('plan')

    def request(self, consumer):
        return {'request_id':'professional-plan', 'reason':'Independent selection analysis', 'stage':'TR2',
                'consumer':consumer, 'materials':[{'id':'plan.selection', 'title':'Independent interface selection',
                'path':'docs/shared 资料 #&.md', 'usage':'deliverable', 'required':True,
                'rationale':'Timing budget for both IR branches', 'execution_dependency':True}]}

    def test_historical_material_never_joins_current_owner_acceptance(self):
        state={'deliverables':[{'id':'plan.result','title':'Current result','phase':'plan',
                               'owner':'team','status':'planned','depends_on':[]}]}
        data={'active_increment':'next','requirements':[],'increments':[], 'flow':{'units':[],
              'nodes':[{'id':'owner:previous:plan.result','type':'Deliverable','label':'plan.result',
                        'core_id':'plan.result','increment':'previous','status':'accepted'},
                       {'id':'previous:artifact:docs/shared.md:old-hash','type':'Artifact','label':'docs/shared.md',
                        'owner':'plan.result','availability':'historical','href':'../requirement_history/old.json'},
                       {'id':'next:artifact:docs/shared.md:new-hash','type':'Artifact','label':'docs/shared.md',
                        'owner':'plan.result','availability':'stale','href':'../../docs/shared.md'}],
              'edges':[{'source':'previous:artifact:docs/shared.md:old-hash','target':'owner:previous:plan.result','relation':'owned_by'}]}}
        model=projection(state,data);entities={e['id']:e for e in model['entities']}
        self.assertEqual(entities['deliverable:plan.result']['status'],'planned')
        self.assertEqual(entities['historical:previous:deliverable:plan.result']['status'],'accepted')
        files=[e for e in model['entities'] if e['kind']=='Material']
        self.assertEqual(len(files),2);self.assertEqual({e['status'] for e in files},{'historical','stale'})
        old=next(e for e in files if e['historical'])
        self.assertEqual(old['related'],['historical:previous:deliverable:plan.result'])

    def test_adoption_preserves_v054_and_rejects_old_contract_and_stale_retry(self):
        self.case.tree(); self.case.plan('TR2')
        old=deepcopy(self.case.registry()); before=self.case.f.bytes()
        request=self.case.f.request('adopt_work_products',roles=[]); plan=preview(self.root,request)
        self.assertEqual(before,self.case.f.bytes())
        with self.assertRaisesRegex(RequirementError,'AUTHORIZATION_REQUIRED'):
            apply_plan(self.root,plan,actor='human',authorized=False)
        apply_plan(self.root,plan,actor='human',authorized=True)
        adopted=self.case.registry(); self.assertEqual(adopted['schema_version'],'1.2')
        saved=json.loads((self.root/adopted['organization']['work_adoption']['path']).read_text(encoding='utf-8'))
        self.assertEqual(saved['registry'],old)
        with self.assertRaises(RequirementError): validate(adopted,ORGANIZED_SCHEMA)
        self.assertEqual(apply_plan(self.root,plan,actor='human',authorized=True)['status'],'already_applied')
        (self.root/adopted['organization']['work_adoption']['path']).write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(RequirementError,'HISTORY_TAMPERED'): input_snapshot(self.root)

    def test_professional_preview_compiles_real_extension_without_writes_and_detects_staleness(self):
        owner=self.prepare(); before=self.case.f.bytes(); plan=work_preview(self.root,self.request(owner))
        self.assertEqual(before,self.case.f.bytes()); self.assertTrue(plan['ready_for_authoring'])
        self.assertEqual(plan['materials'][0]['governance_owner'],'plan.selection')
        self.assertEqual(len(plan['candidate_stage_units']),2)
        self.assertIn({'source':owner,'target':'plan.selection','relation':'depends_on'},plan['candidate_process_extensions']['dependencies'])
        self.assertEqual(check(self.root,plan)['status'],'current')
        (self.root/'docs').mkdir(exist_ok=True); (self.root/'docs/shared 资料 #&.md').write_text('new content',encoding='utf-8')
        with self.assertRaisesRegex(RequirementError,'WORK_PLAN_STALE'): check(self.root,plan)

    def test_support_is_not_an_implicit_execution_dependency(self):
        owner=self.prepare(); request=self.request(owner); request['materials'][0]['execution_dependency']=False
        plan=work_preview(self.root,request)
        self.assertFalse(plan['ready_for_authoring'])
        self.assertIn('SUPPORT_DEPENDENCY_REQUIRED:plan.selection',plan['issues'])
        self.assertNotIn({'source':owner,'target':'plan.selection','relation':'depends_on'},plan['candidate_process_extensions'].get('dependencies',[]))

    def test_boundary_conflict_escape_and_cycles_fail_closed(self):
        owner=self.prepare(); request=self.request(owner)
        self.case.bindings(owner)
        plan=work_preview(self.root,request)
        self.assertIn('WORK_PLAN_OWNER_CONFLICT:docs/shared 资料 #&.md',plan['issues'])
        bad=deepcopy(request);bad['materials'][0]['path']='../escape.md'
        with self.assertRaises(ValueError):work_preview(self.root,bad)
        bad=deepcopy(request);bad['materials'][0]['depends_on']=[owner]
        with self.assertRaises(ValueError):work_preview(self.root,bad)
        self.case.work(owner)
        self.assertIn('WORK_PLAN_ACTIVE: finish the Claim/review before changing process or bindings',work_preview(self.root,request)['issues'])

    def test_declared_roles_required_and_owner_acceptance_not_copied_to_file(self):
        owner=self.prepare(); self.case.bindings(owner)
        unit=deepcopy(self.case.registry()['organization']['units'][0])
        unit['supports']=[{'kind':'artifact','target':'docs/missing.md','owner':owner,'required':False,
                          'rationale':'Optional reference','anchor':'','sha256':None}]
        with self.assertRaisesRegex(RequirementError,'SUPPORT_USAGE'):self.case.f.execute('stage_unit',unit=unit)
        unit['supports'][0]['usage']='deliverable'
        with self.assertRaisesRegex(RequirementError,'SUPPORT_DELIVERABLE'):self.case.f.execute('stage_unit',unit=unit)
        unit['supports'][0]['usage']='reference';self.case.f.execute('stage_unit',unit=unit)
        state=self.case.f.state();next(d for d in state['deliverables'] if d['id']==owner)['status']='accepted'
        write_state(self.root/'.ipd/project_state.yaml',state)
        from ipdctl.requirements import projection as requirements
        core,_=build_dashboard_model(load_state(self.root/'.ipd/tailored_process.yaml'),state)
        model=projection(core,requirements(self.root))
        file=next(e for e in model['entities'] if e['kind']=='Reference')
        self.assertEqual(file['availability'],'missing');self.assertEqual(file['status'],'missing')
        self.assertEqual(next(e for e in model['entities'] if e['id']=='deliverable:'+owner)['status'],'accepted')
        self.assertNotEqual(file['id'],'deliverable:'+owner)

    def test_readonly_shared_entities_single_matrix_and_stage_svg_after_dependency_graph(self):
        self.case.tree();self.case.plan('TR2');owner=self.case.owner('plan');self.case.bindings(owner)
        path=self.root/'docs/shared.md';path.parent.mkdir(exist_ok=True);path.write_text('shared constraint',encoding='utf-8')
        for unit in deepcopy(self.case.registry()['organization']['units']):
            unit['supports']=[{'kind':'artifact','target':'docs/shared.md','owner':owner,'required':True,'rationale':'Shared constraint','anchor':'','sha256':None}]
            self.case.f.execute('stage_unit',unit=unit)
        before=self.case.f.bytes();state=self.case.f.state()
        render_dashboard(self.root,load_state(self.root/'.ipd/tailored_process.yaml'),state,bindings=load_state(self.root/'.ipd/artifact_bindings.yaml'),locale='zh-CN')
        dashboard=self.root/'.ipd/dashboard';data=json.loads((dashboard/'data/state.json').read_text(encoding='utf-8'))
        model=data['work_products'];file=[e for e in model['entities'] if e['details'].get('path')=='docs/shared.md']
        self.assertEqual(len(file),1);self.assertEqual(len(file[0]['consumers']),2)
        self.assertEqual(len(model['entities']),len({e['id'] for e in model['entities']}))
        core_ids={d['id'] for d in state['deliverables']}
        self.assertEqual({e['governance_owner'] for e in model['entities'] if e['kind']=='Deliverable'},core_ids)
        html=(dashboard/'index.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('id="deliverable-matrix"'),1)
        self.assertNotIn('渐进需求、增量与交付件</h2>',html)
        self.assertLess(html.index('id="dependency-flow"'),html.index('id="ipd-stage-flow"'))
        self.assertLess(html.index('id="ipd-stage-flow"'),html.index('id="gate-matrix"'))
        self.assertLess(html.index('id="ipd-stage-flow"'),html.index('</main>'))
        self.assertIn('data-work-diagram=',html)
        self.assertIn('全量满足',html)
        self.assertIn('独立验证',html)
        graph=json.loads((dashboard/'data/graph.json').read_text(encoding='utf-8'))
        self.assertIn(file[0]['id'],{n['id'] for n in graph['nodes']})
        self.assertTrue(any(e['source']==file[0]['id'] and e['relation']=='supports' for e in graph['edges']))
        for relative,content in before.items():self.assertEqual((self.root/relative).read_bytes(),content)


if __name__=='__main__':unittest.main()

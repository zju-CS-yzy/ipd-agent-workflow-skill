"""Independent expectations for multiple parents, shared work and stable IDs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from ipdctl.documents import RequirementError, lint, template
from ipdctl.requirement_contract import LEGACY_SCHEMA, validate
from ipdctl.requirement_verification import verification_context, verification_issue
from ipdctl.requirements import preview, apply_plan, read_registry, readiness, projection, input_snapshot, decision_manifest
from ipdctl.stage_organization import blueprints, codes, unit_issues, validate_organization, referenced_paths
from ipdctl.stage_flow import panel, ordered_requirements
from ipdctl.state import load_state, write_state
from ipdctl.runtime import claim, load_runtime, save_runtime
import tests.test_requirements as requirement_fixtures
requirement = requirement_fixtures.requirement


class StageOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.f = requirement_fixtures.RequirementTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.f.enable()

    def registry(self):
        return read_registry(self.root)

    def adopt(self, stages=None):
        return self.f.execute('adopt_organization', required_stages=stages or ['TR1','TR2','TR3','TR4'])

    def number(self, kind='IR', parent=None, identifier=None, version=1, derived=False, content=None):
        item = requirement(identifier or 'pending',kind,parent,version)
        item.update(content or {})
        item['derived'] = derived
        if identifier is None:
            item.pop('id')
        self.f.execute('numbered_requirement', requirement=item)
        return self.registry()['requirements'][-1]

    def scope(self):
        self.f.execute('scope',scope=[{'requirement':r['id']+'@'+str(r['version']), 'criteria':[a['id'] for a in r['acceptance']]} for r in self.registry()['requirements']])

    def tree(self):
        self.adopt()
        for ir in range(1,3):
            text=('Return a valid current sensor reading within two seconds.' if ir==1 else
                  'Export and restore a versioned calibration configuration without changing its values.')
            criterion=('A current reading or explicit failure is returned within two seconds.' if ir==1 else
                       'The restored schema version and every calibration value equal the exported input.')
            facts={'title':'Measurement response' if ir==1 else 'Configuration portability','statement':text,
                   'source':'public-synthetic-brief@1','rationale':'Independent user goal '+str(ir),
                   'acceptance':[{'id':'response' if ir==1 else 'roundtrip','criterion':criterion,'method':'test'}]}
            self.number(content=facts)
            for sr in range(1,3):
                statements={
                    (1,1):'Validate and timestamp the newly acquired measurement.',
                    (1,2):'Report a current reading or acquisition failure within the response budget.',
                    (2,1):'Serialize all calibration values with a schema version and content digest.',
                    (2,2):'Validate a configuration before restoring it and preserve state on invalid input.'}
                child={**facts,'title':f'Branch {ir} system responsibility {sr}','statement':statements[(ir,sr)]}
                self.number('SR',f'ir-{ir:03}@1',content=child)
                for ar in range(1,3):
                    leaf={**child,'title':f'Allocated responsibility {ir}/{sr}/{ar}',
                          'statement':child['statement']+(' Verify the valid-input path.' if ar==1 else ' Verify boundary and invalid-input behavior.')}
                    self.number('AR',f'sr-{ir:03}-{sr:03}@1',content=leaf)
        self.scope()

    def owner(self, phase):
        return next(d['id'] for d in self.f.state()['deliverables'] if d['phase']==phase)

    def plan(self, stage='TR2', locale='en'):
        owner=self.owner({'TR1':'concept','TR2':'plan','TR3':'develop','TR4':'qualify'}[stage])
        return self.f.execute('stage_plan',stage=stage,owner=owner,locale=locale)

    def bindings(self, owner, glob='docs/**'):
        path=self.root/'.ipd/artifact_bindings.yaml'
        data=load_state(path)
        data['bindings'].append({'id':'binding-'+str(len(data['bindings'])),'glob':glob,'deliverable':owner,'role':'owner','critical':True})
        write_state(path,data)

    def work(self, owner):
        state=self.f.state()
        subject=next(d for d in state['deliverables'] if d['id']==owner)
        state['project'].update(phase=subject['phase'],workflow_step='work')
        subject['status']='in_progress'
        write_state(self.root/'.ipd/project_state.yaml',state)
        save_runtime(self.root,claim(load_runtime(self.root),owner,actor='agent',state_revision=state['revision']))

    def fill(self, item):
        instance=next(i for i in self.registry()['instances'] if i['id']==item['id'])
        record,source=template(self.root,instance['pack'],instance['document_type'],instance['locale'])
        path=self.root/instance['path']
        text=path.read_text(encoding='utf-8')
        match=re.search(r'<table data-ipd-table="requirements">.*?</table>',text,re.S)
        if match:
            table=ET.fromstring(match[0]);body=table.find('tbody');seed=deepcopy(body[0]);body.clear()
            records={r['id']+'@'+str(r['version']):r for r in self.registry()['requirements']}
            for exact in instance['requirements']:
                row=deepcopy(seed)
                for cell in row:
                    cell.attrib.pop('rowspan',None);cell.attrib.pop('colspan',None)
                row[0].text=exact
                if instance['document_type'] in {'sr_spec','ar_spec'}:
                    row[1].text=records[exact]['parent']
                body.append(row)
            text=text[:match.start()]+ET.tostring(table,encoding='unicode')+text[match.end():]
        facts='Public synthetic analysis; verification is planned and has not been executed.'
        if instance['document_type'] in {'ir_decomposition','sr_decomposition','tr1_requirements_feasibility'}:
            facts+='\n'+'\n'.join('<a id="derive-'+r.split('@')[0]+'"></a>' for r in instance['requirements'])
        text=re.sub(r'\[\[TODO:[^\]]+\]\]',lambda m:facts if 'each_' in m[0] or 'elicitation' in m[0] else 'Synthetic observed facts; source@1',text)
        path.write_text(text,encoding='utf-8')
        canonical={r['id']+'@'+str(r['version']):r for r in self.registry()['requirements']}
        self.assertEqual(lint(text,instance,source,record['sections'],canonical=canonical),[])

    def test_adoption_preview_authority_legacy_snapshot_and_retry(self):
        self.f.execute('requirement',requirement=requirement('ir-old'))
        before=self.f.bytes(); request=self.f.request('adopt_organization',required_stages=['TR1','TR2'])
        plan=preview(self.root,request)
        self.assertEqual(before,self.f.bytes())
        with self.assertRaisesRegex(RequirementError,'AUTHORIZATION_REQUIRED'):
            apply_plan(self.root,plan,actor='human',authorized=False)
        apply_plan(self.root,plan,actor='human',authorized=True)
        data=self.registry()
        self.assertEqual(data['requirements'],[requirement('ir-old')])
        self.assertEqual(codes(data),{'ir-old@1':'ir-001'})
        snapshot=json.loads((self.root/data['organization']['adoption']['path']).read_text(encoding='utf-8'))
        self.assertEqual(snapshot['registry']['schema_version'],'1.0')
        with self.assertRaises(RequirementError): validate(data,LEGACY_SCHEMA)
        self.assertEqual(apply_plan(self.root,plan,actor='human',authorized=True)['status'],'already_applied')
        self.assertEqual(data['schema_version'],'1.1')

    def test_independent_numbering_tree_and_exact_replay(self):
        self.tree()
        expected=['ir-001','sr-001-001','ar-001-001-001','ar-001-001-002','sr-001-002','ar-001-002-001','ar-001-002-002',
                  'ir-002','sr-002-001','ar-002-001-001','ar-002-001-002','sr-002-002','ar-002-002-001','ar-002-002-002']
        self.assertEqual([r['id'] for r in self.registry()['requirements']],expected)
        record=requirement('pending','SR','ir-001@1');record.pop('id')
        plan=preview(self.root,self.f.request('numbered_requirement',requirement=record))
        apply_plan(self.root,plan,actor='human',authorized=True)
        self.assertEqual(self.registry()['requirements'][-1]['id'],'sr-001-003')
        self.assertEqual(apply_plan(self.root,plan,actor='human',authorized=True)['status'],'already_applied')

    def test_version_and_reparent_keep_identity_and_historical_codes(self):
        self.adopt();self.number();self.number();self.number('SR','ir-001@1')
        old=deepcopy(self.registry()['requirements'])
        plan=self.f.execute('numbered_requirement',requirement=requirement('sr-001-001','SR','ir-002@1',2))
        self.assertEqual(plan['impact'],self.registry()['changes'][-1])
        self.assertTrue(plan['impact']['affected'])
        data=self.registry()
        self.assertEqual(data['requirements'][:3],old)
        self.assertEqual(codes(data)['sr-001-001@1'],'sr-001-001')
        self.assertEqual(codes(data)['sr-001-001@2'],'sr-002-001')
        child=requirement('pending','SR','ir-002@1');child.pop('id')
        proposal=preview(self.root,self.f.request('numbered_requirement',requirement=child))
        self.assertIsNone(proposal['impact'])  # Never return an unrelated earlier change.
        apply_plan(self.root,proposal,actor='human',authorized=True)
        self.assertEqual(self.registry()['requirements'][-1]['id'],'sr-002-002')

    def test_wrong_numbers_unknown_fields_and_stale_plan_are_zero_write(self):
        self.adopt();self.number()
        before=self.f.bytes()
        with self.assertRaisesRegex(RequirementError,'NUMBER_PARENT'):
            preview(self.root,self.f.request('requirement',requirement=requirement('sr-999-001','SR','ir-001@1')))
        self.assertEqual(before,self.f.bytes())
        item=requirement();item.pop('id')
        plan=preview(self.root,self.f.request('numbered_requirement',requirement=item))
        self.number('SR','ir-001@1')
        with self.assertRaisesRegex(RequirementError,'PLAN_STALE'):
            apply_plan(self.root,plan,actor='human',authorized=True)
        malformed=deepcopy(self.registry());malformed['organization']['unexpected']=1
        with self.assertRaises(RequirementError):validate(malformed)

    def test_derived_and_expanding_sequence_do_not_invent_parent(self):
        self.adopt();self.number('SR',derived=True)
        self.assertEqual(self.registry()['requirements'][-1]['id'],'sr-d-001')
        # Independent allocation history at the boundary, without 1000 state writes.
        data=self.registry();data['organization']['codes'][0]['code']='sr-d-999'
        from ipdctl.stage_organization import assign_code
        record=requirement('pending','SR');record.pop('id');record['derived']=True
        result=assign_code(data,record,allocate_id=True)
        self.assertEqual(result['id'],'sr-d-1000')

    def test_parent_only_plan_has_no_downstream_prerequisite_and_no_writes(self):
        self.adopt();self.number();self.scope()
        before=self.f.bytes()
        plan=preview(self.root,self.f.request('stage_plan',stage='TR2',owner=self.owner('plan'),locale='en'))
        self.assertEqual(before,self.f.bytes())
        self.assertTrue(plan['stage_plan']['binding_issues'])
        proposed=plan['stage_plan']['instances']
        self.assertEqual([p['requirements'] for p in proposed if p['document_type']=='ir_decomposition'],[['ir-001@1']])
        self.assertEqual([p['requirements'] for p in proposed if p['document_type']=='sr_spec'],[[]])
        self.assertFalse(any(i.startswith('STAGE_') for i in readiness(self.root,self.registry(),self.f.state(),stage='TR1',owner=self.owner('plan'))))

    def derive_under_claim(self,stage):
        self.adopt([stage])
        parent=None
        if stage in {'TR2','TR3'}:
            self.number();parent='ir-001@1'
        if stage=='TR3':
            self.number('SR',parent);parent='sr-001-001@1'
        self.scope();self.plan(stage)
        owner=self.owner({'TR1':'concept','TR2':'plan','TR3':'develop'}[stage])
        self.bindings(owner);self.work(owner)
        draft=next(i for i in blueprints(self.registry()) if i['document_type'] not in {'stage_index','ir_spec','sr_spec','ar_spec'})
        self.f.execute('instantiate',actor='agent',instance=draft);self.fill(draft)
        preserved=(self.root/draft['path']).read_bytes()
        for n in (1,2):
            record=requirement('pending',{'TR1':'IR','TR2':'SR','TR3':'AR'}[stage],parent);record.pop('id')
            self.f.execute('numbered_requirement',actor='agent',requirement=record)
        self.f.execute('scope',actor='agent',scope=[{'requirement':r['id']+'@1','criteria':['response']} for r in self.registry()['requirements']])
        if parent:self.f.execute('decomposition',actor='agent',requirement=parent,status='complete')
        unit=deepcopy(self.registry()['organization']['units'][0])
        unit['outputs']=[r['id']+'@1' for r in self.registry()['requirements'][-2:]]
        self.f.execute('stage_unit',actor='agent',unit=unit)
        final=next(i for i in blueprints(self.registry()) if i['id']==draft['id'])
        final.update(id=draft['id']+'-final',path=draft['path'].replace('.md','-final.md'))
        self.f.execute('revise_instance',actor='agent',old=draft['id'],instance=final);self.fill(final)
        unit['conclusion']=final['id'];self.f.execute('stage_unit',actor='agent',unit=unit)
        for item in blueprints(self.registry()):
            if item['id']==final['id']:continue
            self.f.execute('instantiate',actor='agent',instance=item);self.fill(item)
        if stage=='TR3':
            for exact in unit['outputs']:
                self.f.execute('link',actor='agent',link={'requirement':exact,'relation':'satisfied_by','target':owner,'rationale':'Current allocation'})
        unit.update(finalized=True,arguments=[{'requirement':r,'anchor':'derive-'+r.split('@')[0]} for r in unit['outputs']])
        self.f.execute('stage_unit',actor='agent',unit=unit)
        self.assertEqual(unit_issues(self.root,self.registry(),self.f.state(),unit),[])
        self.assertEqual((self.root/draft['path']).read_bytes(),preserved)
        self.assertEqual(len(self.registry()['instances']),4)

    def test_first_ir_is_formed_after_claim_from_empty_scope(self):
        self.derive_under_claim('TR1')

    def test_first_sr_is_derived_then_registered_and_tabulated_within_claim(self):
        self.derive_under_claim('TR2')

    def test_first_ar_is_derived_registered_and_allocated_within_claim(self):
        self.derive_under_claim('TR3')

    def test_claim_derivation_rejects_wrong_actor_stage_revision_and_scope_reduction(self):
        self.adopt();self.number();self.number('SR','ir-001@1');self.scope();self.plan('TR3')
        owner=self.owner('develop');self.work(owner)
        child=requirement('pending','AR','sr-001-001@1');child.pop('id')
        before=self.f.bytes();plan=preview(self.root,self.f.request('numbered_requirement',requirement=child))
        with self.assertRaisesRegex(RequirementError,'INSTANCE_CLAIM'):
            apply_plan(self.root,plan,actor='other-agent',authorized=True)
        self.assertEqual(before,self.f.bytes())
        for op,fields in [('numbered_requirement',{'requirement':requirement('ir-001','IR',version=2)}),
                          ('requirement',{'requirement':requirement('sr-001-002','SR','ir-001@1')}),
                          ('scope',{'scope':[]}),('decomposition',{'requirement':'ir-001@1','status':'complete'}),
                          ('link',{'link':{'requirement':'sr-001-001@1','relation':'satisfied_by','target':self.owner('plan'),'rationale':'Wrong Owner'}})]:
            with self.subTest(op=op),self.assertRaisesRegex(RequirementError,'STAGE_CLAIM_SCOPE'):
                preview(self.root,self.f.request(op,**fields))
            self.assertEqual(before,self.f.bytes())

        runtime=load_runtime(self.root);runtime['active_claims'][owner]['expires_at']='2000-01-01T00:00:00Z'
        save_runtime(self.root,runtime);expired=self.f.bytes()
        with self.assertRaisesRegex(RequirementError,'STAGE_CLAIM_SCOPE'):
            preview(self.root,self.f.request('numbered_requirement',requirement=child))
        self.assertEqual(expired,self.f.bytes())

    def test_per_parent_paths_tables_and_ir_ancestry(self):
        self.tree();self.plan('TR2');self.plan('TR3')
        data=self.registry();units=data['organization']['units']
        self.assertEqual(len([u for u in units if u['stage']=='TR2']),2)
        self.assertEqual(len([u for u in units if u['stage']=='TR3']),4)
        files=blueprints(data)
        ar=[p for p in files if p['document_type']=='ar_spec']
        self.assertEqual({p['path'] for p in ar},{f'docs/increments/mvp/tr3/ir-{i:03}/sr-{i:03}-{s:03}/ar_spec.md' for i in (1,2) for s in (1,2)})
        self.assertTrue(all(len(p['requirements'])==2 for p in ar))
        unit=deepcopy(units[0]);unit['outputs']=['sr-002-001@1']
        with self.assertRaisesRegex(RequirementError,'STAGE_PARENT'):
            self.f.execute('stage_unit',unit=unit)

    def test_shared_artifact_changes_both_contexts_and_reverse_links(self):
        self.tree();self.plan();owner=self.owner('plan');self.bindings(owner)
        path=self.root/'docs/shared.txt';path.parent.mkdir(exist_ok=True);path.write_text('source A',encoding='utf-8')
        for unit in list(self.registry()['organization']['units']):
            unit['supports']=[{'kind':'artifact','target':'docs/shared.txt','owner':owner,'required':True,'rationale':'Shared measured constraint','anchor':'budget','sha256':None}]
            self.f.execute('stage_unit',unit=unit)
        data=self.registry();refs=['ir-001@1','ir-002@1']
        before=[verification_context(self.root,data,r) for r in refs]
        flow=projection(self.root)['flow']
        self.assertEqual(len([n for n in flow['nodes'] if n['type']=='Artifact']),1)
        self.assertEqual(len(flow['reverse']['artifact:docs/shared.txt']['units']),2)
        path.write_text('changed B',encoding='utf-8')
        self.assertTrue(all(a!=verification_context(self.root,data,r) for a,r in zip(before,refs)))
        self.assertTrue(all(any(i.startswith('SUPPORT_STALE') for i in unit_issues(self.root,data,self.f.state(),u)) for u in data['organization']['units']))
        self.assertEqual(input_snapshot(self.root)['docs/shared.txt'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_tr4_reuses_ar_versions_with_distinct_stage_instance_keys(self):
        self.tree();self.plan('TR3');self.plan('TR4')
        files=blueprints(self.registry())
        for i in (1,2):
            for s in (1,2):
                refs={f'ar-{i:03}-{s:03}-001@1',f'ar-{i:03}-{s:03}-002@1'}
                tables=[f for f in files if f['document_type']=='ar_spec' and set(f['requirements'])==refs]
                self.assertEqual({t['key'] for t in tables},{'tr3-register','tr4-register'})
                self.assertEqual(len({t['path'] for t in tables}),2)
        self.assertTrue(all(not u['outputs'] for u in self.registry()['organization']['units'] if u['stage']=='TR4'))

    def test_replanning_adds_parents_without_overwriting_existing_unit(self):
        self.adopt();self.number();self.scope();self.plan()
        original=deepcopy(self.registry()['organization']['units'][0])
        self.number();self.scope();self.plan()
        data=self.registry()
        self.assertEqual(data['organization']['units'][0],original)
        self.assertEqual([u['inputs'] for u in data['organization']['units']],[['ir-001@1'],['ir-002@1']])
        self.assertEqual(len(data['organization']['plans']),1)

    def test_finalizing_missing_documents_or_shared_argument_is_zero_write(self):
        self.adopt();self.number();self.number('SR','ir-001@1');self.number('SR','ir-001@1')
        self.scope();self.plan()
        unit=deepcopy(self.registry()['organization']['units'][0]);unit['finalized']=True
        unit['arguments']=[{'requirement':r,'anchor':'same-argument'} for r in unit['outputs']]
        before=self.f.bytes()
        with self.assertRaisesRegex(RequirementError,'STAGE_NOT_READY|STAGE_ARGUMENT'):
            self.f.execute('stage_unit',unit=unit)
        self.assertEqual(before,self.f.bytes())
        malformed=self.registry();malformed['organization']['units'][0]['arguments']=unit['arguments']
        with self.assertRaisesRegex(RequirementError,'STAGE_ARGUMENT'):validate_organization(malformed)

    def test_shared_reference_hashing_does_not_traverse_unrelated_tree(self):
        self.tree();self.plan();owner=self.owner('plan');self.bindings(owner)
        path=self.root/'docs/shared.txt';path.parent.mkdir(exist_ok=True);path.write_bytes(b'shared fact')
        for unit in list(self.registry()['organization']['units']):
            unit['supports']=[{'kind':'artifact','target':'docs/shared.txt','owner':owner,'required':True,'rationale':'Shared constraint','anchor':'','sha256':None}]
            self.f.execute('stage_unit',unit=unit)
        data=self.registry();original=Path.read_bytes;reads=[]
        def read_bytes(p):
            reads.append(p)
            return original(p)
        with patch.object(Path,'rglob',side_effect=AssertionError('Unrelated tree traversal')),patch.object(Path,'read_bytes',read_bytes):
            result=referenced_paths(self.root,data)
        self.assertEqual(result,{'docs/shared.txt':hashlib.sha256(b'shared fact').hexdigest()})
        self.assertEqual(reads,[path])

    def test_optional_missing_support_is_not_required_or_approved(self):
        self.tree();self.plan();owner=self.owner('plan');self.bindings(owner)
        unit=deepcopy(self.registry()['organization']['units'][0])
        unit['supports']=[{'kind':'artifact','target':'docs/missing.txt','owner':owner,'required':False,'rationale':'Optional future reference','anchor':'','sha256':None}]
        self.f.execute('stage_unit',unit=unit)
        unit=self.registry()['organization']['units'][0]
        self.assertFalse(any(i.startswith('SUPPORT_') for i in unit_issues(self.root,self.registry(),self.f.state(),unit)))
        unit['supports'][0]['required']=True;self.f.execute('stage_unit',unit=unit)
        self.assertTrue(any(i.startswith('SUPPORT_MISSING') for i in unit_issues(self.root,self.registry(),self.f.state(),unit)))

    def test_real_instances_finalize_without_parent_as_child_table_row(self):
        for locale in ('en','zh-CN'):
            # A fresh independent project for each locale.
            if locale=='zh-CN':self.setUp()
            self.tree();self.plan(locale=locale)
            owner=self.owner('plan');self.bindings(owner);self.work(owner)
            files=blueprints(self.registry())
            for item in files:
                self.f.execute('instantiate',actor='agent',instance=item)
                self.fill(item)
            for unit in list(self.registry()['organization']['units']):
                unit['finalized']=True
                unit['arguments']=[{'requirement':r,'anchor':'derive-'+r.split('@')[0]} for r in unit['outputs']]
                self.f.execute('stage_unit',actor='agent',unit=unit)
                self.assertEqual(unit_issues(self.root,self.registry(),self.f.state(),unit),[])
            self.assertFalse(any(i.startswith(('STAGE_','DOCUMENT_')) for i in readiness(self.root,self.registry(),self.f.state(),stage='TR2',owner=owner)))
            flow=projection(self.root)['flow'];text=panel(flow,locale)
            self.assertIn('data-flow-open',text)
            self.assertTrue(all(u['status']=='structurally_ready' for u in flow['units']))
            self.assertEqual(len(flow['edges']),len({(e['source'],e['target'],e['relation']) for e in flow['edges']}))
            chosen=self.registry()['organization']['units'][0]
            document=next(i for i in self.registry()['instances'] if i['id']==chosen['conclusion'])
            path=self.root/document['path'];original=path.read_text(encoding='utf-8')
            target=chosen['arguments'][0]['anchor'];tag='<a id="'+target+'"></a>'
            path.write_text(original.replace(tag,'```html\n'+tag+'\n```'),encoding='utf-8')
            self.assertTrue(any(i.startswith('STAGE_ARGUMENT_ANCHOR') for i in unit_issues(self.root,self.registry(),self.f.state(),chosen)))
            path.write_text(original+'\n'+tag,encoding='utf-8')
            self.assertTrue(any(i.startswith('STAGE_ARGUMENT_ANCHOR') for i in unit_issues(self.root,self.registry(),self.f.state(),chosen)))

    def test_draft_revision_preserves_old_file_and_updates_coverage(self):
        self.adopt();self.number();self.scope();self.plan()
        owner=self.owner('plan');self.bindings(owner);self.work(owner)
        item=next(i for i in blueprints(self.registry()) if i['document_type']=='ir_decomposition')
        self.f.execute('instantiate',actor='agent',instance=item)
        before=(self.root/item['path']).read_bytes()
        revised={**item,'id':item['id']+'-v2','path':item['path'].replace('.md','-v2.md')}
        self.f.execute('revise_instance',actor='agent',old=item['id'],instance=revised)
        self.assertEqual((self.root/item['path']).read_bytes(),before)
        self.assertEqual(self.registry()['instances'][-1]['supersedes'],item['id'])

    def test_required_support_cycle_and_unowned_artifact_are_rejected(self):
        self.tree();self.plan();unit=deepcopy(self.registry()['organization']['units'][0])
        unit['supports']=[{'kind':'artifact','target':'../escape','owner':unit['owner'],'required':True,'rationale':'Invalid path','anchor':'','sha256':None}]
        with self.assertRaisesRegex(RequirementError,'PATH_'):
            self.f.execute('stage_unit',unit=unit)
        unit['supports'][0]['target']='docs/no-owner.txt'
        with self.assertRaisesRegex(RequirementError,'INSTANCE_OWNER'):
            self.f.execute('stage_unit',unit=unit)
        data=self.registry();a,b=data['organization']['units']
        for x,y in ((a,b),(b,a)):
            x['supports']=[{'kind':'instance','target':y['conclusion'],'owner':x['owner'],'required':True,'rationale':'Bad circular conclusion','anchor':'','sha256':None}]
        with self.assertRaisesRegex(RequirementError,'SUPPORT_CYCLE'):validate_organization(data)

    def test_readonly_flow_escapes_text_and_orders_by_real_parent(self):
        self.tree();self.plan()
        before=self.f.bytes();flow=projection(self.root)['flow']
        flow['nodes'][0]['label']='<script>alert(1)</script>'
        text=panel(flow,'en')
        self.assertNotIn('<script>alert(1)</script>',text)
        self.assertIn('&lt;script&gt;',text)
        self.assertEqual(before,self.f.bytes())
        ordered=ordered_requirements(self.registry())
        self.assertEqual([r['id'] for r,depth in ordered[:4]],['ir-001','sr-001-001','ar-001-001-001','ar-001-001-002'])

    def test_adoption_transaction_failure_keeps_all_old_bytes(self):
        before=self.f.bytes()
        plan=preview(self.root,self.f.request('adopt_organization',required_stages=['TR1']))
        from ipdctl.requirements import write_state as original
        def fail(path,data):
            if Path(path).name=='requirements.yaml':raise OSError('injected write failure')
            return original(path,data)
        with patch('ipdctl.requirements.write_state',side_effect=fail),self.assertRaises(OSError):
            apply_plan(self.root,plan,actor='human',authorized=True)
        self.assertEqual(before,self.f.bytes())


if __name__=='__main__':unittest.main()

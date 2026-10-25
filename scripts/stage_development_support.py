"""Filled per-parent documents for the public governed qualification driver.

The source brief/arguments are the existing independently checked worked
project. Software outcomes come from a fresh subprocess, never template text.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from ipdctl.documents import lint, template
from ipdctl.requirements import read_registry
from ipdctl.stage_organization import blueprints


def numbered_catalog(catalog):
    result, mapping, counters = [], {}, {}
    for kind in ('IR','SR','AR'):
        for original in [r for r in catalog if r['kind']==kind]:
            item=deepcopy(original)
            parent=mapping.get(item['parent'])
            prefix=kind.lower()+'-'+(parent.split('@')[0].split('-',1)[1]+'-' if parent else '')
            counters[prefix]=counters.get(prefix,0)+1
            item.update(legacy_id=item['id'],legacy_ref=item['ref'],id=prefix+str(counters[prefix]).zfill(3),parent=parent)
            item['ref']=item['id']+'@1';mapping[original['ref']]=item['ref'];result.append(item)
    return result


def write_stage(project, stage, locale, request, counts, phase_owner):
    data=read_registry(project);inc=data['active_increment']
    plan=next(p for p in data['organization']['plans'] if p['increment']==inc and p['stage']==stage)
    units=[u for u in data['organization']['units'] if u['increment']==inc and u['stage']==stage]
    shared=f'docs/shared/{inc}.md'
    if stage=='TR1':
        path=project/shared;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('Synthetic BRIEF@1: one room, single process, 08:00–18:00, 15-minute grid. '
                        '10 hours × 60 = 600 minutes; 600 / 15 = 40 possible slots. '
                        'No persistence or concurrency claim. Source: reference/'+inc+'/'+locale+'/source-brief.md\n',encoding='utf-8')
    records={r['id']+'@'+str(r['version']):r for r in data['requirements']}
    created={}
    ids={plan['index']}|{i for u in units for i in (u['conclusion'],u['register']) if i}
    for item in [p for p in blueprints(data) if p['id'] in ids]:
        request('instantiate',actor='fixture-agent',instance=item)
        current=read_registry(project)
        instance=next(i for i in current['instances'] if i['id']==item['id'])
        record,source=template(project,instance['pack'],instance['document_type'],locale)
        path=project/item['path'];text=path.read_text(encoding='utf-8')
        unit=next((u for u in units if item['id'] in (u['conclusion'],u['register'])),None)
        selected=unit['outputs'] if unit and unit['outputs'] else unit['inputs'] if unit else list(records)
        derivations=[]
        for exact in selected:
            r=records[exact]
            derivations.append(f'<a id="derive-{r["id"]}"></a>\n'
                f'{exact}; parent={r["parent"]}; {r["statement"]}\n\n'
                f'{r["rationale"]}\n\nCriteria: '+ '; '.join(a['id']+': '+a['criterion'] for a in r['acceptance']))
        anchored_arguments='\n\n'.join(derivations)
        arguments=re.sub(r'<a id="[^"]+"></a>\n','',anchored_arguments)
        inventory='\n'.join(p['id']+' → '+p['path'] for p in blueprints(current) if p['owner']==plan['owner'])
        evidence=f'evidence/{inc}/cases.json'
        actual='Planned, not executed at this stage.' if locale=='en' else '本阶段仅策划，尚未执行。'
        if stage=='TR4':
            observed=json.loads((project/evidence).read_text(encoding='utf-8'))
            assert observed['passed']==observed['total']==21
            actual=f'Fresh software execution: {observed["passed"]}/{observed["total"]}; {evidence}; SHA-256 '+hashlib.sha256((project/evidence).read_bytes()).hexdigest()+'. Human acceptance is a separate synthetic fixture declaration.'
        values={
            'scope_inputs':arguments,'work_product_plan':inventory,'cross_branch_checks':
                'Shared operating-day and grid constraints: 600 min / 15 min = 40 slots. Creation, cancellation and occupancy share the same active ledger; cancellation and overlap must preserve these constraints. '+shared,
            'stage_conclusion':inventory+'\n'+actual,
            'parent_ir':'\n'.join(exact+': '+records[exact]['statement'] for exact in unit['inputs']) if unit else arguments,
            'parent_sr':'\n'.join(exact+': '+records[exact]['statement'] for exact in unit['inputs']) if unit else arguments,
            'supporting_analysis':shared+'; BRIEF@1/C1/C2; reference/'+inc+'/'+locale+'/TR2.md',
            'design_basis':shared+'; reference/'+inc+'/'+locale+'/TR3.md; ledger/validation/calendar boundaries from the worked architecture.',
            'each_sr_derivation':anchored_arguments,'each_ar_derivation':anchored_arguments,
            'elicitation':anchored_arguments,
            'sr_register_reference':inventory,'ar_register_reference':inventory,
            'combined_ir_coverage':arguments+'\nApplicable normal, invalid-input and boundary cases follow the referenced derivation. Future criteria remain deferred.',
            'combined_sr_coverage':arguments+'\n40 slots partition 600 minutes; occupied intervals must be nonoverlapping. Cancelling a booking releases exactly its interval. See the referenced end-to-end case expectations.',
            'ar_inputs':arguments,'implementation_references':f'implementation/{inc}/booking.py; implementation/{inc}/verify_demo.py',
            'executed_ar_results':actual,'sr_ir_results':actual+'\n'+arguments,
            'delivery_summary':actual+'\n'+inventory}
        match=re.search(r'<table data-ipd-table="requirements">.*?</table>',text,re.S)
        if match:
            table=ET.fromstring(match[0]);body=table.find('tbody');seed=deepcopy(body[0]);body.clear()
            columns=[h.attrib['data-ipd-column'] for h in table.find('thead').iter('th')]
            for exact in item['requirements']:
                r=records[exact];row=deepcopy(seed)
                # Expand merged seed cells before filling one explicit record per row.
                while len(row)<len(columns):row.append(ET.Element('td'))
                criteria='; '.join(a['id']+': '+a['criterion'] for a in r['acceptance'])
                children=[ref for ref,child in records.items() if child['parent']==exact]
                cells={'requirement':exact,'parent':r['parent'] or 'None',
                    'shared_context':r['source']+'; '+shared,'scenario_scope':r['statement'],
                    'statement':r['statement'],'value':r['rationale'],'system_behavior':r['statement'],
                    'behavior_constraints':r['statement'],'acceptance_intent':criteria,'verification':criteria,
                    'priority':r['priority']+'; '+r['rationale'],'priority_owner':r['priority']+'; '+r['owner'],
                    'owner':r['owner'],'responsibility':r['module']+'; '+r['owner'],
                    'assigned_module':r['module'],'module_allocation':r['module'],
                    'decomposition':'; '.join(children) if children else 'Not formed; planned at TR2',
                    'child_ar':'; '.join(children) if children else 'Not formed; planned at TR3',
                    'result_evidence':actual,
                    'design_implementation':f'implementation/{inc}/booking.py; {evidence}' if stage=='TR4' else 'TR3 allocation: '+r['module']+'; implementation planned for TR4',
                    'increment':inc+'; only scoped criteria are committed',
                    'increment_status':inc+'; '+actual,
                    'regression':'Shared active-ledger invariants; overlap, cancellation and occupancy cases; '+shared}
                for column,cell in zip(columns,row):
                    cell.attrib.pop('rowspan',None);cell.attrib.pop('colspan',None)
                    cell.text=cells.get(column,r['rationale']+'; source='+r['source']+'; '+shared)
                body.append(row)
            text=text[:match.start()]+ET.tostring(table,encoding='unicode')+text[match.end():]
        text=re.sub(r'\[\[TODO: ([^\]]+)\]\]',lambda m:values.get(m[1],arguments),text)
        path.write_text(text,encoding='utf-8')
        issues=lint(text,instance,source,record['sections'],canonical=records)
        if issues:raise RuntimeError(str(issues))
        created[item['id']]=item['path'];counts['documents']+=1
    for unit in units:
        supports=[{'kind':'artifact','target':shared,'owner':phase_owner['concept'],'required':True,
                   'rationale':'Shared source constraints for all branches','anchor':'','sha256':None}]
        if stage=='TR4':
            supports.extend({'kind':'artifact','target':target,'owner':owner,'required':True,
                             'rationale':'Actual implementation or fresh execution evidence','anchor':'','sha256':None}
                            for target,owner in [(f'implementation/{inc}/booking.py',phase_owner['develop']),
                                                 (evidence,phase_owner['qualify'])])
        unit.update(finalized=True,supports=supports,
                    arguments=[{'requirement':r,'anchor':'derive-'+r.split('@')[0]} for r in unit['outputs']])
        request('stage_unit',actor='fixture-agent',unit=unit)

"""One read-only entity index for both graphs and the requirement/work matrix.

This projection owns no approvals, Claim leases or workflow dependencies.
Files retain their own availability even when their governing Owner is accepted.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from html import escape
import json
import re
from urllib.parse import quote

from .stage_flow import anchor, ordered_requirements


def _id(kind, value):
    return kind + ':' + value


def projection(state, requirements=None):
    """Join by canonical identity/version/context, never by display labels."""
    data = requirements or {}
    active = data.get('active_increment') or ''
    core = {d['id']: d for d in state['deliverables']}
    entities, relations = {}, set()
    def add(key, **fields):
        if key not in entities:
            entities[key] = {'id': key, 'requirements': [], 'increments': [], 'stages': [],
                             'consumers': [], 'related': [], 'files': [], 'issues': [], **fields}
        return entities[key]
    def extend(entity, field, values):
        entity[field] = sorted(set(entity[field]) | set(values))
    for identifier, d in sorted(core.items()):
        add(_id('deliverable', identifier), kind='Deliverable', label=identifier,
            title=d.get('display_label') or d['title'], phase=d['phase'], owner=d.get('owner') or '',
            status=d['status'], availability=None, parent=None, depth=0, historical=False,
            governance_owner=identifier, details=deepcopy(d), files=deepcopy(d.get('owned_files', [])))
        for dependency in d['depends_on']:
            relations.add((_id('deliverable', identifier), _id('deliverable', dependency), 'depends_on'))
    coverage = {r['requirement']: r for r in data.get('coverage', [])}
    codes = {r['requirement']: r['code'] for r in data.get('organization', {}).get('codes', [])}
    for record, depth in ordered_requirements(data) if data else []:
        exact = record['id'] + '@' + str(record['version'])
        members = [i['id'] for i in data['increments'] if any(s['requirement'] == exact for s in i['scope'])]
        entity = add(_id('requirement', exact), kind='Requirement', label=codes.get(exact, exact),
            title=record['title'], phase='', owner=record['owner'], status=record['maturity'],
            availability=None, parent=_id('requirement', record['parent']) if record['parent'] else None,
            depth=depth, historical=bool(members and active not in members), governance_owner=None,
            details={**deepcopy(record), 'coverage': coverage.get(exact, {}),
                     'outcomes': [{**v, 'effective_result': 'unknown' if v['id'] in data.get('verification_diagnostics', {}) else v['result'],
                                   'diagnostic': data.get('verification_diagnostics', {}).get(v['id'])}
                                  for v in data.get('verifications', []) if v['requirement'] == exact]},
            requirements=[exact], increments=members)
    for link in data.get('links', []):
        source, target = _id('requirement', link['requirement']), _id('deliverable', link['target'])
        if target in entities:
            extend(entities[target], 'requirements', [link['requirement']])
            extend(entities[target], 'increments', [link['increment']])
            relations.add((source, target, 'supports'))
    flow = data.get('flow', {})
    mapped = {}
    for node in flow.get('nodes', []):
        if node['type'] == 'Requirement':
            mapped[node['id']] = _id('requirement', node['reference'])
        elif node['type'] == 'Deliverable':
            # Historical Owner facts are separate from the current Owner.
            if node['increment'] == active:
                mapped[node['id']] = _id('deliverable', node['core_id'])
            else:
                key = 'historical:' + node['increment'] + ':deliverable:' + node['core_id']
                mapped[node['id']] = key
                add(key, kind='Deliverable', label=node['core_id'], title=node['core_id'],
                    phase=core.get(node['core_id'], {}).get('phase', ''), owner='', status=node['status'],
                    availability='historical', historical=True, parent=None, depth=0,
                    governance_owner=node['core_id'], increments=[node['increment']], details=deepcopy(node),
                    href=node.get('href'))
        else:
            identity = node['id']
            if node['type'] == 'DocumentInstance':
                identity = node['id'].split(':', 1)[0] + ':' + node.get('reverse_key', identity)
            key = 'work:' + sha256(identity.encode()).hexdigest()[:24]
            mapped[node['id']] = key
            usage = node.get('usage')
            kind = ('Verification' if node['type'] == 'Verification' else 'Reference' if usage == 'reference'
                    else 'Document' if node['type'] == 'DocumentInstance' else 'Material')
            availability = node.get('availability')
            add(key, kind=kind, label=node['label'], title=node.get('title') or node.get('path') or node['label'],
                phase=core.get(node.get('owner'), {}).get('phase', ''), owner='',
                status=node.get('status') if kind == 'Verification' else availability or 'unknown',
                availability=availability, parent=None, depth=0, historical=availability == 'historical',
                governance_owner=node.get('owner'), href=node.get('href'), details=deepcopy(node),
                requirements=[node['reference']] if node.get('reference') else [], usage=usage)
    units = []
    for unit in flow.get('units', []):
        current = deepcopy(unit)
        current['anchor'] = anchor('su-', unit['id'])
        for field in ('inputs', 'supports', 'conclusions', 'outputs', 'results'):
            current[field] = list(dict.fromkeys(mapped[k] for k in unit[field]))
            for key in current[field]:
                item = entities[key]
                extend(item, 'increments', [unit['increment']]); extend(item, 'stages', [unit['stage']])
                extend(item, 'requirements', [k.removeprefix('requirement:') for k in current['inputs'] + current['outputs']])
                extend(item, 'consumers', [unit['id']])
        # Independently governed support is a real Deliverable card, not a
        # fabricated lifecycle status copied onto the supporting file.
        for index, key in enumerate(current['supports']):
            item = entities[key]
            if item.get('usage') == 'deliverable':
                owner_key = (_id('deliverable', item['governance_owner']) if unit['increment'] == active
                             else 'historical:' + unit['increment'] + ':deliverable:' + item['governance_owner'])
                if owner_key in entities:
                    current['supports'][index] = owner_key
                    extend(entities[owner_key], 'consumers', [unit['id']])
                    extend(entities[owner_key], 'stages', [unit['stage']])
                    extend(entities[owner_key], 'increments', [unit['increment']])
                    extend(entities[owner_key], 'requirements', item['requirements'])
                    for parent in current['inputs']:
                        relations.add((parent, owner_key, 'analyzes'))
                    for conclusion in current['conclusions']:
                        relations.add((owner_key, conclusion, 'supports'))
        owner_key = _id('deliverable', unit['owner']) if unit['increment'] == active else 'historical:' + unit['increment'] + ':deliverable:' + unit['owner']
        if owner_key in entities:
            extend(entities[owner_key], 'increments', [unit['increment']]); extend(entities[owner_key], 'stages', [unit['stage']])
            extend(entities[owner_key], 'requirements', [k.removeprefix('requirement:') for k in current['inputs'] + current['outputs']])
        for key in current['supports']:
            if owner_key in entities:
                relations.add((key, owner_key, 'supports'))
        units.append(current)
    for edge in flow.get('edges', []):
        source, target = mapped.get(edge['source']), mapped.get(edge['target'])
        if source in entities and target in entities and source != target:
            relations.add((source, target, edge['relation']))
    # Controlled instances remain visible even without stage organization.
    known_instances = {e['details'].get('reverse_key') for e in entities.values()}
    for instance in data.get('instances', []):
        if 'instance:' + instance['id'] in known_instances:
            continue
        baseline = next((b for b in data.get('baselines', []) if b['increment'] == instance['increment']), None)
        key = 'instance:' + instance['id']
        available = next((f.get('exists', False) for f in core.get(instance['owner'], {}).get('owned_files', [])
                          if f['path'] == instance['path']), False)
        availability = 'historical' if baseline else 'current' if available else 'missing'
        item = add(key, kind='Document', label=instance['id'], title=instance['title'],
            phase=core.get(instance['owner'], {}).get('phase', ''), owner='', status=availability,
            availability=availability, historical=bool(baseline), parent=None, depth=0,
            governance_owner=instance['owner'], requirements=list(instance['requirements']), increments=[instance['increment']],
            details=deepcopy(instance), href='../requirement_history/' + quote(baseline['path'].rsplit('/', 1)[1]) if baseline else '../../' + quote(instance['path'], safe='/'))
        target = _id('deliverable', instance['owner'])
        if not baseline and target in entities:
            relations.add((key, target, 'owned_by'))
            extend(entities[target], 'requirements', item['requirements']); extend(entities[target], 'increments', item['increments'])
    known_results = {e['details'].get('id') for e in entities.values() if e['kind'] == 'Verification'}
    for result in data.get('verifications', []):
        if 'verification:' + result['id'] in known_results:
            continue
        baseline = next((b for b in data.get('baselines', []) if b['increment'] == result['increment']), None)
        diagnostic = data.get('verification_diagnostics', {}).get(result['id'])
        key = 'verification:' + result['increment'] + ':' + result['id']
        add(key, kind='Verification', label=result['id'], title=result['criterion'], phase='', owner='',
            status='unknown' if diagnostic else result['result'], availability='historical' if baseline else None,
            historical=bool(baseline), parent=None, depth=0, governance_owner=None,
            details={**deepcopy(result), 'diagnostic': diagnostic}, requirements=[result['requirement']],
            increments=[result['increment']], href='../requirement_history/' + quote(baseline['path'].rsplit('/',1)[1])
            if baseline else '../../' + quote(result['evidence'],safe='/'))
        relations.add((key, _id('requirement', result['requirement']), 'verifies'))
    # All registered Owner files are visible, including projects without IR/SR/AR.
    paths = {(e.get('governance_owner'), e['details'].get('path')) for e in entities.values() if not e['historical']}
    for identifier, d in sorted(core.items()):
        for file in d.get('owned_files', []):
            if (identifier, file['path']) in paths:
                continue
            key = 'file:' + sha256((identifier + ':' + file['path']).encode()).hexdigest()[:24]
            add(key, kind='Material', label=file['path'], title=file['path'], phase=d['phase'], owner='',
                status='current' if file.get('exists') else 'missing', availability='current' if file.get('exists') else 'missing',
                historical=False, parent=None, depth=0, governance_owner=identifier, details=deepcopy(file), href=file.get('href'))
            relations.add((key, _id('deliverable', identifier), 'owned_by'))
    edges = []
    for key, item in entities.items():
        if item['kind'] != 'Requirement':
            for exact in item['requirements']:
                if _id('requirement', exact) in entities:
                    relations.add((_id('requirement', exact), key, 'associated_with'))
    for source, target, relation in sorted(relations):
        if source in entities and target in entities:
            edges.append({'source': source, 'target': target, 'relation': relation})
            extend(entities[source], 'related', [target]); extend(entities[target], 'related', [source])
    return {'schema_version': '1.0', 'active_increment': active, 'entities': list(entities.values()),
            'relations': edges, 'units': units, 'diagnostics': list(data.get('diagnostics', [])),
            'baselines': deepcopy(data.get('baselines', [])), 'changes': deepcopy(data.get('changes', []))}


def enrich_graph(graph, model):
    """Add material trace nodes without changing the core execution DAG."""
    result = deepcopy(graph)
    current = {e['id']: e for e in model['entities'] if not e['historical']}
    convert = {key: item['governance_owner'] if item['kind'] == 'Deliverable' else key for key, item in current.items()}
    supported = {'Deliverable', 'Material', 'Document', 'Reference'}
    for key, item in current.items():
        if item['kind'] not in supported - {'Deliverable'}:
            continue
        result['nodes'].append({'id': key, 'type': item['kind'], 'title': item['title'],
            'phase': item['phase'], 'status': item['status'], 'detail_key': 'work:' + key, 'caption':item['label']})
    existing = {(e['source'], e['target'], e['relation']) for e in result['edges']}
    for edge in model['relations']:
        if (edge['source'] not in current or edge['target'] not in current or
            any(current[k]['kind'] not in supported for k in (edge['source'], edge['target']))):
            continue
        candidate = (convert[edge['source']], convert[edge['target']], edge['relation'])
        if candidate not in existing and candidate[0] != candidate[1]:
            result['edges'].append(dict(zip(('source', 'target', 'relation'), candidate))); existing.add(candidate)
    return result


def signature(model):
    """Domain/view identity, excluding transient Claim-actionability detail."""
    from .documents import digest
    return digest({**model, 'entities': [{k:v for k,v in e.items() if k != 'details'} for e in model['entities']]})


def graph_slice(graph, phase):
    from .dashboard_model import graph_slice as core_slice
    kinds = {'Deliverable', 'Document', 'Material', 'Reference'}
    result = core_slice(graph, phase=phase or None, node_types=kinds, include_upstream=True)
    visible = {n['id'] for n in result['nodes']}
    while True:
        previous = set(visible)
        visible.update(e['source'] for e in graph['edges'] if e['relation'] in {'supports','owned_by'} and e['target'] in visible)
        if previous == visible: break
    result['nodes'] = [n for n in graph['nodes'] if n['id'] in visible and n['type'] in kinds]
    valid = {n['id'] for n in result['nodes']}
    result['edges'] = [e for e in graph['edges'] if e['source'] in valid and e['target'] in valid]
    return result


WORDS = {
    'matrix': ('需求与交付件矩阵', 'Requirements and work matrix'),
    'flow': ('需求与阶段成果', 'Requirements and stage work products'),
    'Deliverable': ('交付件', 'Deliverable'), 'Requirement': ('需求', 'Requirement'),
    'Document': ('文档实例', 'Document instance'), 'Material': ('成果内材料', 'Material'),
    'Reference': ('参考资料', 'Reference'), 'Verification': ('验证记录', 'Verification'),
    'all': ('全部', 'All'), 'phase': ('阶段', 'Phase'), 'stage': ('TR', 'TR'),
    'increment': ('增量', 'Increment'), 'kind': ('类型', 'Type'), 'owner': ('责任人', 'Responsible'),
    'state': ('状态', 'Status'), 'group': ('组织方式', 'Group by'),
    'requirements': ('需求层级', 'Requirement tree'), 'deliverables': ('交付件', 'Deliverables'),
    'search': ('搜索编号、名称、需求、文件或责任人', 'Search ID, title, requirement, file or owner'),
    'identity': ('编号 / 名称', 'ID / Title'), 'context': ('阶段 / 增量', 'Phase / Increment'),
    'relations': ('关联与依赖', 'Relations and prerequisites'), 'files': ('文件 / 证据 / 评审', 'Files / Evidence / Reviews'),
    'open': ('打开文件或基线', 'Open file or baseline'), 'detail': ('查看详情', 'Details'),
    'expand': ('展开', 'Expand'), 'collapse': ('折叠', 'Collapse'), 'count': ('可见实体', 'Visible entities'),
    'planned': ('已规划', 'Planned'), 'in_progress': ('进行中', 'In progress'),
    'ready_for_review': ('待评审', 'Ready for review'), 'in_review': ('评审中', 'In review'),
    'accepted': ('已接受', 'Accepted'), 'rejected': ('已驳回', 'Rejected'), 'blocked': ('已阻塞', 'Blocked'),
    'superseded': ('已取代', 'Superseded'), 'unknown': ('未知', 'Unknown'), 'current': ('文件当前', 'Current file'),
    'missing': ('文件缺失', 'Missing file'), 'stale': ('内容已变化', 'Changed content'), 'invalid': ('无效路径', 'Invalid path'),
    'historical': ('历史快照', 'Historical snapshot'), 'defined': ('已定义', 'Defined'), 'draft': ('草稿', 'Draft'),
    'open_state': ('未完成', 'Open'), 'complete': ('已完成', 'Complete'), 'passed': ('验证通过', 'Verification passed'),
    'failed': ('验证失败', 'Verification failed'), 'skipped': ('验证跳过', 'Verification skipped'),
    'structurally_ready': ('结构就绪', 'Structurally ready'), 'incomplete': ('结构未就绪', 'Structurally incomplete'),
    'diagnostics': ('诊断与基线', 'Diagnostics and baselines'), 'unassociated': ('其他交付件及材料', 'Other work and materials'),
    'depends_on': ('前置依赖', 'Prerequisite'), 'supports': ('支撑', 'Supports'), 'owned_by': ('归属', 'Owned by'),
    'input': ('输入', 'Input'), 'produces': ('产出', 'Produces'), 'analyzes': ('分析', 'Analyzes'), 'verifies': ('验证', 'Verifies'),
    'governance': ('归属交付件', 'Governing deliverable'), 'consumers': ('使用位置', 'Used by'),
    'hint': ('只读视图；交付件接受、需求定义、文件可用及验证结果分别表达。',
             'Read-only. Deliverable acceptance, requirement definition, file availability and verification are distinct.'),
    'flow_hint': ('输入、支撑和产出关系不改变执行依赖；按 IR 分组展开。',
                  'Inputs, support and outputs do not change execution dependencies. Expand each IR branch.'),
    'current_graph': ('主依赖图显示当前流程；历史成果请在下方按增量查看并打开基线。',
                      'The dependency graph shows current workflow facts; use the stage graph and baseline links for history.'),
    'no_approval': ('此材料没有独立审批状态；归属交付件状态不等于材料独立批准。',
                    'This material has no independent approval. Owner acceptance is not a separate material approval.'),
    'full': ('打开完整矩阵', 'Open full matrix'), 'back': ('返回 Dashboard', 'Back to dashboard'),
    'copy': ('复制路径', 'Copy path'), 'copied': ('已复制', 'Copied'),
    'copy_fallback': ('请选择并复制路径', 'Select and copy the path'),
    'not_generated': ('尚未生成或不可用', 'Not generated or unavailable'),
    'empty': ('没有符合筛选的实体', 'No matching entities'), 'select': ('选择节点查看详情', 'Select an entity'),
    'details': ('详情', 'Details'), 'binding': ('产物绑定就绪度', 'Binding readiness'),
    'owned_files': ('交付件文件', 'Deliverable files'), 'shared_files': ('共享证据文件', 'Shared evidence files'),
    'evidence_files': ('证据文件', 'Evidence files'), 'reviews': ('评审历史', 'Review history'),
    'definition': ('定义', 'Definition'), 'decomposition': ('分解', 'Decomposition'),
    'implementation': ('实现', 'Implementation'), 'verification': ('独立验证', 'Independent verification'),
    'fulfillment': ('全量满足', 'Full-scope fulfillment'), 'full_scope': ('全量', 'Full'),
    'partial': ('部分', 'Partial'), 'none': ('尚无', 'None'), 'module': ('模块', 'Module'),
    'priority': ('优先级', 'Priority'), 'parent': ('上层版本', 'Parent version'),
    'not_ready': ('绑定未就绪', 'Binding not ready'), 'ready': ('绑定就绪', 'Binding ready'),
}


def word(key, locale):
    return WORDS.get(key, (key, key))[0 if locale == 'zh-CN' else 1]


def badge(value, locale):
    css = value if re.fullmatch(r'[a-z_]+', str(value)) else 'unknown'
    return '<span class="badge status-' + css + '">' + escape(word(value, locale)) + '</span>'


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _filters(model, locale, *, stage=False, namespace='ipd-flow-'):
    esc = lambda x: escape(str(x), quote=True)
    entities = model['entities']
    result = ''
    options = {'stage': sorted({s for e in entities for s in e['stages']}),
               'increment': sorted({s for e in entities for s in e['increments']}),
               'phase': sorted({e['phase'] for e in entities if e['phase']}),
               'kind': sorted({e['kind'] for e in entities}),
               'owner': sorted({e['owner'] for e in entities if e['owner']}),
               'state': sorted({e['status'] for e in entities})}
    for field in (('stage', 'increment') if stage else ('phase', 'kind', 'owner', 'state', 'group')):
        values = options.get(field, ['requirements', 'deliverables'])
        identifier = (namespace + field if stage else 'deliverable-status' if field == 'state' else 'work-' + field)
        result += '<label>' + word(field, locale) + ' <select class="select" id="' + identifier + '" data-work-filter="' + field + '">'
        if field != 'group': result += '<option value="">' + word('all', locale) + '</option>'
        for value in values:
            selected = field == 'increment' and value == model['active_increment']
            result += '<option value="' + esc(value) + '"' + (' selected' if selected else '') + '>' + esc(word(value, locale)) + '</option>'
        result += '</select></label>'
    return result


def matrix(model, locale, *, standalone=False):
    w = lambda key: word(key, locale)
    esc = lambda x: escape(str(x), quote=True)
    entities = {e['id']: e for e in model['entities']}
    prefix = '../' if standalone else ''
    rows = []
    # Requirement traversal order is authoritative; sorting readable IDs lexically is not.
    requirements = [e for e in entities.values() if e['kind'] == 'Requirement']
    positions = {e['id']: index for index, e in enumerate(requirements)}
    placement, children = {}, {}
    for entity in entities.values():
        if entity['kind'] == 'Requirement':
            continue
        candidates = [_id('requirement', ref) for ref in entity['requirements'] if _id('requirement', ref) in positions]
        if candidates:
            # One display position, all actual associations remain in the row
            # and details. Shared work must never be counted multiple times.
            parent = min(candidates, key=lambda key: (-entities[key]['depth'], positions[key]))
            placement[entity['id']] = parent
            children.setdefault(parent, []).append(entity)
    ordered = []
    for entity in requirements:
        ordered.append(entity); ordered.extend(children.get(entity['id'], []))
    ordered.extend(e for e in entities.values() if e['kind'] != 'Requirement' and e['id'] not in placement)
    for entity in ordered:
        key = entity['id']; detail = entity['details']; kind = entity['kind']
        display_parent = placement.get(key, entity['parent'])
        display_depth = entities[display_parent]['depth'] + 1 if key in placement else entity['depth']
        target = anchor('rq-', key.removeprefix('requirement:')) if kind == 'Requirement' else anchor('work-row-', key)
        data_node = ' data-node="' + esc(key) + '"' if kind == 'Deliverable' and not entity['historical'] else ''
        button = '<button class="btn work-expand" type="button" data-requirement-toggle="' + esc(key.removeprefix('requirement:')) + '" data-work-collapse="' + esc(key) + '" aria-expanded="true">−</button> ' if kind == 'Requirement' else ''
        context = ' / '.join(entity['stages'] or [entity['phase']]) + '<br><span class="muted">' + esc(', '.join(entity['increments']) or '—') + '</span>'
        related = ' · '.join('<button class="work-link" type="button" data-work-select="' + esc(k) + '">' + esc(entities[k]['label']) + '</button>' for k in entity['related'][:6])
        if len(entity['related']) > 6: related += ' <span class="muted">+' + str(len(entity['related'])-6) + '</span>'
        extra = ''
        status_html = badge(entity['status'], locale)
        if kind == 'Requirement':
            cov = detail.get('coverage', {})
            axes = [('definition', detail['maturity']), ('decomposition', detail['decomposition']),
                    ('implementation', cov.get('implementation', 'unknown')),
                    ('fulfillment', 'full_scope' if cov.get('fulfillment') == 'full' else cov.get('fulfillment', 'none'))]
            status_html = '<br>'.join(esc(w(axis)) + ': ' + badge(value, locale) for axis, value in axes)
            outcomes = detail.get('outcomes', [])
            status_html += '<br>' + esc(w('verification')) + ': ' + ('; '.join(
                esc(v['increment'] + '/' + v['criterion']) + ' ' + badge(v['effective_result'], locale)
                for v in outcomes) or badge('unknown', locale))
            context += '<br>' + esc(w('module') + ': ' + detail['module']) + '<br>' + esc(w('priority') + ': ' + detail['priority'])
        if kind == 'Deliverable':
            ready = detail.get('actionability', {}).get('binding_ready')
            if isinstance(ready, bool): extra = '<br><span title="' + esc(w('binding')) + '">' + badge('ready' if ready else 'not_ready', locale) + '</span>'
        if entity['historical']: extra += '<br>' + badge('historical', locale)
        files = (str(len(entity['files'])) + ' / ' + str(len(detail.get('evidence', []))) + ' / ' + str(len(detail.get('reviews', [])))) if kind == 'Deliverable' else w('detail')
        href = ('../index.html' if standalone else '') + '#node=' + quote(key if kind == 'Deliverable' and not entity['historical'] else 'work:' + key, safe=':')
        rows.append('<tr id="' + target + '" tabindex="0" data-kind="' + kind + '" data-work-key="' + esc(key) + '"' + data_node + ' data-work-depth="' + str(display_depth) + '" data-work-parent="' + esc(display_parent or '') + '">'
            '<td style="padding-left:' + str(10+display_depth*18) + 'px">' + button + '<a class="work-link" href="' + href + '" data-work-select="' + esc(key) + '">' + esc(entity['label']) + '</a><div class="muted">' + esc(entity['title']) + '</div></td>'
            '<td>' + esc(w(kind)) + '</td><td>' + context + '</td><td>' + esc(entity['owner'] or '—') + '</td><td>' + status_html + extra + '</td><td>' + esc((w('parent') + ': ' + (detail['parent'] or '—')) if kind == 'Requirement' else ', '.join(entity['requirements']) or '—') + '</td><td>' + related + '</td><td><button class="btn" type="button" data-work-select="' + esc(key) + '">' + esc(files) + '</button></td></tr>')
    headers = ['identity', 'kind', 'context', 'owner', 'state', 'requirements', 'relations', 'files']
    return '<section class="panel work-panel" id="deliverable-matrix"><div class="panel-head"><div><h2>' + w('matrix') + '</h2><p>' + w('hint') + '</p></div><a class="btn" href="' + ('../index.html#deliverable-matrix' if standalone else 'matrices/deliverable_matrix.html') + '">' + w('back' if standalone else 'full') + '</a></div><div class="panel-body filters">' + ('<div class="filters">' + _filters(model, locale, stage=True, namespace='work-matrix-') + '</div>') + '<input class="search" id="deliverable-search" data-work-filter="search" type="search" placeholder="' + w('search') + '">' + _filters(model, locale) + '<span class="muted" data-work-count></span></div><div id="ipd-requirements" class="table-scroll"><table><thead><tr>' + ''.join('<th>'+w(h)+'</th>' for h in headers) + '</tr></thead><tbody id="deliverable-rows">' + ''.join(rows) + '</tbody></table><p class="empty" data-work-empty hidden>' + w('empty') + '</p></div></section>'


def stage_panel(model, locale):
    w = lambda key: word(key, locale)
    if not model['units']: return ''
    result = '<section class="panel work-panel" id="ipd-stage-flow"><div class="panel-head"><div><h2>' + w('flow') + '</h2><p>' + w('flow_hint') + '</p></div><div class="tools">' + _filters(model, locale, stage=True) + '</div></div><div class="panel-body"><p class="muted">' + w('current_graph') + '</p>'
    for group_index, group in enumerate(sorted({u['root'] for u in model['units']})):
        result += '<details class="work-group" data-flow-group' + (' open' if group_index == 0 else '') + '><summary>' + escape(group) + '</summary>'
        for unit_index, unit in enumerate([u for u in model['units'] if u['root'] == group]):
            identity = anchor('su-', unit['id'])
            search = ' '.join([unit['id'],unit['root'],unit['owner'],*[e['title'] for e in model['entities'] if e['id'] in sum((unit[f] for f in ('inputs','supports','conclusions','outputs','results')), [])]])
            result += '<details class="work-unit" id="' + identity + '" data-flow-unit="' + escape(unit['id'], quote=True) + '" data-stage="' + unit['stage'] + '" data-increment="' + escape(unit['increment'], quote=True) + '" data-search="' + escape(search.lower(), quote=True) + '"' + (' open' if group_index == unit_index == 0 else '') + '><summary>' + escape(unit['stage']+' · '+unit['id']) + ' ' + badge(unit['status'], locale) + '</summary><div class="tools" data-zoom-for="' + identity + '-diagram"><button class="btn" type="button" data-zoom="out">−</button><button class="btn" type="button" data-zoom="reset">100%</button><button class="btn" type="button" data-zoom="in">+</button></div><div class="diagram-frame" id="' + identity + '-diagram">' + work_svg(model, unit, locale) + '</div>'
            if unit['issues']:
                result += '<details class="work-diagnostics"><summary>' + w('diagnostics') + ' (' + str(len(unit['issues'])) + ')</summary><ul>' + ''.join('<li>' + diagnostic(i, locale) + '</li>' for i in unit['issues']) + '</ul></details>'
            result += '</details>'
        result += '</details>'
    result += '</div></section>'
    return result


def diagnostic(value, locale):
    code, _, path = value.partition(':')
    descriptions = {'SUPPORT_MISSING': ('支撑文件尚未生成或已缺失', 'Supporting file is missing'),
                    'SUPPORT_STALE': ('支撑内容已变化，需重新核对', 'Supporting content changed; reassessment is required'),
                    'SUPPORT_UNACCEPTED': ('支撑交付件尚未接受', 'Supporting deliverable has not been accepted'),
                    'STAGE_DRAFT': ('阶段成果尚未定稿', 'Stage work has not been finalized'),
                    'STAGE_DOCUMENT': ('阶段文档尚未登记或不完整', 'Stage document is missing or incomplete'),
                    'VERIFICATION_NOT_PASSED': ('缺少当前上下文的通过验证', 'No passing verification for the current context')}
    message = descriptions.get(code, ('待处理的结构或验证问题', 'Outstanding structure or verification issue'))[0 if locale == 'zh-CN' else 1]
    return escape(message + (': ' + path if path else '')) + '<br><code>' + escape(value) + '</code>'


def diagnostics_panel(model, locale):
    issues = model['diagnostics']
    result = '<details class="panel work-diagnostics"><summary>' + word('diagnostics',locale) + ' (' + str(len(issues)) + ')</summary><ul>'
    result += ''.join('<li>' + diagnostic(i, locale) + '</li>' for i in issues)
    result += ''.join('<li><a href="../requirement_history/' + quote(b['path'].rsplit('/',1)[1]) + '">' + escape(b['id']) + '</a> <code>' + escape(b['sha256']) + '</code></li>' for b in model['baselines'])
    return result + '</ul></details>'


CSS = '''.main>.panel{min-width:0;max-width:100%}.panel-head>div{min-width:0}.work-unit,.work-group{min-width:0}.work-unit summary,.work-group summary{overflow-wrap:anywhere}.work-panel{border-radius:8px}.work-panel .filters{align-items:center}.work-panel label{font-size:12px;color:var(--muted)}.work-link{border:0;padding:0;background:transparent;color:var(--blue);font:inherit;text-align:left;cursor:pointer;overflow-wrap:anywhere}.work-panel td{overflow-wrap:anywhere}.work-panel td:first-child{min-width:220px}.work-expand{min-width:26px;min-height:26px;padding:1px 5px}.work-unit,.work-group{padding:10px;border:1px solid var(--line);border-radius:8px;margin:8px 0;background:#fff}.work-unit>summary,.work-group>summary,.work-diagnostics>summary{cursor:pointer;font-weight:650;padding:8px}.work-unit .diagram-frame>svg{min-width:1000px}.work-unit .diagram-frame{margin-top:10px;min-height:160px}.work-diagnostics{padding:10px 16px;margin-top:10px}.work-diagnostics li{margin:8px 0}.work-diagnostics code{color:var(--muted);overflow-wrap:anywhere}.work-selected{outline:3px solid #84CAFF;outline-offset:-2px}svg .work-selected{outline:none}svg .work-selected>rect{stroke:#1570EF;stroke-width:4}.status-current,.status-defined,.status-draft,.status-historical{color:#667085;background:#F8FAFC}.status-missing,.status-stale,.status-incomplete{color:#B54708;background:#FFFAEB}.status-passed{color:#027A48;background:#ECFDF3}.status-failed,.status-invalid{color:#B42318;background:#FEF3F2}.status-skipped{color:#667085;background:#F8FAFC}@media(max-width:800px){.work-panel .search{width:100%}.work-panel .panel-head{align-items:stretch}.work-panel .filters{gap:10px}}'''


def script(model, locale):
    labels = {key: word(key, locale) for key in WORDS}
    return '<style>' + CSS + '</style><script id="ipd-work-model" type="application/json">' + _json(model) + '</script><script id="ipd-work-labels" type="application/json">' + _json(labels) + '</script><script>' + SCRIPT + '</script>'


SCRIPT = r'''document.addEventListener('DOMContentLoaded',()=>{'use strict';
const model=JSON.parse(document.getElementById('ipd-work-model').textContent),labels=JSON.parse(document.getElementById('ipd-work-labels').textContent),entities=new Map(model.entities.map(e=>[e.id,e])),rows=[...document.querySelectorAll('#deliverable-rows tr[data-work-key]')],filters={stage:'',increment:model.active_increment||'',phase:'',kind:'',owner:'',state:'',group:'requirements',search:''},collapsed=new Set();
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),label=k=>labels[k]||k,words=()=>filters.search.toLowerCase().split(/\s+/).filter(Boolean);
const searchText=new Map(model.entities.map(e=>[e.id,JSON.stringify(e).toLowerCase()])),unitText=new Map(model.units.map(u=>[u.id,[u.id,u.root,u.owner,...['inputs','supports','conclusions','outputs','results'].flatMap(f=>u[f].map(k=>searchText.get(k)||''))].join(' ').toLowerCase()]));
function matches(e){return (!filters.stage||e.stages.includes(filters.stage))&&(!filters.increment||!e.increments.length||e.increments.includes(filters.increment))&&(!filters.phase||!e.phase||e.phase===filters.phase)&&(!filters.kind||e.kind===filters.kind)&&(!filters.owner||e.owner===filters.owner)&&(!filters.state||e.status===filters.state)&&words().every(w=>(searchText.get(e.id)||'').includes(w));}
function update(){
  let visible=0;
  rows.forEach(row=>{const e=entities.get(row.dataset.workKey);let p=row.dataset.workParent,hidden=false;
    while(p){hidden=hidden||collapsed.has(p);p=entities.get(p)?.parent;}
    row.hidden=!matches(e)||(filters.group==='requirements'&&hidden);if(!row.hidden)visible++;
    row.firstElementChild.style.paddingLeft=(10+(filters.group==='requirements'?Number(row.dataset.workDepth)*18:0))+'px';});
  document.querySelectorAll('[data-work-count]').forEach(x=>x.textContent=`${label('count')}: ${visible} / ${entities.size}`);
  document.querySelectorAll('[data-work-empty]').forEach(x=>x.hidden=visible!==0);
  document.querySelectorAll('[data-flow-unit]').forEach(u=>{u.hidden=!!((filters.stage&&u.dataset.stage!==filters.stage)||(filters.increment&&u.dataset.increment!==filters.increment)||!words().every(w=>(unitText.get(u.dataset.flowUnit)||'').includes(w)));});
  document.querySelectorAll('[data-flow-group]').forEach(g=>g.hidden=[...g.querySelectorAll('[data-flow-unit]')].every(u=>u.hidden));
  const frame=document.getElementById('dependency-flow');if(!frame)return;
  const shown=new Set(),nodes=[...frame.querySelectorAll('g[data-work-key]')];
  nodes.forEach(n=>{const e=entities.get(n.dataset.workKey),show=e&&matches(e)&&(!filters.increment||filters.increment===model.active_increment||!model.active_increment);
    n.closest('a').style.display=show?'':'none';if(show)shown.add(n.dataset.nodeId);});
  frame.querySelectorAll('.edge').forEach(e=>{const control=document.querySelector(`[data-relation-toggle][value="${e.dataset.relation}"]`);
    e.style.display=shown.has(e.dataset.source)&&shown.has(e.dataset.target)&&(!control||control.checked)?'inline':'none';});
  let count=frame.querySelector('[data-work-graph-count]');if(!count){count=document.createElement('p');count.dataset.workGraphCount='';count.className='muted';frame.prepend(count);}
  count.textContent=`${label('count')}: ${shown.size} / ${nodes.length} · ${label('current_graph')}`;
}
document.querySelectorAll('[data-relation-toggle],[data-relations-action]').forEach(c=>c.addEventListener(c.matches('input')?'change':'click',()=>{if(c.dataset.relationsAction==='default')document.querySelectorAll('[data-relation-toggle]').forEach(x=>x.checked=['depends_on','supports','owned_by'].includes(x.value));update();}));
const dependencyFrame=document.getElementById('dependency-flow'),initialGraph=dependencyFrame?.querySelector('svg')?.cloneNode(true);
function phaseGraph(){if(!dependencyFrame)return;const source=filters.phase?'phases/'+filters.phase+'.svg':null;
  const template=source?[...document.querySelectorAll('template[data-svg-src]')].find(t=>t.dataset.svgSrc===source):null;
  if(template){const clone=template.content.cloneNode(true);clone.querySelectorAll('[id]').forEach(n=>{const old=n.id,next='dependency-'+old;clone.querySelectorAll('[marker-end]').forEach(e=>{if(e.getAttribute('marker-end')==='url(#'+old+')')e.setAttribute('marker-end','url(#'+next+')');});clone.querySelectorAll('[aria-labelledby],[aria-describedby]').forEach(e=>{for(const a of ['aria-labelledby','aria-describedby'])if(e.hasAttribute(a))e.setAttribute(a,e.getAttribute(a).split(' ').map(k=>k===old?next:k).join(' '));});n.id=next;});dependencyFrame.replaceChildren(clone);}
  else if(initialGraph)dependencyFrame.replaceChildren(initialGraph.cloneNode(true));
}

const phaseControl=document.getElementById('phase-view');phaseControl?.addEventListener('change',()=>{filters.phase=phaseControl.value;document.querySelectorAll('[data-work-filter="phase"]').forEach(c=>c.value=filters.phase);phaseGraph();update();});
document.querySelectorAll('.phase-card').forEach(c=>c.addEventListener('click',()=>{filters.phase=c.dataset.phase;document.querySelectorAll('[data-work-filter="phase"]').forEach(c=>c.value=filters.phase);phaseGraph();update();}));
document.querySelectorAll('[data-work-filter]').forEach(control=>control.addEventListener(control.tagName==='INPUT'?'input':'change',()=>{filters[control.dataset.workFilter]=control.value;document.querySelectorAll('[data-work-filter]').forEach(other=>{if(other.dataset.workFilter===control.dataset.workFilter)other.value=control.value;});if(control.dataset.workFilter==='phase')phaseGraph();if(control.dataset.workFilter==='group'){const body=document.getElementById('deliverable-rows');const ordered=control.value==='deliverables'?[...rows].sort((a,b)=>{const x=entities.get(a.dataset.workKey),y=entities.get(b.dataset.workKey);return (x.governance_owner||'~'+x.label).localeCompare(y.governance_owner||'~'+y.label)||(x.kind==='Deliverable'?0:1)-(y.kind==='Deliverable'?0:1)||x.label.localeCompare(y.label);}):rows;ordered.forEach(r=>body.append(r));}update();}));
document.querySelectorAll('[data-work-collapse]').forEach(b=>b.addEventListener('click',()=>{const id=b.dataset.workCollapse;if(collapsed.has(id)){collapsed.delete(id);b.textContent='−';b.setAttribute('aria-expanded','true');}else{collapsed.add(id);b.textContent='+';b.setAttribute('aria-expanded','false');}update();}));
function select(id,scroll=false){const e=entities.get(id);if(!e)return;document.querySelectorAll('[data-work-key]').forEach(n=>n.classList.toggle('work-selected',n.dataset.workKey===id));const details=document.getElementById('details');if(!details)return;details.hidden=false;document.getElementById('workspace')?.classList.remove('detail-closed');document.getElementById('detail-kind').textContent=label(e.kind);document.getElementById('detail-title').textContent=e.label+' · '+e.title;
const section=(title,value)=>`<section class="detail-section"><h3>${esc(title)}</h3>${value}</section>`,list=xs=>`<ul class="detail-list">${xs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`,button=k=>`<button class="work-link" type="button" data-work-select="${esc(k)}">${esc(entities.get(k)?.label||k)}</button>`;
const fileList=files=>`<ul class="detail-list">${files.map(f=>`<li><code>${esc(f.path)}</code> ${f.exists===false?esc(label('not_generated')):''}<div class="file-actions">${f.href&&/^(\.\.\/|https?:\/\/)/.test(f.href)?`<a href="${esc(f.href)}" target="_blank" rel="noopener noreferrer">${esc(label('open'))}</a>`:''} <button class="btn" type="button" data-copy-path="${esc(f.path)}">${esc(label('copy'))}</button></div></li>`).join('')}</ul>`;
let body=section(label('state'),`<p><span class="badge status-${esc(e.status)}">${esc(label(e.status))}</span></p>`)+section(label('context'),list([e.phase,...e.stages,...e.increments].filter(Boolean)));
if(['Document','Material','Reference'].includes(e.kind)){const governing=e.related.find(k=>entities.get(k)?.kind==='Deliverable'&&entities.get(k)?.governance_owner===e.governance_owner);body+=section(label('governance'),`<p>${esc(label('no_approval'))}</p>`+(governing?button(governing):''));}
body+=section(label('owner'),`<p>${esc(e.owner||'—')}</p>`)+section(label('requirements'),list(e.requirements));
if(e.href&&/^(\.\.\/|https?:\/\/)/.test(e.href))body+=section(label('files'),`<p><a href="${esc(e.href)}" target="_blank" rel="noopener noreferrer">${esc(label('open'))}</a></p>`);
if(e.kind==='Deliverable'){
 body+=section(label('owned_files'),fileList(e.files));
 for(const field of ['shared_files','evidence_files'])if(e.details[field]?.length)body+=section(label(field),`<div data-work-file-group="${field}">${fileList(e.details[field])}</div>`);
 body+=section(label('relations'),list(e.details.depends_on||[]));
 body+=section(label('reviews'),list((e.details.reviews||[]).map(r=>typeof r==='object'?[r.decision||r.result||r.status,r.reviewer||r.actor,r.evidence||r.comment||r.notes].filter(Boolean).join(' · '):r)));
}
body+=section(label('relations'),e.related.map(button).join(' · '))+section(label('consumers'),e.consumers.map(id=>`<button class="work-link" type="button" data-work-unit="${esc(id)}">${esc(id)}</button>`).join('<br>'))+section(label('details'),`<pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(e.details,null,2))}</pre>`);document.getElementById('detail-body').innerHTML=body;
if(scroll){const row=rows.find(r=>r.dataset.workKey===id);if(row){for(const f of ['stage','increment','phase','kind','owner','state','search'])filters[f]='';collapsed.clear();phaseGraph();document.querySelectorAll('[data-work-filter]').forEach(c=>{if(c.dataset.workFilter!=='group')c.value='';});update();row.scrollIntoView({block:'center'});row.focus({preventScroll:true});}}
}
document.addEventListener('click',event=>{const copy=event.target.closest('[data-copy-path]');if(copy){event.preventDefault();event.stopImmediatePropagation();const path=copy.dataset.copyPath,fallback=()=>{copy.textContent=label('copy_fallback');const range=document.createRange();range.selectNodeContents(copy.closest('li')?.querySelector('code')||copy.previousElementSibling||copy);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);};if(navigator.clipboard?.writeText)navigator.clipboard.writeText(path).then(()=>copy.textContent=label('copied')).catch(fallback);else fallback();return;}const unit=event.target.closest('[data-work-unit]');if(unit){const target=[...document.querySelectorAll('[data-flow-unit]')].find(u=>u.dataset.flowUnit===unit.dataset.workUnit);if(target){for(const f of ['stage','increment','search'])filters[f]='';document.querySelectorAll('[data-work-filter]').forEach(c=>{if(['stage','increment','search'].includes(c.dataset.workFilter))c.value='';});update();target.open=true;target.closest('[data-flow-group]').open=true;target.scrollIntoView({block:'center'});}else{const entry=model.units.find(u=>u.id===unit.dataset.workUnit);if(entry)location.href='../index.html#'+entry.anchor;}return;}const button=event.target.closest('[data-work-select]');if(button){event.preventDefault();select(button.dataset.workSelect,button.closest('#detail-body')!==null);return;}const node=event.target.closest('g[data-work-key],tr[data-work-key]');if(node&&entities.has(node.dataset.workKey)&&!event.target.closest('[data-work-collapse]')){event.preventDefault();event.stopPropagation();select(node.dataset.workKey);}},true);
document.addEventListener('keydown',event=>{const node=event.target.closest('g[data-work-key],tr[data-work-key]');if(node&&entities.has(node.dataset.workKey)&&!event.target.closest('button,input,select')&&event.target.tagName.toLowerCase()!=='a'&&(event.key==='Enter'||event.key===' ')){event.preventDefault();event.stopPropagation();select(node.dataset.workKey);}},true);
function route(){const entry=model.units.find(u=>location.hash==='#'+u.anchor);if(entry){const target=document.getElementById(entry.anchor);if(target){for(const field of ['stage','increment','search'])filters[field]='';document.querySelectorAll('[data-work-filter]').forEach(c=>{if(['stage','increment','search'].includes(c.dataset.workFilter))c.value='';});update();target.closest('[data-flow-group]').open=true;target.open=true;target.scrollIntoView({block:'center'});}return;}let match=location.hash.match(/^#node=work:(.+)$/);if(match)select(decodeURIComponent(match[1]),true);else{match=location.hash.match(/^#node=(deliverable:.+)$/);if(match)select(decodeURIComponent(match[1]),true);}}
window.addEventListener('hashchange',route);document.getElementById('details-close')?.addEventListener('click',()=>{document.getElementById('details').hidden=true;document.getElementById('workspace')?.classList.add('detail-closed');});
update();route();});'''


def standalone(state, locale):
    from .dashboard_html import _BASE_CSS
    model = state['work_products']
    return '<!doctype html><html lang="' + locale + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + word('matrix',locale) + '</title><style>' + _BASE_CSS + '</style></head><body><div class="shell"><div class="workspace detail-closed" id="workspace"><main class="main">' + matrix(model,locale,standalone=True) + diagnostics_panel(model,locale) + '</main><aside class="details" id="details" hidden><div class="details-head"><div><p id="detail-kind"></p><h2 id="detail-title">' + word('select',locale) + '</h2></div><button class="details-close" id="details-close">×</button></div><div class="details-body" id="detail-body"></div></aside></div></div>' + script(model,locale) + '</body></html>'


def work_svg(model, unit, locale):
    """Four semantic columns using the very same SVG node/edge primitives."""
    from . import dashboard_svg as svg
    from .i18n import get_translator
    zh = locale == 'zh-CN'; translator = get_translator(locale)
    entities = {e['id']: e for e in model['entities']}
    fields = ('inputs', 'supports', 'conclusions', 'results' if unit['stage'] == 'TR4' else 'outputs')
    headings = (['AR 输入', '设计、实现与证据', '交付结论 / AR 表', 'AR/SR/IR 验证'] if unit['stage'] == 'TR4' else ['上层需求', '支撑成果', '分解结论 / 需求表', '下层需求']) if zh else (['AR inputs', 'Design, implementation, evidence', 'Delivery / AR register', 'AR/SR/IR verification'] if unit['stage'] == 'TR4' else ['Parent requirements', 'Supporting work', 'Derivation / register', 'Child requirements'])
    selected = list(dict.fromkeys(k for field in fields for k in unit[field]))
    records = [{'id': k, 'type': entities[k]['kind'], 'title': entities[k]['title'], 'status': entities[k]['status'], 'caption':entities[k]['label'],
                'phase': entities[k]['phase'], 'detail_key': 'work:' + k} for k in selected]
    nodes, edges = svg._normalise_graph({'nodes': records, 'edges': [e for e in model['relations']
        if e['source'] in selected and e['target'] in selected and e['relation'] in svg.RELATION_STYLES]})
    boxes = {}; height = max(280, max((len(unit[f]) for f in fields), default=0) * 138 + 110)
    width = 1264
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(unit["id"], quote=True)}" data-work-diagram="{escape(unit["id"], quote=True)}">', svg._render_defs(),
             '<style>text{font-family:"Segoe UI","Microsoft YaHei",sans-serif;fill:#182230}.node-title{font-size:13px;font-weight:650}.node-meta{font-size:10px;fill:#667085}.node{cursor:pointer}.node:hover{filter:brightness(.97)}.edge{opacity:.82}</style>', '<rect width="100%" height="100%" fill="#F8FAFC"/>']
    for col, (field, heading) in enumerate(zip(fields, headings)):
        x = 8 + col * 314
        parts += [f'<rect x="{x}" y="8" width="306" height="{height-16}" rx="16" fill="#EFF8FF" stroke="#D0D5DD"/>', f'<text x="{x+14}" y="38" font-size="14" font-weight="700">{escape(heading)}</text>']
        for row, key in enumerate(unit[field]):
            boxes.setdefault(key, svg._Box(x+20, 66+row*138, 264, 110))
        if not unit[field]:
            parts.append(f'<text x="{x+20}" y="90" fill="#667085" font-size="12">' + ('未登记' if zh else 'Not recorded') + '</text>')
    parts.append(svg._render_edges(edges, boxes, translator))
    parts.extend(svg._render_node(n, boxes[n.id], '#node=', translator) for n in nodes)
    parts.append('</svg>')
    result = ''.join(parts)
    prefix = 'work-' + anchor('', unit['id']) + '-'
    for identifier in re.findall(r'(?<![-\w])id="([^"]+)"', result):
        result = result.replace('id="'+identifier+'"', 'id="'+prefix+identifier+'"').replace('url(#'+identifier+')', 'url(#'+prefix+identifier+')')
    return result

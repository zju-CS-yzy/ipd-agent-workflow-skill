"""Zero-write professional-work planning against existing governance contracts.

Candidates are authored into the existing extension/binding inputs and then
accepted through tailor preview/application and baseline adoption. This module
cannot grant a Claim, split historical Owners, or approve a material.
"""
from copy import deepcopy
from pathlib import Path

from .documents import RequirementError, digest, safe_path
from .requirement_contract import ID, validate
from .state import load_state


def adopt_roles(registry, roles, snapshot):
    expected = {(u['id'], s['kind'], s['target']): s for u in registry['organization']['units']
                if u['increment'] == registry['active_increment'] for s in u['supports']}
    if not isinstance(roles, list):
        raise RequirementError('WORK_ADOPTION: roles must be a list')
    selected = {}
    for item in roles:
        if not isinstance(item, dict) or set(item) != {'unit', 'kind', 'target', 'usage'} or item['usage'] not in {'deliverable', 'attachment', 'reference'}:
            raise RequirementError('WORK_ADOPTION: explicitly classify each current support')
        key = (item['unit'], item['kind'], item['target'])
        if key in selected or key not in expected:
            raise RequirementError('WORK_ADOPTION: duplicate or unknown support')
        selected[key] = item['usage']
    if set(selected) != set(expected):
        raise RequirementError('WORK_ADOPTION: every current support needs an explicit role')
    for key, role in selected.items():
        expected[key]['usage'] = role
    registry['schema_version'], registry['contract'] = '1.2', '0.5.5'
    registry['organization']['work_adoption'] = snapshot


def _literal_glob(path):
    return ''.join({'[':'[[]', '*':'[*]', '?':'[?]'}.get(c, c) for c in path)


def preview(root, request):
    from .requirements import read_registry, input_snapshot, file_hash
    from .runtime import load_runtime
    from .stage_organization import stage_phase
    from .dashboard_model import _process_deliverables
    from .tailoring import tailor_profile, preview_process_diff
    from .reconcile import load_artifact_bindings, map_paths_to_deliverables, validate_artifact_bindings
    root = Path(root).resolve()
    if not isinstance(request, dict) or set(request) != {'request_id','reason','stage','consumer','materials'}:
        raise RequirementError('WORK_PLAN: expected request_id, reason, stage, consumer and materials')
    validate(request['request_id'], ID)
    if not isinstance(request['reason'], str) or not request['reason'].strip():
        raise RequirementError('WORK_PLAN: explain the planning reason')
    registry = read_registry(root)
    if not registry or 'organization' not in registry or not registry['active_increment']:
        raise RequirementError('WORK_PLAN: an active organized increment is required')
    if registry['product_state'] != 'active':
        raise RequirementError('WORK_PLAN: retired products are read-only')
    state = load_state(root/'.ipd/project_state.yaml'); process = load_state(root/'.ipd/tailored_process.yaml')
    core = _process_deliverables(process)
    consumer = core.get(request['consumer'])
    if not consumer or consumer['phase'] != stage_phase(registry, state, request['stage']):
        raise RequirementError('WORK_PLAN: choose a canonical consumer in the selected stage')
    extension = deepcopy(load_state(root/'.ipd/process_extensions.yaml'))
    bindings = deepcopy(load_artifact_bindings(root/'.ipd/artifact_bindings.yaml'))
    if not isinstance(request['materials'], list) or not request['materials']:
        raise RequirementError('WORK_PLAN: provide a nonempty material list')
    base = input_snapshot(root, registry); issues = []; planned = []; supports = []
    status = {d['id']: d['status'] for d in state['deliverables']}
    runtime = load_runtime(root)
    if runtime['active_claims'] or state['project']['workflow_step'] in {'work','close','review'}:
        issues.append('WORK_PLAN_ACTIVE: finish the Claim/review before changing process or bindings')
    subject = next(d for d in state['deliverables'] if d['id'] == request['consumer'])
    if status.get(request['consumer']) in {'accepted','superseded'} or subject.get('reviews') or subject.get('evidence'):
        issues.append('WORK_PLAN_HISTORY: plan new work in a new increment; preserve accepted subjects')
    paths = set(); ids = set()
    for raw in request['materials']:
        required = {'id','title','path','usage','required','rationale','execution_dependency'}
        optional = {'owner','phase','activity_id','depends_on'}
        if not isinstance(raw, dict) or not required <= set(raw) or set(raw)-required-optional:
            raise RequirementError('WORK_PLAN: incomplete or unknown material fields')
        validate(raw['id'], ID)
        if not all(isinstance(raw[k], str) and raw[k].strip() for k in ('title','rationale')) or type(raw['required']) is not bool or type(raw['execution_dependency']) is not bool:
            raise RequirementError('WORK_PLAN: use explicit descriptions and boolean decisions')
        if not isinstance(raw['usage'], str) or raw['usage'] not in {'deliverable','attachment','reference'}:
            raise RequirementError('WORK_PLAN: choose deliverable, attachment or reference')
        path = safe_path(root, raw['path']); relative = path.relative_to(root).as_posix()
        if relative != raw['path'] or relative.split('/')[0] in {'.ipd','.git','.svn'} or path.is_dir():
            raise RequirementError('WORK_PLAN: use a normal project-relative artifact path')
        if relative in paths or raw['id'] in ids:
            raise RequirementError('WORK_PLAN: duplicate material identity or path')
        paths.add(relative); ids.add(raw['id']); base[relative] = file_hash(path)
        formal = raw['usage'] == 'deliverable'
        owner = raw['id'] if formal else raw.get('owner', request['consumer'])
        validate(owner, ID)
        if formal and 'owner' in raw and raw['owner'] != owner:
            raise RequirementError('WORK_PLAN: independent work must use its own Deliverable ID as Owner')
        if formal:
            if owner == request['consumer']:
                raise RequirementError('WORK_PLAN: an independent support cannot be its consumer')
            phase = raw.get('phase', core.get(owner, {}).get('phase', consumer['phase']))
            activity = raw.get('activity_id', core.get(owner, {}).get('activity_id', consumer['activity_id']))
            dependency = raw.get('depends_on', [])
            if not isinstance(dependency, list) or not all(isinstance(d, str) for d in dependency) or len(set(dependency)) != len(dependency):
                raise RequirementError('WORK_PLAN: use distinct explicit prerequisites')
            for identifier in dependency: validate(identifier, ID)
            proposed = {'id':owner, 'title':raw['title'], 'phase':phase, 'activity_id':activity,
                        'review_required':True, 'depends_on':dependency}
            if owner not in core:
                extension.setdefault('deliverables', []).append(proposed)
                core[owner] = proposed
                from .dashboard_model import PHASE_ORDER
                if phase not in PHASE_ORDER or PHASE_ORDER.index(phase) < PHASE_ORDER.index(state['project']['phase']):
                    issues.append('WORK_PLAN_CLOSED_PHASE:' + owner)
            elif any(core[owner].get(k) != proposed[k] for k in ('title','phase','activity_id')):
                raise RequirementError('WORK_PLAN: existing Deliverable semantics cannot be rewritten')
            elif 'depends_on' in raw and sorted(core[owner]['depends_on']) != sorted(dependency):
                raise RequirementError('WORK_PLAN: change existing prerequisites through explicit dependency correction')
        elif owner not in core:
            raise RequirementError('WORK_PLAN: attachment/reference Owner is unknown')
        if raw['execution_dependency']:
            if owner == request['consumer']:
                raise RequirementError('WORK_PLAN: self dependency is invalid')
            edge = {'source':request['consumer'],'target':owner,'relation':'depends_on'}
            if owner not in consumer['depends_on'] and edge not in extension.get('dependencies', []):
                extension.setdefault('dependencies', []).append(edge)
        elif raw['required'] and owner != request['consumer'] and status.get(owner) != 'accepted':
            pending, seen = list(consumer['depends_on']), set()
            while pending:
                identifier = pending.pop()
                if identifier in seen: continue
                seen.add(identifier); pending.extend(core.get(identifier, {}).get('depends_on', []))
            if owner not in seen: issues.append('SUPPORT_DEPENDENCY_REQUIRED:' + owner)
        binding = {'id':'work-'+request['request_id']+'-'+raw['id'], 'glob':_literal_glob(relative),
                   'deliverable':owner,'role':'owner','critical':raw['required']}
        matches = map_paths_to_deliverables([relative], bindings)['paths'].get(relative, [])
        owners = {d for match in matches for d in match['owner_deliverable_ids']}
        if owners and owners != {owner}:
            issues.append('WORK_PLAN_OWNER_CONFLICT:' + relative)
        if owners != {owner}: bindings.setdefault('bindings', []).append(binding)
        supports.append({'kind':'artifact','target':relative,'owner':owner,'required':raw['required'],
                         'rationale':raw['rationale'],'anchor':'','sha256':base[relative], 'usage':raw['usage']})
        planned.append({**deepcopy(raw), 'governance_owner':owner, 'new_deliverable':formal and owner not in status,
                        'availability':'current' if path.is_file() else 'planned', 'independent_review':formal})
    compiled = tailor_profile(load_state(root/'.ipd/task_profile.yaml'), extension)
    validate_artifact_bindings(bindings)
    units = []
    for unit in registry['organization']['units']:
        if unit['increment'] == registry['active_increment'] and unit['stage'] == request['stage'] and unit['owner'] == request['consumer']:
            value = deepcopy(unit)
            existing = {(s['kind'], s['target']):s for s in value['supports']}
            existing.update({(s['kind'],s['target']):s for s in supports})
            value['supports'] = list(existing.values()); value['finalized'] = False
            units.append(value)
    result = {'schema_version':'1.0', 'command':'work-plan', 'request':deepcopy(request),
              'source_sha256':digest(base), 'state_revision':state['revision'], 'read_only':True,
              'work_role_adoption_required':registry['schema_version'] != '1.2',
              'materials':planned, 'issues':sorted(set(issues)), 'candidate_process_extensions':extension,
              'candidate_artifact_bindings':bindings, 'tailor_diff':preview_process_diff(process, compiled),
              'candidate_stage_units':units,
              'acceptance_route':['recheck work-plan','author extension and binding candidates','tailor --preview --json',
                                  'authorized tailor/migration when required','adopt-baseline when required',
                                  'stage_unit preview and authorized application'],
              'ready_for_authoring':not issues}
    result['plan_sha256'] = digest(result)
    return result


def check(root, plan):
    if not isinstance(plan, dict) or plan.get('command') != 'work-plan' or preview(root, plan['request']) != plan:
        raise RequirementError('WORK_PLAN_STALE: rebuild the zero-write plan from current facts')
    return {'status':'current','read_only':True,'plan_sha256':plan['plan_sha256'],
            'ready_for_authoring':plan['ready_for_authoring'], 'issues':plan['issues']}

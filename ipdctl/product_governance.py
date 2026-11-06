"""Pinned enabling-product releases and their governed uses in the main product."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from urllib.parse import urlsplit

from .documents import RequirementError, digest, safe_path
from .requirement_contract import ID, IMPORT, PRODUCT, WORK, validate
from .state import load_state


def model(registry):
    if 'components' not in registry:
        raise RequirementError('PRODUCT_CONTRACT: explicitly adopt product governance first')
    return registry['components']


def records(registry, kind):
    data = registry.get('components', {})
    accepted = {item['work'] for item in data.get('acceptances', [])}
    result = {item['release']['id']: item['release'] for item in data.get('imports', [])} if kind == 'release' else {}
    result.update({item['id']: item['record'] for item in data.get('works', [])
                   if item['kind'] == kind and item['id'] in accepted})
    return result


def proofs(record):
    result = []
    if isinstance(record, dict):
        if set(record) == {'path', 'sha256'}:
            result.append(record)
        else:
            for value in record.values():
                result.extend(proofs(value))
    elif isinstance(record, list):
        for value in record:
            result.extend(proofs(value))
    return result


def referenced_paths(root, registry):
    result = {}
    for proof in proofs(registry.get('components', {})):
        path = safe_path(root, proof['path'])
        result[proof['path']] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    for instance in registry['instances']:
        if 'origin' in instance:
            origin = instance['origin']
            path = safe_path(root, origin['path'])
            result[origin['path']] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def _files(root, record):
    issues = []
    for proof in proofs(record):
        path = safe_path(root, proof['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != proof['sha256']:
            issues.append('PRODUCT_EVIDENCE_CHANGED:' + proof['path'])
    return issues


def _source(source):
    parsed = urlsplit(source['repository'])
    if parsed.password or parsed.query or parsed.fragment:
        raise RequirementError('PRODUCT_SOURCE: repository reference must omit credentials and URL parameters')
    if source['backend'] == 'git' and not re.fullmatch(r'[a-f0-9]{40,64}', source['revision']):
        raise RequirementError('PRODUCT_SOURCE: pin a complete Git commit ID')
    if source['backend'] == 'svn' and not source['revision'].isdigit():
        raise RequirementError('PRODUCT_SOURCE: pin a numeric SVN revision')
    if source['backend'] == 'content' and not re.fullmatch(r'[a-f0-9]{64}', source['revision']):
        raise RequirementError('PRODUCT_SOURCE: pin a content SHA-256')
    if source['path'] != '.':
        from pathlib import PurePosixPath
        path = PurePosixPath(source['path'])
        if path.is_absolute() or '..' in path.parts or '\\' in source['path'] or ':' in source['path']:
            raise RequirementError('PRODUCT_SOURCE: use a portable repository-relative path')


def check_relations(registry):
    if 'components' not in registry:
        return
    data = model(registry)
    products = [item['id'] for item in data['products']]
    works = [item['id'] for item in data['works']]
    releases = [item['release'] for item in data['imports']] + [
        item['record'] for item in data['works'] if item['kind'] == 'release']
    ids = works + [item['release']['id'] for item in data['imports']]
    versions = [(item['product'], item['version']) for item in releases]
    accepted = [item['work'] for item in data['acceptances']]
    if (len(set(products)) != len(products) or len(set(ids)) != len(ids) or
            len(set(versions)) != len(versions) or len(set(accepted)) != len(accepted) or not set(accepted) <= set(works)):
        raise RequirementError('PRODUCT_DUPLICATE: product, record or product/version identity is duplicated')
    for work in data['works']:
        if work['id'] != work['record']['id'] or work['increment'] not in {i['id'] for i in registry['increments']}:
            raise RequirementError('PRODUCT_REFERENCE: work identity or increment differs')
    for release in releases:
        _source(release['source'])
        if release['source']['backend'] == 'content' and release['source']['revision'] != digest(release['artifacts']):
            raise RequirementError('PRODUCT_SOURCE: content revision must bind the exact artifact manifest')
        if release['product'] not in products or not set(release['requirements']) <= {
                r['id'] + '@' + str(r['version']) for r in registry['requirements']}:
            raise RequirementError('PRODUCT_REFERENCE: unknown product or requirement version')
    for release in data['withdrawals']:
        if release['release'] not in records(registry, 'release'):
            raise RequirementError('PRODUCT_REFERENCE: unknown accepted release')
    for work in data['works']:
        for field in ('releases', 'datasets', 'checks', 'consumers', 'environments', 'requirements'):
            values = work['record'].get(field, [])
            if len(values) != len(set(values)):
                raise RequirementError('PRODUCT_DUPLICATE: duplicate ' + field)
        cases = work['record'].get('cases', work['record'].get('quality', {}).get('cases', []))
        if len({case['id'] for case in cases}) != len(cases):
            raise RequirementError('PRODUCT_DUPLICATE: duplicate verification case')


def issues(root, registry, kind, record, visiting=None):
    visiting = set(visiting or ())
    key = (kind, record['id'])
    if key in visiting:
        return ['PRODUCT_CYCLE:' + record['id']]
    visiting.add(key)
    result = _files(root, record)
    releases = records(registry, 'release')
    def require(category, identifier):
        item = records(registry, category).get(identifier)
        if item is None:
            result.append('PRODUCT_UNACCEPTED:' + identifier)
        else:
            result.extend(issues(root, registry, category, item, visiting))
        return item
    selected = record.get('releases', [record['recorder']] if kind == 'dataset' else [])
    for identifier in selected:
        release = require('release', identifier)
        if release and (release['protocol'] != record['protocol'] or record['environment'] not in release['environments']):
            result.append('PRODUCT_CONTEXT:' + identifier)
    for identifier in record.get('datasets', []):
        dataset = require('dataset', identifier)
        if dataset and (dataset['recorder'] not in selected or dataset['protocol'] != record['protocol'] or
                        dataset['environment'] != record['environment']):
            result.append('PRODUCT_DATASET_CONTEXT:' + identifier)
    if kind == 'release':
        if any(item['release'] == record['id'] for item in model(registry)['withdrawals']):
            result.append('PRODUCT_WITHDRAWN:' + record['id'])
        imported = next((item for item in model(registry)['imports'] if item['release']['id'] == record['id']), None)
        if imported:
            result.extend(_files(root, imported['approval']))
    if kind in {'compatibility', 'dataset'}:
        evaluation = record['quality'] if kind == 'dataset' else record
        result.extend(_files(root, evaluation))
        if any(case['result'] != 'passed' for case in evaluation['cases']):
            result.append('PRODUCT_TEST_NOT_PASSED:' + record['id'])
    if kind == 'adoption':
        checks = [require('compatibility', identifier) for identifier in record['checks']]
        if not any(check and set(check['releases']) == set(selected) and
                   set(record['datasets']) <= set(check['datasets']) and check['protocol'] == record['protocol'] and
                   check['environment'] == record['environment'] for check in checks):
            result.append('PRODUCT_COMPATIBILITY_UNKNOWN:' + record['id'])
    products = [releases[item]['product'] for item in selected if item in releases]
    if len(products) != len(set(products)) or len(selected) != len(set(selected)):
        result.append('PRODUCT_VERSION_CONFLICT:' + record['id'])
    return sorted(set(result))


def selections(registry):
    data = registry.get('components', {})
    accepted = {item['work'] for item in data.get('acceptances', [])}
    result = {}
    for work in data.get('works', []):
        if work['kind'] != 'adoption' or work['increment'] != registry['active_increment']:
            continue
        key = work['record']['key']
        if key not in result or work['id'] in accepted or result[key]['id'] not in accepted:
            result[key] = work
    return list(result.values())


def impact(registry, old, new):
    adoptions = [work for work in model(registry)['works']
                 if work['kind'] == 'adoption' and old in work['record']['releases']]
    consumers = sorted({owner for work in adoptions for owner in work['record']['consumers']})
    datasets = sorted(item['id'] for item in records(registry, 'dataset').values() if item['recorder'] == old)
    checks = sorted(item['id'] for item in records(registry, 'compatibility').values() if old in item['releases'])
    requirements = sorted({link['requirement'] for link in registry['links'] if link['target'] in consumers})
    changed = []
    releases = records(registry, 'release')
    if new:
        if old not in releases or new not in releases or releases[old]['product'] != releases[new]['product']:
            raise RequirementError('PRODUCT_UPGRADE: choose two accepted versions of the same product')
        changed = [field for field in ('source', 'artifacts', 'protocol', 'environments', 'capabilities', 'scope')
                   if releases[old][field] != releases[new][field]]
    return {'old': old, 'new': new, 'changed': changed, 'consumers': consumers,
            'datasets': datasets, 'checks': checks, 'requirements': requirements,
            'action': 'explicit applicability assessment and affected re-verification',
            'pins_changed': False}


def _dependency(state, consumer, owner):
    core = {item['id']: item for item in state['deliverables']}
    pending, seen = [consumer], set()
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        pending.extend(core[key]['depends_on'])
    return consumer != owner and owner in seen


def readiness(root, registry, state, *, owner=None, phase=None):
    if 'components' not in registry:
        return []
    data = model(registry)
    core = {item['id']: item for item in state['deliverables']}
    order = ('concept', 'plan', 'develop', 'qualify', 'launch', 'lifecycle')
    owners = {owner} if owner else {key for key, item in core.items()
                                  if order.index(item['phase']) <= order.index(phase or state['project']['phase'])}
    accepted = {item['work'] for item in data['acceptances']}
    result = []
    for work in data['works']:
        if work['increment'] == registry['active_increment'] and work['owner'] in owners and work['id'] not in accepted:
            result.extend(issues(root, registry, work['kind'], work['record']))
    for work in selections(registry):
        if owners & set(work['record']['consumers']):
            if work['id'] not in accepted:
                result.append('PRODUCT_ADOPTION_PENDING:' + work['id'])
            result.extend(issues(root, registry, 'adoption', work['record']))
    return sorted(set(result))


def decision_inputs(root, registry, owners):
    """Bind product work and the exact adopted input closure into human review."""
    own = [work for work in model(registry)['works'] if
           work['increment'] == registry['active_increment'] and work['owner'] in owners]
    uses = [work for work in selections(registry) if set(work['record']['consumers']) & owners]
    inputs = {}
    def add(kind, record):
        key = kind + ':' + record['id']
        if key in inputs:
            return
        inputs[key] = record
        for identifier in record.get('releases', [record['recorder']] if kind == 'dataset' else []):
            release = records(registry, 'release').get(identifier)
            if release:
                add('release', release)
        for field, category in (('datasets', 'dataset'), ('checks', 'compatibility')):
            for identifier in record.get(field, []):
                item = records(registry, category).get(identifier)
                if item:
                    add(category, item)
    for work in own + uses:
        add(work['kind'], work['record'])
    paths = {proof['path']: proof for record in inputs.values() for proof in proofs(record)}
    files = {path: hashlib.sha256(safe_path(root, path).read_bytes()).hexdigest()
             if safe_path(root, path).is_file() else None for path in paths}
    own_releases = {work['record']['id'] for work in own if work['kind'] == 'release'}
    withdrawals = [item for item in model(registry)['withdrawals'] if
                   'release:' + item['release'] in inputs and item['release'] not in own_releases]
    return {'works': own, 'uses': uses, 'inputs': inputs, 'files': files, 'withdrawals': withdrawals}


def transition(root, registry, state, runtime, request):
    from .requirements import _fields, _owner, decision_manifest
    from .runtime import _parse_time, utc_now
    data = model(registry)
    operation = request['operation']
    core = {item['id']: item for item in state['deliverables']}
    if operation == 'product_register':
        _fields(request, {'product'})
        validate(request['product'], PRODUCT)
        if any(item['id'] == request['product']['id'] for item in data['products']):
            raise RequirementError('PRODUCT_DUPLICATE: product ID already exists')
        data['products'].append(deepcopy(request['product']))
    elif operation == 'product_import':
        _fields(request, {'import'})
        validate(request['import'], IMPORT)
        if _files(root, request['import']):
            raise RequirementError('PRODUCT_EVIDENCE_CHANGED: imported release or approval bytes differ')
        data['imports'].append(deepcopy(request['import']))
    elif operation == 'product_work':
        _fields(request, {'kind', 'owner', 'record'})
        from .requirement_contract import RECORDS
        if request['kind'] not in RECORDS:
            raise RequirementError('PRODUCT_REFERENCE: unknown work kind')
        validate(request['record'], RECORDS[request['kind']])
        validate(request['owner'], ID)
        work = {key: deepcopy(request[key]) for key in ('kind', 'owner', 'record')}
        work.update(id=work['record']['id'], increment=registry['active_increment'])
        validate(work, WORK)
        owner = work['owner']
        lease = runtime['active_claims'].get(owner)
        if (owner not in core or not lease or _parse_time(lease['expires_at']) <= utc_now() or
                state['project']['workflow_step'] != 'work' or core[owner]['status'] != 'in_progress'):
            raise RequirementError('PRODUCT_CLAIM: hold the current work Owner Claim')
        if any(item['work'] == work['id'] for item in data['acceptances']):
            raise RequirementError('PRODUCT_IMMUTABLE: accepted work cannot be overwritten')
        previous = next((item for item in data['works'] if item['id'] == work['id']), None)
        if previous and any(previous[key] != work[key] for key in ('owner', 'kind', 'increment')):
            raise RequirementError('PRODUCT_IMMUTABLE: preserve work identity and Owner')
        for proof in proofs(work['record']):
            _owner(root, state, proof['path'], owner)
        issues(root, registry, work['kind'], work['record'])
        if work['kind'] == 'adoption':
            record = work['record']
            prior = next((item for item in selections(registry) if item['record']['key'] == record['key']), None)
            if record['prior'] != (prior['id'] if prior and prior['id'] != work['id'] else previous['record']['prior'] if previous else None):
                raise RequirementError('PRODUCT_UPGRADE: pin the exact previous adoption')
            if any(consumer not in core or not _dependency(state, consumer, owner) or
                   core[consumer]['status'] in {'accepted', 'superseded'} for consumer in record['consumers']):
                raise RequirementError('PRODUCT_DEPENDENCY: consumers require an explicit unaccepted downstream dependency')
            affected = set(prior['record']['consumers'] + record['consumers']) if prior else set()
            if {item['target'] for item in record['assessments']} != affected:
                raise RequirementError('PRODUCT_IMPACT: assess every old and new consumer')
        if previous:
            data['works'][data['works'].index(previous)] = work
        else:
            data['works'].append(work)
    elif operation == 'product_accept':
        _fields(request, {'work'})
        work = next((item for item in data['works'] if item['id'] == request['work']), None)
        if not work or work['increment'] != registry['active_increment']:
            raise RequirementError('PRODUCT_REFERENCE: choose current product work')
        owner = core[work['owner']]
        decision = next((review for review in reversed(owner['reviews']) if
                         review.get('reviewer_type') == 'human' and review.get('authorized')), {})
        approval = next((event for event in reversed(runtime['events']) if
                         event.get('action') == 'approve' and event.get('subject') == owner['id']), {})
        manifest = decision_manifest(root, state, owner['id'], 'deliverable')
        if (owner['status'] != 'accepted' or decision.get('decision') != 'approve' or
                approval.get('requirements_sha256') != manifest or issues(root, registry, work['kind'], work['record'])):
            raise RequirementError('PRODUCT_APPROVAL: current exact work needs its Owner human approval')
        data['acceptances'].append({'work': work['id'], 'reviewer': decision['reviewer'],
                                   'approval_sha256': digest(approval), 'manifest_sha256': manifest})
    elif operation == 'product_withdraw':
        _fields(request, {'release'})
        if request['release'] not in records(registry, 'release'):
            raise RequirementError('PRODUCT_REFERENCE: unknown accepted release')
        data['withdrawals'].append({'release': request['release'], 'reason': request['reason']})
    else:
        raise RequirementError('REQUEST_OPERATION: unknown product operation')
    check_relations(registry)


def requirement_impact(registry, affected):
    if 'components' not in registry:
        return []
    releases = {item['id'] for item in records(registry, 'release').values()
                if set(item['requirements']) & set(affected)}
    adoptions = [work for work in model(registry)['works'] if work['kind'] == 'adoption'
                 and releases & set(work['record']['releases'])]
    return sorted({'product-release:' + item for item in releases} |
                  {consumer for work in adoptions for consumer in work['record']['consumers']} |
                  {'product-work:' + work['id'] for work in adoptions})


def guard_scope_change(registry, scope):
    if 'components' not in registry:
        return
    current = next(item for item in registry['increments'] if item['id'] == registry['active_increment'])
    old = {item['requirement']: set(item['criteria']) for item in current['scope']}
    new = {item['requirement']: set(item['criteria']) for item in scope}
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    accepted = {item['work'] for item in model(registry)['acceptances']}
    for work in model(registry)['works']:
        if work['increment'] != registry['active_increment'] or work['id'] not in accepted:
            continue
        references = set(work['record'].get('requirements', []))
        if work['kind'] == 'adoption':
            references.update(link['requirement'] for link in registry['links']
                              if link['increment'] == registry['active_increment'] and
                              link['target'] in work['record']['consumers'])
        if references & changed:
            raise RequirementError('SCOPE_GOVERNED: accepted product work requires a new increment for changed scope')


def change_preview(root, registry, state, request):
    from .requirements import read_registry

    before = read_registry(root)
    old_scope = {item['requirement']: item['criteria'] for increment in (before or {}).get('increments', [])
                 if increment['id'] == before['active_increment'] for item in increment['scope']}
    new_scope = {item['requirement']: item['criteria'] for increment in registry['increments']
                 if increment['id'] == registry['active_increment'] for item in increment['scope']}
    affected = set(old_scope) ^ set(new_scope)
    revised_requirement = request['operation'] in {'requirement', 'numbered_requirement'}
    if revised_requirement:
        affected.add(request['requirement'].get('id', 'proposed') + '@' + str(request['requirement']['version']))
        change = next((item for item in registry['changes'] if item['request_id'] == request['request_id']), None)
        if change:
            affected.update(change['affected'])
    affected.update(key for key in old_scope.keys() & new_scope.keys() if old_scope[key] != new_scope[key])
    consumers = {link['target'] for link in registry['links'] if link['requirement'] in affected}
    if request['operation'] == 'product_work' and request['kind'] == 'adoption':
        record = request['record']
        consumers.update(record['consumers'])
        prior = records(registry, 'adoption').get(record['prior'])
        if prior:
            consumers.update(prior['consumers'])
    core = {item['id']: item for item in state['deliverables']}
    while True:
        downstream = {key for key, item in core.items() if set(item['depends_on']) & consumers}
        if downstream <= consumers:
            break
        consumers.update(downstream)
    return {'scope_added': sorted(new_scope.keys() - old_scope.keys()),
            'scope_removed': sorted(old_scope.keys() - new_scope.keys()),
            'requirements': sorted(affected), 'consumers': sorted(consumers),
            'gates': sorted(gate['id'] for gate in state['gates'] if set(gate.get('requirements', [])) & consumers),
            'verification_results': sorted(item['id'] for item in registry['verifications']
                                           if item['requirement'] in affected),
            'new_requirement_versions_required': revised_requirement}


def claim_issues(root, registry, state, consumer):
    if not any(consumer in work['record']['consumers'] for work in selections(registry)):
        return []
    return readiness(root, registry, state, owner=consumer)


def handoff_preview(root, request):
    from .requirements import _owner, input_snapshot, read_registry
    from .requirement_contract import S, arr, obj
    from .reconcile import load_artifact_bindings, map_paths_to_deliverables
    from .work_planning import _literal_glob

    validate(request, obj({
        'request_id': ID, 'reason': S, 'source_owner': ID, 'target_owner': ID,
        'files': {**arr(obj({'source': S, 'target': S})), 'minItems': 1},
    }))
    registry = read_registry(root)
    model(registry or {})
    state = load_state(root / '.ipd/project_state.yaml')
    owners = {item['id']: item for item in state['deliverables']}
    target = owners.get(request['target_owner'])
    if not target or target['status'] in {'accepted', 'superseded'}:
        raise RequirementError('HANDOFF_OWNER: choose a current editable target Owner')
    binding = load_artifact_bindings(root / '.ipd/artifact_bindings.yaml')
    snapshot = input_snapshot(root, registry)
    rows, paths, diagnostics, candidates = [], set(), [], []
    for item in request['files']:
        _owner(root, state, item['source'], request['source_owner'])
        source = safe_path(root, item['source'])
        destination = safe_path(root, item['target'])
        if not source.is_file() or source.suffix.lower() != '.md' or not item['target'].startswith('docs/'):
            raise RequirementError('HANDOFF_PATH: choose an existing Markdown source and a new docs path')
        if destination.exists() or item['target'].casefold() in paths:
            raise RequirementError('HANDOFF_PATH: target exists or is duplicated')
        paths.add(item['target'].casefold())
        mapping = map_paths_to_deliverables([item['target']], binding)
        bound = {owner for rule in mapping['paths'].get(item['target'], []) for owner in rule['owner_deliverable_ids']}
        if bound and bound != {target['id']}:
            diagnostics.append('HANDOFF_OWNER_CONFLICT:' + item['target'])
        if not bound:
            candidates.append({'id': 'handoff-' + request['request_id'] + '-' + str(len(rows)),
                               'glob': _literal_glob(item['target']), 'role': 'owner', 'deliverable': target['id']})
        proof = {'path': item['source'], 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        snapshot[proof['path']] = proof['sha256']
        rows.append({**item, 'sha256': proof['sha256'], 'source_owner': request['source_owner'],
                     'target_owner': target['id'],
                     'prior_reviews_sha256': digest(owners[request['source_owner']]['reviews'])})
    return {'schema_version': '1.0', 'read_only': True, 'request': request, 'source_sha256': digest(snapshot),
            'files': rows, 'candidate_bindings': candidates, 'issues': diagnostics,
            'next_steps': ['accept explicit target bindings', 'claim target Owner',
                           'preview and apply handoff_instance', 'edit draft and submit normal review']}


def projection(root, registry, state):
    if 'components' not in registry:
        return None
    data = model(registry)
    rows = []
    accepted = {item['work'] for item in data['acceptances']}
    for kind in ('release', 'compatibility', 'dataset', 'adoption'):
        for record in records(registry, kind).values():
            problems = issues(root, registry, kind, record)
            work = next((item for item in data['works'] if item['id'] == record['id']), None)
            rows.append({'id': record['id'], 'kind': kind, 'record': record, 'issues': problems,
                         'owner': work['owner'] if work else None,
                         'increment': work['increment'] if work else None,
                         'status': 'suspended' if problems else 'accepted',
                         'approval_source': 'governed-owner' if work else 'imported-history',
                         'acceptance': next((item for item in data['acceptances'] if item['work'] == record['id']), None)
                         if work else next(item for item in data['imports'] if item['release']['id'] == record['id']),
                         'source_verification': 'local-content-hashes; declared repository citation'})
    rows.extend({'id': work['id'], 'kind': work['kind'], 'record': work['record'], 'owner': work['owner'],
                 'increment': work['increment'],
                 'status': 'pending', 'issues': issues(root, registry, work['kind'], work['record']),
                 'approval_source': 'pending-owner'} for work in data['works'] if work['id'] not in accepted)
    return {'schema_version': '1.0', 'products': data['products'], 'records': rows,
            'selected_adoptions': [work['id'] for work in selections(registry)],
            'serial_governance': True}

"""Read and describe a table's declared Atlas neighborhood, without inferring transfers."""


def complete_upstream(guid, get_detail, get_lineage, get_refs, direction='INPUT'):
    """Visit every ancestor once, combining explicit relationships and Atlas edges."""
    nodes, edges, visited = {}, set(), set()
    pending = [guid]
    while pending:
        key = pending.pop()
        if key in visited:
            continue
        visited.add(key)
        item = get_detail(key)
        if item.get('status') == 'DELETED':
            continue
        nodes[key] = item
        graph = get_lineage(key, direction, 1)
        origin, target = ('fromEntityId', 'toEntityId') if direction == 'INPUT' else ('toEntityId', 'fromEntityId')
        parents = {r[origin] for r in graph.get('relations', [])
                   if r.get(target) == key and r.get(origin)
                   and r.get('relationshipStatus') != 'DELETED'}
        for attribute in (('inputs', 'outputFromProcesses') if direction == 'INPUT' else ('outputs', 'inputToProcesses')):
            parents.update(ref['guid'] for ref in get_refs(item, attribute)
                           if ref.get('guid') and ref.get('relationshipStatus') != 'DELETED'
                           and ref.get('entityStatus') != 'DELETED')
        for parent in parents:
            edges.add((parent, key))
            if parent not in visited:
                pending.append(parent)
    edges = {(a, b) for a, b in edges if a in nodes and b in nodes}
    incoming = {key: set() for key in nodes}
    for a, b in edges:
        incoming[b].add(a)
    paths, cycles = [], False
    pending_paths = [(guid, [guid])]
    while pending_paths:
        key, path = pending_paths.pop()
        parents = incoming.get(key, set())
        if not parents:
            paths.append(list(reversed(path)))
        for parent in sorted(parents):
            if parent in path:
                cycles = True
            else:
                pending_paths.append((parent, path + [parent]))
    if direction == 'OUTPUT':
        edges = {(b, a) for a, b in edges}
        paths = [list(reversed(path)) for path in paths]
    return dict(nodes=nodes, edges=sorted(edges), paths=paths, cycles=cycles)


def read_table_lineage(guid, get_detail, get_lineage, get_refs, direction='BOTH', include_keys=True):
    cache = {}

    def entity(key):
        if key not in cache:
            cache[key] = get_detail(key)
        return cache[key]

    def active(key):
        return entity(key).get('status') != 'DELETED'

    target = entity(guid)
    graph = get_lineage(guid, direction, 2)
    edges = {(r['fromEntityId'], r['toEntityId']) for r in graph.get('relations', [])
             if r.get('fromEntityId') and r.get('toEntityId')
             and r.get('relationshipStatus') != 'DELETED'}

    def related(item, attribute):
        return {ref['guid'] for ref in get_refs(item, attribute) if active(ref['guid'])}

    def deleted_related(item, attribute):
        raw = item.get('raw', {})
        value = (raw.get('relationshipAttributes') or {}).get(attribute,
                (raw.get('attributes') or {}).get(attribute, []))
        values = [value] if isinstance(value, dict) else value or []
        return {ref['guid'] for ref in values if isinstance(ref, dict) and ref.get('guid')
                and (ref.get('relationshipStatus') == 'DELETED' or ref.get('entityStatus') == 'DELETED')}

    def process(key):
        item = entity(key)
        raw = item.get('raw', {})
        return ('process' in item['typeName'].lower()
                or any(k in values for values in (raw.get('attributes') or {},
                                                  raw.get('relationshipAttributes') or {})
                       for k in ('inputs', 'outputs')))

    producers = related(target, 'outputFromProcesses')
    consumers = related(target, 'inputToProcesses') if direction != 'INPUT' else set()
    producers.update(a for a, b in edges if b == guid and active(a) and process(a))
    if direction != 'INPUT':
        consumers.update(b for a, b in edges if a == guid and active(b) and process(b))
    producers.difference_update(deleted_related(target, 'outputFromProcesses'))
    consumers.difference_update(deleted_related(target, 'inputToProcesses'))
    producers = {key for key in producers if guid not in deleted_related(entity(key), 'outputs')}
    consumers = {key for key in consumers if guid not in deleted_related(entity(key), 'inputs')}
    records = {}
    for key in producers | consumers:
        item = entity(key)
        inputs = related(item, 'inputs')
        outputs = related(item, 'outputs')
        inputs.update(a for a, b in edges if b == key and active(a) and not process(a))
        outputs.update(b for a, b in edges if a == key and active(b) and not process(b))
        inputs.difference_update(deleted_related(item, 'inputs'))
        outputs.difference_update(deleted_related(item, 'outputs'))
        if key in producers:
            outputs.add(guid)
        if key in consumers:
            inputs.add(guid)
        records[key] = dict(name=item['name'], description=item.get('description', ''), inputs=sorted(inputs), outputs=sorted(outputs))

    foreign_keys = set()
    for column_id in (related(target, 'columns') if include_keys else []):
        column = entity(column_id)
        for attribute in ('foreignKeyTo', 'referencedBy'):
            for other in related(column, attribute):
                child, parent = (column_id, other) if attribute == 'foreignKeyTo' else (other, column_id)
                child_tables = related(entity(child), 'table')
                parent_tables = related(entity(parent), 'table')
                # A column explicitly contained by the target already has a known parent.
                if child == column_id:
                    child_tables.add(guid)
                if parent == column_id:
                    parent_tables.add(guid)
                if len(child_tables) == len(parent_tables) == 1:
                    ct, pt = next(iter(child_tables)), next(iter(parent_tables))
                    foreign_keys.add((entity(ct)['name'] + '.' + entity(child)['name'],
                                      entity(pt)['name'] + '.' + entity(parent)['name']))

    direct = {(a, b) for a, b in edges if guid in (a, b) and active(a) and active(b)
              and not process(a) and not process(b)}
    visible = set(direct)
    for key, record in records.items():
        visible.update((a, key) for a in record['inputs'])
        visible.update((key, b) for b in record['outputs'])
    node_ids = {guid} | {key for pair in visible for key in pair}
    nodes = {key: dict(id=key, label=entity(key)['name'], type=entity(key)['typeName'],
                       qualifiedName=entity(key).get('qualifiedName', '')) for key in node_ids}
    return dict(guid=guid, name=target['name'], description=target.get('description', ''), records=records, producers=producers,
                consumers=consumers, foreign_keys=sorted(foreign_keys), direct=sorted(direct),
                nodes=nodes, edges=[{'from': a, 'to': b} for a, b in sorted(visible)])


def describe_table_lineage(data, direction='BOTH', question=''):
    import re
    from process_presentation import process_role_suffix
    explain_absence = bool(re.search(r'absence|aucun|pourquoi|existe.*(?:aval|amont)', question, re.I))
    explain_limits = bool(re.search(r'limites?|transfert physique|prouv', question, re.I))
    def quoted(value):
        return '`' + value.replace('`', '') + '`'

    def names(keys):
        return sorted({data['nodes'][key]['label'] for key in keys}, key=str.casefold)

    def joined(values):
        values = [quoted(v) for v in values]
        return ' et '.join(values) if len(values) < 3 else ', '.join(values[:-1]) + ' et ' + values[-1]

    table = quoted(data['name'])
    up = data['producers']
    down = data['consumers']
    central = bool(up and down)
    has_input = bool(up) or any(b == data['guid'] for a, b in data['direct'])
    has_output = bool(down) or any(a == data['guid'] for a, b in data['direct'])
    role = ('relie les traitements en amont aux traitements en aval' if has_input and has_output else
            'reçoit les données issues des étapes précédentes' if has_input else
            'alimente les étapes suivantes' if has_output else
            'ne présente aucune étape reliée dans le parcours disponible')
    introduction = f'La table {table} {role}.'
    description = (data.get('description') or '').strip()
    if description:
        introduction += ' ' + description
    sections = [introduction]
    paths = []
    for enabled, keys, heading, endpoint in (
        (direction != 'OUTPUT', up, 'amont', 'inputs'),
        (direction != 'INPUT', down, 'aval', 'outputs'),
    ):
        if not enabled:
            continue
        direct = [(a, b) for a, b in data['direct']
                  if (b if heading == 'amont' else a) == data['guid']]
        if not keys:
            if not direct and explain_absence:
                sections.append(f'Aucune relation en {heading} n’est enregistrée dans Apache Atlas pour cette table.')
        else:
            clauses = []
            for key in sorted(keys, key=lambda k: data['records'][k]['name']):
                record = data['records'][key]
                endpoints = names(record[endpoint])
                process = quoted(record['name'])
                if heading == 'amont':
                    clause = f'{process}, qui a pour entrées {joined(endpoints)}' if endpoints else f'{process}, dont les entrées ne sont pas renseignées'
                    path = (' + '.join(endpoints) + ' → ' if endpoints else '') + record['name'] + ' → ' + data['name']
                else:
                    clause = (f'{process}, dont la sortie est {joined(endpoints)}' if len(endpoints) == 1 else
                              f'{process}, dont les sorties sont {joined(endpoints)}' if endpoints else
                              f'{process}, dont les sorties ne sont pas renseignées')
                    path = data['name'] + ' → ' + record['name'] + (' → ' + ' / '.join(endpoints) if endpoints else '')
                role = process_role_suffix(record.get('description'))
                if role:
                    if endpoints and heading == 'amont':
                        clause = process+', qui prend '+joined(endpoints)+' en entrée'+role.replace(', qui ', ' et ', 1)
                    elif endpoints:
                        clause = process+', qui produit '+joined(endpoints)+role.replace(', qui ', ' et ', 1)
                    else:
                        clause = process+role
                clauses.append(clause)
                paths.append(path)
            intro = (f'En amont, elle est alimentée par les sorties ' if heading == 'amont'
                     else f'En aval, elle fournit les données d’entrée ')
            if len(clauses) == 1:
                sections.append(intro + 'du processus ' + clauses[0] + '.')
            else:
                sections.append(intro + f'de {len(clauses)} processus :\n\n' + '\n'.join('- ' + c + '.' for c in clauses))
        if direct:
            sections.append(f'Liens directs en {heading}, sans processus intermédiaire documenté :\n\n' +
                            '\n'.join('- ' + quoted(data['nodes'][a]['label'] + ' → ' + data['nodes'][b]['label']) for a, b in direct))
    if paths:
        sections.append('Le parcours est donc :\n\n' + '\n'.join(quoted(p) for p in dict.fromkeys(paths)))
    if data['foreign_keys'] and re.search(r'cl[ée]s?\s+[ée]trang|r[ée]f[ée]rences?', question, re.I):
        sections.append('Les clés étrangères associées décrivent les références techniques entre les tables :\n\n' +
                        '\n'.join('- ' + quoted(a + ' → ' + b) for a, b in data['foreign_keys']))
    if explain_limits and (paths or data['direct']):
        sections.append(('Ces références sont distinctes du Data Lineage. ' if data['foreign_keys'] else '') +
                        'Les relations Atlas décrivent les entrées, processus et sorties déclarés ; elles ne prouvent pas un transfert physique de données.')
    if central and direction == 'BOTH':
        sections.append(f'Ainsi, {table} relie les processus en amont aux traitements en aval.')
    if direction != 'INPUT' and has_input and not has_output:
        sections.append(f'La destination finale de ce parcours est la table {table}.')
    return '\n\n'.join(sections)

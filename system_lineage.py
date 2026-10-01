"""Complete Atlas graphs and prose, preserving every process input and output."""
from collections import defaultdict, deque


def read_system_lineage(seeds, processes, detail, lineage, references):
    cache = {}

    def entity(guid):
        if guid not in cache:
            cache[guid] = detail(guid)
        return cache[guid]

    pending = [e['guid'] for e in seeds if e.get('status') != 'DELETED']
    reverse = defaultdict(set)
    # A dataset's inverse relationship can be absent in an Atlas import.
    for header in processes:
        item = entity(header['guid'])
        if item.get('status') == 'DELETED':
            continue
        for key in ('inputs', 'outputs'):
            relations=(item.get('raw') or {}).get('relationshipAttributes') or {}
            if key in relations and not relations[key]:
                continue
            for ref in references(item, key):
                pair = (ref['guid'],item['guid']) if key=='inputs' else (item['guid'],ref['guid'])
                reverse[ref['guid']].add(pair)
    nodes, edges, blocked, visited = {}, set(), set(), set()
    while pending:
        guid = pending.pop()
        if guid in visited:
            continue
        visited.add(guid)
        item = entity(guid)
        if item.get('status') == 'DELETED':
            continue
        raw = item.get('raw') or {}
        attrs = raw.get('attributes') or {}
        relations = raw.get('relationshipAttributes') or {}
        is_process = ('process' in item['typeName'].lower() or
                      any(k in relations or k in attrs for k in ('inputs', 'outputs')))
        nodes[guid] = dict(id=guid, label=item['name'], type=item['typeName'],
                           description=item.get('description', ''), is_process=is_process)
        pairs = set(reverse[guid])
        for key, upstream in (('inputs', True), ('outputs', False),
                              ('inputToProcesses', False), ('outputFromProcesses', True)):
            # relationshipAttributes is authoritative, including an empty list.
            values = relations.get(key, attrs.get(key, [])) or []
            values = [values] if isinstance(values, dict) else values
            for ref in values:
                other = ref.get('guid')
                if not other:
                    continue
                pair = (other, guid) if upstream else (guid, other)
                if ref.get('relationshipStatus') == 'DELETED' or ref.get('entityStatus') == 'DELETED':
                    blocked.add(pair)
                else:
                    pairs.add(pair)
        graph = lineage(guid, 'BOTH', 1)
        for ref in graph.get('relations', []):
            pair = (ref.get('fromEntityId'), ref.get('toEntityId'))
            if not all(pair) or guid not in pair:
                continue
            if ref.get('relationshipStatus') == 'DELETED':
                blocked.add(pair)
            else:
                pairs.add(pair)
        edges.update(pairs)
        pending.extend(other for pair in pairs - blocked for other in pair if other not in visited)
    edges = sorted((a, b) for a, b in edges - blocked if a in nodes and b in nodes)
    return nodes, [{'from': a, 'to': b} for a, b in edges]


def describe_system_lineage(nodes, edges, system, description_formatter):
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for edge in edges:
        a, b = edge['from'], edge['to']
        if a in nodes and b in nodes:
            incoming[b].add(a)
            outgoing[a].add(b)
    connected = {g for g in nodes if incoming[g] or outgoing[g]}
    if not connected:
        return 'Aucun parcours de Data Lineage n’est enregistré dans Atlas pour '+system+'.'

    def name(g):
        return nodes[g]['label']

    def ordered(keys):
        return sorted(keys, key=lambda g: (name(g).casefold(), g))

    def names(keys):
        values = [name(g) for g in ordered(keys)]
        return ', '.join(values[:-1])+' et '+values[-1] if len(values) > 1 else ''.join(values)

    def process(g):
        return nodes[g].get('is_process', 'process' in nodes[g]['type'].lower())

    roots = {g for g in connected if not incoming[g] and not process(g)}
    paragraphs = [('Le Data Lineage de '+system+' commence par '+
                   ('les tables ' if all('table' in nodes[g]['type'].lower() for g in roots) else 'les sources ')+
                   names(roots)+'.') if roots else
                  'Le Data Lineage de '+system+' ne présente pas de source initiale identifiable dans le parcours enregistré.']
    degrees = {g: len(incoming[g]) for g in connected}
    queue = deque(ordered(g for g in connected if not degrees[g]))
    order = []
    while queue:
        guid = queue.popleft()
        order.append(guid)
        for child in ordered(outgoing[guid]):
            degrees[child] -= 1
            if not degrees[child]:
                queue.append(child)
    cyclic = len(order) < len(connected)
    order.extend(ordered(connected - set(order)))
    paths, covered = [], set()
    for guid in order:
        if not process(guid):
            branches = {g for g in outgoing[guid] if process(g)}
            if len(branches) > 1:
                count = {2: 'deux', 3: 'trois'}.get(len(branches), str(len(branches)))
                paragraphs.append('À partir de '+name(guid)+', le lineage se divise en '+count+' branches.')
            continue
        inputs, outputs = incoming[guid], outgoing[guid]
        sentence = 'Le processus '+name(guid)
        sentence += ' utilise '+names(inputs)+' en entrée' if inputs else ' n’a pas d’entrée renseignée'
        sentence += ' et alimente '+names(outputs)+'.' if outputs else ' ; sa sortie n’est pas renseignée.'
        description = (nodes[guid].get('description') or '').strip()
        if description:
            rendered=description_formatter(description)
            if rendered.startswith('Processus '):
                rendered='Il s’agit d’un '+rendered[0].lower()+rendered[1:]
            sentence += ' '+rendered
        paragraphs.append(sentence)
        paths.append((' + '.join(name(g) for g in ordered(inputs)) or '[entrée non renseignée]')+
                     ' → '+name(guid)+' → '+
                     (' + '.join(name(g) for g in ordered(outputs)) or '[sortie non renseignée]'))
        covered.update((g, guid) for g in inputs)
        covered.update((guid, g) for g in outputs)
    for a in ordered(connected):
        for b in ordered(outgoing[a]):
            if (a, b) not in covered:
                paragraphs.append('Le lineage relie directement '+name(a)+' à '+name(b)+'.')
                paths.append(name(a)+' → '+name(b))
    if paths:
        paragraphs.append('Les parcours enregistrés sont :\n\n'+'\n\n'.join(paths))
    terminals = {g for g in connected if not outgoing[g] and not process(g)}
    if terminals:
        paragraphs.append('Ainsi, '+('ce lineage relie '+names(roots)+' à '+names(terminals)+' en passant par les processus décrits.'
                                    if roots else 'ces traitements alimentent '+names(terminals)+'.'))
    else:
        paragraphs.append('Ce parcours relie les étapes enregistrées dans Atlas, sans destination finale identifiable.')
    if cyclic:
        paragraphs.append('Une boucle est présente ; chaque étape est décrite une seule fois.')
    return '\n\n'.join(paragraphs)

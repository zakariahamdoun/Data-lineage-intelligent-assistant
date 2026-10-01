"""Explain an Atlas upstream graph without repeating shared process inputs."""
from collections import defaultdict, deque


def describe_upstream(data, target):
    from process_presentation import process_flow_suffix
    nodes = data['nodes']
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for a, b in data['edges']:
        incoming[b].add(a)
        outgoing[a].add(b)

    def name(g):
        return nodes[g]['name']

    def ordered(keys):
        return sorted(keys, key=lambda g: (name(g).casefold(), g))

    def process(g):
        raw = nodes[g].get('raw') or {}
        return ('process' in nodes[g].get('typeName', '').lower() or
                any(k in (raw.get('relationshipAttributes') or {}) or k in (raw.get('attributes') or {})
                    for k in ('inputs', 'outputs')))

    def objects(keys):
        keys = ordered(keys)
        names = [name(g) for g in keys]
        joined = ', '.join(names[:-1])+' et '+names[-1] if len(names)>1 else ''.join(names)
        tables = all('table' in nodes[g].get('typeName', '').lower() for g in keys)
        noun = ('la table ' if len(keys)==1 else 'les tables ') if tables else ('l’objet ' if len(keys)==1 else 'les objets ')
        return noun+joined

    ancestors = set(nodes)-{target}
    datasets = {g for g in ancestors if not process(g)}
    direct_inputs = {g for p in incoming[target] if process(p) for g in incoming[p] if not process(g)}
    if datasets and datasets == direct_inputs:
        subject=objects([target])
        paragraphs=[subject[0].upper()+subject[1:]+' est alimentée en amont par '+objects(datasets)+'.']
    else:
        paragraphs = ['En amont de '+objects([target])+', se trouvent '+objects(datasets)+'.'] if datasets else []
    degrees = {g:len(incoming[g]) for g in nodes}
    queue = deque(ordered(g for g in nodes if not degrees[g]))
    order = []
    while queue:
        guid = queue.popleft()
        order.append(guid)
        for child in ordered(outgoing[guid]):
            degrees[child]-=1
            if not degrees[child]:queue.append(child)
    order.extend(ordered(set(nodes)-set(order)))
    covered, segments = set(), []
    for guid in order:
        if not process(guid):continue
        inputs, outputs = incoming[guid], outgoing[guid]
        if inputs:
            subject = objects(inputs)
            sentence = subject[0].upper()+subject[1:]+(' passent' if len(inputs)>1 else ' passe')+' par le processus '+name(guid)
        else:
            sentence = 'Le processus '+name(guid)
        sentence += process_flow_suffix(nodes[guid].get('description'),objects(outputs) if outputs else None)
        if not inputs:sentence+=' Ses entrées ne sont pas renseignées.'
        paragraphs.append(sentence)
        left = ' + '.join(name(g) for g in ordered(inputs)) or '[entrées non renseignées]'
        right = ' + '.join(name(g) for g in ordered(outputs)) or '[sorties non renseignées]'
        segments.append(left+' → '+name(guid)+' → '+right)
        covered.update((g,guid) for g in inputs)
        covered.update((guid,g) for g in outputs)
    for a in order:
        for b in ordered(outgoing[a]):
            if (a,b) not in covered:
                paragraphs.append('Un lien direct relie '+objects([a])+' à '+objects([b])+'.')
                segments.append(name(a)+' → '+name(b))
    if segments:
        paragraphs.append('Le parcours en amont est donc :\n\n'+'\n\n'.join(segments))
    if data.get('cycles'):
        paragraphs.append('Une boucle est présente dans ce parcours ; chaque relation est présentée une seule fois.')
    return '\n\n'.join(paragraphs)

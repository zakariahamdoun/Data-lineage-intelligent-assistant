"""Explain potential impact using only directed edges already retrieved from Atlas."""
from collections import deque


def conclude_impact(nodes, edges, origin, targets, action='modification'):
    def label(guid):
        item = nodes[guid]
        kind = item.get('typeName', '').casefold()
        noun = ('la colonne' if 'column' in kind else 'la table' if 'table' in kind else
                'le fichier' if 'file' in kind or kind == 'hdfs_path' else
                'le processus' if 'process' in kind else 'l’objet')
        return noun+' `'+item['name'].replace('`', '')+'`'

    # One verified explanation path per object; shared branches and cycles remain separate.
    paths = {origin: [origin]}
    adjacency = {}
    for a, b in sorted(edges):
        if a in nodes and b in nodes:adjacency.setdefault(a, []).append(b)
    pending = deque([origin])
    while pending:
        current = pending.popleft()
        for target in adjacency.get(current, []):
            if target not in paths:
                paths[target] = paths[current]+[target]
                pending.append(target)
    sentences = []
    for target in dict.fromkeys(targets):
        if target == origin or target not in paths:continue
        path = paths[target]
        route = ' → '.join(nodes[g]['name'] for g in path)
        subject = label(target)
        source = label(origin)
        source_of = 'du '+source[3:] if source.startswith('le ') else 'de '+source
        link = ('par le processus `'+nodes[path[1]]['name'].replace('`', '')+'`'
                if len(path)==3 and 'process' in nodes[path[1]].get('typeName', '').casefold()
                else 'par la dépendance directe '+route if len(path)==2 else 'par le parcours '+route)
        sentences.append(subject[0].upper()+subject[1:]+
            ' peut être potentiellement impacté'+('e' if subject.startswith('la ') else '')+
            ', car cet objet dépend en aval '+source_of+' '+link+'. Une '+action+' de `'+nodes[origin]['name'].replace('`', '')+
            '` peut ainsi se répercuter sur '+subject+' par cette dépendance.')
    return '\n\n'.join(sentences)

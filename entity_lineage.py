"""Explicit named lineage requests, resolved only from Atlas metadata."""
import re

from atlas_candidates import resolve_candidates, candidate_choices
from chat_context import atlas_scope
from table_lineage import complete_upstream
from process_presentation import process_role_suffix


def format_entity_lineage(guid, traversals, process_types, question=''):
    """Present verified Atlas traversals; no retrieval, inference or model calls."""
    nodes = {key: node for data in traversals.values() for key, node in data['nodes'].items()}

    def noun(key):
        kind = nodes[key].get('typeName', '')
        if kind in process_types:
            return 'le processus'
        if 'table' in kind.casefold():
            return 'la table'
        if kind == 'hdfs_path':
            return 'le fichier'
        return 'l’entité'

    def label(key):
        return noun(key) + ' `' + nodes[key]['name'].replace('`', '') + '`'

    def of_label(key):
        value = label(key)
        return 'du ' + value[3:] if value.startswith('le ') else 'de ' + value

    if guid not in nodes:
        return 'L’entité demandée n’est plus disponible dans les métadonnées Atlas consultées.'
    edges = {edge for data in traversals.values() for edge in data['edges']}
    incoming = any(b == guid for a, b in edges)
    outgoing = any(a == guid for a, b in edges)
    role = ('relie les étapes en amont aux étapes en aval du parcours présenté' if incoming and outgoing else
            'alimente les étapes suivantes du parcours présenté' if outgoing else
            'reçoit les données issues des étapes précédentes du parcours présenté' if incoming else
            'ne présente aucune étape reliée dans le parcours disponible')
    introduction = label(guid)[0].upper() + label(guid)[1:] + ' ' + role + '.'
    description = (nodes[guid].get('description') or '').strip()
    if description:
        introduction += ' ' + description
    sections = [introduction]
    described = {guid} if description else set()
    for mode, data in traversals.items():
        downstream = mode == 'OUTPUT'
        side = 'aval' if downstream else 'amont'
        paths = sorted(data['paths'], key=lambda path: tuple(nodes[g]['name'] for g in path))
        # Explain each verified edge once, even when several paths share a prefix.
        ordered = list(dict.fromkeys((a, b) for path in paths for a, b in zip(path, path[1:])))
        ordered.extend(edge for edge in data['edges'] if edge not in ordered)
        steps = []
        for a, b in ordered:
            if nodes[b].get('typeName') in process_types:
                sentence = ('Les données ' + of_label(a) + ' passent ensuite par ' + label(b) + '.')
            elif nodes[a].get('typeName') in process_types:
                sentence = 'À la sortie ' + of_label(a) + ', les données alimentent ' + label(b) + '.'
            else:
                sentence = 'Le parcours se poursuit ' + of_label(a) + ' vers ' + label(b) + '.'
            steps.append(sentence)
            for key in (a, b):
                description = (nodes[key].get('description') or '').strip()
                if key not in described and nodes[key].get('typeName') in process_types and description:
                    suffix = process_role_suffix(description)
                    token = '`'+nodes[key]['name'].replace('`', '')+'`'
                    steps[-1] = steps[-1].replace(token, token+suffix, 1)
                    described.add(key)
        if steps:
            sections.append('En ' + side + ', le parcours se déroule ainsi :\n\n' + '\n\n'.join(steps))
            routes = [' → '.join(nodes[g]['name'] for g in path) for path in paths if len(path) > 1]
            if routes:
                sections.append('Parcours du Data Lineage' + (' (' + side + ')' if len(traversals) > 1 else '') +
                                ' :\n\n' + '\n'.join(routes))
        elif re.search(r'absence|aucun|pourquoi|existe.*(?:aval|amont)', question, re.I):
            sections.append('Aucune dépendance en ' + side + ' n’est enregistrée pour ' + label(guid) +
                            ' dans ce parcours.')
        if data['cycles']:
            sections.append('Un cycle est enregistré dans ce parcours.')
        if downstream:
            outgoing = {a for a, _ in data['edges']}
            terminals = sorted({path[-1] for path in paths if path and path[-1] not in outgoing},
                               key=lambda key: nodes[key]['name'])
            if terminals:
                sections.append(('La destination finale est ' if len(terminals) == 1 else
                                 'Les destinations finales sont ') +
                                ', '.join(label(key) for key in terminals) + '.')
    return '\n\n'.join(sections)


def format_file_destination(guid, data, process_types):
    """Answer only where the file goes, using the verified downstream graph."""
    nodes = data['nodes']
    name = nodes[guid]['name']
    steps = []
    ordered = list(dict.fromkeys((a, b) for path in data['paths'] for a, b in zip(path, path[1:])))
    ordered.extend(edge for edge in data['edges'] if edge not in ordered)
    described = set()
    for a, b in ordered:
        if nodes[b]['typeName'] in process_types:
            subject = ('Le fichier '+name if a == guid else 'Les données de '+nodes[a]['name'])
            steps.append(subject+' est utilisé comme entrée du processus '+nodes[b]['name']+'.'
                         if a == guid else subject+' passent ensuite par le processus '+nodes[b]['name']+'.')
            if b not in described:
                role = process_role_suffix(nodes[b].get('description'))
                if role:
                    steps.append(('Ce processus '+role[len(', qui '):] if role.startswith(', qui ') else
                                  'Le processus '+nodes[b]['name']+role)+'.')
                described.add(b)
        elif nodes[a]['typeName'] not in process_types:
            steps.append('Les données de '+nodes[a]['name']+' alimentent '+nodes[b]['name']+'.')
    outgoing = {a for a, b in data['edges']}
    terminals = sorted({p[-1] for p in data['paths'] if len(p)>1 and p[-1] not in outgoing},
                       key=lambda g: nodes[g]['name'])
    if terminals:
        labels = [('la table ' if 'table' in nodes[g]['typeName'].casefold() else
                   'le fichier ' if nodes[g]['typeName']=='hdfs_path' else
                   'le processus ' if nodes[g]['typeName'] in process_types else 'l’objet ')+nodes[g]['name'] for g in terminals]
        steps.append(('La destination du fichier '+name+' est donc ' if len(labels)==1 else
                      'Les destinations du fichier '+name+' sont donc ')+', '.join(labels)+'.')
    else:
        steps.append('Aucune destination finale n’a pu être identifiée pour le fichier '+name+'.')
    return '\n\n'.join(steps)


def answer_named_lineage(question, source, api):
    destination = re.search(r'\bdestination\s+(?:du|de ce|de)\s+fichier\s+[`\"\']?([\w.@:/-]+)',
                            question, re.I)
    if not destination and not re.search(r'\blineage\b', question, re.I):
        return None
    if api['requested_lineage_endpoints'](question):
        return None
    match = re.search(
        r"\blineage\s+(?:complet\s+)?(?:de la|du|de)\s+"
        r"(?:(?:la table|table|fichier|processus|l[’']entité)\s+)?[`\"']?([\w.@:/-]+)",
        question.replace('\\_', '_'), re.I)
    match = destination or match
    if not match:
        return None
    name = match.group(1).rstrip('.').casefold()
    if name in ('la', 'le', 'les', 'du', 'des', 'ce', 'cet', 'cette', 'ces', 'mon', 'ma',
                'base', 'bases', 'tables', 'toutes', 'tous',
                'projet', 'système', 'systeme', 'sqlite', 'postgresql'):
        return None
    final = bool(destination or re.search(r'jusqu.*destination\s+finale', question, re.I))
    # Existing table resolution remains authoritative for actual table subjects.
    if not final and any(name in (str((e.get('attributes') or {}).get('name', '')).casefold(),
                                 str((e.get('attributes') or {}).get('qualifiedName', '')).casefold())
                         for _, e in api['find_requested_tables'](question, source)):
        return None
    missing = "L'entité demandée n'a pas été trouvée dans les métadonnées disponibles dans Apache Atlas."
    with atlas_scope(None):
        definitions = api['atlas_get']('/api/atlas/v2/types/typedefs').get('entityDefs', [])
        process_types = api['atlas_process_types'](definitions)
        inventory = {}
        for kind in sorted({d['name'] for d in definitions}):
            for entity in api['atlas_inventory_entities'](kind):
                inventory[entity['guid']] = entity

        def matches(entity):
            attrs = entity.get('attributes') or {}
            return entity.get('status') != 'DELETED' and name in (
                str(attrs.get('name', '')).casefold(), str(attrs.get('qualifiedName', '')).casefold())

        candidates = [e for e in inventory.values() if matches(e)]
        # Search indexes may omit active files referenced by process lineage.
        if not candidates:
            for entity in list(inventory.values()):
                if entity.get('typeName') in process_types:
                    graph = api['get_lineage'](entity['guid'], 'BOTH', 10)
                    inventory.update(graph.get('guidEntityMap') or {})
            candidates = [e for e in inventory.values() if matches(e)]
        if not candidates:
            return missing
        if len(candidates) > 1 and source in ('sqlite', 'postgresql'):
            contextual = []
            for entity in candidates:
                graph = api['get_lineage'](entity['guid'], 'BOTH', 10)
                if any(e.get('typeName', '').casefold().startswith(source)
                       for e in [entity] + list((graph.get('guidEntityMap') or {}).values())):
                    contextual.append(entity)
            if contextual:
                candidates = contextual
        candidates = resolve_candidates(candidates, api['detail'], api['get_lineage'],
                                        api['process_refs'], 'BOTH', source)
        if len(candidates) > 1:
            return 'Plusieurs entités correspondent. Précisez le qualifiedName :\n\n' + candidate_choices(candidates)
        if not candidates:
            return missing
        entity = candidates[0]
        # Keep existing table narratives and graph handling.
        if 'table' in entity.get('typeName', '').casefold() and not final:
            return None
        direction = 'OUTPUT' if final else api['lineage_scope'](question)[0]
        traversals = {}
        for mode in (('INPUT', 'OUTPUT') if direction == 'BOTH' else (direction,)):
            traversals[mode] = complete_upstream(entity['guid'], api['detail'], api['get_lineage'], api['process_refs'], mode)
        if destination:return format_file_destination(entity['guid'], traversals['OUTPUT'], process_types)
        return format_entity_lineage(entity['guid'], traversals, process_types, question)

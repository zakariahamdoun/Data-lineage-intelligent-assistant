"""Conservative logical deduplication using Atlas identity and lineage evidence."""


def resolve_candidates(entities, detail, lineage, refs, direction='BOTH', source=None, prefer_lineage=True):
    unique={e['guid']:e for e in entities if e.get('status')!='DELETED'}
    if len(unique)<2:return list(unique.values())
    records=[]
    for guid,header in unique.items():
        item=detail(guid)
        if item.get('status')=='DELETED':continue
        attrs=(item.get('raw') or {}).get('attributes') or header.get('attributes') or {}
        qualified=item.get('qualifiedName') or attrs.get('qualifiedName')
        kind=item.get('typeName') or header.get('typeName')
        name=item.get('name') or attrs.get('name')
        neighbors=set()
        graph=lineage(guid,direction,1)
        for edge in graph.get('relations',[]):
            if edge.get('relationshipStatus')=='DELETED':continue
            a,b=edge.get('fromEntityId'),edge.get('toEntityId')
            if b==guid and a and direction!='OUTPUT':neighbors.add(('in',a))
            if a==guid and b and direction!='INPUT':neighbors.add(('out',b))
        for attribute,side in (('inputs','in'),('outputFromProcesses','in'),
                               ('outputs','out'),('inputToProcesses','out')):
            if direction=='INPUT' and side=='out' or direction=='OUTPUT' and side=='in':continue
            neighbors.update((side,r['guid']) for r in refs(item,attribute)
                             if r.get('guid') and r.get('relationshipStatus')!='DELETED' and r.get('entityStatus')!='DELETED')
        neighbors={(side,g) for side,g in neighbors if detail(g).get('status')!='DELETED'}
        bases=tuple(sorted(r['guid'] for r in refs(item,'database')))
        environment=attrs.get('databaseName') or bases or None
        key=('qualified',name,qualified,kind,str(environment)) if qualified else (
            ('logical',name,kind,str(environment),tuple(sorted(neighbors))) if neighbors else ('guid',guid))
        contextual=bool(source and (str(kind).casefold().startswith(source) or any(
            detail(g).get('typeName','').casefold().startswith(source) for _,g in neighbors)))
        records.append((key,header,neighbors,contextual))
    groups={}
    for record in records:groups.setdefault(record[0],[]).append(record)
    # Prefer a connected representative of duplicate identities.
    selected=[max(group,key=lambda r:(r[3],bool(r[2]),len(r[2]))) for group in groups.values()]
    contextual=[r for r in selected if r[3]]
    if contextual:selected=contextual
    connected=[r for r in selected if r[2]]
    if connected and prefer_lineage:selected=connected
    return [r[1] for r in selected]


def candidate_options(entities):
    """Keep Atlas identifiers internally while exposing only a business label."""
    options=[]
    for entity in entities:
        attributes=entity.get('attributes') or {}
        name=str(attributes.get('name') or entity.get('displayText') or entity['guid'])
        qualified=str(attributes.get('qualifiedName') or '')
        kind=str(entity.get('typeName') or '')
        object_name=qualified.split('@',1)[0]
        if 'column' in kind.casefold():
            table=object_name.rsplit('.',1)[0] if '.' in object_name else 'table non renseignée'
            label=f'`{name}` dans la table `{table}`'
        elif 'table' in kind.casefold():
            system='SQLite' if kind.casefold().startswith('sqlite') else 'PostgreSQL' if kind.casefold().startswith('postgresql') else 'le catalogue'
            label=f'`{name}` dans {system}'
        else:
            label=f'`{name}`'
        options.append({'guid':entity['guid'],'qualifiedName':qualified,'typeName':kind,
                        'display_label':label,'name':name})
    return options


def candidate_choices(entities):
    return '\n'.join('- '+option['display_label'] for option in candidate_options(entities))


def candidate_clarification(entities):
    options=candidate_options(entities)
    if options and all('column' in option['typeName'].casefold() for option in options):
        return (f"La colonne `{options[0]['name']}` existe dans plusieurs tables.\n\n"
                'Précisez celle que vous souhaitez analyser :\n\n'+candidate_choices(entities))
    if options and all('table' in option['typeName'].casefold() for option in options):
        return (f"La table `{options[0]['name']}` existe dans plusieurs environnements.\n\n"
                'Précisez celle que vous souhaitez consulter :\n\n'+candidate_choices(entities))
    return 'Plusieurs correspondances ont été trouvées. Précisez celle que vous souhaitez analyser :\n\n'+candidate_choices(entities)


"""Resolve positional references only from declared Atlas lineage."""
import re
from chat_context import normalize
from table_lineage import complete_upstream


def reference_role(question):
    text=normalize(question)
    # A traversal endpoint is not the requested starting entity.
    text=re.sub(r'jusqu.*?(?:destinations? finales?|fin du lineage|fin du parcours)', '', text)
    for role,pattern in (
        ('initial',r'source initiale|premier fichier'),
        ('final',r'destination finale|table finale'),
        ('loader',r'processus de chargement'),
        ('previous',r'objet precedent'),
        ('source',r'fichier source|\bla source de\b')):
        if re.search(pattern,text):return role
    return None


def resolve_reference(question, inventory, state, source, detail, lineage, refs, process_types):
    role=reference_role(question)
    if not role:return None
    text=question.casefold().replace('`','').rstrip(' .?!')
    anchors=[e for e in inventory if any(value and re.search(
        r'(?<![\w.@])'+re.escape(value.casefold())+r'(?![\w.@])',text)
        for value in ((e.get('attributes') or {}).get('name'),(e.get('attributes') or {}).get('qualifiedName')))]
    if not anchors:
        active=state.get('active_entity_guid') or state.get('active_table_guid')
        anchors=[e for e in inventory if e['guid']==active and
                 (not source or not e.get('typeName','').lower().startswith(('sqlite','postgresql')) or
                  e.get('typeName','').lower().startswith(source))]
    if not anchors and source in ('sqlite','postgresql'):
        anchors=[e for e in inventory if e.get('typeName','').lower()==source+'table']
    found={}
    for anchor in anchors:
        guid=anchor['guid']
        data=complete_upstream(guid,detail,lineage,refs,'OUTPUT' if role=='final' else 'INPUT')
        nodes=data['nodes'];chosen=set()
        if not data['edges']:
            if role=='final' and complete_upstream(guid,detail,lineage,refs)['edges']:
                if 'table finale' not in normalize(question) or 'table' in nodes[guid].get('typeName','').lower():
                    item=nodes[guid]
                    found[guid]={'guid':guid,'typeName':item['typeName'],'attributes':{
                        'name':item['name'],'qualifiedName':item.get('qualifiedName','')}}
            continue
        def is_file(key):
            kind=nodes[key].get('typeName','').lower()
            return 'file' in kind or kind=='hdfs_path'
        if role=='initial':
            chosen={p[0] for p in data['paths'] if len(p)>1}
            if 'fichier' in normalize(question):chosen={g for g in chosen if is_file(g)}
        elif role=='final':
            chosen={p[-1] for p in data['paths'] if len(p)>1}
            if 'table finale' in normalize(question):chosen={g for g in chosen if 'table' in nodes[g].get('typeName','').lower()}
        elif role in ('loader','previous'):
            chosen={a for a,b in data['edges'] if b==guid}
            if role=='loader':chosen={g for g in chosen if nodes[g].get('typeName') in process_types}
        else:
            for path in data['paths']:
                files=[g for g in reversed(path[:-1]) if is_file(g)]
                if files:chosen.add(files[0])
        for key in chosen:
            item=nodes[key]
            found[key]={'guid':key,'typeName':item['typeName'],'attributes':{
                'name':item['name'],'qualifiedName':item.get('qualifiedName','')}}
    return list(found.values())

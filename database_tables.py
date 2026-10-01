"""Resolve database membership from Atlas, independently of conversation filters."""
import re
from chat_context import atlas_scope


def inventory(kind, api):
    entities = {e['guid']: e for e in api['atlas_inventory_entities'](kind)}
    offset = 0
    while True:
        batch = api['atlas_get']('/api/atlas/v2/search/dsl',
                                 {'query': kind, 'limit': 1000, 'offset': offset}).get('entities', [])
        entities.update((e['guid'], e) for e in batch if e.get('guid'))
        if len(batch) < 1000:break
        offset += len(batch)
    return [e for e in entities.values() if e.get('status') != 'DELETED']


def databases(name, engine, api):
    result = []
    for system in ('SQLite', 'PostgreSQL'):
        if engine and system.casefold() != engine.casefold():continue
        for header in inventory(system+'Database', api):
            entity = api['get_entity'](header['guid']).get('entity', {})
            attrs = entity.get('attributes') or {}
            if entity.get('status') == 'ACTIVE' and name.casefold() in (
                    str(attrs.get('name', '')).casefold(), str(attrs.get('qualifiedName', '')).casefold()):
                result.append((system, entity))
    return result


def attached_tables(system, database, api):
    attrs = database.get('attributes') or {}
    names = {str(attrs[k]).casefold() for k in ('name', 'qualifiedName') if attrs.get(k)}
    rel = database.get('relationshipAttributes') or {}
    children = {r['guid'] for r in api['refs'](rel.get('tables', attrs.get('tables', [])))
                if r.get('relationshipStatus') != 'DELETED' and r.get('entityStatus') != 'DELETED'}
    headers = {e['guid']: e for e in inventory(system+'Table', api)}
    for guid in children:
        if guid not in headers:headers[guid] = {'guid': guid}
    result = {}
    for guid in headers:
        entity = api['get_entity'](guid).get('entity', {})
        if entity.get('status') != 'ACTIVE' or entity.get('typeName') != system+'Table':continue
        a = entity.get('attributes') or {}
        relationships = entity.get('relationshipAttributes') or {}
        parents = [r for key in ('database', 'db') for r in
                   api['refs'](relationships.get(key, a.get(key, {})))]
        if parents:
            attached = any(r['guid'] == database['guid'] and r.get('relationshipStatus') != 'DELETED'
                           and r.get('entityStatus') != 'DELETED' for r in parents)
        elif guid in children:
            attached = True
        elif a.get('databaseName') or a.get('dbName'):
            attached = any(str(a.get(key, '')).casefold() in names for key in ('databaseName', 'dbName'))
        else:
            qualified = str(a.get('qualifiedName', '')).casefold()
            # Match complete identifier components, never a database-name substring.
            attached = any(re.search(r'(?:^|[@/:])'+re.escape(name)+r'(?=$|[@/:])', qualified)
                           for name in names)
        if attached:result[guid] = entity
    return list(result.values())


def find_tables_in_database(database_name, database_type, api):
    with atlas_scope(None):
        matches = databases(database_name, database_type, api)
        if len(matches) > 1:
            raise ValueError('Plusieurs bases correspondent. Précisez le type ou le qualifiedName de la base.')
        return attached_tables(*matches[0], api) if matches else []


def answer_database_tables(question, api):
    from intent_routing import database_tables_request
    request = database_tables_request(question)
    if request is None:return None
    name, engine = request
    with atlas_scope(None):
        matches = databases(name, engine, api)
        if not matches:return 'La base '+name+' est introuvable dans Apache Atlas.'
        if len(matches) > 1:
            return 'Plusieurs bases correspondent. Précisez le type ou le qualifiedName : '+', '.join(
                system+' : '+str((e.get('attributes') or {}).get('qualifiedName') or api['ename'](e)) for system,e in matches)+'.'
        system, database = matches[0]
        tables = attached_tables(system, database, api)
        if not tables:return 'Aucune table active rattachée à la base '+system+' '+api['ename'](database)+' n’a été trouvée dans Apache Atlas.'
        tables.sort(key=lambda e: api['ename'](e).casefold())
        answer = 'La base '+system+' '+api['ename'](database)+' contient '+('la table ' if len(tables)==1 else 'les tables ')+', '.join(api['ename'](e) for e in tables)+'.'
        if len(tables)==1:
            description = ((tables[0].get('attributes') or {}).get('description') or '').strip()
            if description:answer += ' '+description
        return answer

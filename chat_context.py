"""Conversation state and request-local Atlas filtering (no shared user state)."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import re
import unicodedata

DATABASES = {'sqlite': 'transactions1.db', 'postgresql': 'projet_data_lineage'}
QUESTION = 'Souhaitez-vous rechercher dans SQLite, PostgreSQL ou dans les deux bases ?'
_request = ContextVar('atlas_chat_request', default=None)


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))


def normalize_environment_mentions(question):
    """Normalize engine aliases in prose, never inside an Atlas identifier or filename."""
    aliases = r'postgres\s+sql|postgresql|postgres|postgesql|postgre|pgsql|sqlite|transactions1(?:\.db)?'
    pattern = r'(?<![\w.@:/-])(?:' + aliases + r')(?![\w@:/-]|\.\w)'
    def canonical(match):
        value = match.group().casefold()
        if value.startswith('post') or value == 'pgsql':return 'PostgreSQL'
        return 'SQLite' if value in ('sqlite', 'transactions1') else value
    return re.sub(pattern, canonical, question.replace('\\_', '_'), flags=re.I)


def explicit_environments(question):
    text = normalize(normalize_environment_mentions(question))
    def mentioned(pattern):
        return bool(re.search(r'(?<![\w.@:/-])(?:'+pattern+r')(?![\w@:/-]|\.\w)', text))
    return {engine for engine, pattern in (
        ('postgresql', r'postgresql|projet_data_lineage'),
        ('sqlite', r'sqlite|transactions1\.db'),
    ) if mentioned(pattern)}


def reliable_table_context(engine, entity, state):
    """A remembered engine alone is not evidence for a newly named table."""
    attrs = entity.get('attributes') or {}
    return bool(entity.get('guid') and entity['guid'] == state.get('active_table_guid')
                and engine == (state.get('active_database') or state.get('active_chat_source'))
                and (not state.get('active_table_qualified_name') or
                     attrs.get('qualifiedName') == state['active_table_qualified_name']))


def database_inventory_request(question):
    from intent_routing import global_database_catalogue_request
    text = normalize(question)
    if global_location_request(question):return False
    return global_database_catalogue_request(question) or bool(re.search(r'\b(?:sources?|environnements?)\b', text)
                and re.search(r'\b(?:quels?|quelles?|liste\w*|disponibles?|existe\w*|inventaire)\b', text)
                and not re.search(r'\b(?:tables?|colonnes?|processus|lineage|relations?)\b', text))


def global_location_request(question):
    text = normalize(question)
    return bool(re.search(r'\bdans (?:quels?|quelles?)\s+(?:bases?|environnements?|systemes?)\b|'
                          r'\bou\s+se\s+trouve\b|'
                          r'\bexiste\w*(?:-\w+)*\b.*\b(?:sqlite|postgres(?:ql)?|deux|plusieurs)\b', text))


def resolve_database(question, state, source=None):
    question = normalize_environment_mentions(question)
    text = normalize(question)
    environments = explicit_environments(question)
    sqlite, postgres = 'sqlite' in environments, 'postgresql' in environments
    both = sqlite and postgres or global_location_request(question) or bool(re.search(
        r'\b(?:les )?deux (?:bases|environnements|systemes)\b|\ben general\b|'
        r'\b(?:toutes les bases|tous les environnements|plusieurs environnements)\b', text))
    active = state.get('active_database') or state.get('active_chat_source')
    scope = ('all' if both else 'sqlite' if sqlite else 'postgresql' if postgres
             else 'all' if database_inventory_request(question) else source or active)
    if scope in DATABASES:
        if scope == active and 'active_table' not in state:
            state['active_table'] = state.get('sqlite_chat_table') if scope == 'sqlite' else None
        if active != scope:
            state['active_table'] = None
            state['active_table_guid'] = None
            state['active_table_qualified_name'] = None
            state.pop('sqlite_chat_table', None)
        state['active_database'] = scope
        state['active_chat_source'] = scope  # Compatibility with existing handlers.
    state['database_scope'] = scope
    return scope


def scoped_cache(cache_decorator):
    """Never reuse or populate a shared cache with request-filtered metadata."""
    def decorate(function):
        cached = cache_decorator(function)
        @wraps(function)
        def call(*args, **kwargs):
            return function(*args, **kwargs) if _request.get() else cached(*args, **kwargs)
        call.clear = cached.clear
        return call
    return decorate


@contextmanager
def atlas_scope(database):
    token = _request.set({'database': database, 'entities': {}})
    try:
        yield
    finally:
        _request.reset(token)


def filtered_atlas_get(fetch, path, params=None):
    request = _request.get()
    if request is None or request['database'] is None:
        return fetch(path, params)
    scope = request['database']
    cache = request['entities']

    def entity(guid):
        if guid not in cache:
            cache[guid] = fetch('/api/atlas/v2/entity/guid/' + guid, None).get('entity', {})
        return cache[guid]

    def references(value):
        if isinstance(value, dict):
            if value.get('guid') and value.get('relationshipStatus') != 'DELETED' and value.get('entityStatus') != 'DELETED':
                yield value['guid']
            for key, child in value.items():
                if key != 'guid': yield from references(child)
        elif isinstance(value, list):
            for child in value: yield from references(child)

    def belongs(item, seen=None):
        if not item or item.get('status') == 'DELETED': return False
        seen = set() if seen is None else seen
        guid = item.get('guid')
        if guid in seen: return False
        seen = seen | {guid}
        kind = item.get('typeName', '').lower()
        system = 'sqlite' if kind.startswith('sqlite') else 'postgresql' if kind.startswith('postgresql') else None
        if system and system != scope: return False
        attrs = item.get('attributes') or {}
        relations = item.get('relationshipAttributes') or {}
        if 'database' in kind and system:
            return attrs.get('name') == DATABASES[scope]
        database = attrs.get('databaseName') or attrs.get('database')
        if isinstance(database, str): return system in (None, scope) and database == DATABASES[scope]
        parent_refs = list(references([relations.get(k) or attrs.get(k) for k in ('database', 'table', 'schema')]))
        if parent_refs: return any(belongs(entity(g), seen) for g in parent_refs)
        qualified = str(attrs.get('qualifiedName', ''))
        if system and DATABASES[scope] in re.split(r'[@/]', qualified): return True
        if guid and guid not in cache:
            return belongs(entity(guid), seen - {guid})
        if system: return False  # Unknown database membership is not evidence.
        endpoints = list(references([relations.get(k) or attrs.get(k) for k in
                                    ('inputs', 'outputs', 'inputToProcesses', 'outputFromProcesses')]))
        # Imports may omit dataset/process relationships; Atlas lineage is evidence too.
        if not endpoints and guid:
            graphs = request.setdefault('graphs', {})
            if guid not in graphs:
                graphs[guid] = fetch('/api/atlas/v2/lineage/' + guid, {'direction': 'BOTH', 'depth': 1})
            graph = graphs[guid]
            for edge in graph.get('relations', []):
                if edge.get('fromEntityId') == guid: endpoints.append(edge['toEntityId'])
                if edge.get('toEntityId') == guid: endpoints.append(edge['fromEntityId'])
        return any(belongs(entity(g), seen) for g in endpoints)

    def clean(value):
        if isinstance(value, list):
            return [clean(v) for v in value if not isinstance(v, dict) or not v.get('guid') or belongs(entity(v['guid']))]
        if isinstance(value, dict):
            if value.get('guid') and not belongs(entity(value['guid'])): return {}
            return {k: clean(v) for k, v in value.items()}
        return value

    # Filter before pagination reaches consumers; rejected rows must not hide later pages.
    if path.endswith('/search/basic'):
        params = dict(params or {})
        wanted = params.get('typeName', '').lower()
        if wanted.startswith(('sqlite', 'postgresql')) and not wanted.startswith(scope): return {'entities': []}
        limit = int(params.get('limit', 1000)); offset = int(params.get('offset', 0))
        accepted = []; raw_offset = 0
        while len(accepted) < offset + limit:
            payload = fetch(path, dict(params, offset=raw_offset, limit=1000))
            batch = payload.get('entities') or []
            accepted.extend(e for e in batch if belongs(e))
            if len(batch) < 1000: break
            raw_offset += len(batch)
        return {'entities': [clean(e) for e in accepted[offset:offset + limit]]}
    payload = fetch(path, params)
    for guid, item in (payload.get('referredEntities') or {}).items(): cache[guid] = item
    if 'entity' in payload:
        item = payload['entity']; cache[item['guid']] = item
        if not belongs(item): return {'entity': {'guid': item['guid'], 'status': 'DELETED'}}
        return dict(payload, entity=clean(item), referredEntities={
            g: clean(e) for g, e in (payload.get('referredEntities') or {}).items() if belongs(e)})
    if 'guidEntityMap' in payload:
        nodes = {g: e for g, e in payload['guidEntityMap'].items() if belongs(e)}
        return dict(payload, guidEntityMap={g: clean(e) for g, e in nodes.items()},
                    relations=[r for r in payload.get('relations', [])
                               if r.get('fromEntityId') in nodes and r.get('toEntityId') in nodes])
    return payload

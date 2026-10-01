"""Pure intent classification: ordering is explicit; no Atlas or model calls."""
import re
import unicodedata

ENTITY_VERBS = {
    'alimente', 'alimenter', 'provient', 'provenir', 'relie', 'relier',
    'transforme', 'transformer', 'produit', 'produire', 'genere', 'generer',
    'execute', 'executer',
}


INTENT_PRIORITY = (
    'impact_analysis', 'lineage', 'input_output', 'process_details',
    'process_list', 'transformation', 'column_lookup', 'column_list',
    'table_details', 'table_list', 'database_lookup', 'fallback_rag',
)


def normalize_question(question):
    text = unicodedata.normalize('NFKD', question.casefold())
    return ' '.join(re.sub(r'[^\w.@]+', ' ', ''.join(
        c for c in text if not unicodedata.combining(c))).split())


def complete_downstream_request(question):
    text=normalize_question(question)
    limit=bool(re.search(r'jusqu.*(?:destination\w* finale\w*|fin du lineage|fin du parcours)',text))
    return bool((limit and re.search(r'objets?|dependances?|impact\w*|concern\w*|aval|parcours',text)) or
                (re.search(r'\baval\b',text) and re.search(r'\btou(?:s|tes)\b.*(?:objets?|impact\w*|dependances?|concern\w*)',text)))


def column_meaning_request(question):
    """Extract a named column's meaning request, distinct from finding a column."""
    text = normalize_question(question)
    match = re.match(
        r'^(?:que (?:signifie|represente)|a quoi sert|quelle est la signification(?: metier)? de|'
        r'quel est le role de|quel est le (?:libelle|nom) metier de)\s+(?:la colonne\s+)?(.+)$',
        text,
    )
    if not match:return None
    name = re.split(r'\s+(?:dans|sur)\s+|\s+de la table\s+', match.group(1))[0].strip()
    name = re.split(r'\s+(?:et\s+)?(?:quelle est la source|(?:indique|cite|precise) (?:la|ta) source)\b', name)[0].strip()
    if re.match(r'(?:(?:la|le|les|une?|ce|cette)\s+)?(?:table|base|process\w*)\b', name):return None
    return name or None


def column_description_request(question):
    """Recognize a request for the recorded description of one column."""
    text = normalize_question(question)
    match = re.match(
        r'^quelle est la description de\s+(?:(?:la\s+)?colonne\s+)?(.+)$|'
        r'^(?:decris|decrire|que represente)\s+(?:la\s+)?colonne\s+(.+)$',
        text,
    )
    if not match:return None
    name = re.split(r'\s+(?:dans|sur)\s+|\s+de la (?:table|base)\s+', next(value for value in match.groups() if value))[0].strip()
    if re.match(r'(?:(?:la|le|les|une?)\s+)?(?:table|base)\b', name):return None
    return name or None


def primary_key_request(question):
    """Recognize table primary-key metadata before source selection."""
    text = normalize_question(question)
    return bool(re.search(r'\b(?:cles? primaires?|primary key|pk)\b', text)
                and not re.search(r'\b(?:lineage|impact|processus)\b', text))


def path_between_entities_request(question):
    """Recognize a directed lineage path request with two named endpoints."""
    text = normalize_question(question)
    return bool(re.search(
        r'\b(?:parcours|chemin|lineage)\s+(?:entre|de|depuis)\b.*\b(?:et|jusqu a|vers|a)\b|'
        r'\bcomment\s+.+\s+(?:arrive|est transforme)\s+jusqu a\b',
        text,
    ))


def process_role_request(question):
    text = normalize_question(question).replace('_', ' ')
    if re.search(r'\bimpacts?\b|\bsi\b|\b(?:entrees?|sorties?)\b',text):return None
    positional = bool(re.search(r'\b(?:avant|apres|precede|precedent|suit|succede)\b',text))
    process = bool(re.search(r'\b(?:processus|etape)\b',text))
    if positional and (process or re.search(r'\bcreation\b.*\btable\b',text)):
        return 'downstream' if re.search(r'\b(?:apres|suit|succede)\b',text) else 'upstream'
    if process and re.search(r'\bprepar\w*\b',text) and re.search(r'\bfichier\b|\bchargement\b',text):return 'upstream'
    if process and re.search(r'\S+\.(?:csv|xlsx?|json|parquet|txt)\b',text):
        if re.search(r'\bprodui\w*\b',text):return 'producer'
        if re.search(r'\butilis\w*\b|\bconsomm\w*\b',text):return 'consumer'
    return None


def database_tables_request(question):
    """Recognize database contents, never the inverse table-location question."""
    text = normalize_question(question)
    if re.search(r'\b(lineage|impact|amont|aval|processus|colonne|colonnes)\b|dans quelle base|ou se trouve', text):
        return None
    if not re.search(r'\btables?\b', text):return None
    if not re.search(r'\b(?:quelles?|quelles sont|donne|liste|tables)\b', text):return None
    if not re.search(r'\b(?:disponibles?|contient|contiennent|appartient|appartiennent|de|dans)\b', text):return None
    identifier = r'([\w]+(?:[.@:/-][\w]+)*)'
    # Preserve identifier spelling; normalization is used only to classify intent.
    raw = question.replace('`', '').replace('"', '').replace('«', '').replace('»', '')
    patterns = (r'\bbase(?:\s+de\s+donn[ée]es)?\s+(?:(?:SQLite|PostgreSQL|Postgres)\s+)?'+identifier,
                r'\bcontient\s+'+identifier,
                r'\bappartien(?:t|nent)\s+[àa]\s+'+identifier,
                r'\btables\s+(?:de|dans)\s+(?!la\b|une\b)'+identifier)
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            name = match.group(1)
            if name.casefold() in ('sqlite', 'postgres', 'postgresql', 'la', 'une'):continue
            engine = ('sqlite' if re.search(r'\bsqlite\b', text) else
                      'postgresql' if re.search(r'\bpostgres(?:ql)?\b', text) else
                      'sqlite' if name.casefold().endswith('.db') else None)
            return name, engine
    return None


def global_database_catalogue_request(question):
    """Recognize a global Atlas database inventory/count request."""
    text = normalize_question(question)
    if re.search(r'\b(?:tables?|colonnes?|processus|lineage|relations?|impact)\b', text):
        return False
    return bool(
        re.search(r'\bbases?(?: de donnees)?\b', text)
        and re.search(
            r'\b(?:combien|quels?|quelles?|liste\w*|disponibles?|existe\w*|'
            r'inventaire|present\w*|enregistr\w*)\b',
            text,
        )
    )


def table_producer_request(question):
    """Ask who produces a table, rather than describe a named process."""
    text=normalize_question(question)
    if re.search(r'\b(?:impact|colonne|fichier|entrees|sorties|aval)\b|\bprocess_\w+',text):return False
    if re.search(r'\S+\.(?:csv|xlsx?|json|parquet|txt)\b',text):return False
    return bool(re.search(r'^quels? processus (?:cree|creent|alimente|alimentent|produit|produisent)\b',text) or
                re.search(r'^par quels? processus .+\b(?:alimentee?s?|creee?s?|produite?s?)\b',text))


def interpret_lineage_question(question):
    """Parse natural roles before generic identifiers; never rewrite Atlas names."""
    from chat_context import normalize_environment_mentions, explicit_environments
    raw = normalize_environment_mentions(question).strip().rstrip(' .?!')
    text = normalize_question(raw)
    if re.search(r'\bimpact\w*\b|\bsi\b|\b(?:supprim\w*|modifi\w*)\b', text):
        return None
    engines = explicit_environments(raw)
    engine = next(iter(engines)) if len(engines) == 1 else None
    database = None
    scope = re.search(r'\s+(?:de|dans)\s+la\s+base(?:\s+de\s+donn[ée]es)?\s+(.+)$', raw, re.I)
    if scope:
        name = scope.group(1).strip(' `"«»')
        if name.casefold() not in ('sqlite', 'postgres', 'postgresql'):
            database = re.sub(r'^(?:postgres(?:ql)?|sqlite)\s+', '', name, flags=re.I)
        raw = raw[:scope.start()]
    identifier = r'[`"«]?([\w]+(?:[.@:/-][\w]+)*)[`"»]?'
    entity = r'(?:(?:la|le|les|une?|des)\s+)?(?:(?:table|fichier|objet)\s+)?' + identifier
    suffix = r'(?:\s*[?!.]?\s+(?:dans\s+)?(?:postgres(?:ql)?|sqlite|projet_data_lineage|transactions1\.db))?$'

    def result(operation, match=None, purpose=None):
        names = list(match.groups()) if match else []
        if any(normalize_question(n) in ENTITY_VERBS for n in names):
            return None
        return dict(intent='lineage' if operation in ('upstream', 'between') else 'process_details',
                    operation=operation, origin=names[0] if len(names) == 2 else None,
                    target=names[-1] if names else None, purpose=purpose,
                    engine=engine, database=database, conflicting_engines=len(engines) > 1)

    for pattern in (
        r'^de\s+quelles?\s+tables?\s+provien(?:t|nent)\s+' + entity + suffix,
        r'^quelles?\s+tables?\s+aliment(?:e|ent)\s+' + entity + suffix,
        r'\bcomment\s+(?:la\s+)?donn[ée]e\s+arrive\s+jusqu[’\']?[àa]\s+' + entity + suffix,
    ):
        match = re.search(pattern, raw, re.I)
        if match:
            return result('upstream', match)
    match = re.search(r'\blien\s+entre\s+' + entity + r'\s+et\s+' + entity + suffix, raw, re.I)
    if not match:
        match = re.search(r'\bcomment\s+' + entity + r'\s+est\s+reli[ée]e?\s+[àa]\s+' + entity + suffix, raw, re.I)
    if match:
        return result('between', match)
    match = re.search(r'^quels?\s+processus\s+(?:relie\s+' + entity + r'\s+[àa]\s+' + entity + suffix + r')', raw, re.I)
    if not match:
        match = re.search(r'^quels?\s+processus\s+transforme\s+' + entity + r'\s+en\s+' + entity + suffix, raw, re.I)
    if match:
        return result('process_between', match)
    match = re.search(r'^quels?\s+processus\s+permet(?:tent)?\s+d[’\'](?:ex[ée]cuter|r[ée]aliser|effectuer)\s+' + entity + suffix, raw, re.I)
    if match:
        return result('process_purpose', match, purpose='execution')
    match = re.search(r'^quels?\s+outils?\s+(?:sont|est)\s+utilis[ée]s?\s+dans\s+le\s+processus\s+(.+)$', raw, re.I)
    if match:
        return result('process_tools', purpose=match.group(1))
    return None


def process_purpose_terms(value):
    """Small linguistic normalization for metadata matching, not invented roles."""
    aliases = {'executer': 'execution', 'execute': 'execution', 'executes': 'execution',
               'preparer': 'preparation', 'prepare': 'preparation', 'preparees': 'preparation'}
    ignored = {'process', 'processus', 'de', 'du', 'des', 'd', 'le', 'la', 'les', 'l', 'un', 'une'}
    return {aliases.get(word, word.rstrip('s')) for word in normalize_question(value).replace('_', ' ').split()
            if word not in ignored}


def classify_intent(question):
    structured = interpret_lineage_question(question)
    if structured:return structured['intent']
    if table_producer_request(question):return 'lineage'
    if database_tables_request(question):return 'table_list'
    if path_between_entities_request(question):return 'lineage'
    if primary_key_request(question):return 'table_details'
    if column_description_request(question):return 'column_lookup'
    if global_database_catalogue_request(question):return 'database_lookup'
    text = normalize_question(question)
    def has(pattern):
        return bool(re.search(pattern, text))

    process = has(r'\bprocess(?:us)?\b|\bprocess_\w+')
    inventory = has(r'\b(?:quels|quelles|liste|lister|listez|enumere|enumerer)\b|disponibles|existants')
    relations = has(r'\b(?:referenc\w*|relations?|etrangeres?|reli\w*|depend\w*)\b')
    global_columns = has(r'\bchaque colonne\b|\btoutes les colonnes\b|\btypes? (?:de donnees )?(?:de|des) (?:les )?colonnes\b')
    process_inventory = has(r'^(?:liste|lister|listez|quels)\b.*\bprocessus\b') and not has(r'\b(?:produi\w*|utilis\w*|alimente\w*|depend\w*)\b')
    rules = {
        'impact_analysis': complete_downstream_request(question) or has(r'\bimpacts?\b|\baffect\w*|que se passe t il si|\bsi\b.*(?:supprim|modifi|chang)'),
        'lineage': (has(r'\b(?:lineage|amont|aval|parcours|chemin|cheminement)\b|\bgraphe\b') and not process_inventory) or has(r'\b(?:tables?|processus)\b.*\bprodui\w*\b'),
        'input_output': (process or has(r'\b(?:entrees?|sorties?|inputs?|outputs?)\b.*\bde\s+[\w.@]+')) and has(r'\b(?:entrees?|sorties?|inputs?|outputs?)\b') and not has(r'\b(?:outil|date|quand|transformation)\b'),
        'process_details': process and not has(r'\b(?:quels|liste|lister|listez|transformations?|produi\w*|utilis\w*)\b') and has(r'\bprocess_\w+|\b(?:sert|explique|decris|description|role|fonction|quel)\b'),
        'process_list': has(r'\b(?:processus|traitements)\b') and inventory and not has(r'\b(?:produi\w*|utilis\w*|alimente\w*|depend\w*)\b'),
        'transformation': has(r'\btransformations?\b'),
        'column_lookup': not relations and has(r'\bquelle\s+colonne\b|\bquelles?\s+colonnes?\s+(?:represente|contien|correspond)\w*|\b(?:type|signification)\s+(?:metier\s+)?de\b|\b(?:libelle|nom)\s+metier\s+de\b|\b(?:signifie|represente)\s+(?:la\s+colonne\s+)?\w+|\bcolonne\b.*\b(?:nullable|obligatoire)\b'),
        'column_list': not relations and (global_columns or has(r'\bcolonnes\b') and inventory),
        'table_details': not relations and has(r'\btable\s+\w+') and has(r'\b(?:contient|contenu|decris|description|presente|informations|details|metadonnees|role)\b|\ba quoi sert\b'),
        'table_list': has(r'\btables\b') and inventory and not has(r'\b(?:contiennent|referencent|depend\w*|reli\w*)\b'),
        'database_lookup': has(r'\b(?:quelle|quelles|liste|lister|listez)\b.*\bbases?\b') and not has(r'\b(?:tables?|colonnes?|processus)\b|\bdans quelle base\b'),
    }
    if global_columns:rules['column_lookup'] = False
    elif column_meaning_request(question):rules['column_lookup'] = True
    if process_role_request(question):
        rules['process_details'] = True
        rules['lineage'] = False
        rules['process_list'] = False
    return next((intent for intent in INTENT_PRIORITY if rules.get(intent)), 'fallback_rag')

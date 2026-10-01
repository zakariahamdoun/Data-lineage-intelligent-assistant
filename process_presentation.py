"""Grammatical integration of a process description, without inferring its role."""
import re


def process_role_suffix(description):
    text = (description or '').strip().rstrip('.')
    if not text or text.casefold() in {'non renseigné', 'non renseignée', 'n/a'}:
        return ''
    match = re.match(r'^Processus reliant\s+(.+)$', text, re.I | re.S)
    if match:
        return ', qui relie '+match.group(1)
    match = re.match(r"^Processus (?:de |d['’])(création|exécution)\b(.*)$", text, re.I | re.S)
    if match:
        action, rest = match.groups()
        return ', qui assure '+('la ' if action.casefold()=='création' else 'l’')+action.casefold()+rest
    match = re.match(r'Processus de (préparation|chargement|transformation|nettoyage|validation)\b(.*)',
                     text, re.I | re.S)
    if match:
        action, rest = match.groups()
        rest = re.sub(r'^\s+réalisé\b', '', rest, flags=re.I)
        article = 'le ' if action.casefold() in ('chargement', 'nettoyage') else 'la '
        return ', qui assure '+article+action.casefold()+rest
    text = re.sub(r'^(?:Ce|Le) processus\s+', '', text, flags=re.I)
    if re.match(r'^(prépare|charge|transforme|nettoie|valide|prend|utilise|produit|assure|permet|relie)\b', text, re.I):
        return ', qui '+text[0].lower()+text[1:]
    return ' : '+text


def process_flow_suffix(description, destination=None):
    """Combine recorded purpose with the verified output, without adding semantics."""
    role=process_role_suffix(description)
    if not destination:return role+'.' if role else '.'
    if role.startswith(', qui ') and not re.search(r'[.!?]\s+\S',role):
        return role+' et alimente '+destination+'.'
    flow=', qui alimente '+destination+'.'
    if role:
        text=(description or '').strip().rstrip('.')
        flow+=' Son rôle est décrit ainsi : '+text+'.'
    return flow

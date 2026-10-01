"""Evidence-only prose for Atlas table and column metadata."""
import re


def describe_columns(data, question, documentation, display_type):
    columns = data.get('columns') or []
    table = data.get('table') or data.get('name')
    if not columns:
        return f'Les colonnes de la table {table} ne sont pas renseignées dans Apache Atlas.'
    show_types = bool(re.search(r'\btypes?\s+(?:de\s+donn[ée]es|des?\s+colonnes?|de\s+la\s+colonne)\b|'
                                r'\bquell?e?s?\s+(?:(?:sont|est)\s+(?:les?|leurs?)\s+)?types?\b|'
                                r'\b(?:donne|affiche|précise|indique).*\b(?:les?|leurs?)\s+types?\b', question, re.I))
    names = [column['name'] for column in columns]
    joined = ', '.join(names[:-1])+' et '+names[-1] if len(names)>1 else names[0]
    paragraphs = [f'La table {table} contient les colonnes suivantes : '+joined+'.']
    description = (data.get('description') or '').strip()
    if description and not re.search(r'\bcolonnes?\b', question, re.I):paragraphs.append(description)
    sentences = []
    undocumented = []
    for column in columns:
        name = column['name']
        text = documentation(column, table)
        if text:
            text = text.strip().rstrip('.')
            # Only grammatical rewrites of the description, never guesses from names.
            if re.match(r'^(?:Cette|La) colonne\s+', text, re.I):
                text = re.sub(r'^(?:Cette|La) colonne\s+', '', text, flags=re.I)
                sentence = name+' '+text
            elif re.match(r'^(?:indique|contient|identifie|représente|permet|décrit|stocke|précise)\b', text, re.I):
                sentence = name+' '+text[0].lower()+text[1:]
            else:
                nominal = re.match(r'^(Date|Identifiant|Valeur monétaire|Numéro|Statut|Nature)\b', text, re.I)
                lead = {'date': 'indique la ', 'identifiant': 'correspond à l’',
                        'valeur monétaire': 'contient la ', 'numéro': 'indique le ',
                        'statut': 'précise le ', 'nature': 'précise la '}
                sentence = (name+' '+lead[nominal.group(1).casefold()]+text[0].lower()+text[1:]
                            if nominal else name+' : '+text)
            sentences.append(sentence)
        else:
            undocumented.append(name)
        if show_types:
            type_text = 'le type de '+name+' est '+display_type(column.get('type'), question)
            if text:sentences[-1] += ' ; '+type_text
            else:sentences.append(type_text[0].upper()+type_text[1:])
    # Short paragraphs retain Atlas order without inventing business categories.
    for start in range(0, len(sentences), 3):
        group = sentences[start:start+3]
        prefix = 'Enfin, ' if start and start+3 >= len(sentences) else ''
        paragraph = group[0]
        if len(group)>1:
            connector = ', tandis que ' if start == 0 else ', alors que '
            # Preserve complete multi-sentence descriptions without splicing their endings.
            if re.search(r'[.!?]\s+\S', group[0]):connector = ' ; également, '
            paragraph += connector+group[1]
        if len(group)>2:paragraph += ' ; '+group[2]
        paragraphs.append(prefix+paragraph+'.')
    if undocumented:
        for start in range(0, len(undocumented), 4):
            names = undocumented[start:start+4]
            joined = ', '.join(names[:-1])+' et '+names[-1] if len(names)>1 else names[0]
            paragraphs.append('Les colonnes '+joined+' sont présentes, mais leur description n’est pas renseignée.'
                              if len(names)>1 else 'La colonne '+joined+' est présente, mais sa description n’est pas renseignée.')
    return '\n\n'.join(paragraphs)

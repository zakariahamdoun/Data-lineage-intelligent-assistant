# Catalogue des métadonnées

Bloc complet de app.py :

```python
elif st.session_state.page=='Catalogue des métadonnées':
    from catalogue_ui import CATALOGUE_CSS, render_kpis, render_catalogue_table
    with st.container(key='catalogue_workspace'):
        st.markdown(CATALOGUE_CSS,unsafe_allow_html=True)
        st.markdown('<div class="catalogue-eyebrow">DATA INTELLIGENCE</div>',unsafe_allow_html=True)
        st.title('Catalogue des métadonnées')
        st.markdown('<p class="catalogue-subtitle">Consultez, explorez et gérez les métadonnées de vos sources de données.</p>',unsafe_allow_html=True)
        kpi_slot=st.container()
        with st.container(key='catalogue_controls'):
            st.subheader('Source de données')
            src=st.radio('Source de données',['PostgreSQL','Transactions / SQLite'],horizontal=True,key='catalogue_source')
            search_column,refresh_column=st.columns([3,1.5],vertical_alignment='bottom')
            query=search_column.text_input('Rechercher dans le catalogue',placeholder='Rechercher un objet, un type, une description...',key='catalogue_search',label_visibility='collapsed')
            refresh_clicked=refresh_column.button('Actualiser les métadonnées',key='refresh_metadata',type='primary',width='stretch')
        if refresh_clicked:
            try:
                with st.spinner('Actualisation des métadonnées et de l’index FAISS…'):
                    refreshed_documents,_=refresh_metadata()
                st.success(f'Métadonnées actualisées : {len(refreshed_documents)} entités indexées.')
            except Exception as error:
                logger.exception('Metadata refresh failed')
                st.error('L’actualisation des métadonnées n’a pas abouti. Vérifiez Atlas et le modèle de vectorisation.')
        try:
            lignes=[]
            if src=='PostgreSQL':
                c=pg_catalog()
                if c['database']:
                    d=c['database']; lignes.append(catalogue_row(d, 'Base de données'))
                for g,t in c['tables'].items():
                    lignes.append(catalogue_row(t, 'Table'))
                    for cg,tg in c['column_parent'].items():
                        if tg==g:
                            col=c['columns'][cg]
                            lignes.append(catalogue_row(col, "Colonne", f"{t['name']}.{col['name']}"))
                for process in c['processes'].values():
                    lignes.append(catalogue_row(process, 'Processus'))
            else:
                p=get_entity(SQLITE_TABLE_GUID); t=detail(SQLITE_TABLE_GUID,p)
                sqlite_entities={t['guid']:t}
                for g,e in t['referred'].items():
                    if e.get('typeName') in {'SQLiteDatabase','SQLiteColumn'}:
                        sqlite_entities[g]=detail(g)
    
                sqlite_database=exact('SQLiteDatabase','transactions1.db')
                if sqlite_database:
                    sqlite_entities[sqlite_database['guid']]=detail(sqlite_database['guid'])
    
                wanted_lineage_entities={
                    'transactions_sep.xlsx','transactions1.csv','transactions',
                    'preparation_transactions','chargement_sqlite'
                }
                lineage_data=get_lineage(SQLITE_TABLE_GUID,'BOTH',10)
                for g,e in (lineage_data.get('guidEntityMap') or {}).items():
                    if (ename(e).lower() in wanted_lineage_entities
                            or 'process' in e.get('typeName','').lower()):
                        sqlite_entities[g]=detail(g)
    
                for d in sqlite_entities.values():
                    atlas_type=d['typeName']
                    type_lower=atlas_type.lower()
                    if 'database' in type_lower:category='Base de données'
                    elif 'table' in type_lower:category='Table'
                    elif 'column' in type_lower:category='Colonne'
                    elif 'process' in type_lower:category='Processus'
                    else:category='Fichier / Dataset'
                    object_name=f"{t['name']}.{d['name']}" if category=='Colonne' else d['name']
                    lignes.append(catalogue_row(d, category, object_name))
            with kpi_slot:
                render_kpis(st,lignes)
                st.caption('Indicateurs de la source sélectionnée avant recherche. Les sources correspondent aux bases de données récupérées dans Atlas.')
            render_catalogue_table(st,lignes,query)
        except Exception as ex:
            st.error(f"Impossible de charger le catalogue des métadonnées : {ex}")
```

Module catalogue_ui.py (CSS et rendu) :

```python
"""Catalogue presentation, without Atlas calls or metadata mutations."""
from html import escape

CATALOGUE_CSS = """
<style>
.st-key-catalogue_workspace .catalogue-eyebrow{color:#af4c0d;font-size:11px;font-weight:750;letter-spacing:2px;margin:6px 0 10px}
.st-key-catalogue_workspace h1{font-size:36px;letter-spacing:-1px;color:#302820;padding-bottom:8px}
.st-key-catalogue_workspace .catalogue-subtitle{color:#737780;margin-bottom:26px}
.st-key-catalogue_workspace .catalogue-kpi{background:white;border:1px solid #e9e6e2;border-radius:14px;padding:20px;box-shadow:0 3px 14px #34271906;min-height:156px}
.st-key-catalogue_workspace .catalogue-icon{display:inline-flex;align-items:center;justify-content:center;background:#fff1e4;color:#b64e0a;border-radius:10px;width:34px;height:34px;font-size:20px;margin-bottom:10px}
.st-key-catalogue_workspace .catalogue-number{font-size:30px;font-weight:750;line-height:1.2;color:#302820}
.st-key-catalogue_workspace .catalogue-label{font-size:13px;color:#717780;margin-top:7px}
.st-key-catalogue_controls,.st-key-catalogue_table{background:white;border:1px solid #e9e6e2;border-radius:15px;padding:22px;box-shadow:0 3px 14px #34271905}
.st-key-catalogue_workspace h3{font-size:19px;color:#302820;padding-top:0}
.st-key-catalogue_workspace button[kind="primary"]{background:#c6530b;color:white;border-color:#c6530b;border-radius:9px;min-height:42px}
.st-key-catalogue_workspace button[kind="primary"]:hover{background:#a94307;border-color:#a94307}
.st-key-catalogue_workspace .catalogue-table-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}
.st-key-catalogue_workspace .catalogue-table-title{font-size:18px;font-weight:650;color:#302820;display:flex;gap:12px;align-items:center}
.st-key-catalogue_workspace .catalogue-count{font-size:12px;white-space:nowrap;background:#f5f4f2;border-radius:20px;padding:5px 10px;color:#717780}
.st-key-catalogue_workspace .catalogue-scroll{overflow:auto;max-height:610px;border:1px solid #eceef0;border-radius:10px}
.st-key-catalogue_workspace .catalogue-grid{border-collapse:separate;border-spacing:0;width:100%;font-size:13px;text-align:left}
.st-key-catalogue_workspace .catalogue-grid th{position:sticky;top:0;z-index:1;background:#f6f7f9;color:#66707c;font-weight:650;padding:14px 16px;border-bottom:1px solid #e5e7eb;white-space:nowrap}
.st-key-catalogue_workspace .catalogue-grid td{padding:16px;border-bottom:1px solid #edf0f3;vertical-align:top;min-width:150px;max-width:380px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;color:#424c59}
.st-key-catalogue_workspace .catalogue-grid td:nth-child(4),.st-key-catalogue_workspace .catalogue-grid td:nth-child(5){min-width:260px}
.st-key-catalogue_workspace .catalogue-grid tr:hover td{background:#fffaf5}
.st-key-catalogue_workspace .catalogue-badge{display:inline-block;padding:3px 9px;border-radius:6px;font-size:12px;background:#f0f2f5;color:#606976;white-space:nowrap}
.st-key-catalogue_workspace .catalogue-badge.database{background:#edf4fe;color:#36659b}
.st-key-catalogue_workspace .catalogue-badge.table{background:#edf8f1;color:#28724a}
.st-key-catalogue_workspace .catalogue-badge.atlas{background:#f2edfc;color:#7252a4}
@media(max-width:760px){.st-key-catalogue_workspace h1{font-size:28px}.st-key-catalogue_controls,.st-key-catalogue_table{padding:14px}.st-key-catalogue_workspace .catalogue-table-heading{align-items:flex-start;flex-direction:column}}
</style>
"""


def has_business_rule(value):
    return value is not None and str(value).strip().casefold() not in ('', 'non renseignée')


def catalogue_counts(rows):
    return [sum(row.get('Type') == category for row in rows)
            for category in ('Base de données', 'Table', 'Colonne')] + [
                sum(has_business_rule(row.get('Règle métier')) for row in rows)]


def render_kpis(st, rows):
    labels = ['Sources de données', 'Tables', 'Colonnes', 'Règles métier']
    icons = ['◉', '▦', '▥', '✓']
    for cell, count, label, icon in zip(st.columns(4), catalogue_counts(rows), labels, icons):
        cell.markdown(f'<div class="catalogue-kpi"><span class="catalogue-icon" aria-hidden="true">{icon}</span>'
                      f'<div class="catalogue-number">{count}</div><div class="catalogue-label">{label}</div></div>',
                      unsafe_allow_html=True)


def catalogue_table(rows):
    """Escape all Atlas content; preserve every existing metadata column."""
    if not rows:
        return ''
    columns = list(rows[0])
    header = ''.join(f'<th scope="col">{escape(label)}</th>' for label in columns)
    body = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            if column == 'Règle métier' and not has_business_rule(value):
                value = 'Non renseignée'
            content = escape(str(value if value is not None else 'Non renseignée'))
            if column in ('Type', 'Type Atlas'):
                style = 'atlas' if column == 'Type Atlas' else {'Base de données': 'database', 'Table': 'table'}.get(value, '')
                content = f'<span class="catalogue-badge {style}">{content}</span>'
            cells.append(f'<td>{content}</td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    return ('<div class="catalogue-scroll" tabindex="0" role="region" aria-label="Métadonnées Apache Atlas">'
            f'<table class="catalogue-grid"><thead><tr>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def render_catalogue_table(st, rows, query):
    needle = query.strip().casefold()
    visible = [row for row in rows if not needle or any(needle in str(value).casefold() for value in row.values())]
    with st.container(key='catalogue_table'):
        st.markdown('<div class="catalogue-table-heading"><div class="catalogue-table-title">'
                    '<span class="catalogue-icon" aria-hidden="true">▤</span>Métadonnées enregistrées dans Apache Atlas</div>'
                    f'<span class="catalogue-count">{len(visible)} éléments</span></div>', unsafe_allow_html=True)
        if visible:
            st.markdown(catalogue_table(visible), unsafe_allow_html=True)
        else:
            st.info('Aucun objet ne correspond à votre recherche.' if rows else 'Aucune métadonnée disponible dans Apache Atlas.')
        st.caption(f'Affichage de {len(visible)} éléments sur {len(rows)} · Catalogue de la source sélectionnée')

```

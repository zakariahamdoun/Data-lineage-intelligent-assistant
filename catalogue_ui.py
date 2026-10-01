"""Business-facing catalogue presentation. This module never calls Atlas."""
from html import escape
import streamlit as st

MISSING='Non renseigné'
TABLE_COLORS={'clients':('#EAF3FF','#2867A8'),'agences':('#EAF7EF','#26734D'),'comptes':('#FFF2E3','#AA5A12'),'transactions':('#FDEDEE','#A7444C'),'virements':('#F3ECFF','#7044A0')}
FALLBACK_TABLE_COLORS=[('#EDF5FB','#356B91'),('#F0F6EC','#527A45'),('#FFF4E8','#9B642B'),('#F9EFF4','#95506F'),('#F0F0FA','#62629A')]
CATEGORY_CARD_CSS="""<style>
.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button{position:relative;width:100%;min-height:84px;background:#fff;border:1px solid #e7ddd5;border-radius:12px;color:#302820;justify-content:flex-start;align-items:flex-start;padding:13px 14px;font-weight:700}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button:hover{border-color:#c6530b;background:#fffaf5;color:#302820}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button svg{color:#c6530b;margin-top:1px}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button[kind="primary"],.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button[data-testid="stBaseButton-primary"]{border:2px solid #c6530b;background:#fff3e7;color:#302820}.st-key-catalogue_workspace .st-key-metadata_category_card_technical .stButton>button:after{content:"Informations sur la structure des données : tables, colonnes, types et clés."}.st-key-catalogue_workspace .st-key-metadata_category_card_business .stButton>button:after{content:"Informations qui expliquent le sens des données et leur utilisation métier."}.st-key-catalogue_workspace .st-key-metadata_category_card_lineage .stButton>button:after{content:"Informations qui montrent d’où viennent les données, comment elles sont transformées et où elles vont."}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button:after{position:absolute;left:46px;right:12px;bottom:11px;color:#737780;font-size:11px;font-weight:400;line-height:1.25;text-align:left;white-space:normal}
</style>"""

CATALOGUE_CSS="""<style>
.st-key-catalogue_workspace .catalogue-eyebrow{color:#af4c0d;font-size:11px;font-weight:750;letter-spacing:2px;margin:6px 0 10px}.st-key-catalogue_workspace h1{font-size:36px;letter-spacing:-1px;color:#302820;padding-bottom:8px}.st-key-catalogue_workspace .catalogue-subtitle{color:#737780;margin-bottom:26px}.st-key-catalogue_workspace .catalogue-kpi,.st-key-catalogue_controls{background:#fff;border:1px solid #e9e6e2;border-radius:15px;padding:20px;box-shadow:0 3px 14px #34271908}.st-key-catalogue_workspace .catalogue-kpi{min-height:132px}.st-key-catalogue_workspace .catalogue-icon{display:inline-flex;align-items:center;justify-content:center;background:#fff1e4;color:#b64e0a;border-radius:10px;width:34px;height:34px;font-size:20px;margin-bottom:10px}.st-key-catalogue_workspace .catalogue-number{font-size:30px;font-weight:750;line-height:1.2;color:#302820}.st-key-catalogue_workspace .catalogue-label{font-size:13px;color:#717780;margin-top:7px}.st-key-catalogue_workspace h3{font-size:19px;color:#302820;padding-top:0}.st-key-catalogue_workspace button[kind="primary"]{background:#c6530b;color:#fff;border-color:#c6530b;border-radius:9px;min-height:42px}.st-key-catalogue_workspace button[kind="primary"]:hover{background:#a94307;border-color:#a94307}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button{width:100%;min-height:62px;background:#fff;border:1px solid #e7ddd5;border-radius:12px;color:#302820;justify-content:flex-start;padding:12px 14px;font-weight:700}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button:hover{border-color:#c6530b;background:#fffaf5;color:#302820}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"] .stButton>button svg{color:#c6530b}.st-key-catalogue_workspace [class*="st-key-metadata_category_card_"][class*="_active"] .stButton>button{border:2px solid #c6530b;background:#fff3e7}.st-key-catalogue_workspace .catalogue-scroll{overflow:auto;max-height:610px;border:1px solid #eceef0;border-radius:10px}.st-key-catalogue_workspace .catalogue-grid{border-collapse:separate;border-spacing:0;width:100%;font-size:13px;text-align:left}.st-key-catalogue_workspace .catalogue-grid th{position:sticky;top:0;z-index:1;background:#f6f7f9;color:#66707c;font-weight:650;padding:12px 14px;border-bottom:1px solid #e5e7eb;white-space:nowrap}.st-key-catalogue_workspace .catalogue-grid td{padding:13px 14px;border-bottom:1px solid #edf0f3;vertical-align:top;min-width:105px;max-width:340px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.5;color:#424c59}.st-key-catalogue_workspace .catalogue-grid tr:hover td{background:#fffaf5}.st-key-catalogue_workspace .yes{color:#28724a;font-weight:700}.st-key-catalogue_workspace .no{color:#717780}.st-key-catalogue_workspace .table-badge,.st-key-catalogue_workspace .lineage-type-badge{display:inline-block;padding:3px 9px;border-radius:999px;font-weight:700;font-size:12px}.st-key-catalogue_workspace .lineage-type-table{background:#E8F7F8;color:#12636C}.st-key-catalogue_workspace .lineage-type-process{background:#FFF0E2;color:#A85516}.st-key-catalogue_workspace .lineage-type-other{background:#F3F0EC;color:#62574E}@media(max-width:760px){.st-key-catalogue_workspace h1{font-size:28px}.st-key-catalogue_controls{padding:14px}}</style>"""

def simplify_data_type(data_type):
    """Translate only the technical type stored by Atlas into a business label."""
    original=str(data_type or '').strip();normalized=original.casefold()
    if normalized in {'integer','int','int2','int4','int8','int32','int64','bigint','smallint','serial','bigserial'}:return 'Nombre entier'
    if any(token in normalized for token in ('numeric','decimal','real','double precision','double','float')):return 'Nombre décimal'
    if normalized in {'object','string'} or any(token in normalized for token in ('varchar','character varying','character','text','char')):return 'Texte'
    if any(token in normalized for token in ('timestamp','datetime','datetime64')):return 'Date / Heure'
    if normalized=='date':return 'Date'
    if normalized in {'boolean','bool'}:return 'Oui / Non'
    return original or MISSING

CLASSIFICATION_LABELS={
    'DONNEE_BANCAIRE':'Donnée Bancaire',
    'DONNEE_PERSONNELLE':'Donnée Personnelle',
    'DONNEE_FINANCIERE':'Donnée Financière',
    'DONNEE_SENSIBLE':'Donnée Sensible',
    'DONNEE_TECHNIQUE':'Donnée Technique',
}

def classification_label(value):
    """Render Atlas classification names as readable French labels."""
    values=value if isinstance(value,(list,tuple,set)) else str(value or '').split(',')
    labels=[]
    for item in values:
        key=str(item).strip()
        if not key:continue
        labels.append(CLASSIFICATION_LABELS.get(key,key.replace('_',' ').capitalize()))
    return ' · '.join(labels) if labels else 'Non classée'

def _is_empty(value,empty_values):
    if value in empty_values:return True
    try:return value!=value
    except Exception:return False

def is_effectively_empty_or_false(series):
    """Return True when a displayed key column contains no affirmative value."""
    values=series.tolist() if hasattr(series,'tolist') else list(series)
    def without_information(value):
        if value is None or value is False:return True
        if isinstance(value,str) and value.strip().casefold() in {'','-','non'}:return True
        try:return value!=value
        except Exception:return False
    return all(without_information(value) for value in values)

def remove_empty_columns(dataframe):
    """Drop columns containing only None, blanks, NaN, '-', or non-documented values."""
    empty_values={None,'','-',MISSING}
    if hasattr(dataframe,'columns') and hasattr(dataframe,'to_dict'):
        records=dataframe.to_dict('records');keep=[column for column in dataframe.columns if any(not _is_empty(row.get(column),empty_values) for row in records)]
        return dataframe[keep]
    rows=list(dataframe or [])
    if not rows:return rows
    headers=list(dict.fromkeys(key for row in rows for key in row));keep=[header for header in headers if any(not _is_empty(row.get(header),empty_values) for row in rows)]
    return [{key:row.get(key) for key in keep} for row in rows]

def _value(value):return value if not _is_empty(value,{None,'','-'}) else MISSING
def _table_style(name,names):
    if name in TABLE_COLORS:return TABLE_COLORS[name]
    return FALLBACK_TABLE_COLORS[sorted(names,key=str.casefold).index(name)%len(FALLBACK_TABLE_COLORS)]
def _table(rows,table_names=(),bold_business_label=False):
    if not rows:return ''
    headers=list(rows[0]);head=''.join(f'<th scope="col">{escape(header)}</th>' for header in headers);body=[]
    for row in rows:
        cells=[]
        for header in headers:
            value=str(_value(row.get(header)));style='yes' if value=='Oui' else 'no' if value=='Non' else ''
            if header=='Table' and value!=MISSING:
                background,foreground=_table_style(value,table_names);rendered=f'<span class="table-badge" style="background:{background};color:{foreground}">{escape(value)}</span>'
            elif header=='Type d’objet':
                kind='table' if value=='Table' else 'process' if value=='Processus' else 'other'
                rendered=f'<span class="lineage-type-badge lineage-type-{kind}">{escape(value)}</span>'
            elif header=='Libellé métier' and bold_business_label and value not in {MISSING,'Non renseigné','Non renseignée'}:
                rendered=f'<strong>{escape(value)}</strong>'
            else:rendered=escape(value)
            cells.append(f'<td class="{style}">{rendered}</td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    return f'<div class="catalogue-scroll"><table class="catalogue-grid"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

def render_kpis(st,metadata):
    counts=[1 if metadata.get('database') else 0,len(metadata['tables']),len(metadata['columns']),len(metadata['relations'])]
    for cell,count,label,icon in zip(st.columns(4),counts,['Sources de données','Tables','Colonnes','Relations'],['◉','▦','▥','↔']):cell.markdown(f'<div class="catalogue-kpi"><span class="catalogue-icon">{icon}</span><div class="catalogue-number">{count}</div><div class="catalogue-label">{label}</div></div>',unsafe_allow_html=True)
def select_metadata_category(category):
    st.session_state['metadata_category']=category
def render_category_picker(st):
    categories=[('technical',':material/settings:','Métadonnées techniques'),('business',':material/business_center:','Métadonnées métier'),('lineage',':material/sync_alt:','Métadonnées de traçabilité')]
    st.subheader('Choisissez une catégorie de métadonnées')
    for cell,(key,icon,title) in zip(st.columns(3),categories):
        with cell:
            with st.container(key=f'metadata_category_card_{key}'):
                st.button(title,icon=icon,key=f'metadata_category_{key}',width='stretch',
                          type='primary' if st.session_state['metadata_category']==key else 'secondary',
                          on_click=select_metadata_category,args=(key,))

def render_technical(st,metadata):
    st.subheader('Métadonnées techniques')
    object_type=st.radio('Type d’objet',['tables','columns'],format_func=lambda value:{'tables':'Tables','columns':'Colonnes'}[value],horizontal=True,key='technical_object_type')
    table_names=[table['name'] for table in metadata['tables']]
    if object_type=='tables':
        st.subheader('Métadonnées des tables')
        query=st.text_input('Rechercher une table',key='technical_table_search').casefold()
        rows=[]
        for table in metadata['tables']:
            searchable=' '.join(str(table.get(key,'')) for key in ('name','description','processes','lineage_flow','destinations')).casefold()
            if query and query not in searchable:continue
            rows.append({
                'Table':table['name'],
                'Base source':table.get('base_source','Non renseignée'),
                'Description':table.get('description'),
                'Classification':classification_label(table.get('classification')),
                'Processus associé':table.get('processes','Non renseigné'),
                'Flux de lineage':table.get('lineage_flow','Non renseigné'),
                'Destination':table.get('destinations','Non renseignée'),
            })
        if rows:st.markdown(_table(rows,table_names),unsafe_allow_html=True)
        else:st.info('Aucune table ne correspond à la recherche.')
        return
    st.subheader('Métadonnées des colonnes')
    filters=st.columns(4);types=sorted({simplify_data_type(column['type']) for column in metadata['columns'] if column['type']!=MISSING})
    table_filter=filters[0].selectbox('Filtrer par table',['Toutes les tables']+table_names,key='metadata_table_filter')
    type_filter=filters[1].selectbox('Filtrer par type',['Tous les types']+types,key='metadata_type_filter')
    classification_options=['Toutes les classifications','Donnée Personnelle','Donnée Bancaire','Donnée Financière','Donnée Sensible','Donnée Technique','Non classée']
    classification_filter=filters[2].selectbox('Filtrer par classification',classification_options,key='metadata_classification_filter')
    query=filters[3].text_input('Rechercher une colonne',key='metadata_column_search').casefold()
    rows=[]
    for column in metadata['columns']:
        simplified=simplify_data_type(column['type'])
        classification=classification_label(column.get('classification'))
        if (table_filter!='Toutes les tables' and column['table']!=table_filter) or (type_filter!='Tous les types' and simplified!=type_filter) or (classification_filter!='Toutes les classifications' and classification_filter not in classification) or (query and query not in column['name'].casefold()):continue
        rows.append({'Table':column['table'],'Base source':column.get('base_source','Non renseignée'),
                     'Colonne':column['name'],'Identifiant technique':column.get('identifiant_technique','Non renseigné'),
                     'Type':simplified,'Description':column['description'],'Classification':classification,
                     'Clé primaire':column['pk'],'Clé étrangère':column['fk']})
    if rows:st.markdown(_table(rows,table_names),unsafe_allow_html=True)
    else:st.info('Aucune colonne ne correspond aux filtres.')
def render_business(st,metadata):
    st.subheader('Métadonnées métier')
    object_type=st.radio('Type d’objet',['columns','tables'],format_func=lambda value:{'columns':'Colonnes','tables':'Tables'}[value],horizontal=True,key='business_object_type');query=st.text_input('Rechercher par nom',key='business_name_search').casefold();table_names=[table['name'] for table in metadata['tables']]
    if object_type=='columns':
        table_filter=st.selectbox('Filtrer par table',['Toutes les tables']+table_names,key='business_table_filter')
        rows=[{'Table':column['table'],'Colonne':column['name'],'Règle métier':column.get('regle_metier','Non renseignée'),'Libellé métier':column['business_label'],'Description métier':column['description']} for column in metadata['columns'] if (table_filter=='Toutes les tables' or column['table']==table_filter) and (not query or query in column['name'].casefold())]
    else:rows=[{'Table':table['name'],'Libellé métier':table['business_label'],'Description métier':table['description'],'Règle métier':table['business_rule']} for table in metadata['tables'] if not query or query in table['name'].casefold()]
    rows=remove_empty_columns(rows)
    if rows:st.markdown(_table(rows,table_names,bold_business_label=object_type=='columns'),unsafe_allow_html=True)
    else:st.info('Aucune métadonnée métier ne correspond aux filtres.')
def render_lineage(st,metadata):
    st.subheader('Parcours des données')
    rows=[{'Objet du projet':row['object'],'Type d’objet':row['object_type'],
           'Description':row['description'],'Entrées':row['inputs'],'Sorties':row['outputs']}
          for row in metadata.get('lineage_objects',[])]
    rows=remove_empty_columns(rows)
    if rows:st.markdown(_table(rows),unsafe_allow_html=True)
    else:st.info('Aucun objet de traçabilité n’est renseigné dans Apache Atlas pour cette source.')

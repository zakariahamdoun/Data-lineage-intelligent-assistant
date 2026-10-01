# Analyse d’impact

Section complete de app.py :

```python
elif st.session_state.page=='Analyse d’impact':
    from impact_ui import IMPACT_CSS, render_impact_results, sqlite_result_groups
    with st.container(key='impact_workspace'):
        st.markdown(IMPACT_CSS,unsafe_allow_html=True)
        st.markdown('<div class="impact-eyebrow">DATA INTELLIGENCE</div>',unsafe_allow_html=True)
        st.title('Analyse d’impact')
        st.markdown('<p class="impact-copy">Identifiez rapidement les objets et processus impactés par la modification d’une donnée de votre système.</p>',unsafe_allow_html=True)
        try:
            with st.container(key='impact_parameters'):
                st.markdown('<div class="impact-heading"><span class="impact-icon" aria-hidden="true">⇄</span>Paramètres d’analyse</div>',unsafe_allow_html=True)
                st.markdown('<p class="impact-copy">Sélectionnez la source de données, le type d’objet et l’entité à modifier pour analyser son impact sur votre patrimoine de données.</p>',unsafe_allow_html=True)
                source_col,type_col,entity_col,action_col=st.columns([1.5,1,1.5,1.2],vertical_alignment='bottom')
                src=source_col.radio('Source de données',['PostgreSQL','Transactions / SQLite'],horizontal=True,key='is')
                if src=='PostgreSQL':
                    c=pg_catalog();kind=type_col.selectbox('Type d’objet',['Table','Colonne','Base','Process']);op={}
                    if kind=='Table':op={d['name']:g for g,d in c['tables'].items()}
                    elif kind=='Colonne':
                        for g,d in c['columns'].items():op[f"{c['tables'][c['column_parent'][g]]['name']}.{d['name']}"]=g
                    elif kind=='Base' and c['database']:op={c['database']['name']:c['database']['guid']}
                    elif kind=='Process':op={d['name']:g for g,d in c['processes'].items()}
                    run_analysis=False
                    if not op:st.warning('Aucune entité disponible.')
                    else:
                        lab=entity_col.selectbox('Entité à modifier',sorted(op))
                        run_analysis=action_col.button('Analyser l’impact',type='primary',width='stretch')
                else:
                    n,e=sqlite_lineage();op={f"{x['label']} · {x['type']}":g for g,x in n.items()}
                    lab=entity_col.selectbox('Entité à modifier',sorted(op))
                    run_analysis=action_col.button('Analyser l’impact',type='primary',width='stretch',key='sib')
            if run_analysis:
                if src=='PostgreSQL':
                    r=impact_pg(op[lab],kind)
                    render_impact_results(st,r)
                else:
                    dn,_=lineage_graph(get_lineage(op[lab],'OUTPUT',10))
                    items=[x for g,x in dn.items() if g!=op[lab]]
                    render_impact_results(st,sqlite_result_groups(items))
        except Exception as ex:st.error(f"Erreur pendant l’analyse d’impact : {ex}")

```

CSS et presentation :

```python
"""Presentation of existing impact results. No Atlas calls or impact calculation."""
from html import escape

IMPACT_CSS = """
<style>
.st-key-impact_workspace .impact-eyebrow{color:#af4c0d;font-size:11px;font-weight:750;letter-spacing:2px;margin:6px 0 10px}
.st-key-impact_workspace h1{font-size:36px;letter-spacing:-1px;color:#302820;padding-bottom:8px}
.st-key-impact_workspace .impact-copy{color:#737780;line-height:1.7;margin-bottom:22px;font-size:14px}
.st-key-impact_parameters,.st-key-impact_details{background:white;border:1px solid #e9e6e2;border-radius:15px;padding:24px;box-shadow:0 3px 14px #34271906}
.st-key-impact_workspace h3{font-size:20px;color:#302820;padding-top:0}
.st-key-impact_workspace .impact-heading{display:flex;gap:12px;align-items:center;font-size:20px;font-weight:650;color:#302820;margin-bottom:10px}
.st-key-impact_workspace .impact-icon{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:10px;background:#fff1e4;color:#b64e0a;font-size:21px;flex-shrink:0}
.st-key-impact_workspace button[kind="primary"]{background:#c6530b;color:white;border-color:#c6530b;border-radius:9px;min-height:46px}
.st-key-impact_workspace button[kind="primary"]:hover{background:#a94307;border-color:#a94307}
.st-key-impact_parameters [data-baseweb="select"]>div{background:#f7f8fa;border-color:#e1e5e9;border-radius:9px;min-height:46px}
.st-key-impact_workspace .impact-kpi{background:white;border:1px solid #e9e6e2;border-radius:14px;padding:20px;box-shadow:0 3px 14px #34271906}
.st-key-impact_workspace .impact-number{font-size:32px;font-weight:750;color:#302820;margin-top:10px;line-height:1.2}
.st-key-impact_workspace .impact-label{color:#717780;font-size:13px;margin-top:7px}
.st-key-impact_workspace .impact-category{font-size:14px;font-weight:650;color:#414650;margin-bottom:14px}
.st-key-impact_workspace .impact-item{display:flex;gap:10px;align-items:baseline;background:#f7f8fa;border:1px solid #eff0f2;border-radius:9px;padding:11px 13px;margin-bottom:9px;font-size:13px;color:#414650;overflow-wrap:anywhere}
.st-key-impact_workspace .impact-dot{width:6px;height:6px;border-radius:50%;background:#cb5d16;flex-shrink:0}
@media(max-width:900px){
 .st-key-impact_workspace [data-testid="stHorizontalBlock"]{flex-direction:column;gap:16px}
 .st-key-impact_workspace [data-testid="stColumn"]{width:100%!important;flex:1 1 auto!important;min-width:0!important}
 .st-key-impact_parameters,.st-key-impact_details{padding:16px}
 .st-key-impact_workspace h1{font-size:28px}
}
</style>
"""


def sqlite_result_groups(items):
    """Group every returned node for display; keep unclassified nodes visible."""
    groups = {'tables': [], 'columns': [], 'processes': [], 'others': []}
    for item in items:
        kind = item.get('type', '').casefold()
        key = ('tables' if kind.endswith('table') else 'columns' if kind.endswith('column')
               else 'processes' if 'process' in kind else 'others')
        groups[key].append(item)
    return groups


def impact_label(item, category):
    name = item.get('name') or item.get('label') or item.get('guid') or item.get('id') or 'Objet sans nom'
    if category == 'columns' and item.get('table'):
        return f'{item["table"]}.{name}'
    return str(name)


def render_impact_results(st, result):
    categories = [('tables', 'Tables impactées', 'Aucune table impactée.', '▦'),
                  ('columns', 'Colonnes impactées', 'Aucune colonne impactée.', '▥'),
                  ('processes', 'Processus concernés', 'Aucun processus concerné.', '⇄')]
    for cell, (key, label, empty, icon) in zip(st.columns(3), categories):
        cell.markdown(f'<div class="impact-kpi"><span class="impact-icon" aria-hidden="true">{icon}</span>'
                      f'<div class="impact-number">{len(result[key])}</div><div class="impact-label">{label}</div></div>',
                      unsafe_allow_html=True)
    with st.container(key='impact_details'):
        st.subheader('Détail des impacts')
        st.markdown('<p class="impact-copy">Liste des objets et processus impactés par la modification de l’entité sélectionnée.</p>',unsafe_allow_html=True)
        for cell, (key, label, empty, icon) in zip(st.columns(3), categories):
            with cell:
                st.markdown(f'<div class="impact-category">{label} ({len(result[key])})</div>',unsafe_allow_html=True)
                if not result[key]:st.caption(empty)
                for item in sorted(result[key], key=lambda row: impact_label(row,key)):
                    render_impact_item(st,impact_label(item,key))
        if result.get('others'):
            st.markdown(f'<div class="impact-category">Autres objets impactés ({len(result["others"])})</div>',unsafe_allow_html=True)
            for item in result['others']:render_impact_item(st,impact_label(item,'others'))


def render_impact_item(st, label):
    st.markdown(f'<div class="impact-item"><span class="impact-dot" aria-hidden="true"></span><span>{escape(label)}</span></div>',unsafe_allow_html=True)

```

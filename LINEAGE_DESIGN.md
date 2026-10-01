# Visualisation du Data Lineage

Bloc complet dans app.py :

```python
elif st.session_state.page=='Visualisation du Data Lineage':
    from lineage_ui import LINEAGE_CSS, SELECTION_HEADING, PREVIEW_HEADING
    with st.container(key='lineage_workspace'):
        st.markdown(LINEAGE_CSS,unsafe_allow_html=True)
        st.markdown('<div class="lineage-eyebrow">DATA INTELLIGENCE</div>',unsafe_allow_html=True)
        st.title('Visualisation du Data Lineage')
        st.markdown('<p class="lineage-subtitle">Explorez et consultez le parcours des données directement dans Apache Atlas.</p>',unsafe_allow_html=True)
        with st.container(key='lineage_selection'):
            st.markdown(SELECTION_HEADING,unsafe_allow_html=True)
            base_column,table_column=st.columns(2,gap='large')
            lineage_base=base_column.selectbox(
                "Base de données",
                ["projet_data_lineage — PostgreSQL", "transactions1.db — SQLite"],
                key="lineage_base"
            )
        with st.container(key='lineage_preview'):
            st.markdown(PREVIEW_HEADING,unsafe_allow_html=True)
            try:
                guid=None
        
                if lineage_base.endswith("PostgreSQL"):
                    selected_entity=table_column.selectbox(
                        "Table",
                        ["clients", "agences", "comptes", "transactions", "virements"],
                        key="lineage_postgresql_entity"
                    )
                    candidates=[]
                    for entity in search_type("PostgreSQLTable", selected_entity):
                        if ename(entity)!=selected_entity:
                            continue
                        entity_detail=detail(entity["guid"])
                        qualified_name=entity_detail["qualifiedName"].lower()
                        related_database=any(
                            referred.get("typeName")=="PostgreSQLDatabase"
                            and ename(referred)==POSTGRES_DB_NAME
                            for referred in entity_detail["referred"].values()
                        )
                        if POSTGRES_DB_NAME.lower() in qualified_name or related_database:
                            candidates.append(entity_detail)
                else:
                    selected_entity=table_column.selectbox(
                        "Choisir une entité du flux",
                        ["transactions_sep.xlsx", "transactions1.csv", "transactions"],
                        key="lineage_sqlite_entity"
                    )
                    lineage_data=get_lineage(SQLITE_TABLE_GUID,"BOTH",10)
                    candidates=[]
                    for entity in (lineage_data.get("guidEntityMap") or {}).values():
                        if ename(entity)!=selected_entity:
                            continue
                        entity_detail=detail(entity["guid"])
                        if selected_entity!="transactions" or entity_detail["typeName"]=="SQLiteTable":
                            candidates.append(entity_detail)
        
                if len(candidates)==1:
                    guid=candidates[0]["guid"]
                elif len(candidates)>1:
                    st.error(
                        "Plusieurs entités correspondent à cette sélection dans Apache Atlas. "
                        "Le type Atlas, le qualifiedName et la base ne permettent pas de les départager."
                    )
                else:
                    st.warning("Cette entité n'a pas été trouvée dans Apache Atlas.")
        
                if guid:
                    atlas_url=(
                        f"{ATLAS_IFRAME_URL.rstrip('/')}/index.html#!/detailPage/"
                        f"{guid}?tabActive=lineage"
                    )
                    st.iframe(atlas_url,height=760)
            except requests.RequestException:
                st.error("Apache Atlas n'est pas disponible. Vérifiez que le service est démarré et accessible.")
```

CSS et en-tetes dans lineage_ui.py :

```python
"""Styles scoped to the Atlas lineage visualization page."""

LINEAGE_CSS = """
<style>
.st-key-lineage_workspace .lineage-eyebrow{color:#af4c0d;font-size:11px;font-weight:750;letter-spacing:2px;margin:6px 0 10px}
.st-key-lineage_workspace h1{font-size:36px;letter-spacing:-1px;color:#302820;padding-bottom:8px}
.st-key-lineage_workspace .lineage-subtitle{color:#737780;margin-bottom:24px;line-height:1.7}
.st-key-lineage_selection,.st-key-lineage_preview{background:white;border:1px solid #e9e6e2;border-radius:15px;padding:24px;box-shadow:0 3px 14px #34271906}
.st-key-lineage_workspace .lineage-card-heading{display:flex;gap:13px;align-items:center;margin-bottom:8px}
.st-key-lineage_workspace .lineage-card-heading h2{font-size:20px;font-weight:650;color:#302820;margin:0;padding:0;letter-spacing:-.3px}
.st-key-lineage_workspace .lineage-icon{display:inline-flex;align-items:center;justify-content:center;background:#fff1e4;color:#b64e0a;border-radius:10px;width:38px;height:38px;flex-shrink:0}
.st-key-lineage_workspace .lineage-icon svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.st-key-lineage_workspace .lineage-card-copy{font-size:14px;color:#737780;line-height:1.7;margin:0 0 18px}
.st-key-lineage_selection [data-baseweb="select"]>div{background:#f7f8fa;border-color:#e1e5e9;border-radius:9px;min-height:46px}
.st-key-lineage_selection [data-baseweb="select"]:focus-within{outline:2px solid #edb27f;outline-offset:2px;border-radius:9px}
.st-key-lineage_preview iframe{border:1px solid #e5e7eb;border-radius:11px;background:white;width:100%;box-sizing:border-box}
@media(max-width:760px){
 .st-key-lineage_workspace h1{font-size:28px}
 .st-key-lineage_selection,.st-key-lineage_preview{padding:16px}
 .st-key-lineage_selection [data-testid="stHorizontalBlock"]{flex-direction:column;gap:16px}
 .st-key-lineage_selection [data-testid="stColumn"]{width:100%!important;flex:1 1 auto!important;min-width:0!important}
}
</style>
"""

SELECTION_HEADING = '''<div class="lineage-card-heading"><span class="lineage-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/></svg></span><h2>Sélection des données</h2></div>
<p class="lineage-card-copy">Choisissez la base de données et la table dont vous souhaitez visualiser le lineage dans Apache Atlas.</p>'''

PREVIEW_HEADING = '''<div class="lineage-card-heading"><span class="lineage-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="2" y="9" width="6" height="6" rx="1"/><rect x="16" y="2" width="6" height="6" rx="1"/><rect x="16" y="16" width="6" height="6" rx="1"/><path d="M8 12h4V5h4M12 12v7h4"/></svg></span><h2>Aperçu du lineage</h2></div>
<p class="lineage-card-copy">Visualisation interactive du lineage de la table sélectionnée dans Apache Atlas.</p>'''

```

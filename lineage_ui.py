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

LINEAGE_ASSISTANT_CSS = """
<style>
.st-key-lineage_assistant_panel{background:#fff;border:1px solid #eadfd6!important;border-radius:15px!important;box-shadow:0 5px 18px rgba(55,34,18,.08);padding:14px}
.st-key-lineage_assistant_panel h3{color:#302820;font-size:19px;margin:.1rem 0}
.st-key-lineage_assistant_panel .stCaption{color:#737780;line-height:1.45}
.st-key-lineage_assistant_panel .stButton>button{border:1px solid #eadfd6;border-radius:9px;background:#fff;color:#5c4b40;font-size:12px;min-height:36px}
.st-key-lineage_assistant_panel .stButton>button:hover{border-color:#e87900;background:#fff5ec;color:#b64e0a}
.st-key-lineage_assistant_panel [data-testid="stChatMessage"]{background:#fffaf6;border:1px solid #f0e5dc;border-radius:10px;padding:.25rem .45rem;margin:.45rem 0}
.st-key-lineage_assistant_panel [data-testid="stChatInput"]{border:1px solid #dfcfc2;border-radius:10px;background:#fff}
.st-key-lineage_assistant_panel [data-testid="stChatInput"]:focus-within{border-color:#e87900;box-shadow:0 0 0 1px #e87900}
.st-key-lineage_assistant_panel button[data-testid="stChatInputSubmitButton"]{background:#e87900;color:#fff;border:none}
</style>
"""

SELECTION_HEADING = '''<div class="lineage-card-heading"><span class="lineage-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/></svg></span><h2>Sélection des données</h2></div>
<p class="lineage-card-copy">Choisissez la base de données et la table dont vous souhaitez visualiser le lineage dans Apache Atlas.</p>'''

PREVIEW_HEADING = '''<div class="lineage-card-heading"><span class="lineage-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="2" y="9" width="6" height="6" rx="1"/><rect x="16" y="2" width="6" height="6" rx="1"/><rect x="16" y="16" width="6" height="6" rx="1"/><path d="M8 12h4V5h4M12 12v7h4"/></svg></span><h2>Aperçu du lineage</h2></div>
<p class="lineage-card-copy">Visualisation interactive du lineage de la table sélectionnée dans Apache Atlas.</p>'''

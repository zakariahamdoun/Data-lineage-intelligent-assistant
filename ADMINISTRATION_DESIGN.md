# Administration

Code complet du bloc de page dans app.py :

```python
elif st.session_state.page=='Administration':
    if st.session_state.user['role']!='admin':st.error('Accès refusé.');st.stop()
    with st.container(key='admin_workspace'):
        from admin_ui import ADMIN_CSS, status_markup, person_markup
        from html import escape
        st.markdown(ADMIN_CSS,unsafe_allow_html=True)
        heading,add_column=st.columns([3,1.35],vertical_alignment='center')
        with heading:
            st.markdown('<div class="admin-eyebrow">DATA INTELLIGENCE</div>',unsafe_allow_html=True)
            st.title('Administration')
            st.markdown('<p class="admin-subtitle">Gestion des utilisateurs et des accès.</p>',unsafe_allow_html=True)
        if add_column.button('+ Ajouter un utilisateur',key='admin_add_user',type='primary',width='stretch'):
            st.session_state.show_add_user=True
        if st.session_state.pop('admin_user_created',False):
            st.success('Utilisateur créé avec succès.')
        if st.session_state.get('show_add_user',False):
            with st.form('admin_create_user',clear_on_submit=False):
                st.subheader('Ajouter un utilisateur')
                new_username=st.text_input('Identifiant',key='admin_new_username')
                new_password=st.text_input('Mot de passe temporaire',type='password',help='12 caractères minimum.',key='admin_new_password')
                confirmation=st.text_input('Confirmation du mot de passe',type='password',key='admin_new_confirmation')
                status=st.selectbox('Statut',['Actif','Désactivé'],key='admin_new_status')
                create_submitted=st.form_submit_button("Créer l'utilisateur",type='primary')
            if create_submitted:
                try:
                    create_authorized_user(new_username,new_password,confirmation,status=='Actif')
                except ValueError as error:
                    message=str(error)
                    if message=='Mot de passe : 12 caractères minimum.':
                        message+=f' Longueur reçue : {len(new_password)}.'
                    st.error(message)
                else:
                    st.session_state.show_add_user=False
                    st.session_state.admin_user_created=True
                    st.rerun()
        us=users()
        with st.container(key='admin_table'):
            st.subheader('Utilisateurs')
            st.caption(f'{len(us)} compte(s) · Gestion des accès au workspace')
            with st.container(key='admin_table_heading'):
                for cell,label in zip(st.columns([2,1.2,1.5,3]),['Utilisateur','Statut','Date de création','Actions']):
                    cell.write(label)
            for index,account in enumerate(us):
                name=account['username']
                row_active=bool(account['is_active'])
                row_protected=name in (PRIMARY_ADMIN,st.session_state.user['username'])
                with st.container(key=f'admin_user_row_{index}'):
                    identity,state,created,actions=st.columns([2,1.2,1.5,3],vertical_alignment='center')
                    identity.markdown(person_markup(name),unsafe_allow_html=True)
                    state.markdown(status_markup(row_active),unsafe_allow_html=True)
                    created.markdown(f'<span class="admin-date">{escape(str(account["created_at"]))}</span>',unsafe_allow_html=True)
                    with actions:
                        if row_protected:
                            st.markdown('<span class="admin-protected">Compte administrateur</span>',unsafe_allow_html=True)
                        else:
                            with st.container(horizontal=True):
                                if st.button("Désactiver l'accès" if row_active else "Activer l'accès",key=f'admin_row_toggle_{name}'):
                                    set_user_access(name,not row_active);st.rerun()
                                if st.button('Supprimer',key=f'admin_row_delete_{name}'):
                                    delete_user(name);st.rerun()
            if not us:st.caption('Aucun utilisateur à afficher.')
        if us:
            with st.container(key='admin_details'):
                st.subheader("Détails de l'utilisateur")
                u=st.selectbox('Utilisateur',[x['username'] for x in us])
                selected=next(x for x in us if x['username']==u)
                active=bool(selected['is_active'])
                identity,state,created=st.columns(3)
                identity.markdown(f'<div class="admin-label">Identifiant</div><div class="admin-value">{escape(u)}</div>',unsafe_allow_html=True)
                state.markdown('<div class="admin-label">Statut actuel</div>'+status_markup(active),unsafe_allow_html=True)
                created.markdown(f'<div class="admin-label">Date de création</div><div class="admin-value">{escape(str(selected["created_at"]))}</div>',unsafe_allow_html=True)
                protected=u in (PRIMARY_ADMIN,st.session_state.user['username'])
                a,b=st.columns(2)
                if a.button("Désactiver l'accès pour cet utilisateur" if active else "Activer l'accès pour cet utilisateur",type='primary',disabled=protected,width='stretch',key='admin_toggle_access'):
                    set_user_access(u,not active);st.rerun()
                if b.button('Supprimer cet utilisateur',disabled=protected,width='stretch',key='admin_delete_user'):
                    delete_user(u);st.rerun()
                if protected:st.caption('Ce compte administrateur est protégé contre la désactivation et la suppression.')
                with st.expander('Réinitialiser le mot de passe'):
                    with st.form('admin_reset_password_'+u,clear_on_submit=True):
                        reset_value=st.text_input('Nouveau mot de passe temporaire',type='password',help='12 caractères minimum.')
                        reset_confirmation=st.text_input('Confirmer le mot de passe temporaire',type='password')
                        reset_submitted=st.form_submit_button('Réinitialiser le mot de passe')
                    if reset_submitted:
                        try:reset_authorized_password(u,reset_value,reset_confirmation)
                        except ValueError as error:st.error(str(error))
                        else:st.success('Mot de passe réinitialisé. Un changement sera obligatoire à la prochaine connexion.')
        st.markdown('''<div class="admin-information"><span class="admin-info-icon" aria-hidden="true">ⓘ</span><div><strong>Information importante</strong><br>Seuls les utilisateurs activés peuvent se connecter à l’application. L’administrateur ne peut pas désactiver ni supprimer son propre compte.</div></div>''',unsafe_allow_html=True)

```

Module de presentation admin_ui.py (CSS et badges) :

```python
"""Presentation only for the Administration page."""
from html import escape


ADMIN_CSS = """
<style>
.st-key-admin_workspace {color:#263143;}
.st-key-admin_workspace .admin-eyebrow {color:#a44a12;font-size:11px;font-weight:750;letter-spacing:2px;margin:8px 0;}
.st-key-admin_workspace h1 {font-size:38px;letter-spacing:-1.2px;padding:0 0 8px;}
.st-key-admin_workspace .admin-subtitle {color:#717784;margin:0 0 20px;}
.st-key-admin_workspace button {border-radius:9px;min-height:42px;font-weight:600;box-shadow:none;}
.st-key-admin_workspace button[kind="primary"] {background:#c6530b;border-color:#c6530b;color:white;}
.st-key-admin_workspace button[kind="primary"]:hover {background:#a94307;border-color:#a94307;}
.st-key-admin_workspace button:focus-visible {outline:3px solid #efb47c;outline-offset:2px;}
.st-key-admin_workspace button:disabled {opacity:.45;}
.st-key-admin_table,.st-key-admin_details {background:white;border:1px solid #e5e7eb;border-radius:16px;padding:24px;box-shadow:0 4px 18px #24324706;}
.st-key-admin_workspace h3 {font-size:20px;padding-top:0;}
.st-key-admin_table_heading {background:#f7f8fa;border-radius:8px;padding:12px 14px;color:#737b88;font-size:13px;font-weight:650;}
.st-key-admin_workspace [class*="st-key-admin_user_row_"] {border-bottom:1px solid #edf0f3;padding:14px;}
.st-key-admin_workspace .admin-person {display:flex;align-items:center;gap:12px;overflow-wrap:anywhere;font-weight:650;}
.st-key-admin_workspace .admin-avatar {display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;flex-shrink:0;border-radius:10px;background:#fff1e5;color:#a9470b;font-size:14px;}
.st-key-admin_workspace .admin-status {display:inline-flex;align-items:center;gap:7px;padding:5px 10px;border-radius:20px;font-size:13px;font-weight:650;white-space:nowrap;}
.st-key-admin_workspace .admin-status.active {background:#edf8f1;color:#227448;}
.st-key-admin_workspace .admin-status.inactive {background:#fdf0ef;color:#b03232;}
.st-key-admin_workspace .admin-dot {height:7px;width:7px;border-radius:50%;background:currentColor;}
.st-key-admin_workspace .admin-protected {display:inline-block;background:#f0f1f3;color:#666e79;border:1px solid #e3e5e9;border-radius:6px;padding:7px 11px;font-size:12px;}
.st-key-admin_workspace .admin-date {color:#697281;font-size:14px;overflow-wrap:anywhere;}
.st-key-admin_workspace .admin-label {color:#727987;font-size:12px;margin-bottom:9px;}
.st-key-admin_workspace .admin-value {font-weight:650;overflow-wrap:anywhere;}
.st-key-admin_workspace [class*="st-key-admin_row_delete_"] button {color:#b03232;border-color:#eccbcb;background:#fff8f7;}
.st-key-admin_workspace .st-key-admin_delete_user button {background:#ba3737;border-color:#ba3737;color:white;}
.st-key-admin_workspace .admin-information {display:flex;gap:14px;border:1px solid #f3d8bd;background:#fff7ed;color:#805326;padding:20px 24px;border-radius:12px;margin-top:8px;font-size:14px;line-height:1.7;}
.st-key-admin_workspace .admin-info-icon {font-size:21px;line-height:1.4;}
@media(max-width:760px) {
 .st-key-admin_table,.st-key-admin_details {padding:16px;}
 .st-key-admin_workspace h1 {font-size:30px;}
 .st-key-admin_table_heading {display:none;}
}
</style>
"""


def status_markup(active):
    state, label = ('active', 'Actif') if active else ('inactive', 'Désactivé')
    return f'<span class="admin-status {state}"><span class="admin-dot"></span>{label}</span>'


def person_markup(username):
    return (f'<div class="admin-person"><span class="admin-avatar">{escape(username[:1].upper())}</span>'
            f'<span>{escape(username)}</span></div>')

```

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from auth_store import initialize,add_user,authenticate,connection,DISABLED,change_password,account_state,submit_access_request,access_requests
from test_lineage_routing import load_functions


class AdminAccessTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'users.db'
        initialize(self.path)
        for name in ('admin','alice'):add_user(self.path,name,'Test password 2026!')

    def app(self,actor='admin'):
        from streamlit.testing.v1 import AppTest
        source=Path('app.py').read_text(encoding='utf-8')
        page=source[source.index("elif st.session_state.page=='Administration':"):].replace('elif ','if ',1)
        setup=('import sqlite3,time,logging\nimport streamlit as st\nfrom test_lineage_routing import load_functions\n'
               'n=load_functions()\n'
               f'n.update(st=st,sqlite3=sqlite3,USERS_DB={str(self.path)!r},PRIMARY_ADMIN="admin",logger=logging.getLogger(__name__),navigation_started=None,page_render_started=time.perf_counter())\n'
               'globals().update(n)\nst.session_state.page="Administration"\n'
               f'st.session_state.user={{"username":{actor!r},"role":"admin"}}\n')
        return AppTest.from_string(setup+page,default_timeout=15).run()

    def test_table_status_and_protected_admin(self):
        app=self.app()
        self.assertFalse(app.exception)
        from admin_ui import person_markup
        rendered=[x.value for x in app.markdown]
        for label in ('Matricule','Statut','Date de création','Actions'):
            self.assertIn(label,rendered)
        for name in ('admin','alice'):self.assertIn(person_markup(name),rendered)
        self.assertTrue(any('Compte administrateur' in value for value in rendered))
        self.assertFalse(any(x.key=='admin_row_delete_admin' for x in app.button))
        self.assertEqual([x.label for x in app.selectbox],['Matricule','Afficher'])
        self.assertEqual([x.label for x in app.button if x.key in ('admin_toggle_access','admin_delete_user')],["Désactiver l'accès pour cet utilisateur",'Supprimer cet utilisateur'])
        self.assertTrue(all(x.disabled for x in app.button if x.key in ('admin_toggle_access','admin_delete_user')))

    def test_access_request_badge_updates_and_disappears(self):
        self.assertTrue(submit_access_request(self.path,'Alice Martin','alice@banque.ma','amartin','Data','Analyste','Besoin d’un accès à la plateforme.')[0])
        self.assertTrue(submit_access_request(self.path,'Bob Test','bob@banque.ma','btest','IT','Support','Besoin d’un accès à la plateforme.')[0])
        app=self.app()
        self.assertTrue(any('2 nouvelles' in value for value in (item.value for item in app.markdown)))
        first=access_requests(self.path,'pending')[0]
        app.button(key=f'access_request_accept_{first["id"]}').click().run()
        app.text_input(key=f'access_request_password_{first["id"]}').input('Temporary password 2026!')
        app.text_input(key=f'access_request_confirmation_{first["id"]}').input('Temporary password 2026!')
        next(button for button in app.button if button.label=='Accepter la demande').click().run()
        self.assertTrue(any('1 nouvelle' in value for value in (item.value for item in app.markdown)))
        last=access_requests(self.path,'pending')[0]
        app.button(key=f'access_request_reject_{last["id"]}').click().run()
        self.assertEqual(len(access_requests(self.path,'pending')),0)
        app=self.app()
        headings=[item.value for item in app.markdown if '<div class="access-requests-title-row">' in item.value]
        self.assertTrue(headings)
        self.assertNotIn('admin-request-count',headings[0])

    def test_toggle_access_controls_login(self):
        app=self.app()
        app.selectbox[0].select('alice').run()
        self.assertFalse(app.button(key='admin_toggle_access').disabled)
        app.button(key='admin_toggle_access').click().run()
        self.assertEqual(app.button(key='admin_toggle_access').label,"Activer l'accès pour cet utilisateur")
        self.assertTrue(any('Désactivé</span>' in x.value for x in app.markdown))
        self.assertEqual(authenticate(self.path,'alice','Test password 2026!'),(None,DISABLED))
        app.button(key='admin_toggle_access').click().run()
        self.assertEqual(app.button(key='admin_toggle_access').label,"Désactiver l'accès pour cet utilisateur")
        self.assertIsNotNone(authenticate(self.path,'alice','Test password 2026!')[0])

    def test_delete_user(self):
        app=self.app()
        app.selectbox[0].select('alice').run()
        app.button(key='admin_delete_user').click().run()
        self.assertFalse(app.exception)
        with connection(self.path) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE username='alice'").fetchone())
            self.assertIsNotNone(conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone())

    def create_in_ui(self,app,name,password,confirmation,status='Actif'):
        app.button(key='admin_add_user').click().run()
        app.text_input(key='admin_new_username').input(name)
        app.text_input(key='admin_new_password').input(password)
        app.text_input(key='admin_new_confirmation').input(confirmation)
        app.selectbox(key='admin_new_status').select(status)
        next(button for button in app.button if button.label=="Créer l'utilisateur").click().run()

    def test_create_active_and_disabled_accounts_and_refresh(self):
        app=self.app()
        password='Temporary password 2026!'
        for name,status in (('new_active','Actif'),('new_disabled','Désactivé')):
            self.create_in_ui(app,name,password,password,status)
            self.assertFalse(app.exception)
            self.assertEqual(app.success[0].value,'Utilisateur créé avec succès.')
            from admin_ui import person_markup,status_markup
            self.assertIn(person_markup(name),[x.value for x in app.markdown])
            self.assertIn(status_markup(status=='Actif'),[x.value for x in app.markdown])
            self.assertFalse(any(x.key=='admin_new_password' for x in app.text_input))
            user,error=authenticate(self.path,name,password)
            self.assertEqual(error,DISABLED if status=='Désactivé' else None)
            with connection(self.path) as conn:
                row=conn.execute('SELECT password_hash,role FROM users WHERE username=?',(name,)).fetchone()
                self.assertNotEqual(row[0],password)
                self.assertEqual(row[1],'user')

    def test_creation_rejects_mismatch_duplicate_and_short_password(self):
        app=self.app()
        password='Temporary password 2026!'
        self.create_in_ui(app,'new_person',password,'different password')
        self.assertIn('ne sont pas identiques',app.error[0].value)
        self.create_in_ui(app,'alice',password,password)
        self.assertIn('existe déjà',app.error[0].value)
        self.create_in_ui(app,'new_person','short','short')
        self.assertIn('12 caractères minimum',app.error[0].value)
        with connection(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM users').fetchone()[0],2)

    def test_creation_on_real_legacy_schema_and_normalized_duplicates(self):
        self.path=self.path.with_name('legacy.db')
        with connection(self.path) as conn:
            conn.execute("""CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""")
        initialize(self.path)
        add_user(self.path,'admin','Administrator password 2026!')
        app=self.app()
        password='Temporary password 2026!'
        self.create_in_ui(app,' Zakaria ',password,password)
        self.assertFalse(app.exception)
        self.assertEqual(app.success[0].value,'Utilisateur créé avec succès.')
        self.assertTrue(any('<span>Zakaria</span>' in x.value for x in app.markdown))
        for alias in ('Zakaria','zakaria',' Zakaria ','\u200bZakaria\u200b','\u00a0ZAKARIA\u00a0'):
            with self.assertRaisesRegex(ValueError,'existe déjà'):add_user(self.path,alias,password)
        with connection(self.path) as conn:
            rows=conn.execute('SELECT username,created_at FROM users ORDER BY id').fetchall()
        self.assertEqual([r[0] for r in rows],['admin','Zakaria'])
        self.assertTrue(all(r[1] for r in rows))

    def test_existing_admin_and_nonexistent_username(self):
        from auth_store import user_exists
        self.assertIs(user_exists('admin',path=self.path,debug=True),True)
        self.assertIs(user_exists('rrrrrrt',path=self.path,debug=True),False)
        self.assertIs(user_exists(' ADMIN ',path=self.path),True)
        app=self.app()
        password='Temporary password 2026!'
        self.create_in_ui(app,'admin',password,password)
        self.assertEqual(app.error[0].value,'Cet identifiant existe déjà.')
        self.create_in_ui(app,'rrrrrrt',password,password)
        self.assertFalse(app.exception)
        self.assertEqual(app.success[0].value,'Utilisateur créé avec succès.')
        self.assertTrue(any('<span>rrrrrrt</span>' in x.value for x in app.markdown))
        self.assertIs(user_exists('rrrrrrt',path=self.path),True)

    def test_creation_password_length_boundary_and_debug(self):
        from unittest.mock import patch
        import auth_store
        original=auth_store.add_user
        received=[]
        def debug_add(path,username,password,*args,**kwargs):
            # Fictitious values submitted through Streamlit, never real credentials.
            print('PASSWORD LENGTH =',len(password))
            print('PASSWORD RAW =',repr(password))
            received.append(password)
            return original(path,username,password,*args,**kwargs)
        app=self.app()
        app.button(key='admin_add_user').click().run()
        self.assertEqual(len(app.error),0)
        with patch('auth_store.add_user',debug_add):
            for name,password in (('short_test','12345678901'),('exact_test','Abcdef12345!'),
                                   ('long_test','Abcdef123456!'),('spaces_test',' abcdefghij ')):
                self.create_in_ui(app,name,password,password)
                self.assertEqual(received[-1],password)
                self.assertFalse(app.exception)
                if len(password)<12:
                    self.assertIn('12 caractères minimum',app.error[0].value)
                    self.assertIn('Longueur reçue : 11.',app.error[0].value)
                    self.assertEqual(app.text_input(key='admin_new_password').value,password)
                else:
                    self.assertEqual(len(app.error),0)
                    self.assertEqual(app.success[0].value,'Utilisateur créé avec succès.')

    def test_server_guards_current_admin_and_primary_admin(self):
        n=load_functions()
        n.update(USERS_DB=str(self.path),PRIMARY_ADMIN='admin',
                 st=SimpleNamespace(session_state=SimpleNamespace(user={'username':'alice','role':'admin'})))
        for name in ('alice','admin'):
            n['set_user_access'](name,False)
            n['delete_user'](name)
            self.assertIsNotNone(authenticate(self.path,name,'Test password 2026!')[0])
        n['st'].session_state.user={'username':'alice','role':'user'}
        with self.assertRaises(PermissionError):n['delete_user']('admin')
        with self.assertRaises(PermissionError):n['set_user_access']('admin',False)
        with self.assertRaises(PermissionError):n['create_authorized_user']('another','Temporary password 2026!','Temporary password 2026!',True)
        with self.assertRaises(PermissionError):n['reset_authorized_password']('another','Temporary password 2026!','Temporary password 2026!')

    def test_admin_reset_form_requires_change_and_never_shows_hash(self):
        change_password(self.path,'alice','Test password 2026!','Permanent password 2026!','Permanent password 2026!')
        app=self.app()
        app.selectbox[0].select('alice').run()
        password='Replacement temporary password 2026!'
        fields={field.label:field for field in app.text_input}
        fields['Nouveau mot de passe temporaire'].input(password)
        fields['Confirmer le mot de passe temporaire'].input(password)
        next(button for button in app.button if button.label=='Réinitialiser le mot de passe').click().run()
        self.assertFalse(app.exception)
        self.assertIn('Un changement sera obligatoire',app.success[0].value)
        self.assertTrue(account_state('alice',path=self.path)['must_change_password'])
        self.assertIsNone(authenticate(self.path,'alice','Permanent password 2026!')[0])
        self.assertFalse(any('password_hash' in x.value for x in app.markdown))

    def test_row_actions(self):
        app=self.app()
        app.button(key='admin_row_toggle_alice').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(authenticate(self.path,'alice','Test password 2026!'),(None,DISABLED))
        app.button(key='admin_row_toggle_alice').click().run()
        self.assertIsNotNone(authenticate(self.path,'alice','Test password 2026!')[0])
        app.button(key='admin_row_delete_alice').click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(account_state('alice',path=self.path))
        self.assertIsNotNone(account_state('admin',path=self.path))


if __name__=='__main__':unittest.main()

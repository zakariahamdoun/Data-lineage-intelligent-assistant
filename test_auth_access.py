import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from auth_store import connection, initialize, add_user, authenticate, set_active, reset_password, ITERATIONS, INCORRECT, DISABLED, change_password, account_state, submit_access_request, access_requests, pending_access_requests_count, approve_access_request, reject_access_request


class AuthAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'users.db'
        initialize(self.path)

    def test_active_incorrect_missing_and_disabled(self):
        add_user(self.path,'alice','A test password 2026!')
        self.assertEqual(authenticate(self.path,' alice ','A test password 2026!')[0],{'username':'alice','role':'user'})
        self.assertEqual(authenticate(self.path,'alice','incorrect'),(None,INCORRECT))
        self.assertEqual(authenticate(self.path,'unknown','incorrect'),(None,INCORRECT))
        set_active(self.path,'alice',False)
        self.assertEqual(authenticate(self.path,'alice','A test password 2026!'),(None,DISABLED))
        self.assertEqual(authenticate(self.path,'alice','incorrect'),(None,INCORRECT))
        set_active(self.path,'alice',True)
        self.assertIsNotNone(authenticate(self.path,'alice','A test password 2026!')[0])

    def test_salted_hash_and_password_reset(self):
        password='A test password 2026!'
        for name in ('alice','other'):add_user(self.path,name,password)
        with connection(self.path) as conn:
            rows=conn.execute('SELECT salt,password_hash,password_iterations FROM users').fetchall()
        self.assertNotEqual(rows[0][:2],rows[1][:2])
        self.assertEqual(rows[0][2],ITERATIONS)
        self.assertNotIn(password,self.path.read_bytes().decode('latin1'))
        reset_password(self.path,'alice','Replacement password 2026!')
        self.assertIsNone(authenticate(self.path,'alice',password)[0])
        self.assertIsNotNone(authenticate(self.path,'alice','Replacement password 2026!')[0])

    def test_migration_keeps_admin_and_requires_approval_of_old_accounts(self):
        legacy=Path(self.temp.name)/'legacy.db'
        salt=b'1234567890123456'
        digest=hashlib.pbkdf2_hmac('sha256',b'legacy password',salt,200000).hex()
        with connection(legacy) as conn:
            conn.execute('CREATE TABLE users(username TEXT PRIMARY KEY,salt TEXT,password_hash TEXT,role TEXT,created_at TEXT)')
            for name,role in (('admin','admin'),('old_user','user')):
                conn.execute('INSERT INTO users VALUES(?,?,?,?,CURRENT_TIMESTAMP)',(name,salt.hex(),digest,role))
        initialize(legacy)
        self.assertEqual(authenticate(legacy,'old_user','legacy password'),(None,DISABLED))
        self.assertEqual(authenticate(legacy,'admin','legacy password')[0]['role'],'admin')
        with connection(legacy) as conn:
            self.assertEqual(conn.execute("SELECT password_iterations FROM users WHERE username='admin'").fetchone()[0],ITERATIONS)
        set_active(legacy,'old_user',True)
        initialize(legacy)
        self.assertIsNotNone(authenticate(legacy,'old_user','legacy password')[0])

    def test_no_default_admin_or_password(self):
        self.assertEqual(authenticate(self.path,'admin','1234'),(None,INCORRECT))
        add_user(self.path,'admin','Administrator password 2026!')
        with self.assertRaises(ValueError):set_active(self.path,'admin',False)
        with self.assertRaises(ValueError):add_user(self.path,'alice','short')

    def test_only_primary_admin_keeps_admin_role(self):
        for name in ('admin','alice'):add_user(self.path,name,'Temporary password 2026!')
        with connection(self.path) as conn:
            conn.execute("UPDATE users SET role='user' WHERE username='admin'")
            conn.execute("UPDATE users SET role='admin' WHERE username='alice'")
        initialize(self.path)
        self.assertEqual(account_state('admin',path=self.path)['role'],'admin')
        self.assertEqual(account_state('alice',path=self.path)['role'],'user')

    def test_account_state_default_database_and_explicit_database(self):
        from unittest.mock import patch
        default_path=self.path.with_name('app_users.db')
        initialize(default_path)
        add_user(default_path,'alice','Temporary password 2026!',active=False)
        with patch('auth_store.__file__',str(default_path.with_name('auth_store.py'))):
            state=account_state(' alice ')
        self.assertEqual(state,account_state('alice',path=default_path))
        self.assertEqual(state['username'],'alice')
        self.assertFalse(state['is_active'])
        self.assertTrue(state['must_change_password'])
        self.assertIsNone(account_state('absent',path=default_path))

    def test_password_change_validation_and_reset(self):
        temporary='A temporary password 2026!'
        permanent='A permanent password 2026!'
        add_user(self.path,'alice',temporary)
        self.assertTrue(account_state('alice',path=self.path)['must_change_password'])
        for current,new,confirm in (('incorrect',permanent,permanent),
                                     (temporary,permanent,'different'),
                                     (temporary,temporary,temporary),
                                     (temporary,'short','short')):
            with self.assertRaises(ValueError):change_password(self.path,'alice',current,new,confirm)
            self.assertTrue(account_state('alice',path=self.path)['must_change_password'])
        set_active(self.path,'alice',False)
        with self.assertRaisesRegex(ValueError,'désactivé'):
            change_password(self.path,'alice',temporary,permanent,permanent)
        set_active(self.path,'alice',True)
        change_password(self.path,'alice',temporary,permanent,permanent)
        self.assertFalse(account_state('alice',path=self.path)['must_change_password'])
        reset_password(self.path,'alice','Another temporary password 2026!')
        self.assertTrue(account_state('alice',path=self.path)['must_change_password'])
        self.assertIsNone(authenticate(self.path,'alice',permanent)[0])

    def test_reset_restricts_an_existing_session(self):
        temporary='Temporary password 2026!'
        permanent='Permanent password 2026!'
        add_user(self.path,'alice',temporary)
        change_password(self.path,'alice',temporary,permanent,permanent)
        app=self.login_app()
        app.session_state['user']={'username':'alice','role':'user'}
        app.run()
        self.assertEqual(app.success[0].value,'Session ouverte')
        reset_password(self.path,'alice','Another temporary password 2026!')
        app.run()
        self.assertIsNone(app.session_state['user'])
        self.assertEqual(app.title[0].value,'Changer votre mot de passe')
        self.assertEqual(len(app.success),0)
        set_active(self.path,'alice',False)
        app.run()
        self.assertEqual(app.error[0].value,DISABLED)
        self.assertEqual(len(app.text_input),0)

    def test_access_request_lifecycle_creates_an_active_user_with_a_hash(self):
        success,message=submit_access_request(self.path,'Alice Martin','ALICE.MARTIN@BANQUE.MA','amartin','Data','Analyste','Besoin d’accéder aux analyses de lineage.')
        self.assertTrue(success)
        self.assertIn('transmise',message)
        success,message=submit_access_request(self.path,'Alice Martin','alice.martin@banque.ma','other','Data','Analyste','Motif suffisamment détaillé.')
        self.assertFalse(success)
        self.assertIn('déjà en attente',message)
        request=access_requests(self.path,'pending')[0]
        approve_access_request(self.path,request['id'],'Temporary password 2026!')
        self.assertEqual(access_requests(self.path,'approved')[0]['processed_at'] is not None,True)
        self.assertEqual(account_state('amartin',path=self.path)['role'],'user')
        self.assertTrue(account_state('amartin',path=self.path)['is_active'])
        self.assertTrue(account_state('amartin',path=self.path)['must_change_password'])
        with self.assertRaisesRegex(ValueError,'déjà été traitée'):
            approve_access_request(self.path,request['id'],'Temporary password 2026!')
        self.assertTrue(submit_access_request(self.path,'Bob Test','bob.test@banque.ma','btest','IT','Support','Besoin d’un accès pour le support applicatif.')[0])
        rejected=access_requests(self.path,'pending')[0]
        reject_access_request(self.path,rejected['id'])
        self.assertEqual(access_requests(self.path,'rejected')[0]['id'],rejected['id'])
        self.assertIsNone(account_state('btest',path=self.path))

    def test_pending_access_request_count_tracks_acceptance_and_rejection(self):
        self.assertEqual(pending_access_requests_count(self.path),0)
        self.assertTrue(submit_access_request(self.path,'Alice Martin','alice@banque.ma','amartin','Data','Analyste','Besoin d’un accès à la plateforme.')[0])
        self.assertTrue(submit_access_request(self.path,'Bob Test','bob@banque.ma','btest','IT','Support','Besoin d’un accès à la plateforme.')[0])
        self.assertEqual(pending_access_requests_count(self.path),2)
        first=access_requests(self.path,'pending')[0]
        approve_access_request(self.path,first['id'],'Temporary password 2026!')
        self.assertEqual(pending_access_requests_count(self.path),1)
        last=access_requests(self.path,'pending')[0]
        reject_access_request(self.path,last['id'])
        self.assertEqual(pending_access_requests_count(self.path),0)

    def test_badge_count_source_handles_1_3_12_and_0_pending_requests(self):
        for index in range(12):
            success,_=submit_access_request(
                self.path,f'Personne {index}',f'personne{index}@banque.ma',f'user{index}',
                'Data','Analyste','Besoin d’un accès à la plateforme.'
            )
            self.assertTrue(success)
            if index in (0,2,11):
                self.assertEqual(pending_access_requests_count(self.path),index+1)
        for request in access_requests(self.path,'pending'):
            reject_access_request(self.path,request['id'])
        self.assertEqual(pending_access_requests_count(self.path),0)

    def login_app(self):
        from streamlit.testing.v1 import AppTest
        code=Path('app.py').read_text(encoding='utf-8')
        section=code[code.index('# ---------------- AUTH'):code.index('# ---------------- ATLAS')]
        setup=('import os,base64,sqlite3,time,logging\nimport streamlit as st\nlogger=logging.getLogger(__name__)\n'
               f'__file__={str(Path("app.py").resolve())!r}\nUSERS_DB={str(self.path)!r}\nPRIMARY_ADMIN="admin"\n')
        return AppTest.from_string(setup+section+'\nst.success("Session ouverte")\n',default_timeout=15)

    def test_login_ui_has_no_signup_even_with_old_session_mode(self):
        app=self.login_app()
        app.session_state['auth_mode']='signup'
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual([e.label for e in app.text_input],['Matricule','Mot de passe'])
        self.assertEqual([e.label for e in app.button],['Se connecter','Demander un accès'])
        self.assertTrue(any('DATA INTELLIGENCE' in e.value for e in app.markdown))
        app.button(key='access_request_open').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_area[0].label,'Motif de la demande d’accès')

    def test_access_request_form_submits_to_the_administration_source(self):
        app=self.login_app().run()
        app.button(key='access_request_open').click().run()
        fields={field.label:field for field in app.text_input}
        fields['Nom complet'].input('Alice Martin')
        fields['Adresse e-mail professionnelle'].input('ALICE.MARTIN@BANQUE.MA')
        fields['Matricule'].input('amartin')
        fields['Service / Département'].input('Data')
        fields['Fonction / Métier'].input('Analyste')
        app.text_area[0].input('Besoin d’accéder aux analyses de lineage.')
        next(button for button in app.button if button.label=='Envoyer la demande').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.success[0].value,'Votre demande d’accès a bien été transmise à l’administrateur.')
        request=access_requests(self.path,'pending')[0]
        self.assertEqual((request['email'],request['matricule'],request['status']),
                         ('alice.martin@banque.ma','amartin','pending'))

    def test_login_ui_messages_and_session(self):
        add_user(self.path,'alice','A test password 2026!')
        app=self.login_app().run()
        app.text_input[0].input('alice')
        app.text_input[1].input('incorrect')
        app.button[0].click().run()
        self.assertEqual(app.error[0].value,INCORRECT)
        set_active(self.path,'alice',False)
        app.text_input[1].input('A test password 2026!')
        app.button[0].click().run()
        self.assertEqual(app.error[0].value,DISABLED)
        set_active(self.path,'alice',True)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(app.session_state['user'])
        self.assertEqual(app.session_state['password_change_user'],'alice')
        self.assertEqual(app.title[0].value,'Changer votre mot de passe')
        app.text_input[0].input('A test password 2026!')
        app.text_input[1].input('My permanent password 2026!')
        app.text_input[2].input('My permanent password 2026!')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['user'],{'username':'alice','role':'user'})
        self.assertFalse(account_state('alice',path=self.path)['must_change_password'])
        self.assertIsNone(authenticate(self.path,'alice','A test password 2026!')[0])
        self.assertIsNotNone(authenticate(self.path,'alice','My permanent password 2026!')[0])


if __name__=='__main__':unittest.main()

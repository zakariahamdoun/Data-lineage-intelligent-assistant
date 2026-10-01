"""Regression checks for lineage priority over database metadata."""
import ast
from pathlib import Path
from functools import lru_cache
import unittest
from test_lineage_routing import load_functions


class LineagePriorityTests(unittest.TestCase):
    def test_direct_routing_and_endpoints(self):
        n=load_functions();n['Mistral']=None
        for key in ('get_entity','get_lineage','search_type','pg_catalog'):
            n[key]=lru_cache(None)(n[key])
        database='Quelle est la base de données utilisée dans le projet SQLite ?'
        self.assertEqual(n['catalogue_intent'](database),('database','sqlite'))
        self.assertIn('transactions1.db',n['chatbot'](database))
        for question in (
            'Explique le lineage de la base de données SQLite',
            'Explique le Data Lineage du projet SQLite',
            'Quel est le parcours des données dans SQLite ?',
            'Quel est le cheminement des données dans la base SQLite ?',
        ):
            self.assertEqual(n['catalogue_intent'](question),(None,None))
            self.assertEqual(n['lineage_route'](question),('text','sqlite',False))
            answer=n['chatbot'](question)
            for node in n['sqlite_lineage']()[0].values():self.assertIn(node['label'],answer)
        for question in ('Affiche le lineage de SQLite','Affiche le lineage de la base de données SQLite'):
            self.assertEqual(n['catalogue_intent'](question),(None,None))
            self.assertEqual(n['lineage_route'](question),('visualization','sqlite',False))
        for term,expected,excluded in (
            ('source','transactions_sep.xlsx','Chargement_SQLite'),
            ('destination','transactions','transactions_sep.xlsx'),
        ):
            answer=n['chatbot'](f'Quelle est la {term} du lineage SQLite ?')
            self.assertIn(expected,answer)
            self.assertNotIn(excluded,answer)
            self.assertNotIn('→',answer)
        for phrase in ('origine des données','source et destination'):
            self.assertEqual(n['catalogue_intent'](phrase+' de la base SQLite'),(None,None))
        # A generic database question still has no lineage intention.
        self.assertEqual(n['lineage_route'](database),(None,None,False))

    def test_actual_streamlit_branch(self):
        from streamlit.testing.v1 import AppTest
        tree=ast.parse(Path('app.py').read_text(encoding='utf-8'))
        page=next(node for node in tree.body if isinstance(node,ast.If)
                  and ast.unparse(node.test)=="st.session_state.page == 'Assistant IA'")
        setup="""
import streamlit as st
import streamlit.components.v1 as components
from test_lineage_routing import load_functions
n=load_functions()
n.update(st=st,components=components,Mistral=None,MISTRAL_API_KEY='')
globals().update(n)
st.session_state.user={'username':'test','role':'user'}
st.session_state.page='Assistant IA'
building_data=''
"""
        app=AppTest.from_string(setup+'\n'+ast.unparse(page),default_timeout=45).run()
        for question,expected,visual in (
            ('Quelle est la base de données utilisée dans le projet SQLite ?','transactions1.db',False),
            ('Explique le lineage de la base de données SQLite','Preparation_transactions',False),
            ('Explique le Data Lineage du projet SQLite','Chargement_SQLite',False),
            ('Quel est le parcours des données dans SQLite ?','transactions_sep.xlsx',False),
            ('Quelle est la source du lineage SQLite ?','transactions_sep.xlsx',False),
            ('Quelle est la destination du lineage SQLite ?','est transactions.',False),
            ('Affiche le lineage de SQLite','',True),
            ('Affiche le lineage de la base de données SQLite','',True),
        ):
            app.chat_input[0].set_value(question).run()
            self.assertEqual(len(app.exception),0)
            message=app.session_state.messages[-1]
            self.assertEqual(message.get('response_type')=='lineage',visual)
            self.assertIn(expected,message['content'])


if __name__=='__main__':unittest.main()

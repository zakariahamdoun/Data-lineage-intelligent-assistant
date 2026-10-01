"""Offline routing contracts and Atlas database membership regressions."""
import unittest
from unittest.mock import Mock
from intent_routing import classify_intent, INTENT_PRIORITY
from test_lineage_routing import load_functions


CASES = (
    ('Quelle est la base PostgreSQL utilisée ?', 'database_lookup', 'database_lookup_answer'),
    ('Quelles sont les tables disponibles dans la base PostgreSQL ?', 'table_list', 'table_list_answer'),
    ('Quelles sont les colonnes de comptes ?', 'column_list', 'column_list_answer'),
    ('À quoi sert process_ouverture_compte ?', 'process_details', 'process_details_answer'),
    ('Quels processus sont disponibles dans PostgreSQL ?', 'process_list', 'process_list_answer'),
    ('Quel est le lineage de comptes ?', 'lineage', 'lineage_intent_answer'),
    ('Que se passe-t-il si comptes est supprimée ?', 'impact_analysis', 'atlas_impact_analysis'),
    ('Quelles sont les entrées et sorties de process_ouverture_compte ?', 'input_output', 'input_output_answer'),
    ('Que contient la table comptes ?', 'table_details', 'table_details_answer'),
    ('Quelle colonne représente le solde ?', 'column_lookup', 'column_intent_answer'),
    ('Quelle transformation a été appliquée ?', 'transformation', 'transformation_intent_answer'),
)


class IntentTests(unittest.TestCase):
    def test_classification_and_dispatch(self):
        for question, intent, handler in CASES:
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question), intent)
                n = load_functions()
                spy = Mock(return_value='Réponse structurée du gestionnaire')
                n[handler] = spy
                n['context'] = Mock(side_effect=AssertionError('Unexpected RAG'))
                self.assertEqual(n['chatbot'](question, 'postgresql'), spy.return_value)
                spy.assert_called_once_with(question, 'postgresql')

    def test_priority_and_variants(self):
        self.assertEqual(len(INTENT_PRIORITY), 12)
        for question, expected in (
            ('Liste les tables de projet_data_lineage', 'table_list'),
            ('QUELLES TABLES SONT DISPONIBLES dans PostgreSQL ?', 'table_list'),
            ('Quel impact sur le lineage si comptes est supprimée ?', 'impact_analysis'),
            ('Lineage des entrées et sorties de process_test', 'lineage'),
            ('Quelles colonnes représentent le solde ?', 'column_lookup'),
            ('Liste les processus PostgreSQL', 'process_list'),
            ('Bonjour PostgreSQL', 'fallback_rag'),
            ('Dans quelle base se trouve comptes ?', 'fallback_rag'),
        ):
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question), expected)


def entity(guid, kind, name, **attrs):
    return dict(guid=guid, typeName=kind, status='ACTIVE', attributes=dict(name=name, **attrs))


class AtlasTableListTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.db = entity('db', 'PostgreSQLDatabase', 'base_dynamique')
        self.other = entity('other', 'PostgreSQLDatabase', 'autre_base')
        self.table = entity('t', 'PostgreSQLTable', 'nouvelle_table')
        self.table['relationshipAttributes'] = {'database': {'guid': 'db'}}
        self.foreign = entity('f', 'PostgreSQLTable', 'table_exclue', databaseName='autre_base')
        self.deleted = entity('x', 'PostgreSQLTable', 'supprimee', databaseName='base_dynamique')
        self.deleted['status'] = 'DELETED'
        self.entities = [self.db, self.table, self.foreign, self.deleted]
        self.n['atlas_get'] = lambda path, params: {'entities': [e for e in self.entities
            if e['typeName'] == params.get('typeName', params.get('query'))][params['offset']:params['offset']+params['limit']]}
        self.n['get_entity'] = lambda guid: {'entity': next(e for e in self.entities if e['guid'] == guid)}

    def test_dynamic_membership_and_format(self):
        self.entities.append(dict(self.table, guid='duplicate'))
        answer = self.n['chatbot'](CASES[1][0])
        self.assertEqual(answer, 'Base PostgreSQL : base_dynamique\n\nTables disponibles :\n\n- nouvelle_table')

    def test_unknown_and_ambiguous_database(self):
        self.entities.append(self.other)
        answer = self.n['chatbot']('Liste les tables dans PostgreSQL')
        self.assertIn('Précisez', answer)
        self.assertNotIn('- nouvelle_table', answer)
        self.assertIn('introuvable', self.n['chatbot']('Liste les tables de inconnue'))
        self.assertIn('introuvable', self.n['chatbot']('Quelles sont les tables disponibles dans la base inconnue PostgreSQL ?'))
        self.assertIn('contient la table nouvelle_table', self.n['chatbot']('Liste les tables de base_dynamique'))
        self.assertIn('contient la table nouvelle_table', self.n['chatbot']('Liste les tables de base_dynamique','sqlite'))

    def test_empty_database_and_deleted_relationship(self):
        self.table['relationshipAttributes']['database']['relationshipStatus'] = 'DELETED'
        answer = self.n['chatbot']('Liste les tables de base_dynamique')
        self.assertIn('Aucune table', answer)
        self.assertNotIn('- nouvelle_table', answer)

    def test_pagination(self):
        pages=[]
        def atlas(path,params):
            pages.append(params['offset'])
            if params['offset']==0:
                return {'entities':[entity(str(i),'PostgreSQLTable','table_'+str(i)) for i in range(1000)]}
            return {'entities':[entity('last','PostgreSQLTable','derniere')]}
        self.n['atlas_get']=atlas
        self.assertEqual(len(self.n['atlas_inventory_entities']('PostgreSQLTable')),1001)
        self.assertEqual(pages,[0,1000])


class AtlasResponseContractTests(unittest.TestCase):
    """Read-only integration: validate actual responses, not mocked output strings."""
    def test_eight_requested_responses(self):
        from functools import lru_cache
        n=load_functions()
        n['Mistral']=None
        for name in ('atlas_inventory_entities','search_type','get_entity','get_lineage','pg_catalog'):
            n[name]=lru_cache(None)(n[name])
        n['context']=Mock(side_effect=AssertionError('Structured intents must bypass RAG'))
        patterns=(r'base de données.*est .+\.', r'Base PostgreSQL : .+\n\nTables disponibles :\n\n- ',
                  r'Colonnes de comptes\s*:', r'.+compte', r'Processus disponibles',
                  r'(?i)lineage|parcours|processus', r'(?i)impact|suppression|supprim', r'utilise.*entrée.*produit.*sortie')
        for (question,intent,handler),pattern in zip(CASES,patterns):
            with self.subTest(question=question):
                original=n[handler]
                spy=Mock(wraps=original)
                n[handler]=spy
                try:
                    self.assertEqual(n['detect_intent'](question),intent)
                    answer=n['chatbot'](question,'postgresql')
                    spy.assert_called_once_with(question,'postgresql')
                    self.assertIsInstance(answer,str)
                    self.assertRegex(answer.replace('\n',' ') if intent=='input_output' else answer,pattern)
                finally:
                    n[handler]=original

    def test_streamlit_uses_same_table_route(self):
        import ast
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        tree=ast.parse(Path('app.py').read_text(encoding='utf-8'))
        page=next(node for node in tree.body if isinstance(node,ast.If)
                  and ast.unparse(node.test)=="st.session_state.page == 'Assistant IA'")
        setup='''
import streamlit as st
from test_lineage_routing import load_functions
n=load_functions()
n.update(st=st,Mistral=None,MISTRAL_API_KEY='')
globals().update(n)
st.session_state.user={'username':'test','role':'user'}
st.session_state.page='Assistant IA'
building_data=''
'''
        app=AppTest.from_string(setup+'\n'+ast.unparse(page),default_timeout=45).run()
        app.chat_input[0].set_value(CASES[1][0]).run()
        self.assertEqual(len(app.exception),0)
        self.assertRegex(app.session_state.messages[-1]['content'],
                         r'Base PostgreSQL : .+\n\nTables disponibles :\n\n- ')

if __name__ == '__main__':
    unittest.main()

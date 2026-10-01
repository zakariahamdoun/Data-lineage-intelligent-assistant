"""Atlas dependency integration tests plus isolated FK normalization checks."""
import ast
from functools import lru_cache
from pathlib import Path
import unittest
from test_lineage_routing import load_functions


class DependenciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n=load_functions()
        for key in ('search_type','get_entity','get_lineage','pg_catalog'):
            cls.n[key]=lru_cache(None)(cls.n[key])
        def forbidden(*a,**k):raise AssertionError('Explicit Atlas request reached RAG')
        cls.n['context']=forbidden
        cls.n['Mistral']=None

    def test_requested_questions_and_directions(self):
        n=self.n;c=n['pg_catalog']()
        target=c['table_by_name']['comptes']
        def label(g):return c['tables'][c['column_parent'][g]]['name']+'.'+c['columns'][g]['name']
        all_pairs=c['fk_pairs']
        outgoing=[p for p in all_pairs if c['column_parent'][p[0]]==target]
        incoming=[p for p in all_pairs if c['column_parent'][p[1]]==target]
        cases=[
            ('Quelles sont les dépendances de la table comptes ?',outgoing+incoming),
            ('Quelles tables sont référencées par comptes ?',outgoing),
            ('De quelles tables comptes dépend-elle ?',outgoing),
            ('Quelles tables dépendent de comptes ?',incoming),
        ]
        for other in ('clients','agences','virements'):
            cases.append((f'Quelle relation existe entre comptes et {other} ?',[
                p for p in outgoing+incoming if c['table_by_name'][other] in
                (c['column_parent'][p[0]],c['column_parent'][p[1]])]))
        cases.append(('Quelles colonnes référencent comptes.id_compte ?',[
            p for p in incoming if c['columns'][p[1]]['name']=='id_compte']))
        for question,expected in cases:
            with self.subTest(question=question):
                self.assertTrue(expected,'Live Atlas fixture lacks required relations')
                answer=n['chatbot'](question)
                for a,b in all_pairs:
                    fact=f'{label(a)} → {label(b)}'
                    if (a,b) in expected:self.assertIn(fact,answer)
                    else:self.assertNotIn(fact,answer)
                self.assertNotRegex(answer,r'429|rate_limit_exceeded|st\.iframe|\bsvg\b')
                self.assertEqual(n['lineage_route'](question),(None,None,False))
                print(question,'=>',answer)

    def test_impact_reuses_existing_function(self):
        n=self.n;c=n['pg_catalog']()
        guid=next(g for g,d in c['columns'].items() if d['name']=='id_compte' and c['tables'][c['column_parent'][g]]['name']=='comptes')
        original=n['impact_pg'];calls=[]
        def traced(g,k):
            calls.append((g,k))
            return original(g,k)
        n['impact_pg']=traced
        try:answer=n['chatbot']("Quel est l'impact d'une modification de comptes.id_compte ?")
        finally:n['impact_pg']=original
        self.assertEqual(calls,[(guid,'Colonne')])
        result=original(guid,'Colonne')
        for col in result['columns']:self.assertIn(col['table']+'.'+col['name'],answer)
        for a,b in c['fk_pairs']:
            if b==guid:self.assertIn((b,a,'FK'),result['dependencies'])

    def test_intents_and_sqlite(self):
        n=self.n
        for word in ('dépendance','dépendances','dépend de','dépendantes','relation','relations','lié à','liée à','références','clé étrangère','clés étrangères','foreign key','impact structurel'):
            self.assertEqual(n['structural_intent'](word+' comptes'),'dependencies',word)
        self.assertIsNone(n['structural_intent']('Explique le lineage de comptes'))
        self.assertEqual(n['lineage_route']('Afficher le lineage de comptes')[0],'visualization')
        self.assertIn('process_comptes_transactions',n['chatbot']('Explique le lineage de comptes'))
        self.assertNotIn('process_ouverture_compte',n['chatbot']('Explique le lineage de comptes'))
        self.assertIn('id_compte',n['chatbot']('Quelles sont les colonnes de comptes ?'))
        self.assertIn('SQLite ou PostgreSQL',n['chatbot']('Quelles sont les dépendances de transactions ?'))
        self.assertNotIn('comptes',n['chatbot']('Quelles sont les dépendances de transactions SQLite ?','postgresql'))

    def test_no_fk_invention_and_inverse_deduplication(self):
        n=load_functions()
        cols={g:{'raw':{'relationshipAttributes':{}},'status':'ACTIVE'} for g in ('a','b','c')}
        cols['a']['raw']['relationshipAttributes']={'foreignKeyTo':[{'guid':'b'}],'unrelated':[{'guid':'c'}]}
        cols['b']['raw']['relationshipAttributes']={'referencedBy':[{'guid':'a'}]}
        self.assertEqual(n['atlas_fk_pairs'](cols),[('a','b')])
        cols['b']['status']='DELETED'
        self.assertEqual(n['atlas_fk_pairs'](cols),[])

    def test_live_relation_endpoints(self):
        n=self.n;c=n['pg_catalog']()
        # Verify orientation against the relationship entity itself, independently of FK attributes.
        ids={r['relationshipGuid'] for d in c['columns'].values()
             for key in ('foreignKeyTo','referencedBy')
             for r in d['raw'].get('relationshipAttributes',{}).get(key,[])}
        endpoints=set()
        for guid in ids:
            relationship=n['atlas_get']('/api/atlas/v2/relationship/guid/'+guid)['relationship']
            endpoints.add((relationship['end1']['guid'],relationship['end2']['guid']))
        self.assertEqual(set(c['fk_pairs']),endpoints)

    def test_streamlit_chat_routing(self):
        from streamlit.testing.v1 import AppTest
        tree=ast.parse(Path('app.py').read_text(encoding='utf-8'))
        page=next(node for node in tree.body if isinstance(node,ast.If)
                  and ast.unparse(node.test)=="st.session_state.page == 'Assistant IA'")
        # Execute the real assistant UI and functions, excluding authentication/database writes.
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
            ('Quelles sont les dépendances de la table comptes ?','comptes.id_client → clients.id_client',False),
            ('Quelles colonnes référencent comptes.id_compte ?','virements.compte_source → comptes.id_compte',False),
            ('Explique le lineage de comptes','process_comptes_transactions',False),
            ('Afficher le lineage de comptes','',True),
            ("Quel est l’impact d’une modification de comptes.id_compte ?",'Colonnes impactées',False),
            ('Quelles sont les colonnes de comptes ?','id_compte',False),
        ):
            app.chat_input[0].set_value(question).run()
            self.assertEqual(len(app.exception),0)
            message=app.session_state.messages[-1]
            self.assertEqual(message.get('response_type')=='lineage',visual)
            self.assertIn(expected,message['content'])
            self.assertNotRegex(message['content'],r'st\.iframe|\bsvg\b|429|rate_limit_exceeded')


if __name__=='__main__':unittest.main()

"""Presentation checks: real Atlas facts, deterministic Mistral success/error simulations."""
import json
from functools import lru_cache
from types import SimpleNamespace
import unittest
from test_lineage_routing import load_functions


class AnswerStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n=load_functions()
        for name in ('get_entity','get_lineage','search_type','pg_catalog'):
            cls.n[name]=lru_cache(None)(cls.n[name])

    def setUp(self):
        self.n['Mistral']=None

    def test_length_and_natural_dependencies(self):
        n=self.n
        columns=n['chatbot']('Quelles sont les colonnes de la table comptes ?')
        self.assertNotIn('\n',columns)
        self.assertLess(len(columns.split()),35)
        producer=n['chatbot']('Quel processus produit comptes ?')
        self.assertNotIn('\n',producer)
        self.assertLess(len(producer.split()),25)
        self.assertIn('est produite par le processus',producer)
        dependencies=n['chatbot']('Quelles sont les dépendances de la table comptes ?')
        self.assertEqual(len(dependencies.split('\n\n')),2)
        self.assertNotIn(';',dependencies)
        self.assertNotIn('Pour les dépendances',dependencies)
        self.assertIn('via les colonnes',dependencies)
        self.assertNotIn('Data Lineage',dependencies)
        for question in ('Quelles tables dépendent de comptes ?','De quelles tables comptes dépend-elle ?'):
            self.assertEqual(len(n['chatbot'](question).split('\n\n')),1)

    def test_mistral_429_keeps_natural_local_answer(self):
        n=self.n
        questions=['Quelles sont les colonnes de la table comptes ?',
                   'Quelles sont les dépendances de la table comptes ?',
                   'Quelles tables dépendent de comptes ?',
                   'De quelles tables comptes dépend-elle ?',
                   'Quel processus produit comptes ?',
                   'Explique le lineage de la table comptes.',
                   'Explique le Data Lineage du projet SQLite.']
        expected=[n['chatbot'](q) for q in questions]
        calls=[]
        def failing(**kwargs):
            calls.append(kwargs)
            raise RuntimeError('HTTP 429 rate_limit_exceeded')
        n['Mistral']=lambda **kwargs:SimpleNamespace(chat=SimpleNamespace(complete=failing))
        for q,answer in zip(questions,expected):
            self.assertEqual(n['chatbot'](q),answer)
            self.assertNotRegex(answer,r'429|rate_limit_exceeded|st\.iframe|\bsvg\b|indisponible')
        self.assertTrue(calls)
        self.assertEqual(n['lineage_route']('Affiche le Data Lineage du projet SQLite.'),('visualization','sqlite',False))

    def test_mistral_choices_preserve_facts_and_reject_free_text(self):
        n=self.n;q='Quelles sont les dépendances de la table comptes ?'
        local=n['chatbot'](q);captured=[]
        def success(**kwargs):
            captured.append(kwargs)
            options=json.loads(kwargs['messages'][1]['content'])['paragraphs']
            content=json.dumps({'choices':[len(p)-1 for p in options]})
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
        n['Mistral']=lambda **kwargs:SimpleNamespace(chat=SimpleNamespace(complete=success))
        reformulated=n['chatbot'](q)
        self.assertNotEqual(reformulated,local)
        self.assertIn('Elle est également référencée par',reformulated)
        payload=json.loads(captured[0]['messages'][1]['content'])
        self.assertNotIn('process_ouverture_compte',json.dumps(payload))
        self.assertEqual(captured[0]['messages'][0]['role'],'system')
        for invalid in ('Une relation inventée.', '{"choices":[999,0]}', '{"choices":[true,0]}', '{"choices":[]}'):
            def bad(**kwargs):
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=invalid))])
            n['Mistral']=lambda **kwargs:SimpleNamespace(chat=SimpleNamespace(complete=bad))
            self.assertEqual(n['chatbot'](q),local)


if __name__=='__main__':unittest.main()

"""Read-only Atlas integration checks and refresh cache lifecycle checks."""
import json
import unittest
from types import SimpleNamespace
from test_lineage_routing import load_functions


class RefreshTests(unittest.TestCase):
    def test_cache_invalidation_precedes_rebuild(self):
        n=load_functions();calls=[]
        for name in ('get_entity','get_lineage','search_type','pg_catalog','sqlite_lineage','pg_lineage','docs_atlas'):
            n[name]=SimpleNamespace(clear=lambda name=name:calls.append(name))
        def build():calls.append('build');return ['new'],object()
        build.clear=lambda:calls.append('index')
        n['atlas_index']=build
        self.assertEqual(n['refresh_metadata']()[0],['new'])
        self.assertEqual(calls[0],'index');self.assertEqual(calls[-1],'build')
        self.assertIn('get_entity',calls);self.assertIn('docs_atlas',calls)

    def test_live_documents_and_requested_questions(self):
        n=load_functions();n['Mistral']=None;n['context']=lambda *a:[]
        documents=n['docs_atlas']()
        data=[json.loads(doc) for doc in documents]
        self.assertEqual(len(data),len({d['guid'] for d in data}))
        for doc in data:
            for field in ('name','qualifiedName','typeName','description','system','relations','columns','Règle métier','Clé primaire','Entrées','Sorties'):
                self.assertIn(field,doc)
        table=next(d for d in data if d['name']=='comptes' and d['typeName']=='PostgreSQLTable')
        self.assertTrue(table['columns'])
        self.assertTrue(all(c['description'] for c in table['columns']))
        process=next(d for d in data if d['name']=='process_ouverture_compte')
        self.assertTrue(process['Entrées']);self.assertTrue(process['Sorties'])
        expected={'process_ouverture_compte','process_comptes_transactions','process_execution_virement'}
        rows=[n['catalogue_row'](p,'Processus') for p in n['pg_catalog']()['processes'].values()]
        self.assertTrue(expected <= {row['Objet'] for row in rows})
        for row in rows:
            self.assertEqual(list(row), ['Objet','Type','Type Atlas','Description','Règle métier','Clé primaire','Entrées','Sorties','Qualified Name'])
            self.assertEqual(row['Clé primaire'],'Non applicable')
        postgres_docs=[json.loads(doc) for doc in n['docs_atlas']('postgresql')]
        sqlite_docs=[json.loads(doc) for doc in n['docs_atlas']('sqlite')]
        self.assertTrue(expected <= {doc['name'] for doc in postgres_docs})
        self.assertFalse(expected & {doc['name'] for doc in sqlite_docs})
        self.assertTrue(all('businessRule' not in doc for doc in documents))
        self.assertTrue(all('isPrimaryKey' not in doc for doc in documents))
        for question,expected in (
            ('Que contient la table comptes ?','id_compte'),
            ('Décris la table comptes.','comptes bancaires'),
            ('Pourquoi clients est reliée à comptes ?','id_client'),
            ('Quelles sont les entrées de process_ouverture_compte ?','Entrées : agences et clients'),
            ('Explique le lineage de clients.','process_ouverture_compte'),
            ('Quel est l’impact de la suppression de comptes ?','transactions')):
            with self.subTest(question=question):
                answer=n['chatbot'](question)
                self.assertIn(expected,answer)
                self.assertNotIn('informations demandées ne sont pas disponibles',answer)


if __name__=='__main__':unittest.main()

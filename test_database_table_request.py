import unittest
from functools import lru_cache
from types import SimpleNamespace

from intent_routing import database_tables_request, classify_intent
from database_tables import attached_tables
from test_lineage_routing import load_functions


QUESTIONS = (
    'Quelle est la table disponible dans la base SQLite transactions1.db ?',
    'Quelles tables contient transactions1.db ?',
    'Donne-moi les tables de la base transactions1.db',
    'Quelle table appartient à transactions1.db ?',
)


class RoutingTests(unittest.TestCase):
    def test_database_contents(self):
        for question in QUESTIONS:
            self.assertEqual(database_tables_request(question), ('transactions1.db', 'sqlite'))
            self.assertEqual(classify_intent(question), 'table_list')

    def test_other_intents_unchanged(self):
        for question in ('Dans quelle base se trouve la table transactions ?',
                         'Quel est le lineage de la table transactions ?',
                         'Quel impact sur les tables de la base exemple ?',
                         'Quelles colonnes contient la table ventes ?'):
            self.assertIsNone(database_tables_request(question))
        self.assertEqual(database_tables_request('Quelles tables contient la base PostgreSQL comptabilite ?'),
                         ('comptabilite', 'postgresql'))

    def test_dsl_membership_deleted_conflicts_and_deduplication(self):
        def entity(guid, **attrs):
            return dict(guid=guid, status='ACTIVE', typeName='SQLiteTable', attributes=attrs)
        db = dict(guid='db', attributes={'name': 'demo.db'})
        entries = [entity('a', name='a', qualifiedName='a@demo.db@project'),
                   entity('b', name='b', dbName='demo.db'),
                   entity('c', name='c', databaseName='demo.db'),
                   entity('wrong', name='wrong', qualifiedName='wrong@otherdemo.db'),
                   entity('conflict', name='conflict', qualifiedName='conflict@demo.db'),
                   entity('deleted', name='deleted', databaseName='demo.db')]
        entries[-1]['status'] = 'DELETED'
        entries[-2]['relationshipAttributes'] = {'database': {'guid': 'other'}}
        by_id = {e['guid']: e for e in entries}
        n = load_functions()
        n['atlas_inventory_entities'] = lambda kind: []
        n['atlas_get'] = lambda *a, **k: {'entities': entries + [entries[0]]}
        n['get_entity'] = lambda guid: {'entity': by_id[guid]}
        self.assertEqual({e['guid'] for e in attached_tables('SQLite', db, n)}, {'a', 'b', 'c'})


class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = load_functions()
        for name in ('atlas_inventory_entities', 'get_entity'):
            cls.n[name] = lru_cache(None)(cls.n[name])
        cls.n['st'] = SimpleNamespace(session_state={'active_database': 'sqlite'})
        def forbidden(*args, **kwargs):raise AssertionError('LLM/RAG must not resolve tables')
        cls.n['context'] = forbidden
        cls.n['Mistral'] = forbidden

    def test_requested_contents(self):
        for question in QUESTIONS:
            answer = self.n['chat_message'](question)['content']
            self.assertIn('La base SQLite transactions1.db contient la table transactions.', answer)
        entities = self.n['find_tables_in_database']('transactions1.db', 'sqlite')
        self.assertTrue(entities)
        self.assertTrue(all(e['status']=='ACTIVE' and e['typeName']=='SQLiteTable' for e in entities))
        self.assertEqual(len(entities), len({e['guid'] for e in entities}))

    def test_location_preserved(self):
        answer = self.n['chat_message']('Dans quelle base se trouve la table transactions ?')['content']
        self.assertIn('transactions1.db', answer)
        self.assertIn('transactions', answer)


if __name__ == '__main__':unittest.main()

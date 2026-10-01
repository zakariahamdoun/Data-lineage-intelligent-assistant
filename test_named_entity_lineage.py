"""Regression checks and read-only validation against the running Atlas instance."""
from functools import lru_cache
from types import SimpleNamespace
import unittest

from test_lineage_routing import load_functions
from table_lineage import complete_upstream
from atlas_candidates import resolve_candidates


class LiveNamedLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_functions()
        for name in ('atlas_inventory_entities', 'get_entity', 'get_lineage'):
            cls.api[name] = lru_cache(None)(cls.api[name])
        cls.api['st'] = SimpleNamespace(session_state={'active_database': 'sqlite'})
        cls.api['context'] = lambda *a, **k: (_ for _ in ()).throw(AssertionError('FAISS called'))
        cls.api['Mistral'] = lambda *a, **k: (_ for _ in ()).throw(AssertionError('Mistral called'))

    def test_1_complete_file_lineage(self):
        question = 'Quel est le Data Lineage complet de transactions_sep.xlsx jusqu’à sa destination finale ?'
        answer = self.api['chat_message'](question, 'sqlite')['content']
        self.assertIn('Le fichier `transactions_sep.xlsx`', answer)
        self.assertIn('passent ensuite par le processus', answer)
        self.assertIn('La destination finale est la table `transactions`', answer)
        self.assertNotRegex(answer, r'Types Atlas|hdfs_path|SQLiteTable|\(Process\)')
        expected = ['transactions_sep.xlsx', 'Preparation_transactions', 'transactions1.csv',
                    'Chargement_SQLite', 'transactions']
        self.assertIn(' → '.join(expected), answer)
        # Independently verify every edge against live REST lineage (no fixtures).
        processes = self.api['atlas_inventory_entities']('Process')
        graph = next(g for e in processes for g in [self.api['get_lineage'](e['guid'], 'BOTH', 10)]
                     if any(v.get('attributes', {}).get('name') == expected[0]
                            for v in g.get('guidEntityMap', {}).values()))
        nodes = graph['guidEntityMap']
        edges = {(nodes[r['fromEntityId']]['attributes']['name'], nodes[r['toEntityId']]['attributes']['name'])
                 for r in graph['relations']}
        for edge in zip(expected, expected[1:]):
            self.assertIn(edge, edges)
        guid = next(g for g, e in nodes.items() if e['attributes']['name'] == expected[0])
        entity = self.api['get_entity'](guid)['entity']
        self.assertEqual(entity['status'], 'ACTIVE')
        self.assertEqual(entity['typeName'], 'hdfs_path')

    def test_2_csv(self):
        answer = self.api['chatbot']('Quel est le lineage de transactions1.csv ?', 'sqlite')
        self.assertIn('Le fichier `transactions1.csv`', answer)
        self.assertIn('transactions1.csv → Chargement_SQLite → transactions', answer)
        self.assertIn('transactions_sep.xlsx → Preparation_transactions → transactions1.csv', answer)

    def test_3_table(self):
        answer = self.api['chatbot']('Quel est le lineage de transactions ?', 'sqlite')
        self.assertIn('Chargement_SQLite', answer)
        self.assertIn('table', answer)
        self.assertIn('destination finale', answer)
        self.assertNotRegex(answer, r'Aucune relation en aval|transfert physique|impact|aucune dépendance supplémentaire')
        self.assertNotRegex(answer, r'Types Atlas|hdfs_path|SQLiteTable|\(Process\)')

    def test_complete_csv(self):
        answer = self.api['chatbot']("Quel est le Data Lineage complet de transactions1.csv jusqu'à sa destination finale ?", 'sqlite')
        self.assertIn('transactions1.csv → Chargement_SQLite → transactions', answer)
        self.assertIn('passent ensuite par le processus `Chargement_SQLite`', answer)
        self.assertIn('La destination finale est la table `transactions`', answer)
        self.assertNotIn('transactions_sep.xlsx', answer)
        self.assertNotRegex(answer, r'Types Atlas|hdfs_path|SQLiteTable|\(Process\)')

    def test_4_missing(self):
        answer = self.api['chat_message']('Quel est le lineage de entite_inexistante_7abc ?', 'sqlite')['content']
        self.assertIn("L'entité demandée n'a pas été trouvée", answer)
        self.assertNotIn('table', answer)

    def test_file_destination_is_focused(self):
        answer = self.api['chat_message']('Quelle est la destination du fichier transactions1.csv ?', 'sqlite')['content']
        self.assertIn('entrée du processus Chargement_SQLite', answer)
        self.assertIn('chargement des données préparées', answer)
        self.assertIn('La destination du fichier transactions1.csv est donc la table transactions.', answer)
        self.assertNotRegex(answer, r'transactions_sep|Preparation_transactions|[Cc]olonnes|Apache Atlas|métadonnées|impact')
        self.assertEqual(len(answer.split('\n\n')), 3)


class TraversalTests(unittest.TestCase):
    def test_same_qualified_name_different_types_remain_distinct(self):
        entities = [{'guid': g, 'typeName': kind, 'attributes': {'name': 'same', 'qualifiedName': 'same@db'}}
                    for g, kind in [('a', 'hdfs_path'), ('b', 'SQLiteTable')]]
        details = {e['guid']: dict(e, raw=e, name='same', qualifiedName='same@db') for e in entities}
        result = resolve_candidates(entities, details.__getitem__, lambda *a: {}, lambda *a: [])
        self.assertEqual(len(result), 2)

    def test_cycle_branch_and_long_path(self):
        edges = [(str(i), str(i+1)) for i in range(14)] + [('5', '3'), ('4', 'branch')]
        calls = []
        def lineage(guid, direction, depth):
            calls.append(guid)
            return {'relations': [{'fromEntityId': a, 'toEntityId': b} for a, b in edges if a == guid]}
        data = complete_upstream('0', lambda g: {'name': g, 'status': 'ACTIVE'}, lineage,
                                 lambda *a: [], 'OUTPUT')
        self.assertTrue(data['cycles'])
        self.assertIn([str(i) for i in range(15)], data['paths'])
        self.assertIn(['0', '1', '2', '3', '4', 'branch'], data['paths'])
        self.assertEqual(len(calls), len(set(calls)))


if __name__ == '__main__':
    unittest.main()

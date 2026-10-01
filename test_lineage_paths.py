"""Offline contracts for directed lineage paths between heterogeneous Atlas entities."""
import unittest

from test_lineage_routing import load_functions


def entity(guid, kind, name):
    return {
        'guid': guid,
        'typeName': kind,
        'status': 'ACTIVE',
        'attributes': {'name': name, 'qualifiedName': f'{name}@projet_data_lineage'},
    }


class LineagePathChatTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.entities = [
            entity('source-xlsx', 'hdfs_path', 'transactions_sep.xlsx'),
            entity('prepare', 'Process', 'Preparation_transactions'),
            entity('csv', 'hdfs_path', 'transactions1.csv'),
            entity('load-sqlite', 'Process', 'Chargement_SQLite'),
            entity('sqlite-transactions', 'SQLiteTable', 'transactions'),
            entity('clients', 'PostgreSQLTable', 'clients'),
            entity('prepare-clients', 'Process', 'Preparation_clients'),
            entity('pg-transactions', 'PostgreSQLTable', 'transactions'),
            entity('comptes', 'PostgreSQLTable', 'comptes'),
            entity('virement', 'Process', 'Execution_virement'),
            entity('virements', 'PostgreSQLTable', 'virements'),
        ]
        self.edges = [
            ('source-xlsx', 'prepare'), ('prepare', 'csv'), ('csv', 'load-sqlite'),
            ('load-sqlite', 'sqlite-transactions'), ('clients', 'prepare-clients'),
            ('prepare-clients', 'pg-transactions'), ('comptes', 'virement'), ('virement', 'virements'),
        ]
        by_guid = {item['guid']: item for item in self.entities}
        self.n['atlas_inventory_entities'] = lambda kind: [
            item for item in self.entities if item['typeName'] == kind
        ]
        self.n['atlas_get'] = lambda path, params=None: {'entities': []}
        self.n['get_entity'] = lambda guid: {'entity': by_guid[guid]}
        self.n['get_lineage'] = lambda guid, direction='BOTH', depth=10: {
            'relations': [{'fromEntityId': a, 'toEntityId': b} for a, b in self.edges],
            'guidEntityMap': by_guid,
        }

    def ask(self, question):
        return self.n['chatbot'](question)

    def test_xlsx_to_sqlite_table(self):
        answer = self.ask('Quel est le parcours de transactions_sep.xlsx jusqu’à la table transactions ?')
        self.assertIn('transactions_sep.xlsx → Preparation_transactions → transactions1.csv → Chargement_SQLite → transactions', answer)

    def test_arrival_wording_uses_same_path(self):
        answer = self.ask('Comment transactions_sep.xlsx arrive jusqu’à transactions ?')
        self.assertIn('transactions_sep.xlsx → Preparation_transactions → transactions1.csv → Chargement_SQLite → transactions', answer)

    def test_csv_to_sqlite_table(self):
        answer = self.ask('Quel est le chemin entre transactions1.csv et transactions ?')
        self.assertIn('transactions1.csv → Chargement_SQLite → transactions', answer)

    def test_clients_to_postgresql_transactions(self):
        answer = self.ask('Quel est le parcours de clients jusqu’à transactions ?')
        self.assertIn('clients → Preparation_clients → transactions', answer)

    def test_comptes_to_virements(self):
        answer = self.ask('Montre le lineage entre comptes et virements.')
        self.assertIn('comptes → Execution_virement → virements', answer)


if __name__ == '__main__':
    unittest.main()

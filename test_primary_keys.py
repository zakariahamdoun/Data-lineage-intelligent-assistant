"""Offline contracts for primary-key questions resolved from Atlas columns."""
import unittest

from test_lineage_routing import load_functions


def table(guid, kind, name, columns):
    return {
        'guid': guid,
        'typeName': kind,
        'status': 'ACTIVE',
        'attributes': {'name': name, 'qualifiedName': f'{name}@projet_data_lineage'},
        'relationshipAttributes': {'columns': [{'guid': item['guid']} for item in columns]},
    }


def column(guid, kind, table_name, name, primary):
    return {
        'guid': guid,
        'typeName': kind,
        'status': 'ACTIVE',
        'attributes': {
            'name': name,
            'qualifiedName': f'{table_name}.{name}@projet_data_lineage',
            'isPrimaryKey': primary,
        },
    }


class PrimaryKeyChatTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        sqlite_transaction_id = column('sqlite-tx-id', 'SQLiteColumn', 'transactions', 'id_transaction', True)
        sqlite_transaction_amount = column('sqlite-tx-amount', 'SQLiteColumn', 'transactions', 'montant', False)
        postgres_transaction_id = column('pg-tx-id', 'PostgreSQLColumn', 'transactions', 'id_transaction', True)
        postgres_account_id = column('pg-account-id', 'PostgreSQLColumn', 'comptes', 'id_compte', True)
        postgres_client_id = column('pg-client-id', 'PostgreSQLColumn', 'clients', 'id_client', True)
        self.tables = [
            table('sqlite-transactions', 'SQLiteTable', 'transactions', [sqlite_transaction_id, sqlite_transaction_amount]),
            table('pg-transactions', 'PostgreSQLTable', 'transactions', [postgres_transaction_id]),
            table('pg-comptes', 'PostgreSQLTable', 'comptes', [postgres_account_id]),
            table('pg-clients', 'PostgreSQLTable', 'clients', [postgres_client_id]),
        ]
        self.columns = [sqlite_transaction_id, sqlite_transaction_amount, postgres_transaction_id,
                        postgres_account_id, postgres_client_id]
        by_guid = {item['guid']: item for item in self.tables + self.columns}
        self.n['atlas_inventory_entities'] = lambda kind: [
            item for item in self.tables + self.columns if item['typeName'] == kind
        ]
        self.n['search_type'] = lambda kind, query=None: [
            item for item in self.columns if item['typeName'] == kind
        ]
        self.n['get_entity'] = lambda guid: {'entity': by_guid[guid]}

    def ask(self, question):
        return self.n['chatbot'](question)

    def test_unscoped_transactions_returns_both_sources(self):
        answer = self.ask('Quelle est la clé primaire de la table transactions ?')
        self.assertIn('SQLite : clé primaire de transactions = id_transaction', answer)
        self.assertIn('PostgreSQL : clé primaire de transactions = id_transaction', answer)

    def test_sqlite_scope_returns_only_sqlite_key(self):
        answer = self.ask('Quelle est la clé primaire de transactions dans SQLite ?')
        self.assertIn('SQLite : clé primaire de transactions = id_transaction', answer)
        self.assertNotIn('PostgreSQL', answer)

    def test_postgresql_scope_returns_only_postgresql_key(self):
        answer = self.ask('Quelle est la clé primaire de transactions dans PostgreSQL ?')
        self.assertIn('PostgreSQL : clé primaire de transactions = id_transaction', answer)
        self.assertNotIn('SQLite', answer)

    def test_column_wording_resolves_comptes(self):
        self.assertIn('id_compte', self.ask('Quelle colonne est la clé primaire de comptes ?'))

    def test_pk_alias_resolves_clients(self):
        self.assertIn('id_client', self.ask('Quelle est la PK de clients ?'))

    def test_plural_primary_keys_uses_same_atlas_attribute(self):
        answer = self.ask('Quelles sont les clés primaires de la table transactions ?')
        self.assertIn('id_transaction', answer)
        self.assertNotIn('non renseignée', answer)


if __name__ == '__main__':
    unittest.main()

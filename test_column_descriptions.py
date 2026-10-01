"""Offline routing contracts for Atlas column-description questions."""
import unittest

from test_lineage_routing import load_functions


def column(guid, kind, table, name, description):
    return {
        'guid': guid,
        'typeName': kind,
        'status': 'ACTIVE',
        'attributes': {
            'name': name,
            'qualifiedName': f'{table}.{name}@projet_data_lineage',
            'description': description,
        },
    }


class ColumnDescriptionChatTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.columns = [
            column('sqlite-amount', 'SQLiteColumn', 'transactions', 'montant',
                   'Montant de la transaction enregistré dans SQLite.'),
            column('postgres-amount', 'PostgreSQLColumn', 'transactions', 'montant',
                   'Montant monétaire de la transaction enregistré dans PostgreSQL.'),
            column('account-id', 'PostgreSQLColumn', 'comptes', 'id_compte',
                   'Identifiant unique du compte bancaire.'),
            column('transaction-id', 'PostgreSQLColumn', 'transactions', 'id_compte',
                   'Identifiant du compte associé à la transaction.'),
        ]
        by_guid = {item['guid']: item for item in self.columns}
        self.n['atlas_inventory_entities'] = lambda kind: [
            item for item in self.columns if item['typeName'] == kind
        ]
        self.n['get_entity'] = lambda guid: {'entity': by_guid[guid]}

    def ask(self, question):
        return self.n['chatbot'](question)

    def test_unscoped_amount_lists_both_atlas_columns(self):
        answer = self.ask('Quelle est la description de la colonne montant ?')
        self.assertIn('Plusieurs colonnes nommées montant', answer)
        self.assertIn('SQLite / transactions.montant', answer)
        self.assertIn('PostgreSQL / transactions.montant', answer)

    def test_sqlite_scope_reads_only_sqlite_column(self):
        answer = self.ask('Quelle est la description de la colonne montant de la base SQLite ?')
        self.assertIn('Dans SQLite', answer)
        self.assertIn('enregistré dans SQLite', answer)
        self.assertNotIn('PostgreSQL', answer)

    def test_postgresql_scope_reads_only_postgresql_column(self):
        answer = self.ask('Quelle est la description de la colonne montant de PostgreSQL ?')
        self.assertIn('Dans PostgreSQL', answer)
        self.assertIn('enregistré dans PostgreSQL', answer)
        self.assertNotIn('SQLite', answer)

    def test_describe_wording_keeps_sqlite_scope(self):
        answer = self.ask('Décris la colonne montant de SQLite')
        self.assertIn('Dans SQLite', answer)
        self.assertIn('enregistré dans SQLite', answer)

    def test_represent_wording_keeps_postgresql_scope(self):
        answer = self.ask('Que représente la colonne montant dans PostgreSQL ?')
        self.assertIn('Dans PostgreSQL', answer)
        self.assertIn('enregistré dans PostgreSQL', answer)

    def test_unscoped_id_compte_keeps_homonyms(self):
        answer = self.ask('Quelle est la description de id_compte ?')
        self.assertIn('comptes.id_compte', answer)
        self.assertIn('transactions.id_compte', answer)

    def test_table_scope_selects_one_id_compte(self):
        answer = self.ask('Quelle est la description de id_compte dans la table comptes ?')
        self.assertIn('Identifiant unique du compte bancaire', answer)
        self.assertNotIn('associé à la transaction', answer)


if __name__ == '__main__':
    unittest.main()

"""Offline contracts for PostgreSQLColumn.businessLabel chat answers."""
import unittest

from test_lineage_routing import load_functions


def column(guid, table, name, label):
    return {
        'guid': guid,
        'typeName': 'PostgreSQLColumn',
        'status': 'ACTIVE',
        'attributes': {
            'name': name,
            'qualifiedName': f'{table}.{name}@projet_data_lineage',
            'businessLabel': label,
            'description': 'Description technique distincte du libellé métier.',
        },
    }


class BusinessLabelChatTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.columns = [
            column('account-id', 'comptes', 'id_compte', 'Identifiant du compte'),
            column('transaction-id', 'transactions', 'id_compte',
                   'Identifiant du compte associé à la transaction'),
            column('amount', 'transactions', 'montant', 'Montant de la transaction'),
        ]
        by_guid = {item['guid']: item for item in self.columns}
        self.n['atlas_inventory_entities'] = lambda kind: list(self.columns) if kind == 'PostgreSQLColumn' else []
        self.n['get_entity'] = lambda guid: {'entity': by_guid[guid]}
        self.n['named_process_matches'] = lambda question: []

    def ask(self, question):
        return self.n['chatbot'](question)

    def test_unqualified_business_label_lists_all_matches(self):
        answer = self.ask('Quel est le libellé métier de id_compte ?')
        self.assertIn('Deux colonnes portent le nom id_compte', answer)
        self.assertIn('comptes.id_compte : Identifiant du compte', answer)
        self.assertIn('transactions.id_compte : Identifiant du compte associé à la transaction', answer)

    def test_qualified_account_column_returns_its_label(self):
        self.assertEqual(self.ask('Quel est le libellé métier de comptes.id_compte ?'),
                         'Identifiant du compte')

    def test_qualified_transaction_column_returns_its_label(self):
        self.assertEqual(self.ask('Quel est le libellé métier de transactions.id_compte ?'),
                         'Identifiant du compte associé à la transaction')

    def test_meaning_wording_uses_business_label(self):
        answer = self.ask('Que signifie id_compte ?')
        self.assertIn('Identifiant du compte', answer)
        self.assertIn('Identifiant du compte associé à la transaction', answer)

    def test_another_column_uses_its_business_label(self):
        self.assertEqual(self.ask('Quel est le libellé métier de montant ?'),
                         'Montant de la transaction')


if __name__ == '__main__':
    unittest.main()

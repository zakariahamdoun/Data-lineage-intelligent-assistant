"""Offline regressions for Atlas table-scoped column requests."""
import unittest
from types import SimpleNamespace
import test_sqlite_chatbot as fixtures


class ColumnScopeTests(unittest.TestCase):
    setUp = fixtures.SQLiteChatbotTests.setUp

    def configure(self):
        names = ['ID Clients', 'Numéro de compte', 'Identifiant opération',
                 'Type de transaction', 'Status opération', 'Date', 'Montant']
        self.table = {'name': 'transactions', 'columns': [
            {'name': name, 'type': 'TEXT', 'primary_key_position': None} for name in names]}
        self.atlas_fixture['tables'] = [self.table,
            {'name': 'virements', 'columns': [{'name': 'montant', 'type': 'REAL'}]}]
        self.n['st'] = SimpleNamespace(session_state={
            'active_chat_source': 'sqlite', 'sqlite_chat_table': 'transactions'})
        self.n['context'] = lambda *a: self.fail('No broad retrieval')
        self.n['atlas_inventory_entities'] = lambda *a: self.fail('No global column inventory')
        return names

    def test_six_requested_questions(self):
        names = self.configure()
        for question in ('Quel est le type de données de chaque colonne ?',
                         'Quels sont les types des colonnes de transactions ?',
                         'Quelles sont les colonnes de transactions ?'):
            with self.subTest(question=question):
                answer = self.n['chatbot'](question)
                for name in names: self.assertIn(name, answer)
                self.assertNotIn('virements', answer)
                self.assertIsNone(self.n['requested_column'](question))
        for question, expected in (
            ('Quelle colonne représente le montant ?', 'Montant'),
            ('Quelle colonne contient la date ?', 'Date'),
            ('Quelle colonne contient l’identifiant du client ?', 'ID Clients')):
            with self.subTest(question=question):
                self.assertEqual(self.n['chatbot'](question),
                    f'La colonne correspondante dans la table `transactions` est `{expected}`.')

    def test_generic_ranking_description_and_ties(self):
        self.configure()
        self.table['columns'] = [
            {'name': 'code_iso', 'description': 'Devise utilisée'},
            {'name': 'deviseur'}, {'name': 'Identifiant opération'}]
        answer = self.n['chatbot']('Quelle colonne contient la devise ?')
        self.assertIn('`code_iso`', answer)
        self.assertNotIn('deviseur', answer)
        self.table['columns'].append({'name': 'currency', 'description': 'Devise utilisée'})
        answer = self.n['chatbot']('Quelle colonne contient la devise ?')
        self.assertIn('`currency`', answer)
        self.assertIn('`code_iso`', answer)
        self.table['columns'].append({'name': 'Devise'})
        answer = self.n['chatbot']('Quelle colonne contient la devise ?')
        self.assertIn('`Devise`', answer)
        self.assertNotIn('currency', answer)

    def test_missing_type_and_explicit_table(self):
        self.configure()
        self.table['columns'][0]['type'] = ''
        self.assertIn('Type non renseigné dans Apache Atlas.',
            self.n['chatbot']('Quel est le type de données de chaque colonne ?'))
        answer = self.n['chatbot']('Quelle colonne représente le montant dans la table virements ?')
        self.assertIn('`virements`', answer)
        self.assertNotIn('transactions', answer)
        self.n['st'].session_state.pop('sqlite_chat_table')
        self.n['st'].session_state['active_table']=None
        self.n['st'].session_state['active_table_guid']=None
        self.assertIn('De quelle table', self.n['chatbot']('Quelle colonne contient la date ?'))

    def test_generic_atlas_table_scope(self):
        self.n['find_requested_tables'] = lambda q, s: [('postgresql', {'guid': 'chosen'})]
        self.n['table_metadata_context'] = lambda engine, entity: {
            'table': 'payments', 'columns': [{'name': 'amount_total', 'description': 'Montant total'}]}
        self.n['atlas_inventory_entities'] = lambda *a: self.fail('No global column inventory')
        answer = self.n['chatbot']('Quelle colonne représente le montant dans la table payments ?', 'postgresql')
        self.assertIn('`payments`', answer)
        self.assertIn('`amount_total`', answer)
        self.n['find_requested_tables'] = lambda q, s: []
        self.assertIn('Précisez', self.n['chatbot']('Quelle colonne contient la date ?', 'postgresql'))
        self.n['find_requested_tables'] = lambda q, s: [('sqlite', {'guid': 'wrong-system'})]
        self.assertIn('Précisez', self.n['chatbot']('Quelle colonne contient la date ?', 'postgresql'))


if __name__ == '__main__':
    unittest.main()

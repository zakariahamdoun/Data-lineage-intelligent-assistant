"""Offline regression tests for Atlas consumer/output traversal."""
import unittest
from test_lineage_routing import load_functions


class DownstreamTablesTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.entities = {}
        for guid, name, typ, relations in (
            ('s', 'seed', 'Table', {'inputToProcesses': [{'guid': 'p'}, {'guid': 'q'}, {'guid': 'p'}]}),
            ('p', 'first_job', 'Process', {'outputs': [{'guid': 'a'}, {'guid': 'f'}, {'guid': 'a'}]}),
            ('q', 'second_job', 'Process', {'outputs': [{'guid': 'b'}]}),
            ('a', 'alpha', 'SQLiteTable', {}), ('b', 'beta', 'PostgreSQLTable', {}),
            ('f', 'export.csv', 'File', {}),
        ):
            self.entities[guid] = {'name': name, 'typeName': typ, 'raw': {'relationshipAttributes': relations}}
        self.n['find_requested_tables'] = lambda *args: [('sqlite', {'guid': 's'})]
        self.n['detail'] = self.entities.__getitem__

    def test_phrasings_and_dynamic_outputs(self):
        for question in (
            'Quelles tables sont produites à partir de seed ?', 'Que produit la table seed ?',
            'Quelles sont les destinations de seed ?', 'Quelles tables dépendent de seed ?',
            'Où vont les données de seed ?', 'Quels processus utilisent seed ?',
            'Quel est le lineage en aval de seed ?',
        ):
            with self.subTest(question=question):
                self.assertIsNone(self.n['structural_intent'](question))
                self.assertEqual(self.n['lineage_route'](question, resolve_source=False)[0], 'text')
                self.assertEqual(self.n['lineage_scope'](question), ('OUTPUT', None))
                answer = self.n['chatbot'](question)
                self.assertIn('Deux tables', answer)
                self.assertEqual(answer.count('seed → first_job → alpha'), 1)
                self.assertIn('seed → second_job → beta', answer)
                self.assertNotIn('export.csv', answer)

    def test_missing_outputs_and_non_table_outputs(self):
        self.entities['p']['raw']['relationshipAttributes']['outputs'] = [{'guid': 'f'}]
        self.entities['q']['raw']['relationshipAttributes']['outputs'] = []
        answer = self.n['chatbot']('Que produit la table seed ?')
        self.assertIn('ne sont pas des tables', answer)
        self.assertIn('aucune sortie', answer)
        self.assertIn('first_job', answer)
        self.assertIn('second_job', answer)

    def test_deleted_relations_and_explicit_foreign_keys(self):
        self.entities['s']['raw']['relationshipAttributes']['inputToProcesses'] = [
            {'guid': 'missing', 'relationshipStatus': 'DELETED'}]
        self.assertIn('Aucun processus utilisateur', self.n['chatbot']('Que produit seed ?'))
        question = 'Quelles tables dépendent de seed via les clés étrangères ?'
        self.assertFalse(self.n['downstream_tables_intent'](question))
        self.assertEqual(self.n['structural_intent'](question), 'dependencies')


if __name__ == '__main__':
    unittest.main()

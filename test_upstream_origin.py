"""Offline tests for table producer and input relationships."""
import unittest
from test_lineage_routing import load_functions


class UpstreamOriginTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.entities = {}
        for guid, name, typ, relations in (
            ('t', 'target', 'Table', {'outputFromProcesses': [{'guid': 'p'}]}),
            ('p', 'build', 'Process', {'inputs': [{'guid': 'a'}, {'guid': 'b'}]}),
            ('a', 'first', 'Table', {}), ('b', 'second', 'Table', {}),
        ):
            self.entities[guid] = {'name': name, 'typeName': typ,
                                   'raw': {'relationshipAttributes': relations}}
        self.n['find_requested_tables'] = lambda *args: [('sqlite', {'guid': 't'})]
        self.n['detail'] = self.entities.__getitem__

    def test_all_phrasings_use_producer_inputs(self):
        for question in (
            'Quelle est l’origine de la table target ?', 'D’où vient la table target ?',
            'Quelles sont les sources de target ?', 'Comment la table target est-elle produite ?',
            'Quel processus produit target ?', 'Quelles sont les entrées utilisées pour créer target ?',
        ):
            with self.subTest(question=question):
                self.assertEqual(self.n['lineage_route'](question, resolve_source=False)[0], 'text')
                self.assertEqual(self.n['lineage_scope'](question), ('INPUT', None))
                answer = self.n['chatbot'](question)
                self.assertIn('first + second → build → target', answer)
                self.assertIn('des tables first et second', answer)

    def test_partial_metadata_and_multiple_producers(self):
        self.entities['p']['raw']['relationshipAttributes']['inputs'] = []
        answer = self.n['chatbot']('Quel processus produit target ?')
        self.assertIn('aucune entrée', answer)
        self.assertIn('build → target', answer)
        self.entities['q'] = {'name': 'other_build', 'typeName': 'Process',
                              'raw': {'attributes': {'inputs': [{'guid': 'a'}]}}}
        self.entities['t']['raw']['relationshipAttributes']['outputFromProcesses'].append({'guid': 'q'})
        answer = self.n['chatbot']('D’où vient target ?')
        self.assertIn('first → other_build → target', answer)
        self.assertIn('build → target', answer)


if __name__ == '__main__':
    unittest.main()

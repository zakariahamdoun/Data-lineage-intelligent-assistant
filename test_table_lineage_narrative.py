"""Offline Atlas fixtures: lineage narration, scope and unchanged intent dispatch."""
import unittest
from unittest.mock import Mock
from types import SimpleNamespace
from test_lineage_routing import load_functions
from table_lineage import read_table_lineage, describe_table_lineage


class TableLineageNarrativeTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        self.entities = {}
        for name in ('agences', 'clients', 'comptes', 'transactions', 'virements'):
            self.add(name, 'Table')
        self.add('process_ouverture_compte', 'Process', inputs=['agences', 'clients'], outputs=['comptes'])
        self.add('process_comptes_transactions', 'Process', inputs=['comptes'], outputs=['transactions'])
        self.add('process_execution_virement', 'CustomStage', inputs=['comptes'], outputs=['virements'])
        for child, parent in (
            ('comptes.id_agence', 'agences.id_agence'),
            ('comptes.id_client', 'clients.id_client'),
            ('transactions.id_compte', 'comptes.id_compte'),
            ('virements.compte_source', 'comptes.id_compte'),
            ('virements.compte_destination', 'comptes.id_compte'),
        ):
            for column in (child, parent):
                if column not in self.entities:
                    table, name = column.split('.')
                    self.add(column, 'Column', name=name, table=[table])
                    self.entities[table]['relationshipAttributes'].setdefault('columns', []).append({'guid': column})
            self.entities[child]['relationshipAttributes'].setdefault('foreignKeyTo', []).append({'guid': parent})
            self.entities[parent]['relationshipAttributes'].setdefault('referencedBy', []).append({'guid': child})
        self.n['get_entity'] = lambda guid: {'entity': self.entities[guid]}
        self.n['get_lineage'] = lambda *args: {'relations': [
            {'fromEntityId': a, 'toEntityId': b} for a, b in (
                ('agences', 'process_ouverture_compte'), ('clients', 'process_ouverture_compte'),
                ('process_ouverture_compte', 'comptes'), ('comptes', 'process_comptes_transactions'),
                ('process_comptes_transactions', 'transactions'), ('comptes', 'process_execution_virement'),
                ('process_execution_virement', 'virements'))]}
        self.n['find_requested_tables'] = lambda q, source=None: [
            ('fixture', e) for key, e in self.entities.items() if e['typeName'] == 'Table'
            and __import__('re').search(r'\b' + __import__('re').escape(e['attributes']['name']) + r'\b', q)]
        self.n['context'] = Mock(side_effect=AssertionError('Lineage must bypass RAG'))

    def add(self, guid, kind, name=None, **relations):
        self.entities[guid] = dict(guid=guid, typeName=kind, status='ACTIVE',
                                   attributes={'name': name or guid},
                                   relationshipAttributes={key: [{'guid': value} for value in values]
                                                           for key, values in relations.items()})

    def read(self, guid='comptes'):
        return read_table_lineage(guid, self.n['detail'], self.n['get_lineage'], self.n['process_refs'])

    def test_five_requested_questions(self):
        for question, present, absent in (
            ('Explique le lineage de la table comptes', 'agences` et `clients', None),
            ('Quel est le lineage de clients ?', 'process_ouverture_compte', 'process_execution_virement'),
            ('Montre le lineage de transactions', 'process_comptes_transactions', 'process_execution_virement'),
            ('Quels sont les éléments en amont de comptes ?', 'process_ouverture_compte', 'process_execution_virement'),
            ('Quels sont les éléments en aval de comptes ?', 'process_execution_virement', 'process_ouverture_compte'),
        ):
            with self.subTest(question=question):
                self.assertEqual(self.n['detect_intent'](question), 'lineage')
                original = self.n['lineage_intent_answer']
                spy = Mock(wraps=original)
                self.n['lineage_intent_answer'] = spy
                try:
                    answer = self.n['chatbot'](question)
                    spy.assert_called_once_with(question, None)
                    self.assertIn('Apache Atlas', answer)
                    self.assertIn(present, answer)
                    if absent:
                        self.assertNotIn(absent, answer)
                    self.assertNotIn('1. **Rôle général**', answer)
                    self.assertIn('ne prouvent pas un transfert physique', answer)
                finally:
                    self.n['lineage_intent_answer'] = original

    def test_all_five_foreign_keys_and_grouped_inputs(self):
        answer = describe_table_lineage(self.read())
        self.assertIn('agences + clients → process_ouverture_compte → comptes', answer)
        self.assertIn('comptes → process_execution_virement → virements', answer)
        self.assertEqual(len(self.read()['foreign_keys']), 5)
        self.assertIn('virements.compte_destination → comptes.id_compte', answer)
        self.assertIn('distinctes du Data Lineage', answer)
        self.assertLess(len(answer.split()), 280)

    def test_dynamic_names_empty_and_incomplete(self):
        self.add('nouvelle_cible', 'Table')
        self.n['get_lineage'] = lambda *args: {'relations': []}
        answer = self.n['chatbot']('Explique le lineage de nouvelle_cible')
        self.assertIn('Aucune relation en amont', answer)
        self.assertIn('Aucune relation en aval', answer)
        self.assertNotIn('clés étrangères', answer)
        self.add('stage_inconnu', 'Process', outputs=['nouvelle_cible'])
        self.entities['nouvelle_cible']['relationshipAttributes']['outputFromProcesses'] = [{'guid': 'stage_inconnu'}]
        answer = self.n['chatbot']('Explique le lineage de nouvelle_cible')
        self.assertIn('entrées ne sont pas renseignées', answer)
        self.assertIn('stage_inconnu → nouvelle_cible', answer)
        self.assertNotIn('comptes', answer)

    def test_deleted_entities_and_relations(self):
        self.entities['process_execution_virement']['status'] = 'DELETED'
        self.entities['comptes']['relationshipAttributes']['columns'].append({'guid': 'missing', 'relationshipStatus': 'DELETED'})
        self.entities['comptes.id_agence']['relationshipAttributes']['foreignKeyTo'][0]['relationshipStatus'] = 'DELETED'
        answer = describe_table_lineage(self.read())
        self.assertNotIn('process_execution_virement', answer)
        self.assertNotIn('comptes.id_agence → agences.id_agence', answer)

    def test_deleted_endpoint_overrides_stale_graph(self):
        self.entities['process_ouverture_compte']['relationshipAttributes']['inputs'][0]['relationshipStatus'] = 'DELETED'
        self.entities['process_execution_virement']['relationshipAttributes']['inputs'][0]['relationshipStatus'] = 'DELETED'
        data = self.read()
        self.assertNotIn('agences', data['records']['process_ouverture_compte']['inputs'])
        self.assertNotIn('process_execution_virement', data['consumers'])

    def test_cycles_and_missing_output_do_not_invent_paths(self):
        self.n['get_lineage'] = lambda *args: {'relations': []}
        self.add('loop', 'Process', inputs=['comptes'], outputs=['comptes'])
        self.entities['comptes']['relationshipAttributes'].update(
            outputFromProcesses=[{'guid': 'loop'}], inputToProcesses=[{'guid': 'loop'}])
        answer = describe_table_lineage(self.read())
        self.assertEqual(answer.count('`comptes → loop → comptes`'), 1)
        self.entities['loop']['relationshipAttributes']['outputs'] = []
        self.entities['comptes']['relationshipAttributes']['outputFromProcesses'] = []
        answer = describe_table_lineage(self.read())
        self.assertIn('sorties ne sont pas renseignées', answer)
        self.assertNotIn('comptes → loop → comptes', answer)

    def test_visualization_has_same_narrative_and_graph(self):
        texts, graphs = [], []
        data = self.read('transactions')
        self.n['local_lineage_data'] = lambda *args: (data['nodes'], data['edges'], data['name'])
        self.n['st'] = SimpleNamespace(markdown=lambda text: texts.append(text))
        self.n['render_graph'] = lambda nodes, edges, **kwargs: graphs.append((nodes, edges))
        self.n['render_local_lineage']('fixture', 'Montre le lineage de transactions')
        self.assertEqual(len(graphs), 1)
        self.assertIn('process_comptes_transactions', texts[-1])
        self.assertNotIn('process_execution_virement', texts[-1])
        self.assertIn({'from': 'comptes', 'to': 'process_comptes_transactions'}, graphs[0][1])

    def test_other_intents_keep_their_handlers(self):
        from test_intent_routing import CASES
        for question, intent, handler in CASES:
            if intent == 'lineage':
                continue
            with self.subTest(intent=intent):
                n = load_functions()
                n[handler] = Mock(return_value='unchanged')
                n['table_lineage_context'] = Mock(side_effect=AssertionError('Wrong intention'))
                self.assertEqual(n['chatbot'](question), 'unchanged')
                n[handler].assert_called_once_with(question, None)


if __name__ == '__main__':
    unittest.main()

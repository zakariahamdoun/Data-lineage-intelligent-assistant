"""Offline regression checks for complete Atlas relationship explanations."""
import unittest
from test_lineage_routing import load_functions


class RelationContextTests(unittest.TestCase):
    def setUp(self):
        self.n = load_functions()
        def entity(guid, name, kind, attributes=None, relationships=None, description=''):
            return dict(guid=guid, name=name, typeName=kind, status='ACTIVE',
                        description=description, raw=dict(attributes=attributes or {},
                        relationshipAttributes=relationships or {}))
        self.entities = {
            'c': entity('c', 'clients', 'PostgreSQLTable'),
            'a': entity('a', 'agences', 'PostgreSQLTable'),
            't': entity('t', 'comptes', 'PostgreSQLTable', {'businessRule':
                'Un client peut posséder plusieurs comptes, tandis qu’un compte appartient à un seul client.'}),
            'pk': entity('pk', 'id_client', 'PostgreSQLColumn', {'isPrimaryKey': True}, {'table': {'guid': 'c'}}),
            'fk': entity('fk', 'id_client', 'PostgreSQLColumn', relationships={
                'table': {'guid': 't'}, 'foreignKeyTo': [{'guid': 'pk'}]},
                description='Cette relation permet d’identifier le client auquel appartient chaque compte.'),
            'p': entity('p', 'process_ouverture_compte', 'Process', relationships={
                'inputs': [{'guid': 'c'}, {'guid': 'a'}], 'outputs': [{'guid': 't'}]}),
        }
        self.n['detail'] = self.entities.__getitem__
        self.n['search_type'] = lambda kind: [e for e in self.entities.values() if e['typeName'] == kind]
        self.n['find_requested_tables'] = lambda *args: [('postgresql', self.entities[g]) for g in ('c', 't')]

    def answer(self, detailed=False):
        return self.n['table_relation_answer']('Quelle est la relation entre clients et comptes ?' + (' explique en détail' if detailed else ''))

    def test_order_and_full_context(self):
        answer = self.answer()
        facts = ['comptes.id_client référence la clé primaire clients.id_client',
                 'identifier le client', 'Un client peut posséder plusieurs comptes',
                 'un compte appartient à un seul client', 'Dans le Data Lineage',
                 'clients est utilisée', 'process_ouverture_compte', 'produit comptes']
        positions = [answer.index(fact) for fact in facts]
        self.assertEqual(positions, sorted(positions))
        self.assertLessEqual(len(answer.split()), 80)
        self.assertEqual(len(answer.split('\n\n')), 3)
        self.assertNotIn('agences', answer)

    def test_all_outputs_and_attributes_endpoints(self):
        raw = self.entities['p']['raw']
        raw['attributes'] = raw.pop('relationshipAttributes')
        raw['attributes']['outputs'].append({'guid': 'a'})
        self.assertIn('produit agences et comptes', self.answer(detailed=True))
        self.assertNotIn('agences', self.answer())

    def test_missing_evidence_does_not_invent_primary_key_or_cardinality(self):
        self.entities['pk']['raw']['attributes'] = {}
        self.entities['t']['raw']['attributes'] = {}
        answer = self.answer()
        self.assertNotIn('clé primaire', answer)
        self.assertNotIn('plusieurs comptes', answer)
        self.assertNotIn('un seul client', answer)

    def test_primary_key_list(self):
        self.entities['pk']['raw']['attributes'] = {}
        self.entities['c']['raw']['attributes'] = {'primaryKeyColumns': ['id_client']}
        self.assertIn('clé primaire', self.answer())

    def test_filter_unrelated_rules_and_deduplicate(self):
        self.entities['t']['raw']['attributes']['businessRule'] += ' Chaque compte appartient à un client et est rattaché à une agence.'
        self.entities['c']['raw']['attributes']['businessRule'] = self.entities['t']['raw']['attributes']['businessRule']
        answer = self.answer()
        self.assertNotIn('agence', answer)
        self.assertEqual(answer.count('plusieurs comptes'), 1)
        self.assertIn('agence', self.answer(detailed=True))

    def test_dynamic_table_names(self):
        for old,new in [('clients','acheteurs'),('comptes','commandes'),('client','acheteur'),('compte','commande')]:
            for entity in self.entities.values():
                entity['name'] = entity['name'].replace(old,new)
                entity['description'] = entity['description'].replace(old,new)
                attrs=entity['raw']['attributes']
                if 'businessRule' in attrs:attrs['businessRule']=attrs['businessRule'].replace(old,new)
        answer=self.answer()
        self.assertIn('commandes.id_acheteur référence la clé primaire acheteurs.id_acheteur',answer)
        self.assertIn('plusieurs commandes',answer)
        self.assertNotIn('agences',answer)

    def test_unrelated_process_excluded(self):
        self.entities['p']['raw']['relationshipAttributes']['outputs'] = [{'guid': 'a'}]
        self.assertNotIn('process_ouverture_compte', self.answer())


if __name__ == '__main__':
    unittest.main()

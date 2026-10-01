"""User-facing ambiguity labels never expose Atlas identifiers."""
import unittest
from types import SimpleNamespace

from atlas_candidates import candidate_choices, candidate_clarification, candidate_options
from test_lineage_routing import load_functions


def entity(guid, kind, name, qualified):
    return {'guid': guid, 'typeName': kind, 'status': 'ACTIVE',
            'attributes': {'name': name, 'qualifiedName': qualified}}


class AmbiguityPresentationTests(unittest.TestCase):
    def setUp(self):
        self.columns = [
            entity('column-accounts', 'PostgreSQLColumn', 'id_compte', 'comptes.id_compte@projet_data_lineage'),
            entity('column-transactions', 'PostgreSQLColumn', 'id_compte', 'transactions.id_compte@projet_data_lineage'),
        ]

    def test_column_options_keep_internal_identifiers_but_show_business_labels(self):
        options = candidate_options(self.columns)
        self.assertEqual(options[0]['guid'], 'column-accounts')
        self.assertIn('comptes.id_compte@projet_data_lineage', options[0]['qualifiedName'])
        text = candidate_clarification(self.columns)
        self.assertIn('`id_compte` dans la table `comptes`', text)
        self.assertIn('`id_compte` dans la table `transactions`', text)
        self.assertNotIn('qualifiedName', text)
        self.assertNotIn('type Atlas', text)
        self.assertNotIn('GUID', text)

    def test_table_options_show_environments_only(self):
        tables = [
            entity('sqlite-transactions', 'SQLiteTable', 'transactions', 'transactions@transactions1.db'),
            entity('postgres-transactions', 'PostgreSQLTable', 'transactions', 'transactions@projet_data_lineage'),
        ]
        text = candidate_clarification(tables)
        self.assertIn('`transactions` dans SQLite', text)
        self.assertIn('`transactions` dans PostgreSQL', text)
        self.assertNotIn('qualifiedName', text)

    def test_impact_ambiguity_uses_business_clarification(self):
        n = load_functions()
        by_guid = {item['guid']: item for item in self.columns}
        n['st'] = SimpleNamespace(session_state={})
        n['atlas_get'] = lambda path, params=None: {'entityDefs': [{'name': 'PostgreSQLColumn'}]} if path.endswith('/types/typedefs') else {'entities': []}
        n['atlas_inventory_entities'] = lambda kind: list(self.columns) if kind == 'PostgreSQLColumn' else []
        n['get_entity'] = lambda guid: {'entity': by_guid[guid]}
        n['get_lineage'] = lambda guid, direction='BOTH', depth=10: {'relations': []}
        answer = n['entity_impact_answer']('Que se passe-t-il si je modifie id_compte ?')
        self.assertIn('La colonne `id_compte` existe dans plusieurs tables.', answer)
        self.assertIn('`id_compte` dans la table `comptes`', answer)
        self.assertNotIn('qualifiedName', answer)
        self.assertNotIn('GUID', answer)
        self.assertEqual(n['st'].session_state['pending_entity_ambiguity']['options'][0]['guid'], 'column-accounts')

    def test_choice_list_has_no_technical_identifiers(self):
        text = candidate_choices(self.columns)
        self.assertNotIn('qualifiedName', text)
        self.assertNotIn('type Atlas', text)
        self.assertNotIn('GUID', text)


if __name__ == '__main__':
    unittest.main()

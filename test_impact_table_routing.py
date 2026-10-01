"""Regression coverage for explicit table targets in impact questions."""
import unittest

from intent_routing import classify_intent
from test_lineage_routing import load_functions


class ImpactTableRoutingTests(unittest.TestCase):
    def setUp(self):
        self.api = load_functions()

    def assert_table_target(self, question, table):
        self.assertEqual(classify_intent(question), 'impact_analysis')
        self.assertEqual(self.api['requested_table_name'](question), table)
        self.assertIsNone(self.api['impact_column_name'](question))

    def test_comptes(self):
        self.assert_table_target(
            "Quel est l’impact d’une modification de la table comptes ?", "comptes"
        )

    def test_clients(self):
        self.assert_table_target(
            "Quel est l’impact d’une modification de la table clients ?", "clients"
        )

    def test_transactions(self):
        self.assert_table_target(
            "Quel est l’impact d’une modification de la table transactions ?", "transactions"
        )

    def test_explicit_column_in_table(self):
        question = "Quel est l’impact d’une modification de la colonne montant de la table transactions ?"
        self.assertEqual(classify_intent(question), 'impact_analysis')
        self.assertEqual(self.api['requested_table_name'](question), 'transactions')
        self.assertEqual(self.api['impact_column_name'](question), 'montant')
        self.assertEqual(self.api['impact_column_table'](question, 'montant'), 'transactions')


if __name__ == '__main__':
    unittest.main()

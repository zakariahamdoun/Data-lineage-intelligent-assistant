"""Focused tests for ambiguous-column impact requests (no Atlas server required)."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from test_lineage_routing import load_functions


def column(guid, table, name='id_compte'):
    return {
        'guid': guid,
        'typeName': 'PostgreSQLColumn',
        'status': 'ACTIVE',
        'attributes': {
            'name': name,
            'qualifiedName': f'{table}.{name}@projet_data_lineage',
        },
    }


class ImpactColumnAmbiguityTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.columns=[column('account-guid','comptes'),column('transaction-guid','transactions'),
                      column('amount-guid','transactions','montant')]
        self.n['atlas_inventory_entities']=lambda type_name: (
            self.columns if type_name=='PostgreSQLColumn' else [])
        self.n['st']=SimpleNamespace(session_state={})

    def test_ambiguous_column_waits_for_a_business_choice(self):
        impact=Mock(return_value='analyse qui ne doit pas être exécutée')
        self.n['entity_impact_answer']=impact
        answer=self.n['atlas_impact_analysis']('Quel est l’impact de la colonne id_compte ?')
        self.assertIn('La colonne `id_compte` existe dans plusieurs tables.',answer)
        self.assertNotIn('GUID',answer)
        self.assertNotIn('qualifiedName',answer)
        self.assertFalse(impact.called)
        pending=self.n['st'].session_state['pending_impact_candidates']
        self.assertEqual([option['guid'] for option in pending['options']],
                         ['account-guid','transaction-guid'])
        self.assertEqual([option['display_label'] for option in pending['options']],
                         ['`id_compte` dans la table `comptes`',
                          '`id_compte` dans la table `transactions`'])
        seen=[]
        self.n['entity_impact_answer']=Mock(side_effect=lambda *_: seen.append(
            self.n['st'].session_state['selected_ambiguous_entity_guid']) or 'impact comptes')
        # A rerun of the same question still returns only the clarification.
        self.assertEqual(self.n['atlas_impact_analysis'](pending['question']),answer)
        self.assertFalse(seen)
        self.n['st'].session_state['selected_impact_column_guid']='account-guid'
        self.assertEqual(self.n['impact_column_analysis_answer'](
            pending['question'],pending['source'],'id_compte'),'impact comptes')
        self.assertEqual(seen,['account-guid'])

    def test_explicit_account_table_uses_its_exact_guid(self):
        seen=[]
        self.n['entity_impact_answer']=Mock(side_effect=lambda *_: seen.append(
            self.n['st'].session_state['selected_ambiguous_entity_guid']) or 'impact comptes')
        answer=self.n['atlas_impact_analysis'](
            'Que se passe-t-il si je modifie id_compte de la table comptes ?')
        self.assertEqual(answer,'impact comptes')
        self.assertEqual(seen,['account-guid'])
        self.assertNotIn('pending_impact_candidates',self.n['st'].session_state)

    def test_explicit_transaction_table_uses_its_exact_guid(self):
        seen=[]
        self.n['entity_impact_answer']=Mock(side_effect=lambda *_: seen.append(
            self.n['st'].session_state['selected_ambiguous_entity_guid']) or 'impact transactions')
        answer=self.n['atlas_impact_analysis'](
            'Que se passe-t-il si je modifie id_compte dans la table transactions ?')
        self.assertEqual(answer,'impact transactions')
        self.assertEqual(seen,['transaction-guid'])

    def test_qualified_column_uses_its_exact_guid(self):
        seen=[]
        self.n['entity_impact_answer']=Mock(side_effect=lambda *_: seen.append(
            self.n['st'].session_state['selected_ambiguous_entity_guid']) or 'impact comptes')
        answer=self.n['atlas_impact_analysis']('Quel est l’impact de comptes.id_compte ?')
        self.assertEqual(answer,'impact comptes')
        self.assertEqual(seen,['account-guid'])

    def test_unique_column_in_explicit_table_needs_no_clarification(self):
        seen=[]
        self.n['entity_impact_answer']=Mock(side_effect=lambda *_: seen.append(
            self.n['st'].session_state['selected_ambiguous_entity_guid']) or 'impact montant')
        answer=self.n['atlas_impact_analysis'](
            'Que se passe-t-il si je modifie montant de la table transactions ?')
        self.assertEqual(answer,'impact montant')
        self.assertEqual(seen,['amount-guid'])
        self.assertNotIn('pending_impact_candidates',self.n['st'].session_state)

    def test_missing_column_returns_a_not_found_message(self):
        answer=self.n['atlas_impact_analysis']('Que se passe-t-il si je modifie colonne_inexistante ?')
        self.assertIn('Aucune colonne correspondante',answer)
        self.assertNotIn('Impossible de récupérer',answer)

    def test_atlas_http_error_is_not_misreported_as_an_ambiguity(self):
        def unavailable(_):
            raise requests.HTTPError('Atlas unavailable')
        self.n['atlas_inventory_entities']=unavailable
        with self.assertRaises(requests.HTTPError):
            self.n['atlas_impact_analysis']('Que se passe-t-il si je modifie id_compte ?')


if __name__=='__main__':
    unittest.main()

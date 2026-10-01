import re
import unittest

from entity_lineage import format_entity_lineage


class FormattingTests(unittest.TestCase):
    def test_introduction_presents_type_role_and_available_description(self):
        data = self.data()
        data['nodes']['a']['description'] = 'Fichier contenant les données à traiter.'
        answer = format_entity_lineage('a', {'OUTPUT': data}, {'CustomProcess'})
        first = answer.split('\n\n')[0]
        self.assertTrue(first.startswith('Le fichier `entree_variable` alimente les étapes suivantes'))
        self.assertIn(data['nodes']['a']['description'], first)
        self.assertLess(answer.index(first), answer.index('En aval'))

    def data(self, cycle=False):
        return {'nodes': {
            'a': {'name': 'entree_variable', 'typeName': 'hdfs_path'},
            'p': {'name': 'traitement_variable', 'typeName': 'CustomProcess'},
            'b': {'name': 'sortie_variable', 'typeName': 'PostgreSQLTable'},
        }, 'edges': [('a', 'p'), ('p', 'b')] + ([('b', 'a')] if cycle else []),
            'paths': [] if cycle else [['a', 'p', 'b']], 'cycles': cycle}

    def test_closed_facts_and_neutral_process(self):
        data = self.data()
        answer = format_entity_lineage('a', {'OUTPUT': data}, {'CustomProcess'})
        self.assertEqual(set(re.findall(r'`([^`]+)`', answer)),
                         {e['name'] for e in data['nodes'].values()})
        self.assertIn('Les données du fichier `entree_variable` passent ensuite par le processus `traitement_variable`.', answer)
        self.assertIn('entree_variable → traitement_variable → sortie_variable', answer)
        self.assertIn('destination finale est la table `sortie_variable`', answer)
        self.assertNotIn('Description renseignée', answer)
        self.assertNotRegex(answer, r'(?i)impact|risque|conséquence|modification|point de référence|sortie déclarée|destination finale enregistrée')
        self.assertNotRegex(answer, r'hdfs_path|CustomProcess|PostgreSQLTable|Types Atlas')
        self.assertNotRegex(answer, r'Aucune dépendance|aucune dépendance supplémentaire|transfert physique')
        self.assertEqual(answer, format_entity_lineage('a', {'OUTPUT': data}, {'CustomProcess'}))

    def test_description_comes_verbatim_from_metadata(self):
        data = self.data()
        description = 'Transformation documentée pour ce test uniquement.'
        data['nodes']['p']['description'] = description
        answer = format_entity_lineage('a', {'OUTPUT': data}, {'CustomProcess'})
        self.assertEqual(answer.count(description), 1)
        self.assertNotRegex(answer, r'Description renseignée|Selon les métadonnées|sortie déclarée')

    def test_nominal_description_is_integrated_without_new_facts(self):
        data = self.data()
        data['nodes']['p']['description'] = 'Processus de préparation réalisé avec un outil documenté : suppression des champs obsolètes.'
        answer = format_entity_lineage('a', {'OUTPUT': data}, {'CustomProcess'})
        self.assertIn('le processus `traitement_variable`, qui assure la préparation avec un outil documenté : suppression des champs obsolètes.', answer)
        self.assertNotRegex(answer, r'Description renseignée|Selon les métadonnées|sortie déclarée')
        self.assertLess(answer.index('passent ensuite'), answer.index('assure la préparation'))
        self.assertLess(answer.index('assure la préparation'), answer.index('À la sortie'))

    def test_cycle_has_no_fabricated_terminal(self):
        answer = format_entity_lineage('a', {'OUTPUT': self.data(True)}, {'CustomProcess'})
        self.assertIn('Un cycle est enregistré', answer)
        self.assertNotIn('La destination finale est', answer)

    def test_all_branch_destinations_are_retained(self):
        data = self.data()
        data['nodes']['c'] = {'name': 'autre_sortie', 'typeName': 'hdfs_path'}
        data['edges'].append(('p', 'c'))
        data['paths'].append(['a', 'p', 'c'])
        answer = format_entity_lineage('a', {'OUTPUT': data}, {'CustomProcess'})
        self.assertIn('entree_variable → traitement_variable → autre_sortie', answer)
        self.assertIn('Les destinations finales sont', answer)
        self.assertEqual(answer.count('passent ensuite par le processus'), 1)


if __name__ == '__main__':
    unittest.main()

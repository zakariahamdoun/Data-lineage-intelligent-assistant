import unittest
from test_lineage_routing import load_functions


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.api = load_functions()
        self.data = {'table': 'exemple', 'columns': [
            {'name': 'Champ A', 'type': 'object', 'description': 'Contient une référence externe.'},
            {'name': 'Champ B', 'type': 'int64', 'description': 'Identifiant de la ligne.'},
            {'name': 'Champ C', 'type': 'object', 'description': ''},
        ]}

    def test_prose_preserves_names_without_default_types(self):
        answer = self.api['format_atlas_columns'](self.data)
        self.assertEqual(answer.split('\n\n')[0], 'La table exemple contient les colonnes suivantes : Champ A, Champ B et Champ C.')
        self.assertIn(', tandis que Champ B', answer)
        for c in self.data['columns']:self.assertIn(c['name'], answer)
        self.assertNotRegex(answer, r'Type technique|object|int64|(?m:^- )')
        self.assertGreaterEqual(len(answer.split('\n\n')), 3)
        self.assertIn('sa description n’est pas renseignée', answer)

    def test_types_only_when_requested(self):
        answer = self.api['format_atlas_columns'](self.data, 'Quels sont les types des colonnes ?')
        self.assertIn('object', answer)
        self.assertIn('int64', answer)
        self.assertNotIn('Type technique', answer)

    def test_unknown_column_meaning_is_not_inferred_from_name(self):
        answer = self.api['column_meaning_text']({'name': 'Montant', 'description': ''}, 'exemple')
        self.assertNotIn('monétaire', answer)
        self.assertNotIn('semble', answer)

    def test_seven_documented_columns_form_three_linked_paragraphs(self):
        data = {'table': 'autre_table', 'columns': [
            {'name': f'Champ {i}', 'description': 'Contient une valeur documentée.'} for i in range(7)]}
        answer = self.api['format_atlas_columns'](data, 'Quelles sont les colonnes ?')
        paragraphs = answer.split('\n\n')
        self.assertEqual(len(paragraphs), 4)
        self.assertIn(', tandis que Champ 1', paragraphs[1])
        self.assertIn(' ; Champ 2', paragraphs[1])
        self.assertIn(', alors que Champ 4', paragraphs[2])
        self.assertTrue(paragraphs[3].startswith('Enfin, Champ 6'))

    def test_live_sqlite_columns(self):
        answer = self.api['chatbot']('Quelles sont les colonnes de la table transactions dans SQLite ?', 'sqlite')
        tables = self.api['find_requested_tables']('table transactions', 'sqlite')
        entity = next(e for engine, e in tables if engine == 'sqlite')
        data = self.api['table_metadata_context']('sqlite', entity)
        for c in data['columns']:self.assertIn(c['name'], answer)
        self.assertNotRegex(answer, r'Type technique|\bobject\b|\bint64\b|(?m:^- )')
        self.assertGreaterEqual(len(answer.split('\n\n')), 3)


if __name__ == '__main__':unittest.main()

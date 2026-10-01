"""Read-only column search regression checks against Atlas."""
import unittest
from test_lineage_routing import load_functions


class ColumnLookupTests(unittest.TestCase):
    def test_requested_questions(self):
        n=load_functions()
        n['context']=lambda *a:self.fail('Column lookup must precede FAISS')
        for question,column,tables in (
            ('Quel est le type de la colonne id_client ?','id_client',['clients','comptes']),
            ('Quel est le type de id_compte ?','id_compte',['transactions','comptes']),
            ('Dans quelle table se trouve id_agence ?','id_agence',['agences','comptes']),
            ('Quelles tables contiennent id_client ?','id_client',['clients','comptes'])):
            with self.subTest(question=question):
                self.assertEqual(n['requested_column'](question),column)
                self.assertEqual(n['transaction_source'](question),(None,False))
                self.assertEqual(n['catalogue_intent'](question),(None,None))
                answer=n['chatbot'](question,'postgresql')
                for table in tables:self.assertIn('Dans la table '+table+' de PostgreSQL',answer)
                self.assertIn(n['display_column_type']('numeric' if column=='solde' else 'integer'),answer)
                self.assertEqual(len(answer.split('\n\n')),len(tables))

    def test_absence_and_explicit_table(self):
        n=load_functions()
        self.assertIn('n’a pas été trouvée',n['chatbot']('Quel est le type de id_client_inexistant ?'))
        answer=n['chatbot']('Quel est le type de la colonne id_client dans la table comptes ?')
        self.assertIn('Dans la table comptes',answer);self.assertNotIn('Dans la table clients',answer)
        self.assertIsNone(n['requested_column']('Que contient la table comptes ?'))

    def test_atlas_error_is_not_absence(self):
        n=load_functions()
        def unavailable(*a,**k):raise RuntimeError('Atlas unavailable')
        n['atlas_get']=unavailable
        with self.assertRaises(RuntimeError):n['chatbot']('Quel est le type de id_client ?')

    def test_meaning_uses_explicit_table(self):
        n=load_functions()
        answer=n['chatbot']('Que signifie la colonne solde dans comptes ?','postgresql')
        self.assertIn('`solde`',answer)
        self.assertIn('`comptes`',answer)
        self.assertNotIn('Pour comprendre',answer)


if __name__=='__main__':unittest.main()

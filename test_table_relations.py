import unittest
from test_lineage_routing import load_functions


class RelationTests(unittest.TestCase):
    def test_live_relation_pairs(self):
        n=load_functions();n['Mistral']=None
        for question,key,process in (
            ('Quelle est la relation entre clients et comptes ?','comptes.id_client référence clients.id_client','process_ouverture_compte'),
            ('Pourquoi comptes est reliée à virements ?','virements.compte_source référence comptes.id_compte','process_execution_virement'),
            ('Quelle relation existe entre agences et comptes ?','comptes.id_agence référence agences.id_agence','process_ouverture_compte')):
            with self.subTest(question=question):
                answer=n['chatbot'](question)
                self.assertLessEqual(len(answer.split('\n\n')),3)
                self.assertIn(key,answer.replace('référence la clé primaire ', 'référence '));self.assertIn(process,answer)
                if 'clients et comptes' in question:
                    self.assertNotIn('agences',answer)

    def test_unrelated_process_not_included(self):
        n=load_functions();n['Mistral']=None
        answer=n['chatbot']('Quelle est la relation entre clients et agences ?')
        self.assertNotIn('process_ouverture_compte',answer)
        self.assertIn('Aucune relation directe',answer)


if __name__=='__main__':unittest.main()

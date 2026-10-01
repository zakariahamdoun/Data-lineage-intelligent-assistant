"""Explicit process lookup across Atlas types and file-only endpoints."""
import unittest
import test_process_role as fixtures
from intent_routing import classify_intent


class NamedProcessTests(unittest.TestCase):
    setUp=fixtures.ProcessRoleTests.setUp
    ask=fixtures.ProcessRoleTests.ask

    def test_five_requested_questions(self):
        self.state.update(active_table='transactions',active_table_guid='st')
        self.entities['prep']['attributes']['qualifiedName']='Preparation_transactions@projet_data_lineage'
        for question,expected in (
            ('Quelles sont les entrées et sorties du processus Preparation_transactions ?',
             'Le processus `Preparation_transactions` utilise `transactions_sep.xlsx` comme entrée et produit `transactions1.csv` comme sortie.'),
            ('Quelles sont les entrées et sorties de Chargement_SQLite ?',
             'Le processus `Chargement_SQLite` utilise `transactions1.csv` comme entrée et produit `transactions` comme sortie.'),
            ('Quel est le rôle de Preparation_transactions ?','Préparation des données.'),
            ('Quel processus produit transactions1.csv ?','Preparation_transactions'),
            ('Quel processus utilise transactions1.csv ?','Chargement_SQLite')):
            with self.subTest(question=question):
                answer=self.ask(question)
                self.assertIn(expected,answer)
                self.assertNotIn('Other_loader',answer)

    def test_custom_inherited_type_and_qualified_name(self):
        self.entities['prep']['typeName']='CustomPreparation'
        self.entities['prep']['attributes'].update(name='Nettoyage',qualifiedName='workflow.prepare@arbitrary_namespace')
        original=self.n['requests'].get
        def get(url,params,**kw):
            response=original(url,params,**kw)
            if url.endswith('/types/typedefs'):
                response.json=lambda:{'entityDefs':[{'name':'Pipeline','superTypes':['Process']},
                                                  {'name':'CustomPreparation','superTypes':['Pipeline']}]}
            return response
        self.n['requests'].get=get
        for name in ('Nettoyage','workflow.prepare@arbitrary_namespace'):
            answer=self.ask('Quelles sont les entrées et sorties du processus '+name+' ?')
            self.assertIn('`Nettoyage`',answer)
            self.assertIn('transactions_sep.xlsx',answer)
        self.assertEqual(classify_intent('Quelles sont les entrées et sorties de Chargement_SQLite ?'),'input_output')

        self.assertIn('Préparation des données',self.ask('Quel est le rôle de Nettoyage ?'))

    def test_multiple_deleted_and_absent_endpoints(self):
        self.entities['prep']['attributes']['inputs'].extend([{'guid':'csv'},{'guid':'xlsx'},
                                                             {'guid':'pt','relationshipStatus':'DELETED'}])
        answer=self.ask('Quelles sont les entrées et sorties du processus Preparation_transactions ?')
        self.assertIn('`transactions_sep.xlsx`',answer)
        self.assertIn('`transactions1.csv`',answer)
        self.assertEqual(answer.count('`transactions_sep.xlsx`'),1)
        self.assertNotIn('comptes',answer)
        self.entities['prep']['attributes']['inputs']=[]
        answer=self.ask('Quelles sont les entrées et sorties du processus Preparation_transactions ?')
        self.assertIn('entrée non renseignée',answer)
        self.assertNotIn('transactions_sep.xlsx',answer)
        self.assertNotIn('Chargement_SQLite',self.ask('Quelles sont les entrées et sorties de Missing_job ?'))

    def test_qualified_name_disambiguates(self):
        import copy
        self.entities['prep']['attributes']['qualifiedName']='Preparation_transactions@one'
        other=copy.deepcopy(self.entities['prep']);other['guid']='duplicate'
        other['attributes']['qualifiedName']='Preparation_transactions@two'
        self.entities['duplicate']=other
        self.assertIn('Plusieurs processus',self.ask('Quelles sont les entrées et sorties du processus Preparation_transactions ?'))
        answer=self.ask('Quelles sont les entrées et sorties du processus Preparation_transactions@two ?')
        self.assertNotIn('Plusieurs processus',answer)
        self.assertIn('transactions_sep.xlsx',answer)


if __name__=='__main__':unittest.main()

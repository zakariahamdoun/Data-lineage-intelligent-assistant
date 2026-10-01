import json
import unittest
from test_lineage_routing import load_functions


class ProcessLookupTests(unittest.TestCase):
    def test_live_aliases(self):
        n=load_functions()
        n['context']=lambda *a:self.fail('Aliases must bypass FAISS')
        variants={
            'process_ouverture_compte': ['process_ouverture_compte','ouverture_compte',
                'ouverture de compte','processus ouverture_compte','processus d’ouverture de compte',
                'OUVERTURE-DE-COMPTE'],
            'process_comptes_transactions':['comptes_transactions','process_comptes_transactions'],
            'process_execution_virement':['execution_virement','process_execution_virement','exécution de virement']}
        for expected,aliases in variants.items():
            description=n['atlas_get']('/api/atlas/v2/entity/uniqueAttribute/type/Process',{'attr:qualifiedName':expected+'@projet_data_lineage'})['entity']['attributes']['description']
            for alias in aliases:
                with self.subTest(alias=alias):
                    answer=n['chatbot']('Qu’est-ce que le '+alias+' ?')
                    self.assertEqual(description,answer)
                    self.assertNotIn('@projet_data_lineage',answer)
        self.assertEqual(n['chatbot']('process_ouverture_compte'),n['chatbot']('ouverture de compte'))

    def test_normalization_and_unknown_name(self):
        n=load_functions()
        self.assertEqual(n['normalize_process_name']('PROCESSUS D’EXÉCUTION-DE-VIREMENT'), 'execution_virement')
        n['atlas_process_inventory']=lambda:[{'guid':'p','name':'process_ouverture_compte'}]
        n['detail']=lambda *a:self.fail('Unrelated process must not match')
        self.assertIsNone(n['process_answer']('ouverture de compteur'))

    def test_direct_lookup(self):
        n=load_functions()
        payload={'entity':{'guid':'p','typeName':'CustomJob','attributes':{
            'name':'process_test_complet','description':'Description dynamique',
            'businessRule':'Regle dynamique','inputs':[{'guid':'a'}],'outputs':[{'guid':'b'}]}},
            'referredEntities':{'a':{'guid':'a','attributes':{'name':'entree'}},
                                'b':{'guid':'b','attributes':{'name':'sortie'}}}}
        process=n['detail']('p',payload)
        n['atlas_process_inventory']=lambda:[process]
        n['get_entity']=lambda guid:{'entity':payload['referredEntities'][guid]}
        n['atlas_get']=lambda *args:self.fail('No assumed Process type or database suffix')
        self.assertEqual(n['process_answer']('Explique process_test_complet'),'Description dynamique')
        self.assertEqual(n['process_answer']('Regle metier de process_test_complet'),'Regle dynamique')
        # The public endpoint handler recognizes both French and English endpoint terms.
        answer=n['named_process_endpoints']([process],'inputs outputs')
        self.assertEqual(answer,'Le processus `process_test_complet` utilise `entree` comme entrée et produit `sortie` comme sortie.')
        for word in ('lineage','parcours','cheminement'):
            answer=n['process_answer'](word+' de process_test_complet')
            for value in ('Description dynamique','entree','process_test_complet','sortie'):
                self.assertIn(value,answer)

    def test_live_question_and_index(self):
        n=load_functions()
        n['context']=lambda *a:self.fail('Unexpected FAISS lookup')
        payload=n['atlas_get']('/api/atlas/v2/entity/uniqueAttribute/type/Process',
                              {'attr:qualifiedName':'process_ouverture_compte@projet_data_lineage'})
        answer=n['chatbot']('Qu’est-ce que process_ouverture_compte ?')
        self.assertIn(payload['entity']['attributes']['description'].rstrip('.'),answer)
        self.assertEqual(payload['entity']['attributes']['description'],answer)
        self.assertNotIn(payload['entity']['guid'],answer)
        self.assertNotIn('@projet_data_lineage',answer)
        docs=[json.loads(doc) for doc in n['docs_atlas']()]
        self.assertTrue(any(doc['guid']==payload['entity']['guid'] and doc['typeName']=='Process' for doc in docs))


if __name__=='__main__':unittest.main()

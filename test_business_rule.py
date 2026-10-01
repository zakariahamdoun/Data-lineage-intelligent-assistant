"""Direct Atlas business-rule routing and index regression checks."""
import json
import unittest
from test_lineage_routing import load_functions


class BusinessRuleTests(unittest.TestCase):
    def test_direct_lookup_variants(self):
        n=load_functions()
        calls=[]
        rule='Règle issue du catalogue de test, modifiable sans changer le chatbot.'
        def atlas(path,params):
            calls.append((path,params))
            return {'entity':{'attributes':{'businessRule':rule}}}
        n['atlas_get']=atlas
        n['context']=lambda *a:self.fail('FAISS must not handle an explicit rule request')
        for question in ('Quelle est la règle métier de la table comptes ?',
                         'Donne-moi la règle métier de comptes',
                         'Quelles sont les règles métier de comptes ?',
                         'Quelle est la règle métier de la table `comptes@projet_data_lineage` ?'):
            self.assertEqual(n['chatbot'](question),rule)
        self.assertTrue(all(path.endswith('/type/PostgreSQLTable') and
                            params=={'attr:qualifiedName':'comptes@projet_data_lineage'}
                            for path,params in calls))
        rule='Nouvelle valeur Atlas'
        self.assertEqual(n['chatbot']('Donne-moi la règle métier de comptes'),rule)

    def test_empty_attribute(self):
        n=load_functions()
        for attrs in ({},{'businessRule':None},{'businessRule':''},{'businessRule':'  '}):
            n['atlas_get']=lambda *a:{'entity':{'attributes':attrs}}
            self.assertEqual(n['chatbot']('Quelles sont les règles métier de commandes ?'),
                'Aucune règle métier n’est renseignée pour la table commandes dans Apache Atlas.')

    def test_live_rule_and_index(self):
        n=load_functions()
        entity=n['atlas_get']('/api/atlas/v2/entity/uniqueAttribute/type/PostgreSQLTable',
                             {'attr:qualifiedName':'comptes@projet_data_lineage'})['entity']
        expected=entity['attributes']['businessRule']
        self.assertTrue(expected.strip())
        n['context']=lambda *a:self.fail('Unexpected FAISS lookup')
        self.assertEqual(n['chatbot']('Quelle est la règle métier de la table comptes ?'),expected)
        documents=[json.loads(doc) for doc in n['docs_atlas']()]
        table=next(doc for doc in documents if doc['guid']==entity['guid'])
        self.assertEqual(table['Règle métier'],expected)
        self.assertEqual(table['texte_regle_metier'],'Règle métier : '+expected)
        self.assertTrue(all('texte_regle_metier' in doc for doc in documents))


if __name__=='__main__':unittest.main()

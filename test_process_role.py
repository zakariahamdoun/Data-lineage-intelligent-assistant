"""Role/position lookup follows scoped Atlas edges, not fixed process names."""
import unittest
from types import SimpleNamespace
import test_database_context as fixtures
from intent_routing import classify_intent


class ProcessRoleTests(unittest.TestCase):
    ask=fixtures.DatabaseContextTests.ask

    def setUp(self):
        fixtures.DatabaseContextTests.setUp(self)
        self.entities.pop('pr')
        for guid,kind,name,attrs in (
            ('xlsx','hdfs_path','transactions_sep.xlsx',{}),
            ('csv','hdfs_path','transactions1.csv',{}),
            ('prep','Process','Preparation_transactions',{'inputs':[{'guid':'xlsx'}],'outputs':[{'guid':'csv'}],'description':'Préparation des données.'}),
            ('load','Process','Chargement_SQLite',{'inputs':[{'guid':'csv'}],'outputs':[{'guid':'st'}]}),
            ('pg','Process','Other_loader',{'inputs':[{'guid':'pc'}],'outputs':[{'guid':'pt'}]})):
            self.entities[guid]=fixtures.entity(guid,kind,name,**attrs)
        original=self.fetch
        self.extra_edges=[]
        def fetch(path,params=None):
            if '/lineage/' in path:
                edges=[]
                for guid,e in self.entities.items():
                    attrs=e['attributes']
                    edges.extend({'fromEntityId':r['guid'],'toEntityId':guid} for r in attrs.get('inputs',[]))
                    edges.extend({'fromEntityId':guid,'toEntityId':r['guid']} for r in attrs.get('outputs',[]))
                return {'guidEntityMap':self.entities,'relations':edges+self.extra_edges}
            return original(path,params)
        self.n['requests']=SimpleNamespace(get=lambda url,params,**kw:SimpleNamespace(
            raise_for_status=lambda:None,json=lambda:fetch(url.replace(self.n['ATLAS_URL'],''),params)))
        self.state.update(active_database='sqlite',active_chat_source='sqlite')

    def test_requested_questions(self):
        for question,expected in (
            ('Quel processus a préparé les données avant le chargement dans SQLite ?','Preparation_transactions'),
            ('Quelle étape précède Chargement_SQLite ?','Preparation_transactions'),
            ('Quel processus produit transactions1.csv ?','Preparation_transactions'),
            ('Quel processus utilise transactions1.csv ?','Chargement_SQLite'),
            ('Que se passe-t-il avant la création de la table transactions ?','Preparation_transactions'),
            ('Quel processus prépare le fichier utilisé pour SQLite ?','Preparation_transactions')):
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question),'process_details')
                answer=self.ask(question)
                self.assertIn('`'+expected+'`',answer)
                self.assertIn('`transactions1.csv`',answer)
                self.assertNotIn('Other_loader',answer)
                self.assertNotIn('introuvable',answer)
        answer=self.ask('Quel processus a préparé les données avant le chargement dans SQLite ?')
        for name in ('transactions_sep.xlsx','Preparation_transactions','transactions1.csv','Chargement_SQLite'):
            self.assertIn('`'+name+'`',answer)

    def test_renaming_and_downstream(self):
        self.entities['prep']['attributes']['name']='Nettoyage_dynamique'
        self.entities['load']['attributes']['name']='Import_dynamique'
        answer=self.ask('Quel processus intervient avant Import_dynamique ?')
        self.assertIn('Nettoyage_dynamique',answer)
        self.assertNotIn('Preparation_transactions',answer)
        answer=self.ask('Quelle étape suit Nettoyage_dynamique ?')
        self.assertIn('`Import_dynamique`',answer)

    def test_branching_cycles_and_missing_edges(self):
        self.entities['prep2']=fixtures.entity('prep2','Process','Autre_preparation',inputs=[{'guid':'xlsx'}],outputs=[{'guid':'csv'}])
        answer=self.ask('Quelle étape précède Chargement_SQLite ?')
        self.assertIn('Autre_preparation',answer)
        self.assertIn('Preparation_transactions',answer)
        self.entities['prep']['attributes']['inputs'].append({'guid':'st'})
        answer=self.ask('Que se passe-t-il avant la création de la table transactions ?')
        self.assertEqual(answer.count('Le processus `Preparation_transactions`'),1)
        self.entities.pop('prep');self.entities.pop('prep2')
        self.assertIn('Aucun processus en amont',self.ask('Quelle étape précède Chargement_SQLite ?'))

    def test_loader_ambiguity_and_priority(self):
        self.entities['extra']=fixtures.entity('extra','Process','Second_import',inputs=[{'guid':'xlsx'}],outputs=[{'guid':'st'}])
        answer=self.ask('Quel processus a préparé les données avant le chargement dans SQLite ?')
        self.assertIn('Plusieurs processus de chargement',answer)
        self.assertEqual(classify_intent('Quel impact si le processus est supprimé avant le chargement ?'),'impact_analysis')
        self.assertEqual(classify_intent('Quels processus sont disponibles dans SQLite ?'),'process_list')
        self.assertNotIn('Preparation_transactions',self.ask('Quelle étape précède Inconnu ?'))

    def test_lineage_only_process_links(self):
        self.entities['prep']['attributes'].pop('inputs')
        self.entities['prep']['attributes'].pop('outputs')
        self.extra_edges=[{'fromEntityId':'xlsx','toEntityId':'prep'},
                          {'fromEntityId':'prep','toEntityId':'csv'}]
        answer=self.ask('Quelle étape précède Chargement_SQLite ?')
        self.assertIn('Preparation_transactions',answer)
        self.assertIn('transactions_sep.xlsx',answer)
        self.assertIn('transactions1.csv',answer)


if __name__=='__main__':unittest.main()

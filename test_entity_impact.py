import unittest
from types import SimpleNamespace
from test_lineage_routing import load_functions


class EntityImpactTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        names=['transactions_sep.xlsx','Preparation_transactions','transactions1.csv','Chargement_SQLite','transactions']
        kinds=['CustomFile','Process','CustomFile','Process','SQLiteTable']
        self.entities={str(i):{'guid':str(i),'typeName':kind,'attributes':{'name':name},'status':'ACTIVE'}
                       for i,(name,kind) in enumerate(zip(names,kinds))}
        self.n['atlas_get']=lambda *args:{'entityDefs':[{'name':kind} for kind in kinds]}
        self.n['atlas_inventory_entities']=lambda kind:[e for e in self.entities.values() if e['typeName']==kind]
        self.n['get_entity']=lambda guid:{'entity':self.entities[guid]}
        self.n['get_lineage']=lambda guid,*args:{'relations':[
            {'fromEntityId':guid,'toEntityId':str(int(guid)+1)}] if int(guid)<4 else []}
        self.n['st']=SimpleNamespace(session_state={})

    def test_file_without_active_database(self):
        answer=self.n['chat_message']('Si transactions1.csv est modifié, quel objet en aval peut être impacté ?')['content']
        self.assertIn('transactions1.csv → Chargement_SQLite → transactions',answer)
        self.assertIn('SQLiteTable',answer)
        self.assertIn('peut potentiellement impacter',answer)
        self.assertNotIn('Précisez',answer)

    def test_recursive_impact_from_initial_file(self):
        answer=self.n['chatbot']('Quel est l’impact d’une modification de transactions_sep.xlsx ?')
        self.assertIn('transactions_sep.xlsx → Preparation_transactions → transactions1.csv → Chargement_SQLite → transactions',answer)

    def test_processes_are_separate_from_data_objects(self):
        answer=self.n['chatbot']('Si transactions1.csv est modifié, quels objets sont impactés ?')
        objects=answer.split('Objets de données potentiellement impactés :')[1].split('Processus concernés :')[0]
        processes=answer.split('Processus concernés :')[1].split('Parcours :')[0]
        self.assertIn('transactions (SQLiteTable)',objects)
        self.assertNotIn('Chargement_SQLite',objects)
        self.assertIn('Chargement_SQLite (Process)',processes)
        self.assertNotIn('transactions (SQLiteTable)',processes)

    def test_explicit_singular_conclusion(self):
        answer=self.n['chatbot']('Si transactions1.csv est modifié, quels objets sont impactés ?')
        conclusion=answer.split('Objet de départ :')[0]
        self.assertIn('Une modification de `transactions1.csv` peut potentiellement impacter la table `transactions`',conclusion)
        self.assertIn('en aval',answer.split('Conclusion :')[1])
        self.assertNotIn('effet physique',answer)
        self.assertNotIn('Chargement_SQLite',conclusion)

    def test_explicit_plural_conclusion(self):
        answer=self.n['chatbot']('Quel est l’impact d’une modification de transactions_sep.xlsx ?')
        conclusion=answer.split('Objet de départ :')[0]
        self.assertIn('peut potentiellement impacter',conclusion)
        self.assertIn('transactions1.csv',conclusion)
        self.assertIn('le fichier `transactions1.csv`, puis la table `transactions`',conclusion)
        self.assertNotIn('Preparation_transactions',conclusion)
        self.assertNotIn('Chargement_SQLite',conclusion)

    def test_branches_do_not_imply_a_sequential_path(self):
        self.n['get_lineage']=lambda guid,*args:{'relations':[
            {'fromEntityId':'0','toEntityId':'2'}, {'fromEntityId':'0','toEntityId':'4'}] if guid=='0' else []}
        conclusion=self.n['chatbot']('Quel impact si transactions_sep.xlsx est modifié ?').split('Objet de départ :')[0]
        self.assertIn('transactions1.csv',conclusion)
        self.assertIn('`transactions`',conclusion)
        self.assertNotIn('puis',conclusion)

    def test_deletion_conclusion_preserves_requested_action(self):
        conclusion=self.n['chatbot']('Si transactions1.csv est supprimé, quel impact ?').split('Objet de départ :')[0]
        self.assertIn('Une suppression de `transactions1.csv`',conclusion)

    def test_process_only_is_not_concluded_as_data_impact(self):
        self.n['get_lineage']=lambda guid,*args:{'relations':[
            {'fromEntityId':'2','toEntityId':'3'}] if guid=='2' else []}
        answer=self.n['chatbot']('Si transactions1.csv est modifié, quels objets sont impactés ?')
        self.assertTrue(answer.startswith('Aucun objet de données potentiellement impacté'))
        self.assertNotIn('Objets de données potentiellement impactés :',answer)
        self.assertNotIn('Conclusion :',answer)

    def test_process_subtype_uses_atlas_inheritance(self):
        self.entities['3']['typeName']='LoadJob'
        self.n['atlas_get']=lambda *args:{'entityDefs':[{'name':'LoadJob','superTypes':['ETL']},
            {'name':'ETL','superTypes':['Process']},{'name':'CustomFile'}]}
        answer=self.n['chatbot']('Si transactions1.csv est modifié, quels objets sont impactés ?')
        objects,processes=answer.split('Processus concernés :')
        self.assertNotIn('Chargement_SQLite',objects)
        self.assertIn('Chargement_SQLite (LoadJob)',processes)

    def test_process_and_terminal_table(self):
        answer=self.n['chatbot']('Si Chargement_SQLite est supprimé, quels objets sont affectés ?')
        self.assertIn('Chargement_SQLite → transactions',answer)
        self.assertNotIn('Processus concernés :',answer)
        self.assertTrue(answer.startswith('Une suppression de `Chargement_SQLite` peut potentiellement impacter la table `transactions`'))
        answer=self.n['chatbot']('Si la table transactions est modifiée, quels objets sont concernés ?')
        self.assertIn('Aucune dépendance en aval',answer)
        self.assertIn('transactions',answer)
        self.assertNotIn('Parcours :',answer)
        self.assertNotIn('Conclusion :',answer)


if __name__=='__main__':unittest.main()

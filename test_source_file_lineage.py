import unittest
from test_lineage_routing import load_functions


class SourceFileTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        names=['transactions_sep.xlsx','Preparation_transactions','transactions1.csv','Chargement_SQLite','transactions','transactions1.db']
        kinds=['File','Process','File','Process','SQLiteTable','SQLiteDatabase']
        self.entities={str(i):{'guid':str(i),'typeName':kind,'attributes':{'name':name},'status':'ACTIVE'}
                       for i,(name,kind) in enumerate(zip(names,kinds))}
        self.entities['4']['attributes']['database']={'guid':'5'}
        self.n['atlas_inventory_entities']=lambda kind:[e for e in self.entities.values() if e['typeName']==kind]
        self.n['get_entity']=lambda guid:{'entity':self.entities[guid]}
        self.n['get_lineage']=lambda guid,*args:{'relations':[
            {'fromEntityId':str(int(guid)-1),'toEntityId':guid}] if 0<int(guid)<5 else []}

    def test_database_and_table_questions(self):
        for question in ('Quel est le fichier source de transactions1.db ?',
                         'Quel fichier alimente transactions ?',
                         'D’où proviennent les données de transactions1.db ?'):
            answer=self.n['chatbot'](question)
            self.assertIn('Fichier source direct : transactions1.csv.',answer)
            self.assertIn('Source initiale enregistrée : transactions_sep.xlsx.',answer)
            self.assertIn('transactions_sep.xlsx → Preparation_transactions → transactions1.csv → Chargement_SQLite → transactions',answer)
            self.assertNotIn('transactions → transactions1.db',answer)

    def test_requested_database_and_contained_table_are_distinguished(self):
        answer=self.n['chatbot']('Quel est le fichier source de transactions1.db ?')
        self.assertIn('Base concernée : transactions1.db.',answer)
        self.assertIn('Table alimentée : transactions.',answer)
        self.assertIn('Cette table appartient à la base transactions1.db',answer)
        self.assertIn('Chargement_SQLite → transactions (transactions1.db)',answer)
        self.assertIn('Parcours :',answer)

    def test_table_request_does_not_invent_database_label(self):
        answer=self.n['chatbot']('Quel fichier alimente transactions ?')
        self.assertIn('Objet concerné : transactions.',answer)
        self.assertNotIn('Base concernée : transactions.',answer)

    def test_unattached_table_is_not_substituted_for_database(self):
        self.entities['4']['attributes'].pop('database')
        answer=self.n['chatbot']('Quel est le fichier source de transactions1.db ?')
        self.assertIn('transactions1.db',answer)
        self.assertNotIn('Table alimentée',answer)
        self.assertNotIn('transactions1.csv',answer)

    def test_no_fabricated_source(self):
        self.n['get_lineage']=lambda *args:{'relations':[]}
        answer=self.n['chatbot']('Quel fichier alimente transactions1.db ?')
        self.assertIn('Aucun fichier source ni parcours',answer)
        self.assertNotIn('transactions1.csv',answer)


if __name__=='__main__':unittest.main()

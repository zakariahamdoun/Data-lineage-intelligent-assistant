import unittest
from intent_routing import classify_intent, table_producer_request
from test_lineage_routing import load_functions


QUESTIONS=(
    'Quel processus crée ou alimente la table comptes ?',
    'Quel processus alimente la table comptes ?',
    'Quel processus crée la table comptes ?',
    'Par quel processus comptes est-elle alimentée ?',
    'Quel processus produit comptes ?',
)


class TableProducerTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.entities={g:{'guid':g,'name':g,'typeName':'Process' if g.startswith('p') else 'PostgreSQLTable',
                          'status':'ACTIVE','description':'','raw':{'relationshipAttributes':{}}}
                       for g in ('target','left','right','p_maker','p_consumer')}
        self.entities['p_maker']['description']='Opération décrite dans Atlas.'
        self.entities['p_maker']['raw']['relationshipAttributes']={
            'inputs':[{'guid':'left'},{'guid':'right'}],'outputs':[{'guid':'target'}]}
        self.entities['target']['raw']['relationshipAttributes']={'inputToProcesses':[{'guid':'p_consumer'}]}
        self.n['find_requested_tables']=lambda *a:[('postgresql',{'guid':'target'})]
        self.n['detail']=self.entities.__getitem__
        self.calls=[]
        def graph(guid,direction,depth):
            self.calls.append((guid,direction,depth))
            return {'relations':[{'fromEntityId':'p_maker','toEntityId':'target'}]}
        self.n['get_lineage']=graph
        self.n['process_answer']=lambda *a:self.fail('Must not search for a process name')

    def test_variants_use_upstream_and_all_inputs(self):
        for q in QUESTIONS:
            self.assertEqual(classify_intent(q),'lineage')
            answer=self.n['chatbot'](q)
            self.assertIn('left + right → p_maker → target',answer)
            self.assertIn('Opération décrite dans Atlas.',answer)
            self.assertNotIn('p_consumer',answer)
        self.assertEqual(self.calls,[('target','INPUT',2)]*len(QUESTIONS))

    def test_relationship_only_and_multiple_producers(self):
        self.n['get_lineage']=lambda *a:{'relations':[]}
        self.entities['target']['raw']['relationshipAttributes']['outputFromProcesses']=[{'guid':'p_maker'},{'guid':'p_other'}]
        self.entities['p_other']={'guid':'p_other','name':'p_other','typeName':'Process','status':'ACTIVE',
                                  'raw':{'relationshipAttributes':{'inputs':[{'guid':'right'}],'outputs':[{'guid':'target'}]}}}
        answer=self.n['chatbot'](QUESTIONS[0])
        self.assertIn('left + right → p_maker → target',answer)
        self.assertIn('right → p_other → target',answer)

    def test_missing_producer(self):
        self.n['get_lineage']=lambda *a:{'relations':[]}
        self.assertIn('Aucun processus producteur',self.n['chatbot'](QUESTIONS[0]))

    def test_downstream_does_not_need_to_be_loaded(self):
        del self.entities['p_consumer']
        self.assertIn('left + right → p_maker → target',self.n['chatbot'](QUESTIONS[0]))

    def test_missing_inputs_description_and_deleted_links(self):
        self.entities['p_maker']['description']=''
        self.entities['p_maker']['raw']['relationshipAttributes']['inputs']=[{'guid':'left','relationshipStatus':'DELETED'}]
        answer=self.n['chatbot'](QUESTIONS[0])
        self.assertIn('entrées non renseignées',answer)
        self.assertNotIn('left',answer)
        self.assertNotIn('Opération',answer)
        self.entities['p_maker']['status']='DELETED'
        self.assertIn('Aucun processus producteur',self.n['chatbot'](QUESTIONS[0]))

    def test_missing_or_ambiguous_table(self):
        self.n['find_requested_tables']=lambda *a:[]
        self.assertIn('table demandée n’a pas été trouvée',self.n['chatbot'](QUESTIONS[0]))
        self.n['find_requested_tables']=lambda *a:[('postgresql',{'guid':'a'}),('postgresql',{'guid':'b'})]
        self.assertIn('Plusieurs tables',self.n['chatbot'](QUESTIONS[0]))

    def test_other_requests_unchanged(self):
        for q in ('Décris le processus process_test', 'Quel est le rôle du processus process_test ?',
                  'Quelles sont les entrées du processus qui produit comptes ?',
                  'Quel processus utilise la table comptes ?', 'Quel processus produit le fichier test.csv ?',
                  'Quel processus produit transactions1.csv ?',
                  'Explique le lineage complet de la base PostgreSQL'):
            self.assertFalse(table_producer_request(q),q)


if __name__=='__main__':unittest.main()

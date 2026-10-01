"""Offline checks for directed paths with homonymous Atlas endpoints."""
import unittest
from test_lineage_routing import load_functions


class BetweenEntitiesTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.data={}
        for guid,name,typ,system,rels in (
            ('a','origin','PostgreSQLTable','one',{'inputToProcesses':[{'guid':'p'}]}),
            ('p','prepare','Process','one',{'outputs':[{'guid':'b'}],'inputs':[{'guid':'a'},{'guid':'extra'}]}),
            ('b','middle','PostgreSQLTable','one',{'inputToProcesses':[{'guid':'q'}]}),
            ('q','load','Process','one',{'outputs':[{'guid':'z'}]}),
            ('z','target','PostgreSQLTable','one',{}),
            ('sqlite','target','SQLiteTable','two',{}),
            ('extra','secondary','PostgreSQLTable','one',{}),
        ):
            self.data[guid]={'guid':guid,'name':name,'typeName':typ,'qualifiedName':name+'@'+system,
                             'raw':{'relationshipAttributes':rels}}
        self.n['detail']=self.data.__getitem__
        def search(url,params):
            return {'entities':[{'guid':g,'typeName':e['typeName'],
                                 'attributes':{'name':e['name'],'qualifiedName':e['qualifiedName']}}
                                for g,e in self.data.items()
                                if ('process' in e['typeName'].lower())==(params['typeName']=='Process')]}
        self.n['atlas_get']=search
        self.n['get_lineage']=lambda *a:{'relations':[]}

    def test_unique_path_ignores_stale_source_and_secondary_input(self):
        question='Présente le parcours de origin jusqu’à target.'
        self.assertEqual(self.n['lineage_route'](question,'sqlite'),('text',None,False))
        answer=self.n['chatbot'](question,'sqlite')
        self.assertIn('origin → prepare → middle → load → target',answer)
        self.assertNotIn('secondary',answer)
        self.assertNotIn('Précisez',answer)

    def test_between_stops_at_destination_and_omits_context(self):
        question='Quel est le parcours entre origin et middle ?'
        self.assertEqual(self.n['requested_lineage_endpoints'](question),('origin','middle'))
        self.data['p']['description']='Utilise secondary pour alimenter target.'
        answer=self.n['chatbot'](question)
        self.assertIn('La table origin intervient en amont de la table middle.',answer)
        self.assertIn('origin → prepare → middle',answer)
        for excluded in ('secondary','target','load','Rôle général','Clés étrangères','transfert physique'):
            self.assertNotIn(excluded,answer)

    def test_lineage_only_path(self):
        for item in self.data.values():item['raw']['relationshipAttributes']={}
        edges=[('a','p'),('p','b'),('b','q'),('q','z')]
        self.n['get_lineage']=lambda guid,*a:{'relations':[{'fromEntityId':x,'toEntityId':y} for x,y in edges if x==guid]}
        answer=self.n['chatbot']('Quel est le parcours entre origin et middle ?')
        self.assertIn('origin → prepare → middle',answer)
        self.assertNotIn('load',answer)

    def test_explicit_tables_and_chat_session(self):
        from types import SimpleNamespace
        self.n['st']=SimpleNamespace(session_state={'active_database':'sqlite','active_table':'target'})
        q='Quel est le parcours entre la table origin et la table middle ?'
        self.assertEqual(self.n['requested_lineage_endpoints'](q),('origin','middle'))
        self.assertIn('origin → prepare → middle',self.n['chat_message'](q)['content'])

    def test_no_reverse_path_and_cycle_terminates(self):
        self.data['b']['raw']['relationshipAttributes']['inputToProcesses'].append({'guid':'p'})
        answer=self.n['chatbot']('Présente le parcours de origin jusqu’à target.')
        self.assertIn('middle → load → target',answer)
        answer=self.n['chatbot']('Présente le parcours de target jusqu’à origin.')
        self.assertIn('Aucun chemin dirigé',answer)

    def test_ambiguity_only_for_valid_disjoint_paths(self):
        self.data['a2']={'name':'origin','typeName':'SQLiteTable','qualifiedName':'origin@two',
                         'raw':{'relationshipAttributes':{'inputToProcesses':[{'guid':'p2'}]}}}
        self.data['p2']={'name':'other_job','typeName':'Process','qualifiedName':'other_job@two',
                         'raw':{'relationshipAttributes':{'outputs':[{'guid':'sqlite'}]}}}
        answer=self.n['chatbot']('Présente le parcours de origin jusqu’à target.')
        self.assertIn('Plusieurs parcours valides',answer)
        answer=self.n['chatbot']('Présente le parcours de origin jusqu’à target dans PostgreSQL.')
        self.assertIn('origin → prepare → middle → load → target',answer)
        self.assertNotIn('Précisez',answer)
        answer=self.n['chatbot']('Présente le parcours de origin@two jusqu’à target@two.')
        self.assertIn('origin → other_job → target',answer)


if __name__=='__main__':unittest.main()

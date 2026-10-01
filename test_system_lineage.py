import unittest
from system_lineage import read_system_lineage, describe_system_lineage
from test_lineage_routing import load_functions


class SystemLineageTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.items={}
        for key in ('alpha','beta','hub','end_one','end_two','extra','p_join','p_left','p_right'):
            kind='Process' if key.startswith('p_') else 'PostgreSQLTable'
            self.items[key]={'guid':key,'name':key,'typeName':kind,'status':'ACTIVE',
                             'description':'','raw':{'relationshipAttributes':{}}}
        self.relations('p_join',['alpha','beta'],['hub'])
        self.relations('p_left',['hub'],['end_one','extra'])
        self.relations('p_right',['hub'],['end_two'])
        self.items['p_join']['description']='Opération documentée dans Atlas.'

    def relations(self,key,inputs,outputs):
        self.items[key]['raw']['relationshipAttributes']={
            k:[{'guid':g,'entityStatus':'ACTIVE','relationshipStatus':'ACTIVE'} for g in values]
            for k,values in (('inputs',inputs),('outputs',outputs))}

    def graph(self,seeds=('alpha',),lineage=None):
        return read_system_lineage([self.items[g] for g in seeds],
                                   [e for e in self.items.values() if e['typeName']=='Process'],
                                   self.items.__getitem__,lineage or (lambda *a:{'relations':[]}),
                                   self.n['process_refs'])

    def test_all_inputs_outputs_even_without_inverse_or_lineage_edges(self):
        nodes,edges=self.graph()
        pairs={(e['from'],e['to']) for e in edges}
        self.assertEqual(pairs,{('alpha','p_join'),('beta','p_join'),('p_join','hub'),
                               ('hub','p_left'),('p_left','end_one'),('p_left','extra'),
                               ('hub','p_right'),('p_right','end_two')})
        answer=describe_system_lineage(nodes,edges,'test',self.n['natural_process_description'])
        self.assertIn('alpha et beta',answer)
        self.assertIn('alpha + beta → p_join → hub',answer)
        self.assertIn('p_left → end_one + extra',answer)
        self.assertIn('se divise en deux branches',answer)
        self.assertEqual(answer.count('Opération documentée dans Atlas.'),1)
        self.assertNotIn('sans dépendance en amont',answer)
        self.assertTrue(answer.split('\n\n')[-1].startswith('Ainsi,'))

    def test_deleted_relationship_overrides_lineage(self):
        self.items['p_join']['raw']['relationshipAttributes']['inputs'][1]['relationshipStatus']='DELETED'
        nodes,edges=self.graph(lineage=lambda *a:{'relations':[{'fromEntityId':'beta','toEntityId':'p_join'}]})
        self.assertNotIn({'from':'beta','to':'p_join'},edges)

    def test_cycle_terminates_and_keeps_edges(self):
        self.relations('p_right',['hub'],['alpha'])
        nodes,edges=self.graph()
        answer=describe_system_lineage(nodes,edges,'test',self.n['natural_process_description'])
        self.assertIn('Une boucle',answer)
        self.assertIn('hub → p_right → alpha',answer)

    def test_empty_relationship_does_not_revive_stale_attribute(self):
        self.items['p_join']['raw']['relationshipAttributes']['inputs']=[]
        self.items['p_join']['raw']['attributes']={'inputs':[{'guid':'alpha'}]}
        nodes,edges=self.graph()
        self.assertEqual(edges,[])

    def test_empty_and_failure(self):
        self.assertIn('Aucun parcours',describe_system_lineage({},[],'test',str))
        def unavailable(*args):raise RuntimeError('offline')
        with self.assertRaises(RuntimeError):self.graph(lineage=unavailable)

    def test_global_dispatch_and_remembered_table(self):
        n=self.n
        n['global_complete_lineage_data']=lambda source:self.graph()
        for question in ('Quel est le Data Lineage complet de la base PostgreSQL ?',
                         'Explique le Data Lineage complet de la base PostgreSQL.'):
            state={'active_table':'alpha'}
            self.assertEqual(n['conversation_question'](question,'postgresql',state),question)
            answer=n['dispatch_chatbot'](question)
            self.assertIn('alpha + beta → p_join → hub',answer)
            self.assertIn('se divise en deux branches',answer)
        self.assertFalse(n['global_complete_lineage_request']('Explique le lineage complet de la table alpha PostgreSQL'))


if __name__=='__main__':unittest.main()

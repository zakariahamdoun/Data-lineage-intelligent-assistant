import unittest
from upstream_presentation import describe_upstream
from test_lineage_routing import load_functions


class UpstreamPresentationTests(unittest.TestCase):
    def data(self,edges):
        keys={g for pair in edges for g in pair}
        return {'nodes':{g:{'guid':g,'name':g,'typeName':'Process' if g.startswith('p_') else 'PostgreSQLTable',
                             'status':'ACTIVE','raw':{}} for g in keys},
                'edges':edges,'paths':[],'cycles':False}

    def test_grouped_inputs_and_natural_order(self):
        data=self.data([('alpha','p_join'),('beta','p_join'),('p_join','target')])
        answer=describe_upstream(data,'target')
        self.assertTrue(answer.startswith('La table target est alimentée en amont par les tables alpha et beta.'))
        self.assertIn('Les tables alpha et beta passent par le processus p_join, qui alimente la table target.',answer)
        self.assertEqual(answer.count(' → '),2)
        self.assertIn('alpha + beta → p_join → target',answer)
        self.assertNotIn('Parcours enregistrés dans Apache Atlas',answer)

    def test_multiple_stages_and_producers_remain_distinct(self):
        data=self.data([('source','p_first'),('p_first','middle'),('middle','p_join'),
                        ('side','p_join'),('p_join','target'),('other','p_other'),('p_other','target')])
        answer=describe_upstream(data,'target')
        for path in ('source → p_first → middle','middle + side → p_join → target','other → p_other → target'):
            self.assertIn(path,answer)
        self.assertNotIn('source + side',answer)

    def test_files_cycles_and_direct_edges(self):
        data=self.data([('source.csv','p_load'),('p_load','target'),('target','p_load')])
        data['nodes']['source.csv']['typeName']='hdfs_path'
        data['cycles']=True
        answer=describe_upstream(data,'target')
        self.assertIn('source.csv',answer)
        self.assertIn('Une boucle',answer)
        direct=describe_upstream(self.data([('source','target')]),'target')
        self.assertIn('Un lien direct',direct)
        self.assertIn('source → target',direct)

    def test_dispatch_uses_grouped_graph(self):
        n=load_functions()
        data=self.data([('alpha','p_join'),('beta','p_join'),('p_join','target')])
        n['find_requested_tables']=lambda *a:[('postgresql',{'guid':'target'})]
        n['detail']=data['nodes'].__getitem__
        n['process_refs']=lambda *a:[]
        n['get_lineage']=lambda guid,*a:{'relations':[{'fromEntityId':a,'toEntityId':b} for a,b in data['edges'] if b==guid]}
        n['database_tables_answer']=lambda *a:None
        n['named_entity_lineage_answer']=lambda *a:None
        n['lineage_reference_answer']=lambda *a:None
        answer=n['dispatch_chatbot']('Quels objets se trouvent en amont de la table target ?')
        self.assertIn('alpha + beta → p_join → target',answer)


if __name__=='__main__':unittest.main()

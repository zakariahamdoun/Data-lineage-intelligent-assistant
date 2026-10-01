import unittest
from table_lineage import complete_upstream


class CompleteUpstreamTests(unittest.TestCase):
    def test_question_dispatch_returns_complete_path(self):
        from test_lineage_routing import load_functions
        n=load_functions()
        names=['transactions_sep.xlsx','Preparation_transactions','transactions1.csv',
               'Chargement_SQLite','transactions']
        n['find_requested_tables']=lambda *args:[('sqlite',{'guid':'4'})]
        n['detail']=lambda key:{'name':names[int(key)],'typeName':'DataSet'}
        n['process_refs']=lambda *args:[]
        n['get_lineage']=lambda key,*args:{'relations':[
            {'fromEntityId':str(int(key)-1),'toEntityId':key}] if int(key)>0 else []}
        answer=n['chatbot']('Donne-moi toutes les dépendances en amont de la table transactions jusqu’à la source initiale.')
        self.assertIn(' → '.join(names),answer)
        self.assertNotIn('Aucune dépendance',answer)

    def test_mixed_relationships_reach_initial_file(self):
        names=['transactions_sep.xlsx','Preparation_transactions','transactions1.csv',
               'Chargement_SQLite','transactions']
        entities={str(i):{'name':name,'status':'ACTIVE'} for i,name in enumerate(names)}
        calls=[]
        def graph(key,direction,depth):
            calls.append(key)
            return {'relations':[{'fromEntityId':str(int(key)-1),'toEntityId':key}]
                    if key in ('1','3') else []}
        def refs(item,attribute):
            index=names.index(item['name'])
            return [{'guid':str(index-1)}] if index in (2,4) and attribute=='outputFromProcesses' else []
        data=complete_upstream('4',entities.__getitem__,graph,refs)
        self.assertEqual(data['paths'],[['0','1','2','3','4']])
        self.assertEqual(len(calls),5)
        self.assertFalse(data['cycles'])

    def test_branches_and_cycles_are_not_invented_roots(self):
        edges=[('a','b'),('b','a'),('a','t'),('root','t')]
        def graph(key,*args):
            return {'relations':[{'fromEntityId':a,'toEntityId':b} for a,b in edges if b==key]}
        data=complete_upstream('t',lambda key:{'name':key},graph,lambda *args:[])
        self.assertTrue(data['cycles'])
        self.assertEqual(data['paths'],[['root','t']])
        self.assertEqual(set(data['edges']),set(edges))

    def test_errors_propagate_instead_of_claiming_no_dependencies(self):
        def unavailable(*args):raise RuntimeError('Atlas unavailable')
        with self.assertRaises(RuntimeError):
            complete_upstream('t',lambda key:{'name':key},unavailable,lambda *args:[])

    def test_long_chain_has_no_depth_limit(self):
        def graph(key,*args):
            return {'relations':[{'fromEntityId':str(int(key)-1),'toEntityId':key}] if int(key)>0 else []}
        data=complete_upstream('1100',lambda key:{'name':key},graph,lambda *args:[])
        self.assertEqual(len(data['paths'][0]),1101)


if __name__=='__main__':unittest.main()

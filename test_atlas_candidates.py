import unittest
from atlas_candidates import resolve_candidates, candidate_choices


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.headers=[{'guid':g,'typeName':'hdfs_path','attributes':{
            'name':'transactions_sep.xlsx','qualifiedName':q}}
            for g,q in (('a','file@one'),('b','file@two'))]
        self.items={e['guid']:dict(e,name=e['attributes']['name'],qualifiedName=e['attributes']['qualifiedName']) for e in self.headers}
        self.items['p']={'typeName':'Process','name':'Preparation_transactions'}
        self.edges={}

    def resolve(self):
        return resolve_candidates(self.headers,self.items.__getitem__,
            lambda g,*args:{'relations':self.edges.get(g,[])},lambda *args:[],'OUTPUT')

    def test_connected_candidate_is_selected(self):
        self.edges['b']=[{'fromEntityId':'b','toEntityId':'p'}]
        self.assertEqual([e['guid'] for e in self.resolve()],['b'])

    def test_equal_qualified_names_are_deduplicated(self):
        self.items['b']['qualifiedName']='file@one'
        self.edges['b']=[{'fromEntityId':'b','toEntityId':'p'}]
        self.assertEqual([e['guid'] for e in self.resolve()],['b'])

    def test_distinct_connected_identities_require_distinct_choices(self):
        for g in ('a','b'):self.edges[g]=[{'fromEntityId':g,'toEntityId':'p'}]
        result=self.resolve()
        self.assertEqual(len(result),2)
        answer=candidate_choices(result)
        self.assertIn('file@one',answer)
        self.assertIn('file@two',answer)
        self.assertIn('GUID : a',answer)
        self.assertIn('GUID : b',answer)

    def test_deleted_edges_do_not_win_selection(self):
        self.edges['a']=[{'fromEntityId':'a','toEntityId':'p','relationshipStatus':'DELETED'}]
        self.assertEqual(len(self.resolve()),2)

    def test_identical_names_alone_are_not_identity(self):
        self.assertEqual(len(self.resolve()),2)


if __name__=='__main__':unittest.main()

import unittest
from impact_presentation import conclude_impact


class ConclusionTests(unittest.TestCase):
    def test_named_process_and_reason(self):
        nodes={'a': {'name': 'source.csv', 'typeName': 'hdfs_path'},
               'p': {'name': 'Etape', 'typeName': 'Process'},
               'b': {'name': 'resultat', 'typeName': 'SQLiteTable'}}
        text=conclude_impact(nodes,[('a','p'),('p','b')],'a',['b'])
        for term in ('la table `resultat`','du fichier `source.csv`','par le processus `Etape`','car','modification'):
            self.assertIn(term,text)

    def test_direct_branches_cycles_and_unreachable(self):
        nodes={g:{'name':g,'typeName':'DataSet'} for g in 'abcd'}
        text=conclude_impact(nodes,[('a','b'),('a','c'),('b','a')],'a',['b','c','d'],'suppression')
        self.assertIn('a → b',text)
        self.assertIn('a → c',text)
        self.assertNotIn('b → c',text)
        self.assertNotIn('`d`',text)
        self.assertIn('suppression',text)


if __name__=='__main__':unittest.main()

import unittest
from test_lineage_routing import load_functions


class SystemSectionsTests(unittest.TestCase):
    def test_join_and_branches_without_cartesian_paths(self):
        n=load_functions()
        nodes={g:{'label':g,'type':'Process' if g.startswith('p') else 'Table',
                  'description':'Opération '+g+'.'} for g in ('a','b','hub','x','y','p1','p2','p3')}
        edges=[{'from':a,'to':b} for a,b in [('a','p1'),('b','p1'),('p1','hub'),
               ('hub','p2'),('p2','x'),('hub','p3'),('p3','y')]]
        n['pg_catalog']=lambda:{'fk_pairs':[('c','d')],'column_parent':{'c':'hub','d':'a'},
                                  'columns':{'c':{'name':'ref'},'d':{'name':'id'}}}
        answer=n['explain_business_lineage']('Explique le lineage complet du système PostgreSQL',nodes,edges,'unused','postgresql')
        self.assertIn('a + b → p1 → hub',answer)
        self.assertIn('hub → p2 → x',answer)
        self.assertIn('hub → p3 → y',answer)
        for p in ('p1','p2','p3'):
            self.assertEqual(answer.count('Opération '+p+'.'),1)
        self.assertIn('hub.ref → a.id',answer)
        self.assertIn('La table hub occupe une position centrale',answer)
        self.assertIn('des tables a et b',answer)
        self.assertIn('produisant x et y',answer)
        self.assertIn('distinctes du Data Lineage',answer)
        headings=['Rôle général','Flux en amont','Flux en aval','Relations techniques importantes','Conclusion']
        positions=[answer.index(h) for h in headings]
        self.assertEqual(positions,sorted(positions))

    def test_endpoints_and_absence(self):
        n=load_functions()
        nodes={'a':{'label':'source.xlsx','type':'hdfs_path'},
               'p':{'label':'importer','type':'Process'},
               'b':{'label':'final','type':'SQLiteTable'}}
        incoming={'p':{'a'},'b':{'p'}};outgoing={'a':{'p'},'p':{'b'}}
        answer=n['system_lineage_conclusion'](nodes,incoming,outgoing,'SQLite')
        self.assertIn('Le fichier source.xlsx constitue la source initiale',answer)
        self.assertIn('La table final constitue la destination finale',answer)
        self.assertNotIn('centrale',answer)
        self.assertIn('Aucun flux',n['system_lineage_conclusion'](nodes,{}, {},'SQLite'))


if __name__=='__main__':unittest.main()

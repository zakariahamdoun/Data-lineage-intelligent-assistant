"""Entity location routing and exact Atlas lookup regression tests."""
import unittest
from test_lineage_routing import load_functions


QUESTIONS=[
    'La table comptes existe-t-elle dans SQLite ou PostgreSQL ?',
    'Dans quelle base se trouve comptes ?',
    'Dans quel système existe la table clients ?',
    'transactions existe-t-elle dans les deux systèmes ?',
    'Où se trouve la table virements ?',
]


class TableLocationTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions();self.calls=[];self.entities={}
        for engine,names in (('PostgreSQL',['comptes','clients','transactions','virements']),('SQLite',['transactions'])):
            for name in names:
                guid=engine+name
                self.entities[guid]={'guid':guid,'typeName':engine+'Table','status':'ACTIVE',
                    'attributes':{'name':name,'qualifiedName':name+'@'+engine,
                                  'databaseName':'projet_data_lineage' if engine=='PostgreSQL' else 'transactions1.db'}}
        self.entities['PostgreSQLcomptes']['attributes']['qualifiedName']='comptes@projet_data_lineage'
        def atlas_get(path,params):
            self.calls.append(params['typeName'])
            return {'entities':[e for e in self.entities.values() if e['typeName']==params['typeName']]}
        self.n['atlas_get']=atlas_get
        self.n['get_entity']=lambda guid:{'entity':self.entities[guid]}
        self.n['context']=lambda *a:self.fail('Location must use direct Atlas lookup')

    def test_five_requested_questions(self):
        for question,name in zip(QUESTIONS,['comptes','comptes','clients','transactions','virements']):
            with self.subTest(question=question):
                self.calls.clear()
                self.assertTrue(self.n['table_location_intent'](question))
                self.assertEqual(self.n['table_location_name'](question),name)
                self.assertEqual(self.n['transaction_source'](question),(None,False))
                self.assertEqual(self.n['catalogue_intent'](question),(None,None))
                answer=self.n['chatbot'](question,'sqlite')
                self.assertEqual(set(self.calls),{'SQLiteTable','PostgreSQLTable'})
                if name=='transactions':
                    self.assertIn('transactions@PostgreSQL',answer)
                    self.assertIn('transactions@SQLite',answer)
                    self.assertNotIn('uniquement',answer)
                else:
                    self.assertIn('existe uniquement dans PostgreSQL',answer)
                    self.assertIn('projet_data_lineage',answer)
                    self.assertIn('périmètre SQLite',answer)

    def test_qualified_name_and_absence(self):
        answer=self.n['chatbot']('Où se trouve la table comptes@projet_data_lineage ?')
        self.assertIn('existe uniquement dans PostgreSQL',answer)
        self.assertIn('ni dans SQLite ni dans PostgreSQL',self.n['chatbot']('Où se trouve la table comptes_archive ?'))
        self.entities['PostgreSQLcomptes']['status']='DELETED'
        self.assertIn('ni dans SQLite ni dans PostgreSQL',self.n['chatbot'](QUESTIONS[0]))

    def test_database_relationship_and_missing_database(self):
        table=self.entities['PostgreSQLcomptes'];del table['attributes']['databaseName']
        self.assertIn('base n’est pas renseignée',self.n['chatbot'](QUESTIONS[0]))
        table['relationshipAttributes']={'database':{'guid':'db'}}
        self.entities['db']={'guid':'db','typeName':'PostgreSQLDatabase','attributes':{'name':'catalogue'}}
        self.assertIn('base catalogue',self.n['chatbot'](QUESTIONS[0]))

    def test_lookup_error_is_not_absence(self):
        def failing(path,params):raise RuntimeError('Atlas unavailable')
        self.n['atlas_get']=failing
        with self.assertRaises(RuntimeError):self.n['chatbot'](QUESTIONS[0])


if __name__=='__main__':unittest.main()

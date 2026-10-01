"""Offline checks for source filtering and Atlas type/description formatting."""
import unittest
from test_lineage_routing import load_functions


class ColumnSourceTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions();self.queries=[];self.columns={}
        for guid,system,table,typ in (
            ('s','SQLite','transactions','int64'),
            ('p','PostgreSQL','payments','numeric'),
            ('p2','PostgreSQL','archive','integer'),
        ):
            attrs={'name':'Montant','dataType':typ,'qualifiedName':table+'.Montant@'+system}
            parent={'guid':table,'attributes':{'name':table}}
            self.columns[guid]={'guid':guid,'name':'Montant','status':'ACTIVE',
                                'typeName':system+'Column','description':'Elle représente le montant de la transaction.',
                                'raw':{'attributes':attrs,'relationshipAttributes':{'table':{'guid':table}}},
                                'referred':{table:parent}}
        def search(url,params):
            self.queries.append(params['typeName'])
            return {'entities':[{'guid':g,'attributes':c['raw']['attributes']}
                                for g,c in self.columns.items() if c['typeName']==params['typeName']]}
        self.n['atlas_get']=search
        self.n['detail']=self.columns.__getitem__

    def test_selected_sqlite_is_exclusive(self):
        answer=self.n['chatbot']('Quel est le type de la colonne Montant ?', 'sqlite')
        self.assertEqual(answer,'Dans la table transactions de SQLite, la colonne Montant est de type entier 64 bits (int64). Elle représente le montant de la transaction.')
        self.assertEqual(self.queries,['SQLiteColumn'])

    def test_same_source_duplicates_and_no_source(self):
        question='Quel est le type de la colonne Montant ?'
        answer=self.n['chatbot'](question,'postgresql')
        self.assertEqual(len(answer.split('\n\n')),2)
        self.assertNotIn('SQLite',answer)
        self.assertEqual(self.queries,['PostgreSQLColumn'])
        self.assertEqual(len(self.n['chatbot'](question).split('\n\n')),3)

    def test_selection_wins_and_no_cross_source_fallback(self):
        question='Quel est le type de la colonne Montant dans PostgreSQL ?'
        self.assertNotIn('PostgreSQL',self.n['chatbot'](question,'Transactions / SQLite'))
        del self.columns['s']
        self.assertIn('n’a pas été trouvée',self.n['chatbot'](question,'sqlite'))

    def test_translations_preserve_original(self):
        for value,french in [('int64','entier 64 bits'),('integer','nombre entier'),
                             ('numeric','nombre décimal'),('character varying','texte de longueur variable'),
                             ('timestamp without time zone','date et heure sans fuseau horaire')]:
            self.assertEqual(self.n['display_column_type'](value),f'{french} ({value})')
        self.assertEqual(self.n['display_column_type']('custom_type'),'custom_type')


if __name__=='__main__':unittest.main()

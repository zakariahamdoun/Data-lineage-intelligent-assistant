"""Nullable answers read Atlas attributes without retrieval or generation."""
import unittest
from test_lineage_routing import load_functions


class NullableTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.entities={}
        for table,value in [('clients',False),('comptes',True)]:
            attrs={'name':'id_client','qualifiedName':f'{table}.id_client@projet_data_lineage','nullable':value}
            self.entities[table]={'guid':table,'status':'ACTIVE','raw':{'attributes':attrs}}
        self.queries=[]
        def search(path,params):
            self.assertEqual(params['typeName'],'PostgreSQLColumn')
            self.queries.append(params['query'])
            return {'entities':[{'guid':guid} for guid in self.entities]}
        self.n['atlas_get']=search
        self.n['detail']=self.entities.__getitem__
        self.n['context']=lambda *a:self.fail('FAISS must not be used')
        self.n['Mistral']=lambda *a,**k:self.fail('LLM must not be used')

    def test_explicit_columns(self):
        for table,expected in [('clients','ne peut pas être vide'),('comptes','peut donc être vide')]:
            with self.subTest(table=table):
                answer=self.n['chatbot'](f'La colonne {table}.id_client peut-elle être vide ?')
                self.assertIn(expected,answer)
                self.assertIn('Dans '+table,answer)
                self.assertEqual(self.queries[-1],f'{table}.id_client@projet_data_lineage')

    def test_all_occurrences_and_phrasings(self):
        for phrase in ['peut-elle être vide','peut être vide','est-elle obligatoire','accepte-t-elle les valeurs nulles','est nullable']:
            with self.subTest(phrase=phrase):
                answer=self.n['chatbot'](f'La colonne id_client {phrase} ?', 'sqlite')
                self.assertIn('deux tables PostgreSQL',answer)
                self.assertIn('dans clients, elle est non nullable',answer)
                self.assertIn('dans comptes, elle est nullable',answer)
                self.assertEqual(self.queries[-1],'id_client')

    def test_missing_attribute_and_exact_name(self):
        del self.entities['clients']['raw']['attributes']['nullable']
        self.entities['other']={'guid':'other','raw':{'attributes':{'name':'id_client_extra'}}}
        answer=self.n['chatbot']('La colonne id_client peut-elle être vide ?')
        self.assertIn('dans clients, cette information n’est pas renseignée',answer)
        self.assertIn('deux tables',answer)

    def test_recorded_primary_key_explanation(self):
        self.entities['clients']['raw']['attributes']['isPrimaryKey']=True
        answer=self.n['chatbot']('Pourquoi clients.id_client ne peut-elle pas être vide ?')
        self.assertIn('ne peut pas être vide',answer)
        self.assertIn('clé primaire',answer)
        self.assertIn('identifie chaque enregistrement',answer)
        self.assertIn('ne peut pas contenir une valeur NULL',answer)

    def test_nullable_foreign_key_and_business_conflict(self):
        col=self.entities['comptes']
        col['raw']['relationshipAttributes']={'foreignKeyTo':[{'guid':'clients'}], 'table':{'guid':'table'}}
        col['referred']={
            'clients':self.entities['clients']['raw'],
            'table':{'attributes':{'name':'comptes','businessRule':'Chaque compte appartient à un client.'}}
        }
        answer=self.n['chatbot']('Pourquoi comptes.id_client peut-elle être vide ?')
        self.assertIn('clé étrangère vers clients.id_client',answer)
        self.assertIn('lorsqu’une valeur est renseignée',answer)
        self.assertIn('NOT NULL',answer)
        self.assertIn('Écart entre règle métier et contrainte technique',answer)
        answer=self.n['chatbot']('La colonne id_client peut-elle être vide et pourquoi ?')
        self.assertIn('deux tables',answer)
        self.assertIn('clé étrangère vers clients.id_client',answer)

    def test_no_inferred_primary_key_and_no_unrelated_conflict(self):
        attrs=self.entities['clients']['raw']['attributes']
        attrs['description']='Clé primaire identifiant unique'
        attrs['businessRule']='Le nom est obligatoire, mais cette colonne peut être vide.'
        answer=self.n['chatbot']('Pourquoi clients.id_client ne peut-elle pas être vide ?')
        self.assertNotIn('Elle constitue la clé primaire',answer)
        self.assertIn('nullable = false',answer)
        attrs=self.entities['comptes']['raw']['attributes']
        attrs['businessRule']='Le solde est positif.'
        answer=self.n['chatbot']('Pourquoi comptes.id_client peut-elle être vide ?')
        self.assertNotIn('Écart entre',answer)

    def test_primary_key_on_table_and_inconsistent_nullable(self):
        col=self.entities['comptes']
        col['raw']['relationshipAttributes']={'table':{'guid':'table'}}
        col['referred']={'table':{'attributes':{'name':'comptes','primaryKeyColumns':['id_client']}}}
        answer=self.n['chatbot']('La colonne comptes.id_client peut-elle être vide ?')
        self.assertIn('Incohérence dans Atlas',answer)
        self.assertIn('peut donc être vide',answer)


if __name__=='__main__':unittest.main()

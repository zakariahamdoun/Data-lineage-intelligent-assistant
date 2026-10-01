"""Deterministic retrieval and LLM context regression checks."""
import json
from types import SimpleNamespace
import unittest
from test_lineage_routing import load_functions


class TableMetadataTests(unittest.TestCase):
    def test_display_types_preserve_atlas_values(self):
        n=load_functions()
        for raw,label in [('integer','nombre entier'),('numeric','nombre décimal'),
                          ('character varying','texte'),('date','date'),
                          ('timestamp','date et heure'),('boolean','vrai ou faux')]:
            self.assertEqual(n['display_column_type'](raw),label)
            self.assertEqual(n['display_column_type'](raw,'détails techniques'),f'{label} ({raw})')
        self.assertEqual(n['display_column_type']('uuid'),'uuid')

    def setUp(self):
        self.n=load_functions()
        self.table={'guid':'t','typeName':'PostgreSQLTable','attributes':{
            'name':'comptes','qualifiedName':'comptes@db','description':'Comptes bancaires'},
            'relationshipAttributes':{'columns':[{'guid':'c'}]}}
        self.column={'guid':'c','typeName':'PostgreSQLColumn','attributes':{
            'name':'id_compte','dataType':'integer'},'relationshipAttributes':{'table':{'guid':'t'}}}
        self.n['atlas_get']=lambda path,params: {'entities':[self.table] if params['typeName']=='PostgreSQLTable' else []}
        self.n['get_entity']=lambda guid: {'entity':self.table if guid=='t' else self.column}
        self.n['search_type']=lambda *a: [self.column]
        self.n['context']=lambda *a: ['Complément FAISS']
        self.n['Mistral']=None

    def test_requested_metadata_questions(self):
        for question,expected in (
            ('Que contient la table comptes ?','id_compte (nombre entier)'),
            ('Quelles sont les colonnes de comptes ?','id_compte'),
            ('Quelles sont les colonnes et leurs types de comptes ?','id_compte (nombre entier)'),
            ('Quelle est la clé primaire de comptes ?','non renseignée'),
            ('Quelles sont les clés étrangères de comptes ?','non renseignées')):
            answer=self.n['chatbot'](question,'sqlite')
            self.assertIn(expected,answer)
            self.assertNotIn('Souhaitez-vous',answer)
        self.assertIsNone(self.n['table_metadata_intent']('Explique le lineage de comptes.'))

    def test_exact_and_qualified_names(self):
        self.assertEqual(len(self.n['find_requested_tables']('Décris comptes@db')),1)
        self.assertEqual(self.n['find_requested_tables']('Décris comptes@autre'),[])
        self.assertEqual(self.n['find_requested_tables']('Décris comptes_archive'),[])
        self.assertEqual(self.n['transaction_source']('Que contient la table comptes ?'),('postgresql',False))

    def test_overview_hides_technical_details(self):
        answer=self.n['chatbot']('Que contient la table comptes ?')
        for technical in ('qualifiedName','Clé primaire','Clés étrangères','Processus','référence','Comptes bancaires'):
            self.assertNotIn(technical,answer)
        self.assertLess(len(answer.split()),70)
        self.assertIn('integer',self.n['chatbot']('Donne les détails techniques de la table comptes'))
        self.assertIn('comptes@db',self.n['chatbot']('Quel est le qualifiedName de comptes ?'))

    def test_column_meaning_must_be_documented(self):
        for description in ('', 'Colonne id_compte de la table comptes'):
            self.column['attributes']['description']=description
            answer=self.n['chatbot']('Que contient la table comptes ?')
            self.assertIn('id_compte (nombre entier)',answer)
            self.assertNotIn('identifiant',answer)
            self.assertNotIn('Colonne id_compte de la table',answer)
        self.column['attributes']['description']='Identifiant du compte bancaire'
        answer=self.n['chatbot']('Que contient la table comptes ?')
        self.assertIn('id_compte : Identifiant du compte bancaire',answer)
        self.assertNotIn('integer',answer)

    def test_partial_descriptions_and_all_columns(self):
        data={'table':'exemple','columns':[
            {'name':'code','description':'Code documenté','type':'text'},
            {'name':'autre','description':None,'type':'integer'}]}
        answer=self.n['table_column_content'](data)
        self.assertIn('code et autre (nombre entier)',answer)
        self.assertIn('code : Code documenté',answer)
        self.assertNotIn('autre :',answer)

    def test_real_ambiguity_and_deleted_tables(self):
        sqlite=dict(self.table,guid='s',typeName='SQLiteTable',attributes={'name':'comptes','qualifiedName':'comptes@sqlite'})
        self.n['atlas_get']=lambda path,params: {'entities':[self.table] if params['typeName']=='PostgreSQLTable' else [sqlite]}
        self.assertIn('SQLite ou PostgreSQL',self.n['chatbot']('Que contient la table comptes ?'))
        self.assertEqual(len(self.n['find_requested_tables']('Décris comptes@db')),1)
        sqlite['status']='DELETED'
        self.assertEqual(self.n['transaction_source']('Que contient la table comptes ?'),('postgresql',False))

    def test_missing_fields_and_explicit_primary_key(self):
        self.column['attributes']['isPrimaryKey']=True
        self.assertIn('id_compte',self.n['chatbot']('Quelle est la clé primaire de comptes ?'))
        self.assertIn('n’a pas été trouvée',self.n['chatbot']('Que contient la table absente ?'))

    def test_context_sent_to_llm_and_failure_fallback(self):
        captured=[]
        def complete(**kwargs):
            payload=json.loads(kwargs['messages'][1]['content']);captured.append(payload)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({'choices':[0]*len(payload['paragraphs'])})))])
        self.n['Mistral']=lambda **kwargs:SimpleNamespace(chat=SimpleNamespace(complete=complete))
        answer=self.n['chatbot']('Que contient la table comptes ?')
        data=json.loads(captured[0]['atlas_context'][0])
        self.assertEqual(data['columns'][0]['type'],'integer')
        self.assertEqual(data['primaryKey'],[])
        self.assertEqual(captured[0]['atlas_context'][1],'Complément FAISS')
        def failing(*a,**k):raise RuntimeError('unavailable')
        self.n['context']=failing;self.n['Mistral']=failing
        self.assertEqual(answer,self.n['chatbot']('Que contient la table comptes ?'))


if __name__=='__main__':unittest.main()

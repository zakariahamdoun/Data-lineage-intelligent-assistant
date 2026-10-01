"""Offline SQLite chatbot tests; fixtures never modify the project database."""
import ast
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace


class SQLiteChatbotTests(unittest.TestCase):
    def setUp(self):
        app=Path(__file__).with_name('app.py')
        tree=ast.parse(app.read_text(encoding='utf-8'))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        for node in functions:node.decorator_list=[]
        self.n=dict(__file__=str(app),re=re,json=json,sqlite3=sqlite3)
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(app),'exec'),self.n)
        self.n['sqlite_atlas_metadata']=lambda:{'tables':[]}
        self.reader=self.n['sqlite_live_metadata']
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'fixture.db'
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('CREATE TABLE ledger (entry INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL);'
                             'INSERT INTO ledger(amount) VALUES (12),(34);'
                             'CREATE TABLE "odd""name" (a TEXT, b INTEGER, PRIMARY KEY(b,a));')
        self.n['sqlite_live_metadata']=lambda **kw:self.reader(self.path,**kw)
        # Build an isolated Atlas fixture; the application must never call the local reader.
        self.atlas_fixture=dict(self.reader(self.path,include_counts=True),source='atlas')
        self.n['sqlite_atlas_metadata']=lambda:self.atlas_fixture
        self.n['formulate_atlas_answer']=lambda q,a,ctx:a

    def test_inventory_and_ui_route(self):
        q='Quelles sont les tables disponibles dans la base SQLite ?'
        kind,source=self.n['catalogue_intent'](q)
        answer=self.n['catalogue_answer'](kind,source)
        self.assertEqual(answer,self.n['chatbot'](q))
        self.assertIn('- ledger',answer)
        self.assertIn('- odd"name',answer)
        self.assertNotIn('sqlite_sequence',answer)

    def test_columns_type_key_count(self):
        for question,expected in (
            ('Quelles colonnes contient la table ledger ?','amount : REAL'),
            ('Quel est le type de la colonne amount ?','REAL'),
            ('Quelle est la clé primaire de la table ledger ?','entry'),
            ('Combien de lignes contient la table ledger ?','2 lignes'),
            ('Quelle est la clé primaire de la table odd"name ?','b, a'),
        ):
            with self.subTest(question=question):
                self.assertIn(expected,self.n['chatbot'](question,'sqlite'))

    def test_context_contains_live_metadata(self):
        data=json.loads(self.n['context']('Combien de lignes contient la table ledger ?','sqlite')[0])
        ledger=next(t for t in data['tables'] if t['name']=='ledger')
        self.assertEqual(ledger['row_count'],2)
        self.assertEqual(ledger['columns'][0]['primary_key_position'],1)

    def test_absence_empty_missing_and_refresh(self):
        self.assertIn('introuvable',self.n['chatbot']('Quelles colonnes contient la table missing ?','sqlite'))
        self.assertIn('introuvable',self.n['chatbot']('Quel est le type de la colonne missing ?','sqlite'))
        self.atlas_fixture['tables'].append({'name':'fresh','columns':[]})
        self.assertIn('fresh',self.n['chatbot']('Quelles tables sont disponibles dans SQLite ?'))
        self.atlas_fixture['tables']=[]
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('No local fallback')
        self.assertIn('Aucune table',self.n['chatbot']('Quelles tables sont disponibles dans SQLite ?'))

    def test_other_routes_untouched(self):
        for q,source in [('Quelles colonnes contient la table ledger ?','postgresql'),
                         ('Explique le lineage SQLite','sqlite'),
                         ('Analyse l’impact sur la table ledger SQLite','sqlite'),
                         ('Quelles tables sont disponibles dans PostgreSQL ?',None)]:
            self.assertIsNone(self.n['sqlite_question_answer'](q,source))

    def test_real_database(self):
        path=Path(__file__).with_name('transactions1.db')
        before=path.read_bytes()
        data=self.reader(path)
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            expected=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not r[0].startswith('sqlite_')]
        self.assertEqual([t['name'] for t in data['tables']],expected)
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('No local database read by chatbot')
        answer=self.n['chatbot']('Quelles sont les tables disponibles dans la base SQLite ?')
        self.assertIn('ledger',answer)
        self.assertEqual(path.read_bytes(),before)

    def test_atlas_priority_relationships_and_mistral_context(self):
        # Exercise actual REST orchestration with isolated API responses.
        tree=ast.parse(Path(__file__).with_name('app.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sqlite_atlas_metadata')
        exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),self.n)
        entities={
            't':{'typeName':'SQLiteTable','attributes':{'name':'remote_ledger','database':'transactions1.db'},
                 'relationshipAttributes':{'columns':[{'guid':'c'}],'outputFromProcesses':[{'guid':'p'}]}},
            'other':{'attributes':{'name':'excluded','database':'another.db'}},
            'c':{'attributes':{'name':'total','dataType':'DOUBLE','isPrimaryKey':False}},
            'p':{'attributes':{'name':'import_remote'}},
        }
        calls=[]
        def api(path,params=None):
            calls.append((path,params))
            if path.endswith('/search/basic'):
                return {'entities':[{'guid':'t'},{'guid':'other'}] if params['offset']==0 else []}
            return {'entity':entities[path.rsplit('/',1)[-1]]}
        self.n['atlas_get']=api
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('Atlas results must take priority')
        contexts=[]
        self.n['formulate_atlas_answer']=lambda q,a,ctx:contexts.append(json.loads(ctx[0])) or a
        answer=self.n['chatbot']('Quelles sont les tables disponibles dans la base SQLite ?')
        self.assertEqual(answer,'La base transactions1.db contient la table remote_ledger.')
        self.assertEqual(contexts[-1]['tables'][0]['outputFromProcesses'][0]['name'],'import_remote')
        self.assertIn('total : DOUBLE',self.n['chatbot']('Quelles colonnes contient la table remote_ledger ?','sqlite'))
        self.assertIn('DOUBLE',self.n['chatbot']('Quel est le type de la colonne total ?','sqlite'))
        self.assertIn('n’est pas renseigné',self.n['chatbot']('Combien de lignes contient la table remote_ledger ?','sqlite'))
        self.assertEqual(json.loads(self.n['context']('Quelles tables sont disponibles dans SQLite ?')[0])['source'],'atlas')
        self.assertTrue(any(params and params['offset']==2 for _,params in calls))

    def test_atlas_error_is_not_empty(self):
        def unavailable():raise RuntimeError('Atlas unavailable')
        self.n['sqlite_atlas_metadata']=unavailable
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('No local fallback on API failure')
        with self.assertRaises(RuntimeError):
            self.n['chatbot']('Quelles tables sont disponibles dans SQLite ?')

    def test_business_questions(self):
        names=['Identifiant opération','Montant','ID Clients','Type de transaction',
               'Status opération','Numéro de compte','Date','Montant net']
        self.n['sqlite_atlas_metadata']=lambda:{'source':'atlas','tables':[
            {'name':'records','columns':[{'name':name,'type':'TEXT','primary_key_position':None} for name in names]}]}
        self.n['formulate_atlas_answer']=lambda q,a,ctx:a
        cases=[('Quelles informations sont stockées pour chaque transaction ?',names),
               ('Quelle colonne représente le montant d’une transaction ?',['Montant']),
               ('Quelle colonne contient la date de l’opération ?',['Date']),
               ('Quelle colonne correspond au client ?',['ID Clients']),
               ('Quelle colonne correspond au numéro de compte ?',['Numéro de compte']),
               ('Quelle colonne contient le statut ?',['Status opération']),
               ('Quelle colonne représente le type de transaction ?',['Type de transaction'])]
        for question,expected in cases:
            with self.subTest(question=question):
                answer=self.n['chatbot'](question,'sqlite')
                for name in expected:self.assertIn(name,answer)
                for name in set(names)-set(expected):self.assertNotIn(name,answer)
        self.assertIn('type TEXT',self.n['chatbot']('Quel est le type de la colonne Montant ?','sqlite'))
        self.assertNotIn('Montant net',self.n['chatbot']('Quel est le type de la colonne Montant ?','sqlite'))
        self.assertIn('Aucune description métier plus détaillée',self.n['chatbot']('Que signifie la colonne Date ?','sqlite'))
        self.assertIn('préciser',self.n['chatbot']('Quelle colonne contient la devise ?','sqlite'))

    def source_fixture(self):
        entities={
            'db':{'name':'transactions1.db','typeName':'SQLiteDatabase'},
            'table':{'name':'transactions','typeName':'SQLiteTable','outputFromProcesses':[{'guid':'load'}]},
            'load':{'name':'loader','typeName':'Process','inputs':[{'guid':'file'},{'guid':'db'}],
                    'outputs':[{'guid':'unrelated'}]},
            'file':{'name':'dynamic_source.csv','typeName':'hdfs_path'},
            'unrelated':{'name':'unrelated.csv','typeName':'hdfs_path'},
        }
        self.n['sqlite_atlas_metadata']=lambda:{'tables':[{'name':'transactions','guid':'table'}]}
        self.n['search_type']=lambda kind:[{'guid':'db','attributes':{'name':'transactions1.db'}}]
        def details(guid):
            attrs=entities[guid]
            return dict(attrs,guid=guid,raw={'attributes':attrs})
        self.n['detail']=details
        self.n['get_lineage']=lambda *a:{'relations':[]}
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('Source files must come from Atlas')
        return entities

    def test_source_file_questions(self):
        self.source_fixture()
        for question in ('Quel fichier a été utilisé pour créer la base SQLite ?',
                         'Quel est le fichier source de transactions1.db ?',
                         'À partir de quel fichier la table transactions a-t-elle été chargée ?',
                         'À partir de quel fichier transactions1.db a-t-elle été créée ?'):
            with self.subTest(question=question):
                kind,source=self.n['catalogue_intent'](question,'sqlite')
                answer=self.n['catalogue_answer'](kind,source)
                self.assertEqual(answer,self.n['chatbot'](question,'sqlite'))
                self.assertIn('à partir du fichier dynamic_source.csv',answer)
                self.assertNotIn('unrelated.csv',answer)
                self.assertNotIn('du fichier transactions1.db',answer)

    def test_source_files_multiple_absent_and_lineage(self):
        entities=self.source_fixture()
        entities['file2']={'name':'second.xlsx','typeName':'hdfs_path'}
        entities['load']['inputs'].append({'guid':'file2'})
        question='Quel est le fichier source de transactions1.db ?'
        answer=self.n['chatbot'](question)
        self.assertIn('dynamic_source.csv',answer)
        self.assertIn('second.xlsx',answer)
        entities['table']['outputFromProcesses']=[]
        self.assertEqual(self.n['chatbot'](question),"Le fichier source de transactions1.db n'est pas renseigné dans les métadonnées Apache Atlas.")
        self.n['get_lineage']=lambda guid,*a:{'relations':[{'fromEntityId':'load','toEntityId':'table'}] if guid=='table' else []}
        self.assertIn('second.xlsx',self.n['chatbot'](question))

    def test_transformations_from_upstream_atlas(self):
        entities=self.source_fixture()
        entities['file']['outputFromProcesses']=[{'guid':'prepare'}]
        entities['prepare']={'name':'preparer','typeName':'Process','description':'Conversion des dates en ISO.',
                             'inputs':[{'guid':'raw'}],'outputs':[{'guid':'file'}]}
        entities['raw']={'name':'raw.json','typeName':'hdfs_path'}
        self.n['process_names']=lambda e,d:', '.join(entities[r['guid']]['name'] for r in e.get(d,[]))
        self.n['sqlite_tracking_transformations']=lambda:self.fail('Atlas takes priority')
        self.n['formulate_atlas_answer']=lambda q,a,ctx:a
        for question in ('Quelle transformation a été appliquée aux données avant leur importation ?',
                         'Quel traitement a été effectué avant le chargement dans SQLite ?',
                         'Quelles transformations ont été appliquées aux données ?'):
            with self.subTest(question=question):
                answer=self.n['chatbot'](question,'sqlite')
                self.assertIn('Conversion des dates en ISO.',answer)
                self.assertIn('raw.json',answer)
                self.assertIn('dynamic_source.csv',answer)
                self.assertNotIn('Localisation',answer)

    def test_tracking_transformations_fallback_and_absence(self):
        self.n['sqlite_atlas_metadata']=lambda:{'tables':[]}
        reader=self.n['sqlite_tracking_transformations']
        self.n['sqlite_tracking_transformations']=lambda:reader(self.path)
        question='Quelles transformations ont été appliquées aux données ?'
        self.assertEqual(self.n['chatbot'](question,'sqlite'),"Aucune transformation n'est renseignée dans les métadonnées disponibles.")
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE tracking_data (transformation TEXT, unrelated TEXT)')
            db.execute('INSERT INTO tracking_data VALUES (?,?)',('Normalisation des dates','not a transformation'))
            db.commit()
        answer=self.n['chatbot'](question,'sqlite')
        self.assertNotIn('Normalisation des dates',answer)
        self.assertNotIn('not a transformation',answer)

    def test_transformation_presentation_preserves_evidence(self):
        render=self.n['transformation_presentation']
        answer=render([{'process':'prepare_test','metadata':{
            'description':'Processus de préparation réalisé avec Tool/Test : conversion des dates.'},
            'inputs':'source.csv','outputs':'result.csv'}])
        for label in ('Processus','Outil utilisé','Transformation','Entrées','Sorties'):
            self.assertIn('**'+label+' :**',answer)
        self.assertIn('Tool/Test',answer)
        self.assertIn('conversion des dates.',answer)
        self.assertIn('\n\n- ',answer)
        incomplete=render([{'process':'p','metadata':{'description':'Traitement documenté.',
                          'transformation':{'steps':['validation','conversion']}},
                          'inputs':'non renseignées','outputs':'result.csv'}])
        self.assertNotIn('Outil utilisé',incomplete)
        self.assertNotIn('{',incomplete)
        self.assertNotIn("['",incomplete)
        self.assertIn('validation; conversion',incomplete)

    def test_chat_presentation_only(self):
        render=self.n['present_chat_answer']
        answer=render('La base example.db contient la table example_table.')
        self.assertIn('**Tables disponibles :**\n\n- ',answer)
        self.assertIn('example_table',answer)
        columns=render('Colonnes de la table demo :\n- amount : REAL\n- date : TEXT')
        self.assertIn('\n\n- ',columns)
        self.assertIn(' : REAL',columns)
        message='Aucune transformation renseignée.'
        self.assertEqual(render(message),message)

    def attribute_fixture(self):
        entities=self.source_fixture()
        entities['file']['outputFromProcesses']=[{'guid':'prepare'}]
        entities['prepare']={'name':'preparer','typeName':'Process',
                             'description':'Processus de préparation réalisé avec ToolPrep : conversion des dates.',
                             'inputs':[{'guid':'raw'}],'outputs':[{'guid':'file'}]}
        entities['load']['outil_utilise']='ToolImport'
        entities['raw']={'name':'raw.json','typeName':'hdfs_path'}
        self.n['process_names']=lambda e,d:', '.join(entities[r['guid']]['name'] for r in e.get(d,[]))
        self.n['sqlite_tracking_transformations']=lambda:[]
        return entities

    def test_process_attribute_intents_and_missing_values(self):
        entities=self.attribute_fixture()
        for q,expected in (
            ('Quel outil a été utilisé ?','ToolPrep'),
            ('Quel outil a été utilisé pour préparer les données ?','ToolPrep'),
            ('Quel outil a été utilisé pour importer les données ?','ToolImport'),
            ('Quel est le fichier d’entrée ?','raw.json'),
            ('Quel fichier a été produit ?','dynamic_source.csv')):
            answer=self.n['chatbot'](q,'sqlite')
            self.assertIn(expected,answer)
            self.assertNotIn('Transformations enregistrées',answer)
        for q in ('Quelle est la date de la transformation ?', 'Quand la transformation a-t-elle été réalisée ?'):
            self.assertEqual(self.n['chatbot'](q,'sqlite'),"La date de la transformation n'est pas renseignée dans les métadonnées disponibles.")
        q='Combien de lignes existaient avant et après la transformation ?'
        self.assertIn("n'est pas renseigné",self.n['chatbot'](q,'sqlite'))
        entities['prepare'].update(nombre_lignes_avant=123,nombre_lignes_apres=0,date_transformation='2026-01-02')
        answer=self.n['chatbot'](q,'sqlite')
        self.assertIn('123',answer);self.assertIn('**Après transformation :** 0',answer)
        self.assertNotIn('conversion',answer)
        self.assertIn('2026-01-02',self.n['chatbot']('Quelle est la date de la transformation ?','sqlite'))
        before=self.n['chatbot']('Quel est le nombre de lignes avant la transformation ?','sqlite')
        self.assertIn('123',before);self.assertNotIn('Après transformation',before)
        after=self.n['chatbot']('Combien de lignes restent après le traitement ?','sqlite')
        self.assertIn('**Après transformation :** 0',after);self.assertNotIn('Avant transformation',after)

    def test_explicit_tracking_records(self):
        self.n['sqlite_atlas_metadata']=lambda:{'tables':[]}
        reader=self.n['sqlite_tracking_transformations']
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE tracking_data (processus TEXT, source TEXT, destination TEXT, type_transformation TEXT, description TEXT, outil_utilise TEXT, date_transformation TEXT, nombre_lignes_avant INTEGER, nombre_lignes_apres INTEGER)')
            db.execute('INSERT INTO tracking_data VALUES (?,?,?,?,?,?,?,?,?)',('prep','in.csv','out.csv','filter','Description réelle','Tool','2026-01-01',10,0))
            db.commit()
        self.n['sqlite_tracking_transformations']=lambda:self.fail('Tracking must not be read')
        answer=self.n['chatbot']('Quelles transformations ont été enregistrées dans tracking_data ?','sqlite')
        self.assertEqual(answer,"Aucune transformation n'est renseignée dans les métadonnées disponibles.")

    def test_partial_process_attribute_fallback(self):
        entities=self.attribute_fixture()
        entities['prepare']['rowsBefore']=25
        self.n['sqlite_tracking_transformations']=lambda:[
            {'processus':'preparer','nombre_lignes_avant':99,'nombre_lignes_apres':12},
            {'processus':'other','nombre_lignes_apres':500}]
        answer=self.n['chatbot']('Combien de lignes existaient avant et après la transformation ?','sqlite')
        self.assertIn('**Avant transformation :** 25',answer)
        self.assertIn('**Après transformation :** non renseigné',answer)
        self.assertNotIn('99',answer);self.assertNotIn('500',answer)

    def test_process_inventory_questions_subtypes_and_duplicates(self):
        entities={
            'p':{'typeName':'Process','attributes':{'name':'prepare_dynamic','description':'Processus de préparation réalisé avec ToolX : conversion.'},
                 'relationshipAttributes':{'inputs':[{'guid':'in'}],'outputs':[{'guid':'out'}]}},
            'custom':{'typeName':'CustomStage','attributes':{'name':'custom_dynamic','outil_utilise':'ToolY','transformation':'validation'}},
            'deleted':{'typeName':'Process','status':'DELETED','attributes':{'name':'deleted_dynamic'}},
            'in':{'attributes':{'name':'input_dynamic.csv'}},
            'out':{'attributes':{'name':'output_dynamic.csv'}}}
        calls=[]
        def api(path,params=None):
            calls.append((path,params))
            if path.endswith('/types/typedefs'):
                return {'entityDefs':[{'name':'Process','superTypes':['Asset']},
                                      {'name':'CustomStage','superTypes':['Process']}]}
            if path.endswith('/search/basic'):
                return {'entities':[{'guid':g} for g in ('p','custom','deleted')] if params['offset']==0 else []}
            return {'entity':entities[path.rsplit('/',1)[-1]]}
        self.n['atlas_get']=api
        self.n['sqlite_tracking_transformations']=lambda:self.fail('No tracking reads')
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('No SQLite reads')
        for q in ('Quels processus ont été enregistrés ?', 'Quels processus sont disponibles ?',
                  'Quels traitements sont enregistrés ?', 'Liste les processus du lineage.',
                  'Quels processus existent dans Atlas ?'):
            with self.subTest(question=q):
                answer=self.n['chatbot'](q)
                self.assertEqual(answer,self.n['catalogue_answer'](*self.n['catalogue_intent'](q)))
                self.assertEqual(answer.count('prepare_dynamic'),1)
                self.assertEqual(answer.count('custom_dynamic'),1)
                for value in ('ToolX','ToolY','input_dynamic.csv','output_dynamic.csv','conversion','validation'):
                    self.assertIn(value,answer)
                self.assertNotIn('deleted_dynamic',answer)
        self.assertTrue(any(params and params.get('typeName')=='CustomStage' for _,params in calls))
        self.assertTrue(any(params and params.get('offset')==3 for _,params in calls))
        for q in ('Quel processus produit la table comptes ?', 'Quels processus utilisent la table comptes ?'):
            self.assertFalse(self.n['process_inventory_intent'](q))

    def test_process_inventory_empty(self):
        self.n['atlas_get']=lambda path,params=None:{'entityDefs':[],'entities':[]}
        self.assertEqual(self.n['chatbot']('Quels processus ont été enregistrés ?'),
                         "Aucun processus n'est enregistré dans Apache Atlas.")

    def test_targeted_import_endpoints(self):
        entities=self.source_fixture()
        entities['load']['outputs']=[{'guid':'table'}]
        entities['table']['database']='dynamic.db'
        entities['prepare']={'name':'prepare','typeName':'Process','inputs':[{'guid':'unrelated'}],'outputs':[{'guid':'file'}]}
        self.n['atlas_process_inventory']=lambda:[self.n['detail'](g) for g in ('prepare','load')]
        self.n['atlas_text_fallback']=lambda *a:self.fail('No full lineage response')
        q='Quelles sont les entrées et les sorties du processus d’importation ?'
        self.assertEqual(self.n['lineage_route'](q,'sqlite'),(None,None,False))
        self.assertEqual(self.n['lineage_route'](q,resolve_source=False),(None,None,False))
        answer=self.n['chatbot'](q,'sqlite')
        self.assertEqual(answer,self.n['catalogue_answer'](*self.n['catalogue_intent'](q,'sqlite')))
        for value in ('loader','dynamic_source.csv','transactions','dynamic.db'):
            self.assertIn(value,answer)
        self.assertNotIn('prepare',answer)
        self.assertNotIn('rôle général',answer)
        only_inputs=self.n['chatbot']('Quelles sont les entrées du processus de chargement ?','sqlite')
        self.assertIn('dynamic_source.csv',only_inputs)
        self.assertNotIn('**Sortie',only_inputs)
        self.assertFalse(self.n['process_endpoints_intent']('Explique le lineage complet du processus de chargement'))
        entities['second']={'name':'another_loader','typeName':'Process','outputs':[{'guid':'table'}]}
        self.n['atlas_process_inventory']=lambda:[self.n['detail'](g) for g in ('load','second')]
        self.assertIn('Quel processus souhaitez-vous consulter',self.n['chatbot'](q,'sqlite'))

    def test_endpoints_without_destination(self):
        self.source_fixture()
        self.n['atlas_process_inventory']=lambda:[self.n['detail']('load')]
        answer=self.n['chatbot']('Quelles sont les entrées et les sorties du processus loader ?')
        self.assertNotIn('**Destination',answer)

    def test_entity_explanations_use_only_atlas_facts(self):
        explain=self.n['atlas_entity_explanation']
        self.assertEqual(explain({'typeName':'SQLiteTable','description':'Données validées.'}),'Données validées.')
        for kind,label in (('SQLiteColumn','colonne'),('SQLiteTable','table'),
                           ('SQLiteDatabase','base de données'),('Process','processus'),('hdfs_path','fichier')):
            text=explain({'typeName':kind})
            self.assertIn(label,text)
            self.assertNotIn('transactions',text)
        entities=self.source_fixture()
        entities['load']['description']='Importe les données validées.'
        entities['load']['outputs']=[{'guid':'table'}]
        entities['file']['description']='Fichier validé par le contrôle qualité.'
        entities['table']['columns']=[{'guid':'col'}]
        entities['col']={'name':'custom_field','typeName':'SQLiteColumn'}
        self.n['atlas_process_inventory']=lambda:[self.n['detail']('load')]
        answer=self.n['chatbot']('Quelles sont les entrées et les sorties du processus d’importation ?','sqlite')
        self.assertEqual(answer.count('Importe les données validées.'),1)
        self.assertEqual(answer.count('Fichier validé par le contrôle qualité.'),1)
        self.assertIn('custom_field',answer)
        self.assertNotIn('Python/Pandas',answer)

    def impact_fixture(self):
        def make(guid,kind,name,relations=None):
            return {'guid':guid,'typeName':kind,'name':name,'description':'Description de '+name,
                    'raw':{'attributes':{'name':name},'relationshipAttributes':relations or {}}}
        entities={
            'c':make('c','SQLiteColumn','Amount'),
            't':make('t','SQLiteTable','ledger'),
            'p':make('p','Process','consumer',{'inputs':[{'guid':'t'}],'outputs':[{'guid':'out'}]}),
            'producer':make('producer','Process','loader',{'outputs':[{'guid':'t'}]}),
            'out':make('out','SQLiteTable','result'),
        }
        entities['c']['raw']['relationshipAttributes']['table']={'guid':'t'}
        self.n['detail']=lambda guid:entities[guid]
        self.n['atlas_get']=lambda path,params=None:{'entities':[{'guid':'c','attributes':{'name':'Amount'}}] if params['offset']==0 and params['typeName']=='SQLiteColumn' else []}
        self.n['atlas_process_inventory']=lambda:[entities['p'],entities['producer']]
        self.n['get_lineage']=lambda *a:{'guidEntityMap':{},'relations':[]}
        self.n['column_lookup_answer']=lambda *a:self.fail('Impact must precede column lookup')
        self.n['sqlite_tracking_transformations']=lambda:self.fail('No local tracking')
        return entities

    def test_impact_priority_and_table_potential(self):
        self.impact_fixture()
        for q in ('Que se passe-t-il si la colonne Amount est supprimée ?',
                  'Quel est l’impact de la suppression de Amount ?',
                  'Quels éléments seront affectés si Amount change ?',
                  'Que se passe-t-il si je modifie Amount ?',
                  'Quel est l’impact d’un changement de type de Amount ?',
                  'Quelles dépendances seraient affectées ?'):
            self.assertTrue(self.n['impact_analysis_intent'](q))
            self.assertEqual(self.n['catalogue_intent'](q,'sqlite')[0],'impact_analysis')
            self.assertEqual(self.n['lineage_route'](q,'sqlite'),(None,None,False))
        answer=self.n['chatbot']('Que se passe-t-il si la colonne Amount est supprimée ?','sqlite')
        self.assertIn('ledger.Amount',answer)
        self.assertIn('Aucune dépendance directe',answer)
        potential=answer.split('**Impacts potentiels au niveau de la table :**')[1]
        self.assertIn('consumer',potential);self.assertIn('result',potential)
        self.assertNotIn('loader',answer)
        self.assertIn('ne prouvent pas',answer)

    def test_direct_column_impact_and_cycle(self):
        entities=self.impact_fixture()
        entities['p']['raw']['relationshipAttributes']['inputs']=[{'guid':'c'}]
        entities['p']['raw']['relationshipAttributes']['outputs'].append({'guid':'c'})
        answer=self.n['chatbot']('Quel est l’impact de la suppression de Amount ?','sqlite')
        self.assertIn('Processus directement concernés',answer)
        self.assertIn('consumer',answer);self.assertIn('result',answer)
        self.assertNotIn('Impacts potentiels',answer)
        self.assertNotIn('Aucune dépendance directe',answer)

    def test_process_database_grouping(self):
        def make(guid,kind,name,attrs=None,relations=None):
            return {'guid':guid,'typeName':kind,'name':name,'raw':{
                'attributes':dict(attrs or {},name=name),'relationshipAttributes':relations or {}}}
        entities={
            'prep':make('prep','Process','prepare',relations={'outputs':[{'guid':'file'}]}),
            'load':make('load','Process','load',relations={'inputs':[{'guid':'file'}],'outputs':[{'guid':'sq'}]}),
            'pgp':make('pgp','Process','postgres_step',relations={'outputs':[{'guid':'pg'}]}),
            'unknown':make('unknown','Process','unattached'),
            'shared':make('shared','Process','cross_database',relations={'inputs':[{'guid':'sq'}],'outputs':[{'guid':'pg'}]}),
            'file':make('file','hdfs_path','intermediate.csv'),
            'sq':make('sq','SQLiteTable','same_name',{'database':'dynamic.db'}),
            'pg':make('pg','PostgreSQLTable','same_name',relations={'database':[{'guid':'db'}]}),
            'db':make('db','PostgreSQLDatabase','dynamic_pg'),
        }
        processes=[entities[g] for g in ('prep','load','pgp','unknown','shared')]
        self.n['detail']=lambda guid:entities[guid]
        groups=self.n['process_database_groups'](processes)
        self.assertEqual(groups['prep'],(('SQLite','dynamic.db'),))
        self.assertEqual(groups['load'],groups['prep'])
        self.assertEqual(groups['pgp'],(('PostgreSQL','dynamic_pg'),))
        self.assertEqual(groups['unknown'],())
        self.assertEqual(len(groups['shared']),2)
        self.n['atlas_process_inventory']=lambda:processes
        self.n['process_names']=lambda e,k:', '.join(entities[r['guid']]['name'] for r in self.n['process_refs'](e,k))
        answer=self.n['process_inventory_answer']()
        for name in ('prepare','load','postgres_step','unattached','cross_database'):
            self.assertEqual(answer.count(self.n['response_name'](name)),1)
        self.assertIn('Base SQLite',answer)
        self.assertIn('Base PostgreSQL',answer)
        self.assertIn('Autres processus / base non identifiée',answer)
        self.assertIn('Processus partagés',answer)

    def test_global_column_types_local_and_session(self):
        self.n['st']=SimpleNamespace(session_state={})
        question='Quel est le type de données de chaque colonne ?'
        self.assertIn('De quelle table SQLite',self.n['chatbot'](question,'sqlite'))
        self.n['chatbot']('Quelles colonnes contient la table ledger ?','sqlite')
        for q in (question,'Montre toutes les colonnes','Les types des colonnes',
                  'Quel est le type de chaque colonne ?'):
            with self.subTest(question=q):
                self.assertEqual(self.n['sqlite_question_intent'](q,'sqlite'),'column_types')
                answer=self.n['chatbot'](q,'sqlite')
                self.assertIn('entry : INTEGER',answer)
                self.assertIn('amount : REAL',answer)
                self.assertNotIn('introuvable',answer)
        explicit=self.n['chatbot']('Les types des colonnes de la table odd"name','sqlite')
        self.assertIn('a : TEXT',explicit)
        self.assertNotIn('amount',explicit)
        self.n['st'].session_state['sqlite_chat_table']='removed_table'
        self.n['st'].session_state['active_table']='removed_table'
        self.assertIn('De quelle table SQLite',self.n['chatbot'](question,'sqlite'))

    def test_global_column_types_atlas_unique_and_missing_type(self):
        self.n['sqlite_atlas_metadata']=lambda:{'source':'atlas','database':'transactions1.db','tables':[
            {'name':'remote_only','columns':[{'name':'value','type':'DECIMAL'},
                                           {'name':'untyped','type':''}]}]}
        self.n['sqlite_live_metadata']=lambda **kw:self.fail('Must use Atlas')
        contexts=[]
        self.n['formulate_atlas_answer']=lambda q,a,ctx:contexts.append(ctx) or a
        q='Quel est le type de données de chaque colonne ?'
        kind,source=self.n['catalogue_intent'](q,'sqlite')
        answer=self.n['catalogue_answer'](kind,source)
        self.assertIn('table remote_only',answer)
        self.assertIn('value : DECIMAL',answer)
        self.assertIn('untyped : Type non renseigné dans Apache Atlas.',answer)
        self.assertTrue(contexts)


if __name__=='__main__':unittest.main()

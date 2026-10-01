"""Offline multi-turn tests using the real dispatcher and filtered Atlas gateway."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from chat_context import resolve_database, atlas_scope, filtered_atlas_get, scoped_cache, QUESTION
from test_lineage_routing import load_functions


def entity(guid, kind, name, **attributes):
    return {'guid': guid, 'typeName': kind, 'status': 'ACTIVE',
            'attributes': dict(name=name, **attributes)}


class DatabaseContextTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.state={}
        self.n['st']=SimpleNamespace(session_state=self.state)
        self.n['Mistral']=None
        self.n['formulate_atlas_answer']=lambda q,a,*args:a
        self.n['context']=lambda *a:[]
        items=[entity('sdb','SQLiteDatabase','transactions1.db'),
               entity('pdb','PostgreSQLDatabase','projet_data_lineage'),
               entity('other','PostgreSQLDatabase','other_database'),
               entity('st','SQLiteTable','transactions',database={'guid':'sdb'},columns=[{'guid':'sc'},{'guid':'sd'}]),
               entity('pt','PostgreSQLTable','comptes',database={'guid':'pdb'},columns=[{'guid':'pc'}]),
               entity('wrong','PostgreSQLTable','comptes',database={'guid':'other'}),
               entity('sc','SQLiteColumn','Montant',table={'guid':'st'},dataType='REAL',description='Montant de transaction'),
               entity('sd','SQLiteColumn','Date',table={'guid':'st'},dataType='TEXT'),
               entity('pc','PostgreSQLColumn','solde',table={'guid':'pt'},dataType='numeric',description='Montant disponible'),
               entity('pr','Process','process_comptes',inputs=[{'guid':'pt'}],outputs=[{'guid':'st'}])]
        self.entities={e['guid']:e for e in items}
        def fetch(path,params=None):
            if path.endswith('/types/typedefs'):return {'entityDefs':[{'name':'Process','superTypes':[]}]}
            if path.endswith('/search/basic'):
                found=[e for e in self.entities.values() if e['typeName']==params['typeName']]
                return {'entities':found[params.get('offset',0):params.get('offset',0)+params.get('limit',1000)]}
            if '/entity/guid/' in path:return {'entity':self.entities[path.rsplit('/',1)[1]]}
            if '/lineage/' in path:
                return {'guidEntityMap':self.entities,'relations':[
                    {'fromEntityId':'pt','toEntityId':'pr'}, {'fromEntityId':'pr','toEntityId':'st'}]}
            if '/uniqueAttribute/' in path:return {'entity':self.entities['pr']}
            raise AssertionError(path)
        self.fetch=fetch
        self.n['requests']=SimpleNamespace(get=lambda url,params,**kw:SimpleNamespace(
            raise_for_status=lambda:None,json=lambda:fetch(url.replace(self.n['ATLAS_URL'],''),params)))

    def ask(self,q):return self.n['chatbot'](q)

    def test_column_format_is_identical_across_environments(self):
        self.entities['sc']['attributes'].update(name='montant',dataType='DECIMAL(12,2)',description='Montant documenté')
        self.entities['pc']['attributes'].update(name='montant',dataType='DECIMAL(12,2)',description='Montant documenté')
        self.entities['st']['attributes']['columns']=[{'guid':'sc'}]
        self.entities.pop('sd')
        sqlite=self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        postgres=self.ask('Quelles sont les colonnes de comptes dans PostgreSQL ?')
        self.assertEqual(sqlite.replace('transactions','comptes'),postgres)
        self.assertIn('DECIMAL(12,2)',sqlite)
        self.assertIn('Montant documenté',sqlite)
        self.assertIn('montant',sqlite)

    def test_columns_preserve_missing_metadata(self):
        self.entities['sc']['attributes'].pop('dataType')
        self.entities['sc']['attributes'].pop('description')
        answer=self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        self.assertIn('Type technique : non renseigné dans Apache Atlas',answer)
        self.assertIn('Description : non renseignée dans Apache Atlas',answer)
        self.assertIn('TEXT',answer)
        self.assertNotIn('REAL',answer)

    def test_column_inventory_follows_reverse_relationships(self):
        self.entities['st']['attributes']['columns']=[]
        answer=self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        self.assertIn('Montant',answer)
        self.assertIn('REAL',answer)
        self.assertIn('Montant de transaction',answer)

    def test_global_inventory_without_clarification(self):
        for question in ('Quelles sont les bases de données disponibles ?',
                         'Quelles sources sont disponibles ?',
                         'Quels environnements existent ?'):
            answer=self.ask(question)
            self.assertIn('PostgreSQL',answer)
            self.assertIn('SQLite',answer)
            self.assertIn('other_database',answer)
            self.assertNotIn('Souhaitez-vous',answer)

    def test_inventory_overrides_context_temporarily(self):
        self.ask('Quelles sont les tables disponibles dans SQLite ?')
        answer=self.n['chat_message']('Quelles bases sont disponibles ?')['content']
        self.assertIn('PostgreSQL',answer)
        self.assertIn('SQLite',answer)
        self.assertEqual(self.state['active_database'],'sqlite')
        answer=self.ask('Quels environnements PostgreSQL sont disponibles ?')
        self.assertIn('PostgreSQL',answer)
        self.assertNotIn('SQLite',answer)

    def test_inventory_does_not_invent_missing_environment(self):
        self.entities={g:e for g,e in self.entities.items() if e['typeName']!='SQLiteDatabase'}
        answer=self.ask('Quelles bases sont disponibles ?')
        self.assertNotIn('SQLite',answer)
        self.entities={}
        self.assertIn('Aucune base',self.ask('Quelles bases sont disponibles ?'))

    def test_resolve_unique_table_and_clarify_duplicate(self):
        self.entities.pop('wrong')  # This scenario has exactly one Atlas entity named comptes.
        answer=self.ask('Décris la table comptes.')
        self.assertNotEqual(answer,QUESTION)
        self.assertEqual(self.state['active_database'],'postgresql')
        self.state.clear()
        self.entities['duplicate']=entity('duplicate','SQLiteTable','comptes',database={'guid':'sdb'})
        self.assertEqual(self.ask('Décris la table comptes.'),QUESTION)
        self.state['active_database']='postgresql'
        self.assertEqual(self.ask('Décris la table comptes.'),QUESTION)
        self.assertNotEqual(self.ask('Décris la table comptes dans PostgreSQL.'),QUESTION)

    def test_table_name_does_not_require_qualified_name(self):
        self.entities.pop('wrong')
        self.entities['pt']['attributes']['qualifiedName']='server/catalog/public/comptes@production'
        answer=self.ask('Décris la table comptes.')
        self.assertIn('solde',answer)
        self.assertEqual(self.state['active_table_guid'],'pt')
        self.assertNotIn('Précisez son nom',answer)

    def test_global_lookup_before_missing_in_active_environment(self):
        self.state['active_database']='postgresql'
        answer=self.ask('Décris la table transactions')
        self.assertEqual(self.state['active_database'],'sqlite')
        self.assertEqual(self.state['active_table_guid'],'st')
        self.assertIn('transactions',answer)
        self.assertNotIn('introuvable',answer)

    def test_transactions_duplicate_uses_context(self):
        self.entities['ptrans']=entity('ptrans','PostgreSQLTable','transactions',database={'guid':'pdb'})
        self.assertEqual(self.ask('Décris la table transactions'),QUESTION)
        self.state['active_database']='sqlite'
        self.assertEqual(self.ask('Quelles sont les colonnes de transactions ?'),QUESTION)
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        answer=self.ask('Quelles sont les colonnes de transactions ?')
        self.assertIn('Montant',answer)
        self.assertEqual(self.state['active_table_guid'],'st')

    def test_global_location_and_comparison_preserve_active_context(self):
        self.entities['ptrans']=entity('ptrans','PostgreSQLTable','transactions',
                                      database={'guid':'pdb'},description='Version PostgreSQL')
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        remembered={k:self.state.get(k) for k in ('active_database','active_table','active_table_guid')}
        for question in (
            'Dans quelle base se trouve la table transactions ?',
            'Dans quelles bases existe la table transactions ?',
            'Où se trouve la table transactions ?',
            'Est-ce que transactions existe dans PostgreSQL et SQLite ?',
            'Compare transactions dans PostgreSQL et SQLite.',
        ):
            with self.subTest(question=question):
                answer=self.n['chat_message'](question)['content']
                self.assertIn('PostgreSQL',answer)
                self.assertIn('SQLite',answer)
                self.assertNotIn('uniquement',answer)
                self.assertNotIn('Souhaitez-vous',answer)
                self.assertEqual(remembered,{k:self.state.get(k) for k in remembered})
                self.assertEqual(self.state['database_scope'],'all')
        self.assertIn('Montant',self.ask('Quelles sont les colonnes de transactions ?'))
        self.assertEqual(self.state['database_scope'],'sqlite')

    def test_global_location_finds_table_outside_active_database(self):
        self.state['active_database']='sqlite'
        answer=self.ask('Dans quelle base se trouve la table comptes ?')
        self.assertIn('PostgreSQL',answer)
        self.assertIn('other_database',answer)
        self.assertNotIn('introuvable',answer)
        self.assertEqual(self.state['active_database'],'sqlite')

    def test_sqlite_persistence(self):
        self.assertIn('transactions',self.ask('Quelles sont les tables disponibles dans la base SQLite ?'))
        self.assertIn('Montant',self.ask('Quelles sont les colonnes de transactions ?'))
        answer=self.ask('Quelle colonne représente le montant ?')
        self.assertIn('`Montant`',answer)
        self.assertNotIn('solde',answer)
        self.assertEqual(self.state['active_database'],'sqlite')
        self.assertEqual(self.state['active_table'],'transactions')

    def test_switch_and_lineage_followup(self):
        spy=Mock(return_value='lineage')
        self.n['lineage_intent_answer']=spy
        self.ask('Explique le lineage de transactions dans SQLite')
        self.ask('Maintenant explique le lineage de comptes dans PostgreSQL')
        self.ask('Quels sont les éléments en aval ?')
        question,source=spy.call_args.args
        self.assertIn('table comptes',question)
        self.assertEqual(source,'postgresql')
        self.assertEqual(self.state['active_table'],'comptes')
        self.assertNotIn('transactions',question)
        answer=self.ask('Quelle colonne représente le solde ?')
        self.assertIn('`solde`',answer)

    def test_temporary_global(self):
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        answer=self.ask('Cherche dans les deux bases les colonnes liées au montant')
        self.assertIn('`Montant`',answer)
        self.assertIn('`solde`',answer)
        self.assertEqual(self.state['database_scope'],'all')
        self.assertEqual(self.state['active_database'],'sqlite')
        self.assertEqual(self.state['active_table'],'transactions')
        self.assertIn('`Date`',self.ask('Quelle colonne contient la date ?'))
        self.assertEqual(self.state['database_scope'],'sqlite')
        for q in ('Compare SQLite et PostgreSQL','Quelles sont les tables dans SQLite et PostgreSQL ?'):
            answer=self.ask(q)
            self.assertIn('transactions',answer)
            self.assertIn('comptes',answer)
            self.assertEqual(self.state['active_database'],'sqlite')

    def test_unknown_database_no_atlas_query(self):
        self.n['requests'].get=Mock(side_effect=AssertionError('No Atlas before scope resolution'))
        self.assertEqual(self.ask('Quelle colonne représente le montant ?'),QUESTION)

    def test_aliases_invalid_table_and_session_isolation(self):
        self.n['lineage_intent_answer']=Mock(return_value='lineage')
        self.ask('Quel est le lineage dans transactions1.db ?')
        self.assertEqual(self.state['active_database'],'sqlite')
        self.ask('Quelles sont les colonnes de transactions ?')
        self.ask('Quelles sont les colonnes de la table inconnue ?')
        self.assertEqual(self.state['active_table'],'transactions')
        self.assertNotIn('Montant',self.ask('Quelles sont les colonnes de inconnue ?'))
        self.ask('Quelles sont les tables de projet_data_lineage ?')
        self.assertEqual(self.state['active_database'],'postgresql')
        self.assertIsNone(self.state['active_table'])
        self.n['st']=SimpleNamespace(session_state={})
        self.assertEqual(self.ask('Quelle colonne contient la date ?'),QUESTION)

    def test_scope_filters_membership_relationships_and_graph(self):
        with atlas_scope('postgresql'):
            tables=filtered_atlas_get(self.fetch,'/api/atlas/v2/search/basic',{'typeName':'PostgreSQLTable'})['entities']
            self.assertEqual([t['guid'] for t in tables],['pt'])
            self.assertEqual(filtered_atlas_get(self.fetch,'/api/atlas/v2/search/basic',{'typeName':'SQLiteTable'})['entities'],[])
            process=filtered_atlas_get(self.fetch,'/api/atlas/v2/entity/guid/pr')['entity']
            self.assertEqual(process['attributes']['outputs'],[])
            graph=filtered_atlas_get(self.fetch,'/api/atlas/v2/lineage/pt')
            self.assertNotIn('st',graph['guidEntityMap'])
            self.assertEqual(len(graph['relations']),1)
        self.assertIn('st',filtered_atlas_get(self.fetch,'/api/atlas/v2/lineage/pt')['guidEntityMap'])

    def test_cache_bypass_and_exception_cleanup(self):
        cached=Mock(return_value='cached');cached.clear=Mock()
        function=scoped_cache(lambda f:cached)(lambda:'scoped')
        self.assertEqual(function(),'cached')
        with self.assertRaises(RuntimeError):
            with atlas_scope('sqlite'):
                self.assertEqual(function(),'scoped')
                raise RuntimeError('fixture failure')
        self.assertEqual(function(),'cached')

    def test_all_intents_receive_context(self):
        from test_intent_routing import CASES
        for question,intent,handler in CASES:
            with self.subTest(intent=intent):
                spy=Mock(return_value='scoped answer')
                previous=self.n[handler]
                self.n[handler]=spy
                try:
                    self.state.update(active_database='postgresql',active_chat_source='postgresql')
                    self.assertEqual(self.ask(question),'scoped answer')
                    self.assertEqual(spy.call_args.args[1],'postgresql')
                finally:self.n[handler]=previous

    def test_graph_ui_uses_context(self):
        message=self.n['chat_message']('Affiche le lineage de comptes dans PostgreSQL')
        self.assertEqual(message['response_type'],'lineage')
        self.assertEqual(self.state['active_table'],'comptes')
        message=self.n['chat_message']('Affiche le lineage en aval')
        self.assertIn('table comptes',message['lineage_question'])

    def test_pagination_after_rejected_page(self):
        bad=entity('bad','PostgreSQLTable','bad',databaseName='other_database')
        good=entity('good','PostgreSQLTable','good',databaseName='projet_data_lineage')
        rows=[dict(bad,guid='bad'+str(i)) for i in range(1000)]+[good]
        def fetch(path,params):
            if '/entity/guid/' in path:return {'entity':good}
            return {'entities':rows[params['offset']:params['offset']+params['limit']]}
        with atlas_scope('postgresql'):
            result=filtered_atlas_get(fetch,'/api/atlas/v2/search/basic',{'typeName':'PostgreSQLTable','limit':1})
            self.assertEqual([e['guid'] for e in result['entities']],['good'])

    def test_process_answers_are_filtered_before_formatting(self):
        answer=self.ask('Quels processus sont disponibles dans PostgreSQL ?')
        self.assertIn('process_comptes',answer)
        self.assertIn('comptes',answer)
        self.assertNotIn('transactions',answer)
        self.assertNotIn('SQLite',answer)

    def test_file_membership_from_lineage(self):
        self.entities['file']=entity('file','hdfs_path','source.csv')
        original=self.fetch
        def fetch(path,params=None):
            payload=original(path,params)
            if '/lineage/' in path:
                payload['relations'].append({'fromEntityId':'file','toEntityId':'pr'})
            return payload
        with atlas_scope('postgresql'):
            self.assertEqual(filtered_atlas_get(fetch,'/api/atlas/v2/entity/guid/file')['entity']['status'],'ACTIVE')


if __name__=='__main__':unittest.main()

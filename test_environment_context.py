"""Context priority through the real app.py chat entry point; read-only Atlas fixture."""
import unittest
from types import SimpleNamespace

from chat_context import explicit_environments, normalize_environment_mentions, resolve_database, QUESTION
from intent_routing import interpret_lineage_question
from test_lineage_routing import load_functions


class EnvironmentContextTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.state={}
        self.n.update(st=SimpleNamespace(session_state=self.state),Mistral=None,context=lambda *a:[],
                      SQLITE_TABLE_GUID='sq_transactions')
        self.entities={}
        for guid,name,kind,db in (
            ('clients','clients','PostgreSQLTable','projet_data_lineage'),
            ('agences','agences','PostgreSQLTable','projet_data_lineage'),
            ('comptes','comptes','PostgreSQLTable','projet_data_lineage'),
            ('pg_transactions','transactions','PostgreSQLTable','projet_data_lineage'),
            ('sq_transactions','transactions','SQLiteTable','transactions1.db'),
            ('csv','transactions1.csv','File',''),
            ('opening','process_ouverture_compte','Process',''),
            ('posting','process_comptes_transactions','Process',''),
            ('loading','Chargement_SQLite','Process',''),
        ):
            self.entities[guid]=dict(guid=guid,status='ACTIVE',typeName=kind,
                attributes=dict(name=name,qualifiedName=name+'@'+(db or 'project'),databaseName=db),
                relationshipAttributes={})
        self.edges=[('clients','opening'),('agences','opening'),('opening','comptes'),
                    ('comptes','posting'),('posting','pg_transactions'),('csv','loading'),('loading','sq_transactions')]
        for a,b in self.edges:
            left=self.entities[a];right=self.entities[b]
            left['relationshipAttributes'].setdefault('outputs' if left['typeName']=='Process' else 'inputToProcesses',[]).append({'guid':b})
            right['relationshipAttributes'].setdefault('inputs' if right['typeName']=='Process' else 'outputFromProcesses',[]).append({'guid':a})
        self.n['requests']=SimpleNamespace(get=self.get)

    def get(self,url,params=None,**kwargs):
        params=params or {}
        if '/types/typedefs' in url:
            payload={'entityDefs':[{'name':'Process','superTypes':[]}]}
        elif '/search/' in url:
            kind=params.get('typeName') or params.get('query','').removeprefix('from ')
            items=[e for e in self.entities.values() if e['typeName']==kind or kind=='DataSet' and e['typeName']!='Process']
            offset=params.get('offset',0)
            payload={'entities':items[offset:offset+params.get('limit',1000)]}
        elif '/entity/guid/' in url:
            payload={'entity':self.entities[url.rsplit('/',1)[1]]}
        elif '/lineage/' in url:
            start=url.rsplit('/',1)[1];seen={start};front={start};edges=set()
            for _ in range(params.get('depth',1)):
                step={(a,b) for a,b in self.edges if
                      (params.get('direction')!='INPUT' and a in front) or
                      (params.get('direction')!='OUTPUT' and b in front)}
                edges.update(step);found={g for pair in step for g in pair}
                front=found-seen;seen.update(found)
            payload={'guidEntityMap':{g:self.entities[g] for g in seen},
                     'relations':[dict(fromEntityId=a,toEntityId=b) for a,b in edges]}
        else:raise AssertionError('Unexpected Atlas read: '+url)
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload)

    def ask(self,question,source=None):
        return self.n['chat_message'](question,source)['content']

    def previous_sqlite(self):
        self.ask('Peux-tu résumer le Data Lineage SQLite dans ce projet ?')
        self.assertEqual(self.state['active_database'],'sqlite')

    def test_unique_accounts_overrides_previous_sqlite(self):
        self.previous_sqlite()
        answer=self.ask('Quel est le lineage complet de la table comptes ?')
        self.assertEqual(self.state['active_database'],'postgresql')
        self.assertEqual(self.state['active_table'],'comptes')
        self.assertIn('process_ouverture_compte',answer)
        self.assertNotIn('environnement sqlite',answer)

    def test_all_postgresql_aliases_override_sqlite(self):
        for alias in ('POSTGRESQL','POSTGESQL','postgres','postgres sql','projet_data_lineage','postgre','pgsql'):
            with self.subTest(alias=alias):
                self.previous_sqlite()
                answer=self.ask('Quel est le lineage complet de la table comptes de la base '+alias+'?')
                self.assertEqual(self.state['active_database'],'postgresql')
                self.assertEqual(self.state['active_table'],'comptes')
                self.assertIn('process_ouverture_compte',answer)

    def test_ambiguous_transactions_without_reliable_context(self):
        for state in ({},{'active_database':'sqlite'},
                      {'active_database':'sqlite','active_table_guid':'deleted'}):
            self.state.clear();self.state.update(state)
            answer=self.ask('Quelle table alimente transactions ?')
            self.assertIn('PostgreSQL',answer);self.assertIn('SQLite',answer)
            self.assertIn('Laquelle',answer)

    def test_explicit_transactions_postgresql(self):
        self.previous_sqlite()
        answer=self.ask('Quelle table alimente transactions dans PostgreSQL ?')
        self.assertIn('comptes → process_comptes_transactions → transactions',answer)
        self.assertEqual(self.state['active_database'],'postgresql')

    def test_explicit_transactions_sqlite_aliases(self):
        for alias in ('SQLite','transactions1.db','transactions1'):
            with self.subTest(alias=alias):
                self.state['active_database']='postgresql'
                answer=self.ask('Quelle table alimente transactions dans '+alias+' ?')
                self.assertIn('transactions1.csv → Chargement_SQLite → transactions',answer)
                self.assertEqual(self.state['active_database'],'sqlite')

    def test_generic_homonyms_require_reliable_identity(self):
        self.entities['sq_accounts']=dict(guid='sq_accounts',status='ACTIVE',typeName='SQLiteTable',
            attributes=dict(name='comptes',qualifiedName='comptes@transactions1.db',databaseName='transactions1.db'))
        self.previous_sqlite()
        self.assertEqual(self.ask('Quel est le lineage complet de la table comptes ?'),QUESTION)

    def test_explicit_wrong_engine_never_silently_switches(self):
        answer=self.ask('Quel est le lineage complet de la table comptes dans SQLite ?')
        self.assertIn('pas dans l’environnement sqlite',answer)
        self.assertEqual(self.state['active_database'],'sqlite')

    def test_validated_identity_and_button_choice(self):
        self.ask('Quelle table alimente transactions dans SQLite ?')
        self.assertIn('Chargement_SQLite',self.ask('Quelle table alimente transactions ?'))
        self.assertIn('process_comptes_transactions',self.ask('Quelle table alimente transactions ?','postgresql'))

    def test_identifiers_and_filenames_unchanged(self):
        for value in ('transactions1.csv','transactions@transactions1.db@projet_data_lineage',
                      'table@postgres','postgres_column','/data/transactions1'):
            self.assertEqual(normalize_environment_mentions(value),value)
            self.assertEqual(explicit_environments(value),set())

    def test_alias_detection_and_structured_parser_agree(self):
        for alias in ('POSTGESQL','postgres sql','postgre','pgsql'):
            question='Quelle table alimente transactions de la base '+alias+'?'
            self.assertEqual(resolve_database(question,{'active_database':'sqlite'}),'postgresql')
            parsed=interpret_lineage_question(question)
            self.assertEqual((parsed['engine'],parsed['target'],parsed['database']),('postgresql','transactions',None))


if __name__=='__main__':unittest.main()

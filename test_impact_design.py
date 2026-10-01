import ast
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
import unittest

from impact_ui import sqlite_result_groups


class ImpactDesignTests(unittest.TestCase):
    def fixture(self):
        return {'tables': {'t': {'guid':'t','name':'source'}, 'out':{'guid':'out','name':'target'}},
                'columns': {'c':{'guid':'c','name':'id'},'ref':{'guid':'ref','name':'source_id'}},
                'column_parent': {'c':'t','ref':'out'}, 'fk_pairs':{('ref','c')},
                'processes':{'p':{'guid':'p','name':'transform'}},'database':None}

    def test_queue_results_unchanged_and_no_magic_nulls(self):
        source=Path('app.py').read_text(encoding='utf-8')
        function=next(ast.get_source_segment(source,node) for node in ast.parse(source).body
                      if isinstance(node,ast.FunctionDef) and node.name=='impact_pg')
        old=function.replace("q.append(('table',source_guid))\n        for cg,tg in par.items():\n            if tg==source_guid:q.append(('column',cg))",
                             "q.append(('table',source_guid));[q.append(('column',cg)) for cg,tg in par.items() if tg==source_guid]")
        old=old.replace("elif kind=='Base':\n        for g in tables:q.append(('table',g))",
                        "elif kind=='Base':[q.append(('table',g)) for g in tables]")
        setup = f'''
from collections import defaultdict,deque
def pg_catalog(use_dsl=False):return {self.fixture()!r}
POSTGRES_TABLE_NAMES={{'source','target'}}
def downstream_table(g):return {{'out':{{'label':'target','type':'PostgreSQLTable'}},'p':{{'label':'transform','type':'Process'}}}}
def get_lineage(*args):return {{}}
def lineage_graph(data):return {{}},[]
'''
        before={};after={}
        exec(setup+old,before);exec(setup+function,after)
        for kind,guid in [('Table','t'),('Colonne','c'),('Base','db'),('Process','p')]:
            self.assertEqual(before['impact_pg'](guid,kind),after['impact_pg'](guid,kind))
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_string(setup+function+"\nr=impact_pg('t','Table')\nr=impact_pg('db','Base')").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.json)

    def test_sqlite_grouping_preserves_all_nodes(self):
        items=[{'id':str(i),'label':kind,'type':kind} for i,kind in enumerate(
            ['SQLiteTable','SQLiteColumn','Process','SQLiteDatabase','File'])]
        original=deepcopy(items)
        groups=sqlite_result_groups(items)
        self.assertEqual([len(groups[k]) for k in ('tables','columns','processes','others')],[1,1,1,2])
        self.assertEqual(items,original)
        self.assertEqual({x['id'] for group in groups.values() for x in group},{x['id'] for x in items})

    def test_page_postgresql_sqlite_and_empty_results(self):
        from streamlit.testing.v1 import AppTest
        source=Path('app.py').read_text(encoding='utf-8')
        start=source.index("elif st.session_state.page=='Analyse d’impact':")
        end=source.index('\nelif st.session_state.page==',start+1)
        page=source[start:end].replace('elif ','if ',1)
        setup=f'''
import streamlit as st
st.session_state.page='Analyse d’impact'
def pg_catalog(use_dsl=False):return {self.fixture()!r}
def impact_pg(guid,kind,catalog=None):
    st.session_state.called=(guid,kind)
    return {{'tables':[{{'name':'target'}}], 'columns':[{{'table':'target','name':'source_id'}}], 'processes':[{{'name':'transform'}}]}}
def sqlite_lineage():return {{'s':{{'label':'source','type':'SQLiteTable'}}}},[]
def get_lineage(*args):
    st.session_state.lineage_args=args
    return {{}}
def lineage_graph(data):return {{}},[]
'''
        app=AppTest.from_string(setup+page).run()
        self.assertFalse(app.exception)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.called,('t','Table'))
        self.assertTrue(any('target.source_id' in m.value for m in app.markdown))
        self.assertFalse(app.json)
        app.radio(key='is').set_value('Transactions / SQLite').run()
        app.button(key='sib').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.lineage_args,('s','OUTPUT',10))
        self.assertIn('Aucune table impactée.',[c.value for c in app.caption])
        self.assertIn('Aucune colonne impactée.',[c.value for c in app.caption])
        self.assertIn('Aucun processus concerné.',[c.value for c in app.caption])


if __name__=='__main__':unittest.main()

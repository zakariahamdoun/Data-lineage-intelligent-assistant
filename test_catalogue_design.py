from pathlib import Path
import unittest

from catalogue_ui import catalogue_counts, catalogue_table


class CatalogueDesignTests(unittest.TestCase):
    def test_counts_and_safe_rendering(self):
        rows = [{'Objet': '<script>alert(1)</script>', 'Type': category,
                 'Type Atlas': 'TestType', 'Description': 'Texte réel', 'Règle métier': rule}
                for category, rule in [('Base de données', None), ('Table', ''),
                                       ('Colonne', '  '), ('Colonne', 'Non renseignée'),
                                       ('Processus', 'Règle documentée')]]
        self.assertEqual(catalogue_counts(rows), [1, 1, 2, 1])
        rendered = catalogue_table(rows)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('Règle documentée', rendered)
        self.assertEqual(rows[0]['Règle métier'], None)

    def test_source_selection_search_and_refresh(self):
        from streamlit.testing.v1 import AppTest
        source = Path('app.py').read_text(encoding='utf-8')
        start = source.index("elif st.session_state.page=='Catalogue des métadonnées':")
        end = source.index('\nelif st.session_state.page==', start+1)
        page = source[start:end].replace('elif ', 'if ', 1)
        setup = '''
import streamlit as st
from test_lineage_routing import load_functions
globals().update(load_functions())
st.session_state.page='Catalogue des métadonnées'
def entity(guid, name, kind, rule=None):
    return dict(guid=guid,name=name,typeName=kind,description='Description Atlas',
                qualifiedName=name,raw={'attributes':{'businessRule':rule}},referred={})
db=entity('db','demo','PostgreSQLDatabase')
table=entity('t','example','PostgreSQLTable','Règle Atlas')
column=entity('c','id','PostgreSQLColumn')
def pg_catalog():
    return dict(database=db,tables={'t':table},columns={'c':column},column_parent={'c':'t'},processes={})
SQLITE_TABLE_GUID='sql'
def get_entity(guid):return {'stub':True}
def detail(guid,payload=None):return entity('sql','transactions','SQLiteTable')
def exact(*args):return None
def get_lineage(*args):return {'guidEntityMap':{}}
def refresh_metadata():
    st.session_state.refreshed=True
    return [table],None
'''
        app = AppTest.from_string(setup+page).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Règle Atlas' in x.value for x in app.markdown))
        app.text_input(key='catalogue_search').input('absent').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        app.text_input(key='catalogue_search').input('').run()
        app.radio(key='catalogue_source').set_value('Transactions / SQLite').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('SQLiteTable' in x.value for x in app.markdown))
        self.assertFalse(any('PostgreSQLTable' in x.value for x in app.markdown))
        app.button(key='refresh_metadata').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state.refreshed)


if __name__ == '__main__':
    unittest.main()

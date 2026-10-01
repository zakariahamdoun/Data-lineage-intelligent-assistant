from pathlib import Path
import unittest


class AssistantExampleTests(unittest.TestCase):
    questions=[
        'Combien de bases de données sont présentes dans Apache Atlas ?',
        'Explique le Data Lineage de la base SQLite',
        'Explique le Data Lineage de la base PostgreSQL',
        'Quel est l’impact d’une modification de la table comptes ?'
    ]

    def app(self):
        from streamlit.testing.v1 import AppTest
        source=Path('app.py').read_text(encoding='utf-8')
        start=source.index("if st.session_state.page=='Assistant IA':")
        end=source.index("elif st.session_state.page=='Visualisation du Data Lineage':")
        section=source[start:end]
        setup="""import re
import streamlit as st
building_data=''
def present_chat_answer(value): return value
def chatbot_error_message(error): return str(error)
def render_chat_lineage(*args): pass
def chat_message(question, source=None): return {'role':'assistant','content':'Réponse : '+question}
st.session_state.page='Assistant IA'
"""
        return AppTest.from_string(setup+section,default_timeout=15).run()

    def test_each_example_prefills_without_creating_a_chat_message(self):
        for index,question in enumerate(self.questions):
            with self.subTest(question=question):
                app=self.app()
                app.button(key=f'example_question_{index}').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.chat_input(key='assistant_chat_input').value,question)
                self.assertEqual(app.session_state['messages'],[])


if __name__=='__main__': unittest.main()

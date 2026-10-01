import unittest
from test_entity_impact import EntityImpactTests
from lineage_references import resolve_reference


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        fixture=EntityImpactTests()
        fixture.setUp()
        self.n=fixture.n
        self.entities=fixture.entities
        def graph(guid,direction,*args):
            index=int(guid)
            neighbor=index-1 if direction=='INPUT' else index+1
            if not 0<=neighbor<5:return {'relations':[]}
            a,b=(str(neighbor),guid) if direction=='INPUT' else (guid,str(neighbor))
            return {'relations':[{'fromEntityId':a,'toEntityId':b}]}
        self.n['get_lineage']=graph

    def test_initial_source_impact_without_exact_name(self):
        answer=self.n['chatbot']('Quels objets seraient concernés si la source initiale du lineage SQLite était modifiée ?')
        self.assertIn('Une modification de `transactions_sep.xlsx`',answer)
        self.assertIn('le fichier `transactions1.csv`, puis la table `transactions`',answer)
        self.assertIn('Preparation_transactions (Process)',answer)
        self.assertNotIn('n’a pas été trouvé',answer)

    def test_roles_resolve_from_context(self):
        for question,expected in (
            ('le premier fichier du lineage','0'),
            ('le fichier source','2'),
            ('le processus de chargement','3'),
            ('l’objet précédent','3'),
            ('la destination finale','4'),
            ('la table finale','4'),
            ('la source de transactions','2')):
            with self.subTest(question=question):
                found=resolve_reference(question,list(self.entities.values()),{'active_table_guid':'4'},'sqlite',
                    self.n['detail'],self.n['get_lineage'],self.n['process_refs'],{'Process'})
                self.assertEqual([e['guid'] for e in found],[expected])

    def test_missing_lineage_does_not_invent_identity(self):
        self.n['get_lineage']=lambda *args:{'relations':[]}
        answer=self.n['chatbot']('Quel impact si la source initiale du lineage SQLite est modifiée ?')
        self.assertIn('ne peut pas être résolue',answer)
        self.assertNotIn('Une modification de `transactions_sep.xlsx`',answer)

    def test_nonimpact_reference_uses_conversation_context(self):
        self.n['st'].session_state.update(active_database='sqlite',active_table_guid='4')
        answer=self.n['chat_message']('Quelle est la destination finale ?')['content']
        self.assertIn('`transactions`',answer)
        self.assertNotIn('potentiellement impacter',answer)


if __name__=='__main__':unittest.main()

"""Table purpose must come from the full Atlas entity, never its name."""
import unittest
from intent_routing import classify_intent
from test_lineage_routing import load_functions


class TableRoleTests(unittest.TestCase):
    def setUp(self):
        self.n=load_functions()
        self.raw={'guid':'t','status':'ACTIVE','typeName':'PostgreSQLTable',
                  'attributes':{'name':'clients'},'relationshipAttributes':{}}
        self.n['find_requested_tables']=lambda *a:[('postgresql',self.raw)]
        self.calls=[]
        def fetch(path,params=None):
            self.calls.append(path)
            return {'entity':self.raw}
        self.n['atlas_get']=fetch
        self.n['context']=lambda *a:self.fail('Role must bypass vector retrieval')

    def answer(self):
        return self.n['table_metadata_answer']('Quel est le rôle de la table clients ?')

    def test_routing(self):
        for q in ('Quel est le rôle de la table clients ?', 'À quoi sert la table clients ?'):
            self.assertEqual(classify_intent(q),'table_details')
            self.assertEqual(self.n['table_metadata_intent'](q),'role')
        self.assertEqual(classify_intent('Quel est le rôle du processus process_test ?'),'process_details')
        self.assertNotEqual(self.n['table_metadata_intent']('Quel est le rôle de la colonne nom ?'),'role')

    def test_documentation_and_full_entity_endpoint(self):
        self.raw['attributes'].update(description="Table contenant les informations d'identification des clients.",
                                      businessRule='Un client peut posséder plusieurs comptes.')
        answer=self.answer()
        self.assertIn("La table clients contient les informations d'identification",answer)
        self.assertIn('Un client peut posséder plusieurs comptes.',answer)
        self.assertEqual(self.calls,['/api/atlas/v2/entity/guid/t'])
        for technical in ('description','businessRule','qualifiedName','relationshipAttributes'):
            self.assertNotIn(technical,answer)

    def test_missing_documentation_does_not_infer_role(self):
        for value in (None,'','   '):
            self.raw['attributes'].update(description=value,businessRule=value)
            answer=self.answer()
            self.assertIn('n’est pas renseigné',answer)
            self.assertNotIn('identification',answer)
            self.assertNotIn('compte',answer)

    def test_rule_only_and_live_changes(self):
        self.raw['attributes']['businessRule']='Règle documentée.'
        self.assertEqual(self.answer(),'Règle documentée.')
        self.raw['attributes']['businessRule']='Règle modifiée.'
        self.assertEqual(self.answer(),'Règle modifiée.')

    def test_only_active_process_relations(self):
        self.raw['relationshipAttributes']['inputToProcesses']=[
            {'guid':'p','displayText':'process_test','entityStatus':'ACTIVE','relationshipStatus':'ACTIVE'},
            {'guid':'old','displayText':'process_deleted','entityStatus':'ACTIVE','relationshipStatus':'DELETED'}]
        answer=self.answer()
        self.assertIn('n’est pas renseigné',answer)
        self.assertIn('déclarée en entrée du processus process_test',answer)
        self.assertNotIn('process_deleted',answer)

    def test_inactive_entity(self):
        self.raw['status']='DELETED'
        self.assertIn('pas été trouvée',self.answer())


if __name__=='__main__':unittest.main()

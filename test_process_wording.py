import unittest
from process_presentation import process_flow_suffix
from upstream_presentation import describe_upstream
import test_between_entities


class ProcessWordingTests(unittest.TestCase):
    def test_recorded_role_in_natural_sentence(self):
        self.assertEqual(process_flow_suffix('Processus reliant les comptes aux transactions bancaires.','la table transactions'),
                         ', qui relie les comptes aux transactions bancaires et alimente la table transactions.')

    def test_no_role_invented(self):
        for value in (None,'','  ','Non renseignée','N/A'):
            self.assertEqual(process_flow_suffix(value,'la table destination'),', qui alimente la table destination.')

    def test_unknown_prose_preserved(self):
        text='Contrôle spécifique. Les anomalies sont conservées.'
        self.assertIn(text,process_flow_suffix(text,'la table destination'))

    def test_targeted_path_and_upstream_use_recorded_role(self):
        fixture=test_between_entities.BetweenEntitiesTests();fixture.setUp()
        fixture.data['p']['description']='Processus reliant les données aux opérations validées.'
        answer=fixture.n['chatbot']('Quel est le parcours entre origin et middle ?')
        self.assertIn('qui relie les données aux opérations validées et alimente la table middle',answer)
        self.assertNotIn('secondary',answer)
        data={'nodes':fixture.data,'edges':[('a','p'),('p','b')],'cycles':False}
        data['nodes']={g:fixture.data[g] for g in ('a','p','b')}
        self.assertIn('qui relie les données aux opérations validées',describe_upstream(data,'b'))


if __name__=='__main__':unittest.main()

import json
import unittest
from test_lineage_routing import load_functions


class MultipleRelationTests(unittest.TestCase):
    def test_live_questions_and_index(self):
        n=load_functions()
        n['context']=lambda *args:self.fail('These questions must bypass FAISS')
        answers=[]
        for question in ('Pourquoi un virement est-il relié deux fois à la table comptes ?',
                         'Quelles colonnes relient virements à comptes ?'):
            answer=n['chatbot'](question)
            answers.append(answer)
            for fact in ('deux relations', 'compte_source', 'compte_destination',
                         'comptes.id_compte', 'débité', 'crédité'):
                self.assertIn(fact,answer)
            self.assertNotIn('@projet',answer)
            self.assertLess(len(answer.split()),75)
        documents=[json.loads(doc) for doc in n['docs_atlas']()]
        table=next(doc for doc in documents if doc['name']=='virements' and doc['typeName']=='PostgreSQLTable')
        self.assertIn(answers[0],table['Relations multiples'])

    def test_dynamic_descriptions_and_deleted_relation(self):
        n=load_functions()
        def entity(name,kind,relationships=None,description=''):
            return dict(name=name,typeName=kind,status='ACTIVE',description=description,
                        raw={'relationshipAttributes':relationships or {}})
        entities={'a':entity('trajets','PostgreSQLTable'), 'b':entity('lieux','PostgreSQLTable'),
                  'pk':entity('id','PostgreSQLColumn',{'table':{'guid':'b'}})}
        for guid,description in [('depart','Lieu de départ'),('arrivee','Lieu d’arrivée')]:
            entities[guid]=entity(guid,'PostgreSQLColumn',{'table':{'guid':'a'},
                'foreignKeyTo':[{'guid':'pk'}]},description)
        text=n['grouped_foreign_key_texts'](entities)[('a','b')]
        for fact in ('trajets','lieux.id','lieu de départ','lieu d’arrivée'):
            self.assertIn(fact,text)
        entities['depart']['description']='Point initial documenté'
        self.assertIn('point initial documenté',n['grouped_foreign_key_texts'](entities)[('a','b')])
        entities['depart']['raw']['relationshipAttributes']['foreignKeyTo'][0]['relationshipStatus']='DELETED'
        self.assertEqual(n['grouped_foreign_key_texts'](entities),{})


if __name__=='__main__':unittest.main()

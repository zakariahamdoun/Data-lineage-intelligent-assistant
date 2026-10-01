"""Column meaning uses documented Atlas facts and the active conversation scope."""
import unittest
import test_database_context as fixtures
from intent_routing import classify_intent, column_meaning_request


class ColumnMeaningTests(unittest.TestCase):
    setUp=fixtures.DatabaseContextTests.setUp
    ask=fixtures.DatabaseContextTests.ask

    def add_column(self,guid,table,name,**attrs):
        kind='SQLiteColumn' if table=='st' else 'PostgreSQLColumn'
        self.entities[guid]=fixtures.entity(guid,kind,name,table={'guid':table},**attrs)
        self.entities[table]['attributes'].setdefault('columns',[]).append({'guid':guid})

    def test_six_requested_questions(self):
        self.add_column('type','st','Type de transaction',description='Colonne Type de transaction de la table transactions.')
        self.add_column('client','st','ID Clients')
        self.add_column('agency','pt','id_agence',businessDescription='Identifie l’agence de rattachement.')
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        for question,name,expected in (
            ('Que signifie la colonne Type de transaction ?','Type de transaction','nature ou la catégorie'),
            ('Que représente Montant ?','Montant','montant de transaction'),
            ('À quoi sert la colonne Date ?','Date','situer dans le temps'),
            ('Quel est le rôle de ID Clients ?','ID Clients','identifier ou à distinguer')):
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question),'column_lookup')
                answer=self.ask(question)
                self.assertIn('`'+name+'`',answer)
                self.assertIn(expected,answer)
                self.assertIn('`transactions`',answer)
                self.assertNotIn('Pour comprendre',answer)
                for value in ('virement','retrait','dépôt','paiement','comptes'):self.assertNotIn(value,answer)
        self.ask('Quelles sont les colonnes de comptes dans PostgreSQL ?')
        answer=self.ask('Que signifie la colonne solde dans comptes ?')
        self.assertIn('montant disponible',answer)
        self.assertNotIn('transactions',answer)
        self.assertIn('agence de rattachement',self.ask('À quoi sert id_agence ?'))

    def test_documentation_priority_and_business_metadata(self):
        self.add_column('code','st','Code événement',businessDescription='Classe les événements selon leur origine.',
                        businessRule='La valeur est attribuée à la création.',
                        technicalDescription='Code issu du système source.',purpose='Permet le regroupement.')
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        question='Quelle est la signification de Code événement ?'
        attrs=self.entities['code']['attributes']
        for key,expected in (
            ('businessDescription','classe les événements'),
            ('businessRule','attribuée à la création'),
            ('technicalDescription','système source'),
            ('purpose','regroupement')):
            answer=self.ask(question)
            self.assertIn(expected,answer)
            self.assertNotIn('D’après son nom',answer)
            attrs.pop(key)
        self.entities['code']['businessAttributes']={'Métier':{'businessDescription':'Permet de classer les événements.'}}
        self.assertIn('classer les événements',self.ask(question))

    def test_generic_unknown_name_and_missing_column(self):
        self.add_column('opaque','st','X42',description='Colonne X42 de la table transactions.')
        self.entities['opaque']['attributes']['table']['attributes']={'description':'Description de la table à exclure.'}
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        answer=self.ask('Que représente la colonne X42 ?')
        self.assertIn('ne permet pas de déterminer',answer)
        self.assertIn('Aucune description métier plus détaillée',answer)
        self.assertNotIn('Atlas',answer)
        self.assertNotIn('Colonne X42 de la table transactions.',answer)
        self.assertNotIn('Description de la table',answer)
        self.assertIn('introuvable',self.ask('Que signifie la colonne absente ?'))
        self.assertIn('introuvable',self.ask('Que signifie la colonne Montant dans inconnue ?'))

    def test_skip_boilerplate_and_use_documented_key_role(self):
        self.add_column('key','st','Code',businessDescription='Non renseignée',
                        description='Colonne Code de la table transactions.',isPrimaryKey=True)
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        self.assertIn('participe à la clé primaire',self.ask('Que représente Code ?'))

    def test_other_intents_and_named_column_parser(self):
        for question in ('À quoi sert process_comptes ?', 'Que représente la table comptes ?',
                         'Quelle colonne représente le montant ?'):
            self.assertIsNone(column_meaning_request(question))
        for question,intent in (
            ('À quoi sert process_comptes ?','process_details'),
            ('Quelle colonne représente le montant ?','column_lookup'),
            ('Quelles sont les colonnes de transactions ?','column_list'),
            ('Quel est le lineage de comptes ?','lineage'),
            ('Quel impact si comptes est supprimée ?','impact_analysis'),
            ('Que contient la table comptes ?','table_details')):
            self.assertEqual(classify_intent(question),intent)

    def test_explicit_table_overrides_active_and_database_filter(self):
        self.entities['another']=fixtures.entity('another','SQLiteTable','archives',database={'guid':'sdb'},columns=[])
        self.add_column('othercol','another','Date',businessDescription='Date d’archivage documentée.')
        self.entities['othercol']['typeName']='SQLiteColumn'
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        answer=self.ask('À quoi sert la colonne Date dans archives ?')
        self.assertIn('date d’archivage',answer)
        self.assertIn('`archives`',answer)
        self.assertIn('introuvable',self.ask('Que signifie la colonne solde ?'))

    def test_postgres_business_attributes_and_qualified_column_name(self):
        self.entities['pc']['attributes']['name']='comptes.solde'
        self.entities['pc']['businessAttributes']={'Métier':{'businessDescription':'Valeur disponible après comptabilisation.'}}
        self.ask('Quelles sont les colonnes de comptes dans PostgreSQL ?')
        self.assertIn('après comptabilisation',self.ask('Que signifie la colonne solde dans comptes ?'))

    def test_natural_wording_and_explicit_source(self):
        self.add_column('type','st','Type de transaction',businessDescription='Nature ou catégorie de l’opération enregistrée.')
        self.ask('Quelles sont les colonnes de transactions dans SQLite ?')
        answer=self.ask('Que signifie Type de transaction ?')
        self.assertEqual(answer,'La colonne `Type de transaction` permet d’identifier la nature ou la catégorie de l’opération enregistrée dans la table `transactions`.')
        self.assertNotIn('Atlas',answer)
        self.assertIn('Source : Apache Atlas.',self.ask('Que signifie Type de transaction ? Indique la source.'))
        self.entities['type']['attributes']['businessDescription']='Selon Apache Atlas, Nature ou catégorie de l’opération enregistrée.'
        self.assertNotIn('Atlas',self.ask('Que signifie Type de transaction ?'))


if __name__=='__main__':unittest.main()

"""Offline checks of Atlas-driven lineage summaries."""
import unittest
from test_lineage_routing import load_functions


class LineageSummaryTests(unittest.TestCase):
    def test_system_path_is_ordered_and_typed(self):
        n = load_functions()
        nodes = {
            'end': {'label': 'target', 'type': 'SQLiteTable'},
            'load': {'label': 'load_job', 'type': 'Process', 'description': 'Charge le fichier.'},
            'csv': {'label': 'intermediate.csv', 'type': 'File'},
            'prep': {'label': 'prepare_job', 'type': 'Process', 'description': 'Prépare le fichier.'},
            'start': {'label': 'initial.xlsx', 'type': 'File'},
        }
        edges = [{'from': a, 'to': b} for a, b in
                 [('load', 'end'), ('prep', 'csv'), ('csv', 'load'), ('start', 'prep')]]
        answer = n['explain_system_lineage'](nodes, edges, 'SQLite')
        self.assertIn('initial.xlsx → prepare_job → intermediate.csv → load_job → target', answer)
        self.assertLess(answer.index('processus prepare_job'), answer.index('processus load_job'))
        self.assertIn('Prépare le fichier.', answer)
        self.assertIn('la table SQLite target', answer)
        self.assertIn('Le fichier Excel initial.xlsx constitue la source initiale', answer)
        for phrase in ('Flux en amont', 'Flux en aval', 'Aucun flux visible', 'sélection Atlas'):
            self.assertNotIn(phrase, answer)
        nodes['branch'] = {'label': 'second_target', 'type': 'Table'}
        edges.append({'from': 'load', 'to': 'branch'})
        answer = n['explain_system_lineage'](nodes, edges)
        self.assertIn('load_job → second_target', answer)
        self.assertNotIn('target → second_target', answer)

    def test_complete_data_question_uses_system_walk(self):
        n=load_functions()
        question='Présente le parcours complet des données dans SQLite'
        self.assertTrue(n['whole_system_lineage'](question))
        self.assertFalse(n['whole_system_lineage']('Explique le lineage complet de la table cible dans SQLite'))
        nodes={g:{'label':label,'type':typ,'description':'Description Atlas.'} for g,label,typ in (
            ('t','cible','SQLiteTable'),('p2','charger','Process'),('csv','milieu.csv','hdfs_path'),
            ('p1','preparer','Process'),('xls','depart.xlsx','hdfs_path'))}
        edges=[{'from':a,'to':b} for a,b in [('p2','t'),('csv','p2'),('p1','csv'),('xls','p1')]]
        answer=n['explain_system_lineage'](nodes,edges,'SQLite')
        self.assertIn('depart.xlsx → preparer → milieu.csv → charger → cible',answer)
        self.assertTrue(answer.startswith('Parcours du Data Lineage :\n\n'))
        self.assertIn('Le fichier Excel depart.xlsx constitue la source initiale',answer)
        self.assertIn('enregistrées dans le fichier CSV milieu.csv',answer)
        path,explanation=answer.split('Explication du parcours :')
        self.assertEqual(len(path.strip().splitlines()),3)
        positions=[explanation.index(label) for label in ('depart.xlsx','preparer','milieu.csv','charger','cible')]
        self.assertEqual(positions,sorted(positions))
        self.assertNotIn('\n- ',explanation)
        for transition in ('passent ensuite','À l’issue de cette étape','sert ensuite d’entrée','Enfin,'):
            self.assertIn(transition,explanation)
        self.assertNotIn('Processus de chargement',explanation)
        nodes['p1']['description']='Préparation : suppression des doublons.'
        nodes['p2']['description']='Chargement dans la base cible.'
        answer=n['explain_business_lineage']('Explique le lineage complet de la table cible',nodes,edges,'cible','sqlite')
        self.assertIn('Préparation : suppression des doublons.',answer)
        self.assertIn('Chargement dans la base cible.',answer)
        for forbidden in ('Flux en amont','Flux en aval','Aucun flux visible','sélection Atlas'):
            self.assertNotIn(forbidden,answer)

    def test_natural_description_preserves_dynamic_details(self):
        n=load_functions()
        text=n['natural_process_description']('Processus de préparation réalisé avec outilA/outilB : suppression des colonnes champA et champB.')
        self.assertEqual(text,'Ce processus est réalisé avec outilA et outilB. Il supprime les colonnes champA et champB.')
        self.assertEqual(n['natural_process_description']('Processus de chargement des données depuis source.csv vers destination.'),
                         'Ce processus charge les données depuis source.csv vers destination.')
        self.assertEqual(n['natural_process_description']('Ne supprime aucune colonne.'),'Ne supprime aucune colonne.')

    def test_dynamic_paths_and_structure(self):
        n = load_functions()
        nodes = {g: {'label': g, 'type': 'Process' if g.startswith('job') else 'Table'}
                 for g in ('alpha', 'beta', 'gamma', 'job_in', 'job_out')}
        edges = [{'from': a, 'to': b} for a, b in
                 [('alpha', 'job_in'), ('job_in', 'beta'),
                  ('beta', 'job_out'), ('job_out', 'gamma')]]
        n['pg_catalog'] = lambda: {
            'fk_pairs': [('c1', 'c2')], 'column_parent': {'c1': 'beta', 'c2': 'alpha'},
            'columns': {'c1': {'name': 'reference'}, 'c2': {'name': 'key'}}}
        answer = n['explain_business_lineage'](
            'Explique le lineage de la table beta', nodes, edges, 'beta', 'postgresql')
        self.assertEqual(len(__import__('re').findall(r'^\d\. \*\*', answer, __import__('re').M)), 5)
        upstream = answer.split('2. **')[1].split('3. **')[0]
        downstream = answer.split('3. **')[1].split('4. **')[0]
        self.assertIn('alpha → job_in → beta', upstream)
        self.assertIn('beta → job_out → gamma', downstream)
        self.assertNotIn('job_out', upstream)
        self.assertNotIn('job_in', downstream)
        self.assertIn('beta.reference → alpha.key', answer)
        self.assertIn('enregistrée comme entrée du processus dans Apache Atlas', answer)
        for phrase in ('proviennent', 'Origine des données', 'Processus appliqué',
                       'Résultat produit', 'Interprétation technique'):
            self.assertNotIn(phrase, answer)
        self.assertLess(len(answer.split()), 230)

    def test_incomplete_and_cyclic_graph(self):
        n = load_functions()
        nodes = {'x': {'label': 'x', 'type': 'Table'},
                 'p': {'label': 'p', 'type': 'Process'}}
        edges = [{'from': 'x', 'to': 'p'}]
        answer = n['explain_business_lineage']('lineage x', nodes, edges, 'x', 'sqlite')
        self.assertIn('x → p → [sortie non visible]', answer)
        edges.append({'from': 'p', 'to': 'x'})
        answer = n['explain_business_lineage']('lineage x', nodes, edges, 'x', 'sqlite')
        self.assertIn('x → p → x', answer)
        self.assertLess(len(answer), 2000)


if __name__ == '__main__':
    unittest.main()

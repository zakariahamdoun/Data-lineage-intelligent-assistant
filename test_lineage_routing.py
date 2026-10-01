"""Read-only integration checks: python test_lineage_routing.py (Atlas must be running)."""
import ast
import collections
import html
import json
import logging
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
import requests


def load_functions():
    tree=ast.parse(Path('app.py').read_text(encoding='utf-8'))
    functions=[node for node in tree.body if isinstance(node,ast.FunctionDef)]
    for node in functions:node.decorator_list=[]
    namespace=dict(re=re,html=html,json=json,requests=requests,
                   defaultdict=collections.defaultdict,deque=collections.deque,
                   logger=logging.getLogger('test'),MISTRAL_API_KEY='test',
                   ATLAS_URL=os.getenv('ATLAS_URL','http://localhost:21000'),
                   ATLAS_AUTH=(os.getenv('ATLAS_USERNAME','admin'),os.getenv('ATLAS_PASSWORD','admin')))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in
            {'SQLITE_TABLE_GUID','POSTGRES_DB_NAME','POSTGRES_TABLE_NAMES','SYSTEM_PROMPT'} for t in node.targets):
            exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),namespace)
    exec(compile(ast.Module(body=functions,type_ignores=[]),'app.py','exec'),namespace)
    return namespace


class LineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n=load_functions()
        # Cache read-only Atlas responses for a consistent snapshot across assertions.
        from functools import lru_cache
        for name in ('get_entity','get_lineage','search_type','pg_catalog','sqlite_lineage'):
            cls.n[name]=lru_cache(None)(cls.n[name])

    def test_requested_questions(self):
        n=self.n
        def unavailable(**kwargs):raise RuntimeError('HTTP 429 rate_limit_exceeded')
        n['Mistral']=unavailable
        n['context']=lambda *a,**k: self.fail('Explicit requests must bypass FAISS')
        for source,question in (
            ('postgresql','Afficher le lineage de la table comptes'),
            ('sqlite','Affiche le Data Lineage du projet SQLite')):
            self.assertEqual(n['lineage_route'](question),( 'visualization',source,False))
            expected=n['local_lineage_data'](source,question)
            captured=[]
            n['st']=SimpleNamespace(markdown=lambda *a:None)
            original=n['render_graph']
            n['render_graph']=lambda nodes,edges,**k:captured.append((nodes,edges))
            n['render_local_lineage'](source,question)
            n['render_graph']=original
            self.assertEqual(captured[0],expected[:2])
            self.assertTrue(expected[1])
            explanation=n['chatbot'](question.replace('Afficher','Explique').replace('Affiche','Explique'),source)
            for node in expected[0].values():
                if any(node['id'] in (e['from'],e['to']) for e in expected[1]):
                    self.assertIn(node['label'],explanation)
            print(source,':',len(expected[0]),'nodes,',len(expected[1]),'relations')
        for question in (
            'Explique le lineage de la table comptes','Quel est le lineage de comptes ?',
            "D'où vient la table comptes ?",'Quel processus produit comptes ?',
            'Quel processus produit la table comptes ?',
            'Quelles sont les entrées du processus qui produit comptes ?',
            'Quelles sont les colonnes de la table comptes ?',
            'Explique le Data Lineage du projet SQLite'):
            answer=n['chatbot'](question)
            self.assertNotIn('Les informations demandées ne sont pas disponibles',answer)
            self.assertNotRegex(answer,r'st\.iframe|\bsvg\b|429|rate_limit_exceeded')
            print(question,'=>',answer)

    def test_ambiguity(self):
        self.assertEqual(self.n['lineage_route']('Explique le lineage de transactions'),('text',None,True))
        self.assertEqual(self.n['lineage_route']('Explique le lineage de transactions SQLite','postgresql'),('text','sqlite',False))
        self.assertEqual(self.n['lineage_route']('Explique le lineage de transactions_sep.xlsx'),('text','sqlite',False))

    def test_mistral_error_fallback(self):
        n=load_functions()
        def unavailable(**kwargs):raise RuntimeError('HTTP 429 rate_limit_exceeded')
        n['Mistral']=unavailable
        n['context']=lambda *a:['Fait Atlas']
        n['atlas_text_fallback']=lambda *a:'Fait Atlas local'
        self.assertEqual(n['chatbot']('Décris les métadonnées','postgresql'),'Fait Atlas local')

    def test_graph_browser_interactions(self):
        from playwright.sync_api import sync_playwright
        n=self.n
        nodes,edges,_=n['local_lineage_data']('postgresql','lineage de comptes')
        documents=[]
        n['components']=SimpleNamespace(html=lambda doc,**k:documents.append(doc))
        n['render_graph'](nodes,edges,height=560)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1400,'height':800})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.set_content(documents[0])
            page.wait_for_timeout(200)
            before=page.locator('#w').evaluate('(el)=>el.style.transform')
            page.get_by_role('button',name='Zoom +',exact=True).click()
            self.assertNotEqual(before,page.locator('#w').evaluate('(el)=>el.style.transform'))
            for name in ('Zoom -','Ajuster','Centrer'):
                page.get_by_role('button',name=name,exact=True).click()
            page.locator('.node').first.click()
            self.assertIn('qualified name',page.locator('#d').inner_text().lower())
            self.assertEqual(page.locator('.node').count(),len(nodes))
            self.assertEqual(errors,[])
            browser.close()


if __name__=='__main__':unittest.main()

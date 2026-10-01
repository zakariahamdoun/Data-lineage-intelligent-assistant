# Routage des questions

## Constat avant correction

Trois points prenaient des décisions : `chatbot`, `catalogue_intent` et la branche
Streamlit « Assistant IA ». L'interface consultait `catalogue_intent` avant le chatbot.
Dans ce routeur, la règle suivante précédait l'inventaire des tables :

```python
if mentions_database and database_source:
    return 'database', database_source
```

Ainsi, « Quelles sont les tables disponibles dans la base PostgreSQL ? » retournait
le nom de la base. Une correction limitée à `chatbot` n'aurait pas corrigé l'interface.
Les noms de processus pouvaient aussi intercepter des questions sur leurs entrées,
sorties ou transformations.

## Priorités et exécution

`intent_routing.py` contient un classificateur pur, sans réseau ni modèle. La constante
`INTENT_PRIORITY` définit l'ordre : impact, lineage, entrées/sorties, détails processus,
liste processus, transformation, recherche colonne, liste colonnes, détails table,
liste tables, base, repli.

`app.detect_intent` expose ce classificateur. `app.chatbot` associe chaque intention à
un gestionnaire. `catalogue_intent` utilise la même décision et conserve les identifiants
historiques nécessaires à l'interface. Les visualisations restent gérées par `lineage_route`.

Les réponses spécialisées existantes sont réutilisées. `specialized_fallback_answer`
conserve les sous-cas historiques (clés étrangères, fichiers, règles métier, etc.) et
le RAG. Il ne redispatche pas une intention déjà reconnue, pour éviter les boucles.
La détection d'une intention ne dépend jamais de la présence du seul mot PostgreSQL.

## Inventaire PostgreSQL

Le gestionnaire résout d'abord la base par son nom/qualifiedName dans Atlas, puis par
le système demandé et le contexte. Un nom explicite prime sur le contexte. Une base
inconnue ou plusieurs bases possibles produisent un message explicite.

Les recherches Atlas sont paginées. Les tables sont filtrées par relation `database`,
ou, en l'absence de cette relation, par la relation inverse `tables` ou l'attribut
`databaseName`. Les relations et entités supprimées sont exclues. Les noms sont
dédoublonnés et triés ; aucune liste métier codée en dur n'est utilisée.
Le lecteur Atlas SQLite existant est conservé pour les demandes SQLite sans nom de
base explicite.

## Vérification

```powershell
python -X utf8 -m unittest test_intent_routing -v
python -X utf8 -m unittest discover -v
```

Les tests de classification, de dispatch et d'inventaire simulé fonctionnent sans
Atlas. `AtlasResponseContractTests` vérifie les huit réponses demandées et la branche
Streamlit en lecture seule sur Atlas local. La suite historique contient également
des tests d'intégration nécessitant Atlas et un navigateur pour certains graphiques.
L'option UTF-8 évite les erreurs d'affichage des flèches dans la console Windows.

### Résultat de validation — 14 septembre 2026

- Nouveaux tests : 8 réussis, couvrant les onze intentions, les huit réponses,
  l'interface, le filtrage des bases, les suppressions et la pagination.
- Vérification ciblée avec la recherche de colonnes historique : 11 tests réussis.
- Suite complète finale : 115 tests exécutés, 30 échecs, aucune erreur d'exécution.
- Avant modification : 107 tests, 29 échecs et 13 erreurs, notamment d'encodage.
  Les anciens tests de lineage et dépendances ont aussi été réexécutés en UTF-8
  contre le code antérieur reconstitué, sans remplacer le fichier de l'application.
  Tous les échecs finaux figurent dans ces références : aucune nouvelle régression
  détectée. La suite historique n'est donc pas entièrement verte.

Les sorties sont conservées dans `intent-test-results.txt`, `routing-validation.txt`,
`final-regression-tests.txt`, `baseline-tests.txt` et `baseline-utf8-comparison.txt`.

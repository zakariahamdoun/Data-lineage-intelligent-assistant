# Diagnostic de l’index Assistant IA — 21 septembre 2026

## Échec reproduit

`docs_atlas()` échoue dès la recherche `PostgreSQLDatabase` :
`GET http://localhost:21000/api/atlas/v2/search/basic?typeName=PostgreSQLDatabase&limit=1000&offset=0`
retourne HTTP 500. Une seconde requête avec `limit=100` échoue également.
Identifiants des erreurs retournés : `86820a036e74b67e`, `bf19ddd138ffba28`.
Les paramètres Atlas utilisés correspondent à ceux de l’application.

Les journaux du conteneur `atlas-v2`, consultés sans modification, montrent des
`java.net.ConnectException: Connection refused` vers ZooKeeper `localhost:2181`
et des échecs HBase sur `/hbase/meta-region-server` (`CONNECTIONLOSS`).
Cette panne de dépendance côté Atlas est cohérente avec les HTTP 500 ; les
identifiants HTTP n’ont pas été retrouvés dans la sortie standard du conteneur.
La cause directement reproduite du non-indexage est l’échec de récupération Atlas,
avant tout appel aux embeddings ou à FAISS.

## Vérifications

- NumPy 2.5.2, FAISS 1.15.0 et SentenceTransformer 6.0.1 s’importent correctement.
- Le modèle `sentence-transformers/all-MiniLM-L6-v2` se charge depuis le cache local,
  sans téléchargement. Un texte de diagnostic produit un embedding `(1, 384)`
  et un index FAISS contenant un vecteur.
- Aucun fichier FAISS n’est lu ou écrit par l’application : l’index est un
  `IndexFlatIP` conservé en mémoire par `st.cache_resource`.
- Au redémarrage du processus, l’index est reconstruit au premier affichage de la
  sidebar après connexion, à condition que la récupération Atlas réussisse.
- `refresh_metadata()` vide le cache de l’index puis les caches des métadonnées,
  et rappelle `atlas_index()` : Atlas → embeddings → FAISS. L’échec Atlas interrompt
  cette chaîne dès la première étape.
- Aucun indicateur `session_state` ne pilote la disponibilité de l’index.
  Le message de la sidebar provient d’une exception attrapée lors de sa construction.
- Aucun état de cache incorrect n’est nécessaire pour reproduire la panne :
  l’appel direct à `docs_atlas()` sans ses décorateurs de cache échoue aussi.
  Le code peut par ailleurs conserver une liste vide en cache si Atlas retourne
  zéro document, mais ce n’est pas l’erreur observée ici (HTTP 500).

## Changements limités dans app.py

Logs temporaires : chemin en mémoire, nombre de documents, forme des embeddings,
taille FAISS, disponibilité et étape ayant échoué. Aucun contenu métier ni secret
n’est imprimé. Les erreurs continuent à être propagées.

Le message de sidebar utilise maintenant un emplacement effaçable : une
actualisation réussie retire immédiatement l’ancien avertissement, même si celui-ci
a été affiché plus tôt pendant la même exécution Streamlit.

## Limite

La panne Atlas n’est pas réparée : la consigne interdit de modifier Apache Atlas.
La restauration de l’accès ZooKeeper/HBase doit être traitée côté service avant
de valider la reconstruction avec les vraies métadonnées et le chatbot complet.
Ni Data Lineage, ni Mistral, ni la configuration Atlas n’ont été modifiés.

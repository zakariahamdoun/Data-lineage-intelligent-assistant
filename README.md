# Intelligent Lineage Assistant


**Intelligent Lineage Assistant** est une plateforme de **Data Lineage** développée en **Python avec Streamlit**, et intégrée à **Apache Atlas** pour la gestion, l’exploration et la traçabilité des métadonnées.

Elle permet de **suivre le parcours des données de leur source jusqu’à leur destination**, en retraçant les transformations, dépendances et processus qu’elles traversent.

La plateforme centralise les métadonnées techniques et métier, permet de visualiser le **Data Lineage**, d’identifier les relations entre tables, colonnes et processus, et d’analyser l’impact potentiel d’une modification sur les objets dépendants.

Elle intègre également un **assistant conversationnel intelligent** permettant d’interroger les métadonnées et le parcours des données en langage naturel grâce à une architecture **RAG** combinant **FAISS, embeddings et Mistral**.

## Contexte et objectifs

Les objets de données d’une banque — tables PostgreSQL, données de transactions SQLite, fichiers et processus de transformation — doivent être compréhensibles et traçables. Le projet fournit une interface métier pour consulter leur structure, leur sens, leurs classifications, leur provenance et les impacts possibles d’un changement.

Ses objectifs sont de :

— Automatiser l’alimentation d’Apache Atlas : envoyer automatiquement les
métadonnées vers Apache Atlas à l’aide de ses API afin d’éviter la création manuelle
de chaque table, colonne et relation.
— Représenter les liens et les dépendances : mettre en évidence les relations
entre les différents objets de données et les processus qui les transforment.

— Réaliser une analyse d’impact : identifier les conséquences possibles d’une
modification. Par exemple, lorsqu’une colonne est supprimée, la solution doit permettre
de retrouver les traitements, les tables et les autres éléments susceptibles
d’être affectés.

— Interroger le Data Lineage en langage naturel : permettre à l’utilisateur de
poser des questions de manière simple, sans avoir à écrire de code ou à maîtriser
les aspects techniques d’Apache Atlas.

— Produire des réponses contextualisées : permettre au LLM de générer des
réponses à partir des métadonnées réelles récupérées dans Apache Atlas, afin de
limiter les réponses non fondées et de fournir des informations adaptées au contexte
du projet.

## Fonctionnalités principales

- Catalogue des métadonnées : vues Tables et Colonnes, classifications Atlas, descriptions, clés, identifiants techniques et règles métier.
- Data Lineage : exploration des sources, transformations, processus et destinations.
- Analyse d’impact : identification des objets et processus potentiellement concernés en aval.
- Assistant conversationnel : RAG avec embeddings, FAISS et Mistral lorsque la clé est configurée ; un repli fondé sur Atlas reste disponible sans clé Mistral.
- Gestion des accès : demandes d’accès, validation/refus par un administrateur, comptes actifs/désactivés et mots de passe hachés localement.

## Architecture générale

```text
Navigateur
    │
    ▼
Streamlit (app.py)
    ├── Catalogue / Lineage / Impact
    ├── Authentification locale SQLite
    └── Assistant RAG (FAISS + embeddings + Mistral optionnel)
             │
             ▼
       Apache Atlas ─── PostgreSQL / SQLite / fichiers / processus
```

L’application consulte Apache Atlas par son API REST. PostgreSQL et la source `Transactions / SQLite` sont représentés dans Atlas ; l’application n’ouvre pas directement la base PostgreSQL lors de son exécution normale.

## Technologies

- Python et Streamlit pour l’interface.
- Apache Atlas pour le catalogue, les classifications et le Data Lineage.
- PostgreSQL et SQLite comme sources de données documentées.
- FAISS, `sentence-transformers` et embeddings pour la recherche sémantique/RAG.
- Mistral pour la reformulation conversationnelle optionnelle.
- Docker et Nginx pour le proxy local de l’interface Atlas embarquée.

## Structure du projet

```text
.
├── app.py                         # Point d’entrée Streamlit
├── auth_store.py                  # Comptes, accès et hachage des mots de passe
├── admin_ui.py                    # Composants d’administration
├── catalogue_ui.py                # Présentation du catalogue des métadonnées
├── lineage_ui.py / lineage_*.py   # Présentation et logique de lineage
├── impact_ui.py / impact_*.py     # Présentation et logique d’impact
├── chat_context.py                # Contexte de conversation et cache
├── assets/                        # Logo et visuels utilisés par l’interface
├── nginx/                         # Configuration du proxy Atlas
├── docker-compose.yml             # Proxy Atlas sécurisé en local
├── .streamlit/                    # Secrets locaux Streamlit (non versionnés)
├── test_*.py                      # Tests automatisés
├── *DESIGN.md                     # Documents de conception
├── Latex rapport data_lineage/    # Sources du rapport LaTeX
├── Code_source_data_lineage/      # Archives et éléments de revue locaux
├── .env.example                   # Modèle de configuration sans secret
└── requirements.txt               # Dépendances runtime
```

Les notebooks historiques d’alimentation Atlas restent locaux et sont ignorés : ils contiennent des paramètres propres à l’environnement. Les sources à publier doivent être assainies avant d’être ajoutées explicitement.

## Prérequis

- Python 3.10 ou supérieur ;
- Apache Atlas disponible, par défaut sur `http://localhost:21000` ;
- Docker Desktop uniquement si le proxy Atlas embarqué est souhaité ;
- une clé Mistral seulement si la reformulation par Mistral est activée.

## Installation

Sous PowerShell, à la racine du projet :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuration

Copiez le modèle sans le publier :

```powershell
Copy-Item .env.example .env
```

L’application lit ses paramètres depuis les variables d’environnement ou `st.secrets`. Pour Streamlit en local, créez plutôt `.streamlit/secrets.toml` à partir de ces noms, sans jamais versionner ce fichier :

```toml
ATLAS_URL = "http://localhost:21000"
ATLAS_USERNAME = ""
ATLAS_PASSWORD = ""
MISTRAL_API_KEY = ""
```

Variables reconnues :

| Variable | Rôle |
| --- | --- |
| `ATLAS_URL` | URL de l’API Apache Atlas ; valeur par défaut : `http://localhost:21000`. |
| `ATLAS_USERNAME` | Identifiant Atlas. |
| `ATLAS_PASSWORD` | Mot de passe Atlas. |
| `ATLAS_IFRAME_URL` | URL du proxy Atlas ; valeur par défaut : `http://localhost:8081`. |
| `MISTRAL_API_KEY` | Clé Mistral optionnelle. |
| `ATLAS_AUTHORIZATION` | En-tête Basic privé, utilisé uniquement par le proxy Docker. |

Le fichier `.env` est un fichier local ignoré. Sans chargeur `.env` dans le code, exportez ses valeurs dans votre shell ou utilisez `.streamlit/secrets.toml` pour Streamlit. Ne placez jamais de valeur réelle dans `.env.example`.

## Apache Atlas et proxy Docker

Apache Atlas doit être accessible sur `http://localhost:21000`, sauf si `ATLAS_URL` est défini autrement. Pour démarrer le proxy local de l’iframe Atlas après avoir défini `ATLAS_AUTHORIZATION` dans votre environnement ou `.env` :

```powershell
docker compose up -d
```

Le proxy est lié à `127.0.0.1:8081` et ne publie aucune autorisation dans le dépôt.

## Lancement

Depuis l’environnement virtuel activé :

```powershell
python -m streamlit run app.py
```

## Tests

Les tests sont basés sur `unittest` :

```powershell
python -m unittest discover -p "test_*.py"
```

## Sécurité et publication

- Ne versionnez jamais `.env`, `.streamlit/secrets.toml`, `app_users.db`, les notebooks locaux ni les exports de données.
- Utilisez uniquement des secrets injectés par l’environnement ou par Streamlit Secrets.
- Faites pivoter toute clé qui aurait été présente dans un fichier local ou dans l’historique d’un dépôt déjà publié.
- Vérifiez le contenu de l’index avant chaque publication : `git status` puis `git diff --cached`.

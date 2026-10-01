# Accès à l’application

## Fichiers et modifications exactes

- `app.py` : seul le bloc d’authentification et le chemin de la base des comptes sont modifiés. Le formulaire d’inscription, les boutons associés et le mot de passe administrateur créé automatiquement sont supprimés. Le diff exact figure dans `LOGIN_ACCESS.diff`.
- `auth_store.py` : code complet de stockage, migration, authentification et gestion locale des comptes. PBKDF2-SHA256, sel aléatoire de 16 octets, 600 000 itérations et comparaison avec `hmac.compare_digest`. Aucun mot de passe en clair n’est enregistré.
- `manage_users.py` : outil réservé à une exécution locale sur le serveur, sans interface publique et sans nouveau système de rôles. Les mots de passe sont saisis de façon masquée, jamais dans les arguments de commande.
- `test_auth_access.py` : tests du stockage et du formulaire Streamlit sur des bases temporaires.
- `LOGIN_ACCESS.md` et `LOGIN_ACCESS.diff` : documentation et détail exact du code ajouté/supprimé dans la page.

Les pages Assistant IA, Analyse d’impact, Visualisation du Data Lineage et Catalogue des métadonnées sont conservées. Aucun formulaire d’inscription ne subsiste, même si une ancienne session contient `auth_mode="signup"`.

La page Administration gère les accès : tableau `username`, `role`, `statut`, `created_at`, sélection d’un utilisateur, statut actuel, activation/désactivation et suppression. Les rôles sont affichés en français : `admin` → Administrateur, `user` → Utilisateur. Le formulaire de création ne demande aucun rôle : tous les comptes créés depuis cette page sont des utilisateurs, et l’identifiant principal `admin` est réservé. Le compte principal et celui de l’administrateur connecté sont protégés contre la désactivation et la suppression. Aucun bouton ne permet de modifier les rôles. À chaque initialisation, `admin` conserve son rôle et tous les autres comptes sont harmonisés sur `user` ; le rôle d’une session ouverte est actualisé. `test_admin_access.py` vérifie ces comportements. Le diff `LOGIN_ACCESS.diff` décrit uniquement la modification initiale de la connexion, avant cette évolution de la page Administration.

## Migration des comptes existants

Au prochain démarrage de l’application, ou à la première commande de gestion :

1. `is_active` est ajouté à la table `users` si nécessaire.
2. Les comptes historiques sont désactivés, car ils pouvaient provenir de l’inscription libre. Le compte principal `admin`, s’il existe déjà avec le rôle `admin`, reste actif.
3. L’administrateur réactive individuellement les personnes autorisées avec `enable`.
4. Les anciens hashes restent vérifiables à 200 000 itérations. Après une connexion réussie d’un compte actif, ils sont renouvelés à 600 000 itérations.

La migration est répétable : les démarrages suivants ne désactivent pas les comptes déjà approuvés. Aucun utilisateur existant n’est supprimé. La base réelle n’a pas été modifiée pendant les tests de cette intervention.

Le statut actif et l’obligation de changement sont contrôlés à la connexion et à chaque réexécution de la page. Une désactivation ou une réinitialisation bloque une session déjà ouverte à sa prochaine interaction ; aucune notification immédiate n’est envoyée à un navigateur inactif.

## Gestion manuelle par l’administrateur

Depuis la page Administration, le bouton « + Ajouter un utilisateur » en haut à droite ouvre un formulaire : identifiant, mot de passe temporaire, confirmation et statut Actif/Désactivé. Après validation, le compte est créé avec un hash sécurisé, le message « Utilisateur créé avec succès. » apparaît et le tableau est actualisé. Les identifiants existants, les mots de passe différents ou de moins de 12 caractères sont refusés. Cette fonctionnalité est réservée à l’administrateur et ne rétablit pas l’inscription libre. Chaque nouveau compte reçoit `must_change_password=True` : la première connexion est limitée au changement du mot de passe.

Exécuter ces commandes depuis le dossier du projet, dans un terminal local accessible uniquement à l’administrateur du serveur. Le fichier utilisé est `app_users.db`, à côté de `app.py`, quelle que soit la position du terminal.

```powershell
# Ajouter une personne autorisée (active immédiatement)
python manage_users.py add alice

# Examiner les identifiants et leur activation, sans afficher les hashes
python manage_users.py list

# Autoriser un ancien compte
python manage_users.py enable alice

# Désactiver un compte
python manage_users.py disable alice

# Changer un mot de passe
python manage_users.py password alice
```

Pour `add` et `password`, saisir deux fois un mot de passe d’au moins 12 caractères ; rien ne s’affiche pendant la saisie. Un identifiant existant n’est pas écrasé par `add`. Changer le mot de passe ne réactive pas un compte désactivé : utiliser `enable` séparément.

Le seul nom créé avec le rôle administrateur par cet outil est `admin`. Les autres sont créés avec le rôle `user`. Aucun nouveau rôle n’est ajouté.

Pour une installation neuve, créer explicitement l’administrateur :

```powershell
python manage_users.py add admin
```

Pour l’installation existante, changer le mot de passe administrateur historique :

```powershell
python manage_users.py password admin
```

L’ancien mot de passe fixe n’est plus généré automatiquement. Un hash déjà présent conserve son mot de passe jusqu’à ce que l’administrateur le change.

## Tester

Tests automatiques isolés, sans toucher aux comptes réels :

```powershell
python -m unittest test_auth_access test_admin_access -v
```

Test manuel :

```powershell
python manage_users.py add utilisateur_test
python -m streamlit run app.py
```

1. Vérifier la photo, le logo, les deux colonnes, les couleurs, le titre « Connexion sécurisée », le sous-titre et le message de contact. Aucun bouton de création de compte ne doit apparaître.
2. Saisir un identifiant inconnu ou un mauvais mot de passe : « Identifiant ou mot de passe incorrect. »
3. Se connecter avec `utilisateur_test` et son mot de passe : accès à l’application.
4. Se déconnecter, exécuter `python manage_users.py disable utilisateur_test`, puis essayer son mot de passe correct : « Votre accès est désactivé. Contactez l'administrateur. »
5. Réactiver avec `python manage_users.py enable utilisateur_test` et vérifier la connexion.
6. Vérifier la connexion de `admin` et l’accès à la page Administration existante.
7. Dans Administration, sélectionner `utilisateur_test`, cliquer sur « Désactiver l'accès », puis « Activer l'accès » et vérifier les changements de statut. Sélectionner `admin` : les boutons d’action doivent être désactivés. La suppression d’un compte de test doit le retirer du tableau.

Pour tester sur une autre base, ajouter `--db chemin_vers_test.db` avant l’action dans `manage_users.py` ; l’application continue d’utiliser sa propre base.


## Mot de passe temporaire obligatoire

La migration ajoute `must_change_password`, sans forcer les comptes déjà existants à changer leur mot de passe. Chaque création ou réinitialisation, depuis Administration ou le terminal, définit ensuite ce champ à `True`.

Après vérification de l’identifiant, du mot de passe et du statut actif, l’utilisateur est limité à la page « Changer votre mot de passe ». Il doit saisir son mot de passe actuel, un nouveau mot de passe d’au moins 12 caractères et sa confirmation. Le nouveau mot de passe doit être différent. Le changement vérifie à nouveau le statut actif et le mot de passe actuel, remplace le hash et le sel, puis définit `must_change_password=False`. La session normale n’est ouverte qu’après cette réussite.

Dans Administration, sélectionner un utilisateur et ouvrir « Réinitialiser le mot de passe ». Saisir et confirmer un nouveau mot de passe temporaire dans les champs masqués, puis cliquer sur « Réinitialiser le mot de passe ». L’ancien mot de passe devient invalide. Le statut actif/désactivé ne change pas. L’administrateur ne peut consulter ni récupérer le mot de passe actuel.

Pour tester : créer un utilisateur actif, se connecter avec son mot de passe temporaire et vérifier que seule la page de changement apparaît. Tester un mot de passe actuel erroné, une confirmation différente et un nouveau mot de passe identique à l’ancien. Après un changement valide, vérifier l’accès à l’application et le refus de l’ancien mot de passe. Réinitialiser ensuite le compte depuis Administration et vérifier qu’une nouvelle modification est imposée, y compris pour une session déjà ouverte à sa prochaine interaction.

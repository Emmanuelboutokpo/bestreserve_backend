# Rapport de contenu du dépôt BestRev

**Date du relevé :** 6 novembre 2026  
**Périmètre :** fichiers du dépôt visibles dans l'espace de travail, hors `.git`, caches et environnements virtuels. Ce document décrit l'organisation et le rôle apparent des fichiers ; il ne reproduit pas le code source.

## 1. Synthèse

Ce dépôt contient le backend Python de BestRev, une API asynchrone bâtie avec FastAPI, SQLModel et SQLAlchemy. Il couvre l'authentification, les comptes, le catalogue d'établissements et de lieux, les réservations, les paiements, les avis, les notifications, les médias et les outils d'administration.

L'architecture sépare principalement les routes HTTP (`app/api`), les traitements métier (`app/services`), les modèles persistés (`app/models`) et les contrats de requête/réponse (`app/schemas`). PostgreSQL est configuré via une URL de base de données, Redis sert notamment aux jetons et données temporaires, Cloudinary au stockage d'images, et des intégrations externes gèrent les courriels, OAuth et les paiements.

La documentation couvre une conception plus ambitieuse que le schéma effectivement présent. Le document MCD expose 32 tables, tandis que les modèles SQLModel et la migration initiale présentent 19 tables. Le dépôt ne contient qu'un fichier de test fonctionnel, consacré au téléversement de photos.

## 2. Vue d'ensemble des dossiers

```text
.
├── alembic/                 Migrations et configuration Alembic
├── app/
│   ├── api/                 Routes publiques et d'administration
│   ├── cores/               Connexions base de données et Redis
│   ├── dependencies/        Authentification et autorisations FastAPI
│   ├── emails/              Envoi d'e-mails et modèles de messages
│   ├── helpers/             Intégrations utilitaires, dont Cloudinary
│   ├── models/              Modèles SQLModel et enums métier
│   ├── schemas/              Contrats Pydantic des API
│   └── services/             Logique applicative et métier
└── tests/                    Tests automatisés présents dans le dépôt
```

## 3. Fichiers à la racine

| Fichier | Contenu / rôle |
|---|---|
| `README.md` | Instructions succinctes pour l'authentification Google et Facebook : obtention d'un jeton fournisseur côté frontend puis échange contre les jetons BestRev. |
| `BestRev_API_V1_endpoints.md` | Document de conception API/MCD : conventions, tables prévues, relations, enums, sécurité, scalabilité et catalogue d'endpoints. |
| `bestrev-regles-metier-reservation.md` | Règles métier de réservation : acteurs, création, prix, statuts, paiements, commissions, capacités, notifications, routes proposées et critères d'acceptation. |
| `requirements.txt` | Dépendances Python épinglées, notamment FastAPI, SQLModel/SQLAlchemy, Alembic, asyncpg, Redis, Cloudinary, PyJWT, Resend, Web Push et clients HTTP. |
| `pytest.ini` | Configuration minimale de pytest (deux lignes). |
| `.env.example` | Présent, mais vide (0 octet) : aucun exemple de variables d'environnement n'est fourni. |

## 4. Migrations (`alembic/`)

| Fichier | Contenu / rôle |
|---|---|
| `alembic.ini` | Configuration Alembic, emplacement du script et paramètres de migration. |
| `alembic/README` | Fichier d'aide Alembic généré par défaut. |
| `alembic/env.py` | Environnement Alembic : charge la configuration et le metadata SQLModel pour les migrations en ligne/hors ligne. |
| `alembic/script.py.mako` | Gabarit de génération des scripts de migration. |
| `alembic/versions/5e6a383c3567_initial_migration.py` | Création initiale des tables du domaine et de leurs relations/index. |
| `alembic/versions/90733424c276_add_is_deleted_to_users.py` | Ajout du marqueur de suppression logique aux utilisateurs. |
| `alembic/versions/ba84526ffc24_fix_reservation_paid_at_timezone.py` | Ajustement du type/fuseau horaire de la date de paiement d'une réservation. |
| `alembic/versions/d87e9b70d579_fix_reviews_approved_at_timezone.py` | Ajustement du type/fuseau horaire de la date d'approbation des avis. |

La migration initiale crée les entités correspondant aux modèles actuels, notamment utilisateurs/profils, établissements/catalogue, réservations, transactions, photos, documents de validation, avis, favoris, notifications, paramètres et journaux d'activité.

## 5. Application (`app/`)

### Démarrage, configuration et infrastructure

| Fichier | Contenu / rôle |
|---|---|
| `app/__init__.py` | Initialisation du paquet applicatif. |
| `app/main.py` | Construit l'application FastAPI, configure CORS et le cycle de vie, initialise la base et monte les routeurs. Contient aussi le middleware du mode maintenance. |
| `app/config.py` | Paramètres Pydantic chargés depuis l'environnement : base, JWT, OAuth, fournisseurs de paiement, Cloudinary, Redis, notifications push, pagination, taxes et commissions. |
| `app/utils.py` | Hachage/vérification de mots de passe, création/décodage de jetons et utilitaire de clé de cache. |
| `app/error.py` | Fichier vide dans l'état relevé. |
| `app/cores/__init__.py` | Initialisation du paquet `cores`. |
| `app/cores/db.py` | Engine/session asynchrones et dépendance de session ; `init_db` appelle `SQLModel.metadata.create_all`. |
| `app/cores/redis.py` | Client Redis et stockage de blacklist JWT, OTP, délais de renvoi et jetons de réinitialisation. |
| `app/dependencies/__init__.py` | Initialisation du paquet de dépendances. |
| `app/dependencies/dependencies.py` | Vérification des jetons d'accès/rafraîchissement, chargement de l'utilisateur courant et garde-fous client/administrateur. |
| `app/helpers/__init__.py` | Initialisation du paquet `helpers`. |
| `app/helpers/cloudinary.py` | Configuration Cloudinary et fonctions asynchrones d'envoi/suppression d'images et d'extraction d'identifiants publics. |
| `app/emails/__init__.py` | Initialisation du paquet `emails`. |
| `app/emails/email.py` | Envoi d'e-mails et contenus/templates pour OTP, confirmation de compte, réinitialisation de mot de passe, réservation, paiement et remboursement. |

### Routes HTTP (`app/api/`)

Les routeurs de cette section exposent les fonctionnalités utilisateur et catalogue. Les fichiers `app/api/admin/` regroupent les opérations administratives.

| Fichier | Contenu / rôle |
|---|---|
| `app/api/__init__.py` | Paquet API, sans contenu métier. |
| `app/api/user.py` | Inscription, vérification OTP, renvoi OTP, connexion, renouvellement de jeton, récupération/réinitialisation de mot de passe et déconnexion. |
| `app/api/oauth.py` | Connexion via Google et Facebook. |
| `app/api/account.py` | Compte courant : lecture/modification, suppression, mot de passe, avatar et notifications personnelles. |
| `app/api/locations.py` | Consultation, recherche de proximité et liste des pays/lieux. |
| `app/api/categories.py` | Consultation du catalogue de catégories. |
| `app/api/subcategories.py` | Consultation des sous-catégories. |
| `app/api/amenities.py` | Consultation des équipements et gestion des équipements d'établissements ; contient aussi certains routeurs administratifs. |
| `app/api/establishments.py` | Recherche/liste, popularité, proximité, détail, avis et établissements similaires. |
| `app/api/favorites.py` | Liste, ajout, suppression et vidage des favoris de l'utilisateur. |
| `app/api/payment_conditions.py` | Lecture des conditions de paiement publiques associées à un établissement. |
| `app/api/reservations.py` | Vérification de disponibilité, devis, liste/détail, création et annulation de réservations client. |
| `app/api/payments.py` | Création/confirmation de paiement et réception du webhook Kkiapay. |
| `app/api/reviews.py` | Création, modification et suppression des avis d'un utilisateur. |
| `app/api/settings.py` | Routes d'administration des paramètres, état de services et mode maintenance. |

#### Administration (`app/api/admin/`)

| Fichier | Contenu / rôle |
|---|---|
| `app/api/admin/__init__.py` | Exporte les routeurs d'administration des catégories, sous-catégories et statistiques. |
| `app/api/admin/admin_accounts.py` | Actions d'administration sur le compte utilisateur : profil, suppression, mot de passe, avatar et identité admin. |
| `app/api/admin/admin_users.py` | Liste/détail/statistiques utilisateurs, création, édition, désactivation, rôles/statuts et consultation des réservations, favoris et activités. |
| `app/api/admin/admin_notifications.py` | Consultation, création, lecture et suppression des notifications administratives. |
| `app/api/admin/locations.py` | Création, modification et suppression des lieux. |
| `app/api/admin/categories.py` | Création/modification/suppression des catégories et opérations liées aux sous-catégories. |
| `app/api/admin/subcategories.py` | Modification et suppression des sous-catégories. |
| `app/api/admin/amenities.py` | Gestion administrative du catalogue d'équipements et association aux établissements. |
| `app/api/admin/establishments.py` | Liste/détail et création, modification, suppression, statut et disponibilité des établissements. |
| `app/api/admin/establishment_media.py` | Ajout/suppression de photos d'établissement et choix de la couverture. |
| `app/api/admin/payment_conditions.py` | Gestion des conditions de paiement et association aux établissements. |
| `app/api/admin/reservations.py` | Liste/statistiques/détail, changement de statut et remboursement des réservations. |
| `app/api/admin/payments.py` | Liste, statistiques et détail des paiements. |
| `app/api/admin/reviews.py` | Modération, approbation et suppression d'avis. |
| `app/api/admin/stats.py` | Routes de statistiques de synthèse, utilisateurs, établissements, réservations, revenus, destinations, activités et graphiques. |

### Modèles persistés (`app/models/`)

Les modèles utilisent SQLModel et représentent 19 tables dans l'état du dépôt.

| Fichier | Entité / rôle |
|---|---|
| `app/models/__init__.py` | Agrège les modèles pour l'enregistrement dans le metadata. |
| `app/models/base.py` | Mixins de timestamps et identifiants UUID communs. |
| `app/models/enums.py` | Valeurs typées pour rôles/états utilisateurs, lieux, établissements, disponibilité, validation, réservation, paiements, notifications et conditions de paiement. |
| `app/models/user.py` | Utilisateurs, authentification/fournisseur, statut et version de jeton. |
| `app/models/profile.py` | Informations de profil associées à l'utilisateur. |
| `app/models/location.py` | Référentiel hiérarchique des lieux. |
| `app/models/category.py` | Catégories du catalogue. |
| `app/models/sub_category.py` | Sous-catégories du catalogue. |
| `app/models/amenity.py` | Catalogue des équipements. |
| `app/models/establishment.py` | Données et paramètres métier des établissements réservables. |
| `app/models/establishment_amenity.py` | Table de liaison établissement-équipement. |
| `app/models/payment_condition.py` | Conditions de paiement disponibles. |
| `app/models/establishment_payment_condition.py` | Table de liaison établissement-condition de paiement. |
| `app/models/photo.py` | Médias photos liés aux établissements, dont l'indicateur de couverture. |
| `app/models/validation_document.py` | Documents de validation/conformité associés aux entités concernées. |
| `app/models/favorite.py` | Favoris utilisateur. |
| `app/models/reservation.py` | Réservation, prix, statut, dates et suivi de paiement. |
| `app/models/transaction.py` | Transactions de paiement/remboursement. |
| `app/models/review.py` | Avis et état de modération. |
| `app/models/notification.py` | Notifications adressées aux utilisateurs. |
| `app/models/activity_log.py` | Traces des actions et événements métier. |
| `app/models/platform_setting.py` | Paramètres de plateforme, dont valeurs typées/JSON. |

### Contrats API (`app/schemas/`)

| Fichier | Contenu / rôle |
|---|---|
| `app/schemas/__init__.py` | Exports des schémas. |
| `app/schemas/commons/common.py` | Réponses génériques, pagination, paramètres de pagination et utilitaire de slug. |
| `app/schemas/auth.py` | Contrats d'inscription, connexion, OAuth, OTP, jetons, récupération de compte et réponse d'authentification. |
| `app/schemas/account.py` | Mise à jour du profil, mot de passe, suppression de compte, consentements et notifications. |
| `app/schemas/admin_user.py` | Entrées/sorties d'administration utilisateur, favoris, réservations, activités et statistiques. |
| `app/schemas/location.py` | Création/modification, import, arbre, liste et résultats de recherche géographique. |
| `app/schemas/category.py` | Création, modification, sortie publique et pagination des catégories. |
| `app/schemas/subcategory.py` | Contrats des sous-catégories. |
| `app/schemas/amenity.py` | Contrats des équipements et associations établissement-équipement. |
| `app/schemas/catalog.py` | Schémas publics de catalogue, équipements et avis. |
| `app/schemas/establishment.py` | Création/modification, listes/détails publics et administratifs, disponibilités et avis. |
| `app/schemas/photo.py` | Représentation publique d'une photo. |
| `app/schemas/favorite.py` | Favori public et page de favoris. |
| `app/schemas/payment_condition.py` | Création/mise à jour, sortie et association des conditions de paiement. |
| `app/schemas/reservation.py` | Réservation, annulation, statuts admin, remboursement, disponibilité, devis, pages et statistiques. |
| `app/schemas/payments.py` | Requêtes/réponses checkout, confirmation, remboursement et vues administratives. |
| `app/schemas/reviews.py` | Création/mise à jour et sorties publiques/admin des avis. |
| `app/schemas/notifications.py` | Abonnements push et contrats de notifications administratives. |
| `app/schemas/settings.py` | Mise à jour des paramètres, demande de maintenance et sorties d'état système. |

### Services métier (`app/services/`)

| Fichier | Contenu / rôle |
|---|---|
| `app/services/__init__.py` | Paquet de services. |
| `app/services/user.py` | Opérations de service utilisateur. |
| `app/services/account.py` | Profil, compte, mot de passe, avatar, consentements et opérations liées au compte. |
| `app/services/oauth.py` | Échanges et validation des identités OAuth. |
| `app/services/location.py` | Recherche, gestion, hiérarchie et opérations sur les lieux. |
| `app/services/category.py` | Gestion des catégories. |
| `app/services/subcategory.py` | Gestion des sous-catégories. |
| `app/services/amenity.py` | Gestion des équipements et de leurs associations. |
| `app/services/establishment.py` | Recherche, consultation, sérialisation et gestion des établissements. |
| `app/services/favorite.py` | Gestion des favoris. |
| `app/services/payment_condition.py` | CRUD et associations des conditions de paiement. |
| `app/services/reservation.py` | Logique centrale de réservation : disponibilité/capacité, devis, prix, création idempotente, statuts, annulation, filtres et suivi administratif. |
| `app/services/payment.py` | Checkout, validation de transaction distante, confirmation, opérations admin et statistiques de paiement. |
| `app/services/reviews.py` | Création/édition, affichage, modération et approbation des avis. |
| `app/services/notification.py` | Notifications utilisateurs et administration : création, lecture, listes et suppression. |
| `app/services/notifi_dispatcher.py` | Distribution d'e-mails/notifications lors des événements de réservation, paiement et remboursement. |
| `app/services/stats.py` | Agrégats, statistiques, données de graphiques et export de données statistiques. |

## 6. Tests (`tests/`)

| Fichier | Contenu / rôle |
|---|---|
| `tests/__init__.py` | Initialisation du paquet de tests. |
| `tests/test_upload.py` | Test asynchrone d'envoi de plusieurs photos d'établissement via l'API, avec utilisateur/admin et session de test. |

Le périmètre de tests visible est étroit par rapport aux domaines fonctionnels présents : aucun fichier dédié aux parcours d'authentification, réservation, paiements, avis ou administration générale n'apparaît dans le dossier `tests`.

## 7. Parcours fonctionnels présents

- **Authentification et compte :** inscription, OTP, connexion par mot de passe ou OAuth, renouvellement/révocation de jetons, récupération de mot de passe, gestion du profil et de l'avatar.
- **Catalogue :** lieux, catégories, sous-catégories, équipements, recherche et consultation des établissements.
- **Réservation :** devis, contrôle de disponibilité/capacité, création, consultation et annulation côté client ; traitement administratif des demandes et statuts.
- **Paiement :** création et confirmation de checkout, webhook, suivi des transactions, statistiques et remboursement administratif.
- **Confiance et communication :** documents de validation, avis/modération, notifications, e-mails, notifications push et journal d'activité.
- **Administration :** comptes, établissements, contenu, paramètres, paiements, réservations et tableaux de statistiques.

## 8. Écarts et points à vérifier

1. **MCD versus implémentation :** `BestRev_API_V1_endpoints.md` décrit 32 tables conceptuelles. Les modèles et migrations relevés en définissent 19 ; plusieurs éléments du MCD (par exemple disponibilités dédiées, sessions, préférences, webhooks ou consentements) ne sont pas représentés par une table SQLModel/migration distincte dans cet état du dépôt.
2. **Routeur des paramètres :** `app/api/settings.py` définit des routes administratives, mais `app/main.py` ne l'importe ni ne l'enregistre avec `include_router`. Ces routes ne semblent donc pas exposées par l'application actuelle.
3. **Configuration locale :** `.env.example` est vide alors que `app/config.py` requiert plusieurs variables d'environnement pour démarrer (base, secret JWT, fournisseurs, stockage et Redis).
4. **Initialisation du schéma :** le démarrage appelle `SQLModel.metadata.create_all` tandis qu'un historique Alembic existe également. Les responsabilités de création/mise à jour du schéma devraient être confirmées pour les environnements de déploiement.
5. **Paiements :** la configuration accepte des paramètres Kkiapay et FedaPay, mais les routes présentes exposent un webhook Kkiapay et le service de réservation contient notamment une vérification de paiement FedaPay. Le fournisseur actif et la cohérence du parcours doivent être confirmés.
6. **Documentation de démarrage :** le `README.md` traite l'OAuth, mais ne décrit pas l'installation, le lancement, les migrations, les variables d'environnement ou l'exécution des tests.
7. **Couverture de tests visible :** un seul cas de test de téléversement est présent ; la couverture des autres parcours n'est pas documentée par des fichiers dans `tests/`.

Ces constats sont des observations statiques sur les fichiers du dépôt, pas une validation d'exécution ou un audit de sécurité.

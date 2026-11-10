# Recommandations d'adaptation : propriétaire (partenaire) et administrateur

**Date du relevé :** 7 novembre 2026  
**Nature :** recommandations d'architecture et de périmètre, sans modification du code.

> **Interprétation validée du besoin :** « partenaire » désigne le rôle actuel `PROPRIETAIRE`; « super admin » désigne le rôle actuel `ADMIN`. Le propriétaire soumet une copie de son registre de commerce et le contrat de partenariat à l'inscription. L'admin valide uniquement le compte propriétaire. Une fois validé, le propriétaire peut publier et gérer librement ses établissements et réservations; l'admin ne valide pas les établissements ni les réservations. Le propriétaire reçoit les paiements et BestRev prélève 10 % sur chaque paiement.

## 1. Objectif

Faire évoluer BestRev depuis son fonctionnement actuel vers une répartition claire entre deux rôles existants :

1. **`ADMIN` (administrateur / super admin)** : valide les comptes propriétaires à l'inscription, contrôle les indicateurs globaux et perçoit/suit la commission BestRev de 10 % sur chaque paiement. Il n'approuve pas les établissements ni les opérations de réservation.

2. **`PROPRIETAIRE` (partenaire)** : s'inscrit et fournit les documents requis; après validation de son compte, gère entièrement son profil, ses établissements, leurs médias, équipements, tarifs, disponibilités et réservations, ainsi que ses revenus et paiements.

Le rôle `CLIENT` et ses parcours de réservation doivent continuer à fonctionner. Le propriétaire peut publier ses établissements après approbation de son compte, mais ne peut accéder aux ressources d'un autre propriétaire. La validation du compte est la seule étape d'approbation opérée par `ADMIN`.

## 2. État actuel pertinent

| Domaine | Ce qui existe | Ce qui manque pour le besoin |
|---|---|---|
| Rôles | [`app/models/enums.py`](./app/models/enums.py) définit déjà `CLIENT`, `PROPRIETAIRE` et `ADMIN`. | Les rôles conviennent à la répartition demandée; c'est surtout l'autorisation des routes qui doit évoluer. Pas besoin d'introduire `PARTNER` ou `SUPER_ADMIN`. |
| Utilisateurs | [`app/models/user.py`](./app/models/user.py) porte le rôle et `UserStatus`, qui comprend `EN_ATTENTE`, `ACTIF`, `INACTIF` et `SUSPENDU`. | Définir comment le statut du compte propriétaire reflète la validation admin; éviter de confondre validation du dossier et suspension ultérieure du compte. |
| Relation établissement-propriétaire | [`app/models/establishment.py`](./app/models/establishment.py) possède déjà `owner_id` vers `users`; un propriétaire peut avoir plusieurs établissements. | Cette relation convient au besoin. Il faut l'utiliser pour filtrer et autoriser toutes les opérations de l'espace propriétaire. |
| Création d'établissement | [`app/api/admin/establishments.py`](./app/api/admin/establishments.py) est protégée par `require_admin`; la création associe l'établissement à l'admin courant. | Déplacer le CRUD vers des routes propriétaire et renseigner `owner_id` avec le compte courant. Après validation du compte propriétaire, il peut publier sans validation admin individuelle. |
| Inscription et validation | [`app/api/user.py`](./app/api/user.py) expose l'inscription; [`app/schemas/auth.py`](./app/schemas/auth.py) ne demande actuellement que l'e-mail et le mot de passe. [`app/models/validation_document.py`](./app/models/validation_document.py) rattache les justificatifs à un établissement. | Ajouter dès l'inscription propriétaire le registre de commerce et le contrat de partenariat, avec revue/approbation admin avant activation de l'espace propriétaire. Autoriser la correction et la resoumission d'un dossier rejeté. |
| Modération d'établissement | `EstablishmentStatus` comprend `EN_ATTENTE`, `PUBLIE`, `REJETE`, `SUSPENDU`. | Ne pas imposer de validation admin par établissement. Définir les statuts utilisés pour la publication autonome par un propriétaire dont le compte est validé; conserver les états existants seulement si des cas de suspension/retrait restent nécessaires. |
| Réservations | [`app/models/reservation.py`](./app/models/reservation.py) relie réservation, client et établissement; il conserve des montants et des traces d'état. | Exposer au propriétaire la gestion complète des réservations de ses établissements, avec filtrage strict par `owner_id`; `ADMIN` n'intervient pas dans leur validation opérationnelle selon la décision actuelle. |
| Finances | La réservation conserve `commission_rate`, `commission_amount`, `partner_amount`; [`app/config.py`](./app/config.py) contient des taux par catégorie. [`app/models/transaction.py`](./app/models/transaction.py) trace paiements et remboursements. | Appliquer une commission BestRev fixe de 10 % sur chaque paiement. Aucun mécanisme de partage automatique, de collecte de commission, de rapprochement ou de relevé propriétaire n'a été identifié. |
| Disponibilités | L'établissement a un état global de disponibilité, une capacité et des champs tarifaires. | Ajouter un inventaire quotidien exprimé en chambres/unités, modifiable par le propriétaire et cohérent avec les réservations existantes. |
| Autorisations | [`app/dependencies/dependencies.py`](./app/dependencies/dependencies.py) fournit `require_admin` et `require_client`. | Il manque `require_proprietaire`/propriétaire actif et le contrôle de propriété de chaque établissement, réservation, photo et ressource liée. |
| Administration utilisateur | [`app/schemas/admin_user.py`](./app/schemas/admin_user.py) limite le changement de rôle à `CLIENT` ou `ADMIN`. | Le flux d'inscription doit créer un compte `PROPRIETAIRE` sans permettre au client de choisir arbitrairement un rôle privilégié; l'admin approuve le dossier et active l'accès propriétaire. |
| Statistiques et paramètres | Services globaux dans [`app/services/stats.py`](./app/services/stats.py); paramètres de plateforme dans le modèle dédié. | Pas de vues filtrées par partenaire. Le routeur défini dans [`app/api/settings.py`](./app/api/settings.py) n'est pas monté dans [`app/main.py`](./app/main.py), à vérifier avant de bâtir l'administration des réglages dessus. |
| Médias et équipements | Les routes d'administration d'images et d'équipements demandent `require_admin`. | Donner ces capacités au propriétaire pour ses établissements uniquement, en filtrant par `owner_id`. |

Le dépôt possède déjà le rôle `PROPRIETAIRE` et la relation `Establishment.owner_id`. L'évolution consiste à autoriser ce rôle à gérer tout son périmètre après validation de son compte, sans approbation admin établissement par établissement. La documentation métier initiale décrivait un lancement sans espace Owner ([`bestrev-regles-metier-reservation.md`](./bestrev-regles-metier-reservation.md)); le besoin actuel remplace cette hypothèse.

## 3. Modèle de rôles retenu

### Réutiliser les rôles déjà présents

- **`User`** reste le compte de connexion et d'identité.
- **`PROPRIETAIRE`** est le partenaire, représenté par son compte utilisateur actuel.
- **`ADMIN`** reste l'administrateur principal/super admin.
- **`Establishment.owner_id`** détermine les établissements gérés par ce propriétaire.

Il n'est pas nécessaire, pour le besoin décrit, d'ajouter un modèle `Partner`, une table d'appartenance ou des rôles `PARTNER`/`SUPER_ADMIN`. Un profil professionnel complémentaire peut être nécessaire si les justificatifs ou coordonnées d'entreprise ne trouvent pas leur place dans `Profile`, mais cela ne doit pas créer un nouveau type d'acteur.

### Cycle de vie du compte propriétaire

1. Le candidat crée un compte avec le rôle `PROPRIETAIRE`, vérifie son adresse e-mail et soumet la copie du registre de commerce et le contrat de partenariat.
2. La vérification OTP de l'e-mail ne vaut pas validation professionnelle : tant que `ADMIN` n'a pas approuvé le dossier, l'accès à la gestion des établissements, réservations et finances reste bloqué.
3. `ADMIN` vérifie le dossier et approuve ou rejette la demande avec un motif.
4. Après vérification de l'e-mail et approbation admin, le compte peut accéder à l'espace propriétaire; une suspension ultérieure peut bloquer le compte sans effacer l'historique.

Les valeurs de statut existantes doivent être employées de façon cohérente. Vérifier en particulier que la validation OTP ne transforme pas prématurément le propriétaire en compte pleinement actif. `UserStatus.EN_ATTENTE` peut rester en vigueur jusqu'à l'approbation admin; ajouter un statut de validation dédié seulement si le statut de connexion doit être séparé du dossier professionnel.

Le changement de statut doit invalider les jetons existants ou, au minimum, chaque requête doit revérifier le statut actuel du compte. Le comportement d'authentification actuel charge l'utilisateur depuis la base; confirmer que tous les parcours utilisent cette vérification avant d'accorder des droits.

## 4. Améliorations des modèles

### 4.1 Compte propriétaire et documents d'inscription

Ne pas ajouter un modèle `Partner` pour représenter l'acteur : le partenaire est le compte `User` dont le rôle est `PROPRIETAIRE`.

Le flux d'inscription doit permettre de soumettre les documents professionnels avant la création du premier établissement. Le modèle [`ValidationDocument`](./app/models/validation_document.py) actuel est lié obligatoirement à un établissement et ne convient donc pas tel quel à la validation initiale du propriétaire.

Faire évoluer la gestion des justificatifs afin qu'un document puisse être rattaché à un propriétaire sans établissement (ou à un dossier d'inscription propriétaire), avec :

- type de pièce, nom, URL de stockage, taille et type MIME;
- état de revue, date de soumission et date de décision;
- admin ayant examiné le document, commentaire et motif de rejet;
- relation explicite vers le propriétaire `User`;
- possibilité de conserver les anciennes pièces et décisions lors d'une resoumission.

Décider si les pièces requises sont validées individuellement et si le compte n'est approuvé que lorsque tous les documents obligatoires sont acceptés. Une décision globale d'approbation/rejet du dossier propriétaire doit également être historisée.

Réutiliser `UserStatus.EN_ATTENTE`/`ACTIF` si ces statuts suffisent pour bloquer ou autoriser l'espace propriétaire. Ajouter un état de dossier dédié seulement si le statut de connexion doit rester indépendant du niveau de vérification professionnelle. Ajouter un type de document tel que `CONTRAT_PARTENARIAT` à `DocumentType`, qui ne distingue pas actuellement ce contrat du registre de commerce.

### 4.2 Établissements gérés par leur propriétaire

- Conserver `Establishment.owner_id` comme relation de propriété et source de vérité pour l'accès du propriétaire; ne pas ajouter de relation partenaire redondante.
- Déplacer la création, la modification et la suppression métier de l'établissement vers le propriétaire. À la création, le serveur renseigne `owner_id` depuis l'utilisateur authentifié; le client ne choisit pas cet identifiant.
- Dès que le compte `PROPRIETAIRE` est approuvé, il peut publier ses établissements sans validation admin individuelle. À la création, le statut public doit donc suivre cette règle; le propriétaire peut aussi gérer l'état de disponibilité/publication qui lui est autorisé.
- Garder séparés `owner_id` (propriétaire) et `created_by`/`updated_by` (acteur de la modification). Ne pas créer de processus de revue admin par établissement.
- Les pièces d'identité/entreprise du propriétaire doivent être séparées des pièces propres à la conformité d'un établissement, même si les deux types réutilisent un service de stockage de fichiers.
- Le propriétaire gère le contenu, les médias, les équipements, les tarifs et les disponibilités de ses établissements. Définir les règles de suspension/retrait pour contenu illégal, fraude ou fermeture, sans réintroduire une validation systématique des modifications par l'admin.
- Si le compte propriétaire est suspendu, empêcher ses opérations et définir le traitement de ses établissements publiés; conserver réservations et traces historiques.

### 4.3 Réservations gérées par le propriétaire

- Les réservations devraient continuer à référencer l'établissement; le propriétaire est retrouvé via `Establishment.owner_id`.
- Le propriétaire gère toutes les réservations de ses établissements : consultation, décision, suivi de la prestation et actions de réservation définies par le cycle métier.
- `ADMIN` ne valide pas les réservations. Les actions d'administration globales éventuelles doivent rester hors du flux ordinaire du propriétaire et ne pas imposer son intervention sur chaque réservation.
- Conserver un historique des changements de statut/décisions avec l'acteur et le motif, afin de suivre les actions du propriétaire et d'instruire les éventuels litiges.
- Continuer à figer sur la réservation le tarif et la commission appliqués au moment de la réservation. Ces snapshots sont essentiels pour éviter qu'une modification ultérieure du contrat recalcule l'historique.

### 4.4 Commissions, règlements et relevés

La règle métier donnée est une commission BestRev de **10 % sur chaque paiement**, alors que le propriétaire reçoit le paiement. Les champs financiers de réservation fournissent une base de calcul historique, mais ils ne suffisent pas à représenter le partage et le rapprochement effectifs.

À prévoir :

- remplacer les valeurs de commission par catégorie existantes comme règle par défaut du nouveau parcours par un taux défini à 10 %, sauf décision ultérieure explicite de différenciation;
- calculer et enregistrer la commission pour chaque paiement confirmé, et non uniquement une fois sur le total de réservation; enregistrer la base exacte, le taux, la commission et le net revenant au propriétaire;
- utiliser le fournisseur de paiement pour répartir automatiquement le paiement (10 % à BestRev et 90 % au propriétaire) si cette fonction est disponible; sinon définir un mécanisme fiable de collecte/versement et de rapprochement. Le transfert doit respecter l'exigence que le propriétaire reçoive le paiement;
- conserver un journal financier/ledger de chaque paiement, commission, remboursement et ajustement, relié aux transactions existantes;
- fournir au propriétaire son historique de paiements, commissions prélevées, montants reçus et relevés téléchargeables; fournir à `ADMIN` le suivi global des commissions perçues;
- définir comment la commission est corrigée si un paiement est remboursé, annulé, échoué ou partiellement remboursé, sans supprimer les transactions d'origine.

Les tableaux de bord devront distinguer au minimum : paiement client, montant transmis au propriétaire, commission BestRev calculée et effectivement perçue, remboursement et solde net. Ne pas assimiler `partner_amount` à une somme réellement versée sans preuve du fournisseur ou du registre financier.

### 4.5 Tarifs et disponibilités

- Décider si les champs tarifaires actuels portés par `Establishment` suffisent pour la première version ou si les tarifs doivent varier selon les périodes, unités, options ou catégories de service.
- Pour la gestion demandée, définir un inventaire quotidien par établissement et par chambre/unité (nombre total, disponible, bloqué/réservé, éventuellement prix et fermeture). Le champ global `availability_status` seul n'exprime pas cette disponibilité datée.
- Définir les règles de réservation concurrente et de mise à jour de l'inventaire afin qu'une unité ne puisse pas être vendue deux fois; la capacité restante doit être recalculée en tenant compte des réservations actives.
- Conserver les règles de calcul dans les services métier et leurs snapshots dans la réservation; ne pas laisser le frontend calculer un prix faisant autorité.

## 5. Améliorations des schémas

Organiser les schémas par espace et par intention, sans exposer directement les modèles SQLModel :

### Propriétaire (`PROPRIETAIRE`)

- schéma d'inscription propriétaire avec les champs professionnels et documents requis;
- distinguer l'inscription client existante de l'inscription propriétaire; ne jamais accepter `ADMIN` comme rôle choisi par le demandeur;
- schéma de consultation/mise à jour du profil propriétaire;
- schéma de réponse publique/administrative, avec champs sensibles séparés;
- schéma réservé à `ADMIN` pour approuver/rejeter/suspendre un propriétaire avec motif;
- schémas de soumission, lecture et revue des documents du propriétaire.

Le propriétaire ne doit jamais pouvoir fournir dans son payload `owner_id`, son statut de validation, le statut public d'un établissement, la commission définitive ou un champ d'audit. Le serveur déduit le propriétaire du compte authentifié.

### Établissements

- conserver les schémas de données descriptives existants autant que possible;
- permettre au propriétaire validé de créer et modifier son établissement, avec un schéma ne contenant ni `owner_id`, ni champs d'audit;
- le serveur déduit `owner_id` du compte authentifié et fixe l'état publiable automatiquement pour un propriétaire approuvé; le propriétaire peut ensuite gérer la disponibilité et, si nécessaire, masquer/réactiver sa propriété;
- ne pas prévoir de schéma/endpoint d'approbation admin établissement par établissement;
- séparer les schémas de tarifs et d'inventaire quotidien par chambre/unité si leurs règles de validation diffèrent;
- ne pas inclure les données internes d'administration dans les réponses publiques.

### Réservations

- créer des réponses adaptées au propriétaire, qui gère intégralement les réservations de ses établissements;
- permettre les actions de gestion selon le cycle métier et historiser les changements, sans validation admin comme étape ordinaire;
- le propriétaire consulte toutes les informations client nécessaires à la gestion de la réservation.

### Finance et statistiques

- schémas propriétaire filtrés par `owner_id` de l'utilisateur authentifié;
- filtres de période, devise, statut et établissement pour les relevés;
- contrats distincts pour le paiement client, le prélèvement de 10 %, le montant transmis au propriétaire et les remboursements;
- export de relevé avec période et détails de rapprochement, en veillant à ne pas exposer les données d'autres partenaires.

### Utilisateurs et paramètres

- préserver une attribution contrôlée du rôle `PROPRIETAIRE` à l'inscription propriétaire; réserver l'attribution de `ADMIN` et les changements de rôle aux opérations administratives protégées;
- permettre à `ADMIN` d'approuver/rejeter le dossier et de modifier le statut du compte avec journalisation;
- permettre au propriétaire de lire et modifier uniquement son profil, jamais les champs d'administration ou les paramètres globaux de la plateforme.

## 6. Améliorations des helpers et dépendances

Les règles d'accès doivent être communes aux routeurs et aux services, pas recopiées dans chaque endpoint.

À prévoir dans les dépendances d'autorisation :

1. garder `require_admin` pour la validation des comptes propriétaires et l'accès aux tableaux de bord globaux;
2. ajouter `require_proprietaire` pour vérifier que le compte authentifié a le rôle `PROPRIETAIRE`, que l'e-mail est vérifié et que le compte a été approuvé par `ADMIN`;
3. ajouter une fonction partagée de chargement d'établissement qui vérifie `Establishment.owner_id == current_user.id`;
4. appliquer ce contrôle aux photos, équipements, réservations, tarifs, inventaire, revenus, commissions et statistiques liées à un établissement.

Le filtrage par `owner_id` doit être fait dans les requêtes SQL des services, avant pagination, comptage et export. Ne pas charger une ressource globale puis compter sur un contrôle uniquement dans la route. Un identifiant d'établissement fourni par l'appelant ne prouve jamais qu'il en est propriétaire.

Le propriétaire doit disposer des informations de réservation et client nécessaires à la gestion complète de son activité. Les notes purement internes à l'administration restent séparées des données de réservation visibles par le propriétaire.

## 7. Évolution des API

Conserver les routes publiques et client existantes autant que possible. Ajouter des espaces fonctionnels nettement séparés, par exemple :

### `ADMIN` — administrateur principal

- propriétaires : liste/détail, revue des documents d'inscription (registre de commerce et contrat de partenariat), approbation/rejet du compte et suivi des resoumissions;
- établissements : aucune validation ou CRUD requis dans le parcours normal; visibilité globale uniquement si nécessaire au suivi de plateforme;
- réservations : aucune validation ou gestion opérationnelle dans le parcours normal du propriétaire;
- finances : suivi des 10 % prélevés sur chaque paiement, rapports et rapprochements;
- paramètres et statistiques globaux selon le périmètre de l'administration.

Les routes actuelles d'administration des utilisateurs constituent un point de départ pour les comptes propriétaires. Les routes actuelles de création/modification des établissements ne doivent plus être le parcours normal du propriétaire; créer un espace propriétaire distinct et réserver à l'admin seulement les actions retenues ci-dessus. Les routes de paramètres doivent être vérifiées/montées avant d'être considérées comme disponibles.

### `PROPRIETAIRE` — partenaire

- profil : consultation et modification des informations autorisées, documents, logo et coordonnées;
- établissements : après approbation du compte, créer, publier, modifier et gérer exclusivement ses établissements, médias, équipements, tarifs et inventaire journalier;
- réservations : gestion complète des réservations de ses établissements et accès aux informations client requises;
- finances : recevoir les paiements, consulter les 10 % prélevés par BestRev, ses montants nets et ses relevés;
- statistiques : réservations, établissements performants, chiffre d'affaires et taux d'occupation par chambre/unité.

Les routes existantes de gestion des établissements, médias et équipements sont protégées par `require_admin`; la création actuelle attribue `owner_id` à l'admin. Il faut transférer ce CRUD au rôle `PROPRIETAIRE`, filtrer toutes les opérations par le propriétaire connecté et empêcher l'accès avant validation de son compte. La publication d'un établissement ne requiert pas une décision admin.

## 8. Matrice de droits cible

| Capacité | Client | Propriétaire (`PROPRIETAIRE`) | Admin (`ADMIN`) |
|---|---:|---:|---:|
| Consulter les établissements publiés | Oui | Oui | Oui |
| Gérer son profil et ses documents | Non | Son propre compte | Tous / revue |
| Créer/modifier ses établissements | Non | Oui, uniquement les siens | Non |
| Publier/gérer un établissement | Non | Oui, les siens après validation de son compte | Pas de validation obligatoire |
| Consulter les réservations | Ses réservations | Toutes celles de ses établissements | Suivi global éventuel |
| Gérer une réservation | Non | Oui, entièrement pour ses établissements | Pas d'approbation opérationnelle |
| Consulter les données client | Ses propres données | Oui, toutes les données nécessaires à son activité | Selon nécessité de suivi |
| Gérer les catégories ou paramètres globaux | Non | Non | Oui |
| Consulter les finances | Ses paiements | Paiements reçus, commission prélevée et relevés propres | Commission BestRev globale de 10 % |
| Définir/modifier la commission | Non | Non | Oui; règle retenue actuellement : 10 % par paiement |
| Consulter/administrer un autre propriétaire | Non | Non | Oui |

Cette matrice reflète les décisions données : le propriétaire gère son activité et ses réservations; l'admin valide son compte et suit la commission. Les modalités de remboursement et de traitement des litiges restent à formaliser.

## 9. Parcours recommandés

### Inscription et validation du propriétaire

1. Le candidat crée un compte avec le rôle `PROPRIETAIRE`, vérifie son e-mail et soumet une copie du registre de commerce et le contrat de partenariat.
2. Le compte/dossier reste en attente; la vérification d'e-mail seule ne débloque pas les fonctions propriétaire.
3. `ADMIN` examine les deux pièces et approuve ou rejette le compte avec motif; la décision est journalisée.
4. Si le dossier est rejeté, le candidat peut corriger/remplacer les documents et resoumettre; l'accès reste bloqué jusqu'à l'approbation.
5. Après approbation admin, le propriétaire peut gérer son compte et publier ses établissements sans validation individuelle.
6. Une suspension ultérieure du compte (si elle fait partie de la politique retenue) bloque ses opérations sans détruire ses établissements ni les données financières.

### Publication d'un établissement

1. Le propriétaire dont le compte est validé crée et publie un établissement qui lui appartient.
2. Le serveur fixe automatiquement `owner_id`; aucune validation admin établissement par établissement n'est demandée.
3. Le propriétaire gère ensuite le contenu, les médias, les équipements, les tarifs et les disponibilités.
4. Les mécanismes de signalement, suspension ou retrait par l'admin en cas d'abus restent à définir séparément; ils ne constituent pas une approbation préalable à la publication.

### Réservation et règlements

1. Le client paie selon le flux existant; la transaction est associée à la réservation et à l'établissement du propriétaire.
2. Le fournisseur répartit chaque paiement de sorte que le propriétaire reçoive le montant net et BestRev 10 %, ou un mécanisme alternatif enregistre et collecte explicitement la commission.
3. Le propriétaire gère la réservation et consulte le paiement associé à son établissement.
4. Le système garde une trace rapprochable du montant brut, des 10 %, du net propriétaire, du statut du transfert et de tout remboursement.
5. Les relevés présentent au propriétaire ses paiements et commissions; l'administration suit la part BestRev.

## 10. Migration et compatibilité

Il n'est pas nécessaire de migrer vers de nouveaux rôles ou de créer des partenaires distincts. Avant le développement, inventorier les comptes `PROPRIETAIRE`, les établissements liés à chaque `owner_id`, les comptes `ADMIN` qui ont créé des établissements et les documents de validation.

Plan recommandé :

1. conserver les valeurs de rôle `CLIENT`, `PROPRIETAIRE` et `ADMIN`;
2. inventorier les comptes propriétaires actuels en `EN_ATTENTE` ou `ACTIF` et décider lesquels ont déjà été approuvés;
3. ajouter le rattachement et l'historique des documents/décisions du dossier propriétaire;
4. examiner les établissements existants dont `owner_id` désigne un admin : attribuer le véritable propriétaire après vérification, sans transfert automatique;
5. conserver les réservations, transactions, références et snapshots financiers existants;
6. introduire les contrôles d'accès par `owner_id` avant d'exposer les nouvelles routes propriétaire;
7. déplacer le CRUD d'établissement vers le propriétaire; l'admin ne valide pas les propriétés. Toute action exceptionnelle de retrait/suspension pour abus doit être une règle distincte, si elle est retenue.

Tester les migrations sur une copie de données représentative et vérifier les propriétaires sans documents, les comptes en attente, les établissements gérés historiquement par BestRev, les suppressions logiques et les réservations historiques.

## 11. Ordre de travail conseillé

1. **Décisions métier** — documents requis, approbation du compte propriétaire, transitions de réservation, visibilité des données client et règles de commission/règlement.
2. **Modèle de données** — pièces/décisions du compte propriétaire, inventaire de disponibilité et registre financier des paiements/commissions; réutiliser `owner_id`.
3. **Migrations et compatibilité** — reprise des comptes/dossiers et attribution vérifiée des établissements existants, conservation intégrale de l'historique.
4. **Autorisations communes** — `require_admin`, `require_proprietaire` et filtrage par `owner_id` au niveau des services.
5. **Inscription et établissement** — soumission du compte/documents, validation admin du compte, puis CRUD et publication autonomes par le propriétaire.
6. **Espace propriétaire réservation** — listes filtrées, transitions métier et informations client limitées.
7. **Finances et statistiques** — politiques de commission, rapprochement, règlements, relevés et agrégats par partenaire.
8. **Contrats d'API et documentation** — schémas dédiés, routes et documentation des réponses/erreurs.
9. **Tests d'accès et de parcours** — vérifier notamment qu'un partenaire A ne peut lire ou modifier aucune ressource du partenaire B, par ID direct, filtre, pagination, export ou relation secondaire.

## 12. Décisions déjà prises et derniers points techniques

### Décisions déjà prises

- Rôles inchangés : `PROPRIETAIRE` = partenaire; `ADMIN` = super admin.
- Documents requis à l'inscription du propriétaire : copie du registre de commerce et contrat de partenariat.
- Un dossier rejeté peut être corrigé et resoumis.
- Après validation du compte, le propriétaire peut publier et gérer librement ses établissements; l'admin ne valide pas les établissements.
- Le propriétaire gère ses réservations et voit les informations nécessaires des clients.
- BestRev prélève 10 % sur chaque paiement; le propriétaire reçoit son paiement.
- L'inventaire d'hébergement est quotidien et exprimé en chambres/unités.

### À préciser techniquement avant l'implémentation financière
commission est-elle collectée?
2. Les 10 % sont-ils calculés sur le montant brut de chaque transaction avant frais du fournisseur, ou sur le montant
1. Le fournisseur de paiement choisi permet-il un partage automatique du paiement (10 % vers BestRev, 90 % vers le propriétaire)? Sinon, à quel moment et par quel mécanisme la  net après frais?
3. En cas de remboursement total ou partiel, la commission de 10 % est-elle remboursée au prorata?
4. Les champs exacts de l'inventaire quotidien par chambre/unité (unités totales, fermeture, prix journalier, minimum de nuits) restent à détailler; l'unité d'inventaire est déjà décidée.

Ces points ne remettent pas en cause les décisions métier déjà fixées; ils servent à rendre leur traitement et leur rapprochement possibles.

## Conclusion

La transition ne nécessite pas de refaire tout le backend ni de créer de nouveaux rôles ou un modèle d'entreprise distinct : `PROPRIETAIRE`, `ADMIN` et `Establishment.owner_id` fournissent les fondations nécessaires. Le changement central est de transférer le CRUD des établissements et la gestion des réservations vers le propriétaire, avec des vérifications d'accès par `owner_id`. L'admin valide les comptes propriétaires et non les établissements.

Les principales lacunes à traiter sont l'inscription propriétaire avec les deux documents et la resoumission après rejet, les autorisations par `owner_id`, l'inventaire quotidien par chambre/unité et le partage/traçage financier des 10 % par paiement. La validation du compte propriétaire est le seul contrôle préalable effectué par l'admin.

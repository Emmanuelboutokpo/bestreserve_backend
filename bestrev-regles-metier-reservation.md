# BestRev --- Règles métier du module de réservation

**Version :** 1.0\
**Contexte :** lancement de BestRev sans espace Owner. Les
établissements et les réservations sont gérés depuis l'administration
centrale de BestRev.

## 1. Objectif et principes fondamentaux

Le module permet aux clients de réserver un hébergement, une table au
restaurant ou une activité de loisir. Au lancement, BestRev assure la
gestion opérationnelle des établissements partenaires.

Principes fondamentaux :

1.  Le client peut consulter les établissements publiés et soumettre une
    réservation.
2.  Seuls les administrateurs autorisés peuvent créer et modifier les
    établissements, leurs tarifs et leurs disponibilités.
3.  Une demande de réservation n'est pas automatiquement confirmée.
4.  La disponibilité doit être vérifiée côté backend avant la
    confirmation.
5.  Le prix est calculé par le backend selon les règles tarifaires de
    l'établissement.
6.  Les prestations, suppléments, taxes, frais de service et commissions
    sont distingués.
7.  Le détail du calcul tarifaire est conservé avec la réservation.
8.  Les annulations, remboursements et commissions suivent des règles
    définies.
9.  Les opérations sensibles sont traçables.
10. Le modèle doit permettre l'ajout futur d'un espace Owner sans
    refonte majeure.

## 2. Acteurs et responsabilités

  -----------------------------------------------------------------------
  Acteur                              Responsabilités
  ----------------------------------- -----------------------------------
  Client                              Consulter les offres, créer une
                                      réservation, suivre son statut et
                                      demander une annulation.

  Administrateur BestRev              Gérer les établissements, tarifs,
                                      disponibilités, demandes et suivi
                                      financier.

  Établissement partenaire            Confirmer les disponibilités auprès
                                      de BestRev, fournir la prestation
                                      et respecter les conditions
                                      convenues.

  Prestataire de paiement             Traiter les paiements et
                                      transmettre leur résultat au
                                      backend si le paiement en ligne est
                                      activé.

  Système BestRev                     Calculer les prix, gérer les
                                      statuts, contrôler les règles
                                      métier et déclencher les
                                      notifications.
  -----------------------------------------------------------------------

Au lancement, le partenaire n'a pas besoin de compte. Ses confirmations
peuvent être recueillies par téléphone ou WhatsApp, puis enregistrées
dans l'administration par un administrateur BestRev.

## 3. Chronologie d'une réservation

1.  **Recherche et sélection :** le client choisit un établissement et
    renseigne les dates, créneaux, voyageurs ou participants requis.
2.  **Validation des données :** le backend vérifie l'établissement, les
    dates, la capacité et les règles de réservation.
3.  **Calcul du prix :** le backend calcule les prestations,
    suppléments, taxes, réductions et frais applicables.
4.  **Création de la demande :** une réservation est enregistrée avec le
    statut `EN_ATTENTE` et une référence unique.
5.  **Vérification par BestRev :** un administrateur contacte le
    partenaire pour confirmer la disponibilité et le tarif.
6.  **Paiement ou validation finale :** selon les conditions convenues,
    le client paie intégralement, verse un acompte ou paie sur place.
7.  **Confirmation :** lorsque toutes les conditions sont satisfaites,
    la réservation passe à `CONFIRMEE`.
8.  **Prestation :** elle passe à `EN_COURS` lorsque le service
    commence, puis à `TERMINEE` lorsqu'il est achevé.

Le paiement n'est pas nécessairement obligatoire avant confirmation pour
toutes les catégories. Les conditions doivent être définies par
catégorie et par accord partenaire.

## 4. Règles métier de création

### RB-01 --- Conditions préalables

Le système vérifie que :

-   l'établissement existe et est publié ;
-   il accepte le type de réservation demandé ;
-   les informations obligatoires sont présentes ;
-   les dates et créneaux sont valides ;
-   le nombre de personnes respecte la capacité ;
-   les règles tarifaires sont définies ;
-   l'établissement accepte les enfants ou les animaux déclarés, lorsque
    cela s'applique.

Si une condition essentielle n'est pas remplie, la réservation ne doit
pas être créée.

### RB-02 --- Données de réservation

Chaque réservation contient au minimum :

-   un identifiant unique et une référence lisible ;
-   le client et l'établissement ;
-   la catégorie : hébergement, restaurant ou loisir ;
-   la date de création ;
-   les dates du séjour ou le créneau de la prestation ;
-   le nombre d'adultes, d'enfants et, si nécessaire, les âges des
    enfants ;
-   le nombre et le type d'animaux, si applicable ;
-   le détail du calcul tarifaire ;
-   le montant total et la devise ;
-   le montant payé et le solde restant ;
-   le statut de réservation et le statut de paiement ;
-   les informations de suivi administratif.

Les champs propres à chaque catégorie restent spécifiques. Une
réservation de restaurant, par exemple, ne nécessite pas de date de
départ.

### RB-03 --- Prévention des doublons

Le système doit éviter les doubles créations causées par un double clic,
une relance réseau ou une nouvelle tentative. Prévoir une clé
d'idempotence pour les opérations sensibles et des contrôles
transactionnels de disponibilité.

## 5. Règles de calcul du prix

Le calcul doit être centralisé dans un service métier, par exemple
`PriceCalculationService`.

### RB-04 --- Hébergement

Si le tarif est par chambre et par nuit :

`Sous-total hébergement = somme des prix applicables à chaque nuit`

Le serveur ajoute les suppléments applicables : voyageurs
supplémentaires, enfants, animaux, ménage ou services optionnels.

Si le tarif est par personne et par nuit, il applique les règles
configurées pour les adultes et les enfants.

**Règle :** ne pas multiplier automatiquement le tarif par le nombre de
voyageurs si le prix correspond à une chambre entière.

### RB-05 --- Restaurant

Le système prend en charge :

-   la réservation simple sans paiement anticipé ;
-   la réservation avec acompte ;
-   le forfait par personne ou par groupe ;
-   les éventuels frais de réservation.

Le montant estimé du repas ne doit pas être confondu avec le montant
réellement payé pour les consommations.

### RB-06 --- Loisirs

Le calcul peut être basé sur :

-   le nombre de participants ;
-   la durée de l'activité ;
-   un tarif fixe par prestation ;
-   un forfait de groupe ;
-   des options supplémentaires.

La méthode tarifaire est définie pour chaque offre.

### RB-07 --- Frais, taxes et réductions

Formule générale :

`Total client = prestations + frais applicables + taxes applicables − réductions`

Chaque composant est enregistré séparément. Les règles précisent quels
frais sont obligatoires ou optionnels, qui les perçoit et quelle
assiette s'applique à chaque taxe. Les taxes doivent être validées selon
la réglementation en vigueur.

### RB-08 --- Conservation du prix

Au moment de la création, conserver une copie du calcul :

-   tarifs unitaires appliqués ;
-   quantités et durées ;
-   suppléments ;
-   taxes ;
-   réductions ;
-   frais de service ;
-   total client ;
-   commission BestRev ;
-   montant revenant au partenaire.

Une modification ultérieure des tarifs ne doit pas changer le prix
historique d'une réservation déjà conclue, sauf modification
expressément acceptée et tracée.

## 6. Gestion des statuts

### RB-09 --- Statuts de réservation

  -----------------------------------------------------------------------
  Statut                              Signification
  ----------------------------------- -----------------------------------
  `EN_ATTENTE`                        Demande créée, vérification ou
                                      validation en cours.

  `CONFIRMEE`                         Toutes les conditions de
                                      confirmation sont satisfaites.

  `EN_COURS`                          La prestation a commencé.

  `TERMINEE`                          La prestation est achevée.

  `REFUSEE`                           La demande a été refusée.

  `ANNULEE`                           La réservation a été annulée
                                      conformément aux règles.

  `EXPIREE`                           Le délai de validation ou de
                                      paiement est dépassé.
  -----------------------------------------------------------------------

Les transitions sont contrôlées côté serveur. Une réservation refusée ne
peut pas être directement transformée en réservation terminée. Une
réservation terminée ne peut pas être annulée via la procédure
ordinaire.

### RB-10 --- Confirmation manuelle

Au lancement, un administrateur confirme la réservation après
vérification auprès du partenaire. Il enregistre :

-   le résultat de la vérification ;
-   la date et l'heure de la réponse ;
-   le canal utilisé ;
-   l'identité de l'administrateur ;
-   les observations éventuelles.

La confirmation est interdite si la disponibilité n'a pas été validée ou
si les conditions de paiement exigées ne sont pas remplies.

### RB-11 --- Refus et expiration

En cas de refus, le motif est enregistré et le client est informé.

Si aucune réponse n'est reçue avant le délai prévu, la demande peut
expirer. Si un paiement a déjà été effectué, le remboursement est traité
selon les conditions applicables.

## 7. Paiements

### RB-12 --- Modes de paiement

Selon les options activées, BestRev peut proposer :

-   paiement intégral en ligne ;
-   paiement d'un acompte ;
-   réservation en ligne avec paiement sur place.

Le mode applicable doit être communiqué au client avant la confirmation.

### RB-13 --- Validation du paiement

Une réservation n'est jamais considérée comme payée uniquement parce que
le navigateur affiche une page de succès. Le backend vérifie la
confirmation officielle du prestataire, par exemple via un webhook dont
la signature est vérifiée.

Chaque transaction est traitée de manière idempotente afin d'éviter les
doubles opérations.

### RB-14 --- Annulation et remboursement

Avant un remboursement, le système vérifie :

-   les conditions d'annulation ;
-   le montant réellement encaissé ;
-   les éventuelles pénalités contractuelles ;
-   le montant remboursable ;
-   les remboursements déjà effectués.

Le remboursement possède son propre suivi, distinct du statut de
réservation.

## 8. Monétisation BestRev

### RB-15 --- Conditions de commission

Chaque partenariat doit définir :

-   le taux ou montant de commission ;
-   la base de calcul ;
-   les catégories et prestations concernées ;
-   le moment où la commission devient due ;
-   les règles en cas d'annulation ou de remboursement ;
-   les modalités et échéances de règlement.

Une commission sur les prestations éligibles est un modèle de départ
possible. Le taux est négocié et formalisé avec chaque partenaire.

### RB-16 --- Calcul de commission

Exemple : prestation éligible de 20 000 FCFA et commission de 10 %.

`Commission BestRev = 20 000 × 10 % = 2 000 FCFA`

Il faut distinguer la commission calculée, la commission devenue
exigible et la commission effectivement encaissée. Les taxes collectées
pour le compte de l'État ne constituent pas un revenu de BestRev. Les
frais du prestataire de paiement sont suivis séparément.

### RB-17 --- Suivi financier

L'administration doit permettre de consulter :

-   le montant total des réservations ;
-   les montants encaissés ;
-   les commissions dues et réglées ;
-   les sommes à reverser aux partenaires, si BestRev encaisse ;
-   les remboursements ;
-   les réservations annulées ou contestées.

## 9. Disponibilités et capacités

### RB-18 --- Hébergement

Vérifier les nuits concernées et empêcher les chevauchements
incompatibles avec les réservations confirmées, les blocs de
disponibilité et les éventuelles retenues temporaires.

### RB-19 --- Restaurant

Contrôler la capacité disponible au créneau, le nombre de personnes et
les éventuelles limites de durée.

### RB-20 --- Loisirs

Vérifier les places restantes, les horaires, la capacité maximale et les
conditions d'accès.

### RB-21 --- Gestion manuelle des disponibilités

L'administration doit permettre de bloquer manuellement une chambre, une
table, un créneau ou une activité. L'interface doit préciser si la
disponibilité est vérifiée en temps réel ou nécessite une confirmation
du partenaire.

Les contrôles de disponibilité doivent être protégés contre les
opérations concurrentes. Une simple vérification suivie d'une écriture
non protégée ne suffit pas à empêcher les doubles réservations.

## 10. Notifications

### RB-22 --- Notifications client

Envoyer les notifications pertinentes lors des événements suivants :

-   création de la demande ;
-   confirmation ou refus ;
-   demande de paiement ;
-   confirmation du paiement ;
-   annulation ou remboursement ;
-   rappel avant la prestation ;
-   modification importante.

### RB-23 --- Notifications administratives

Alerter l'administration des nouvelles demandes, des réservations à
vérifier, des paiements en échec et des annulations nécessitant une
action.

Une panne d'e-mail ou de WhatsApp ne doit pas annuler une réservation
enregistrée. Les notifications doivent pouvoir être réessayées et leur
résultat doit être traçable.

## 11. Routes API proposées

  ------------------------------------------------------------------------------------
  Méthode                 Endpoint                             Responsabilité
  ----------------------- ------------------------------------ -----------------------
  `POST`                  `/reservations`                      Créer une demande de
                                                               réservation

  `GET`                   `/reservations/me`                   Consulter les
                                                               réservations du client
                                                               connecté

  `GET`                   `/reservations/:id`                  Consulter une
                                                               réservation autorisée

  `POST`                  `/reservations/:id/cancel`           Demander une annulation

  `GET`                   `/admin/reservations`                Consulter les
                                                               réservations dans
                                                               l'administration

  `GET`                   `/admin/reservations/:id`            Consulter le détail et
                                                               le suivi

  `PATCH`                 `/admin/reservations/:id/confirm`    Confirmer une
                                                               réservation validée

  `PATCH`                 `/admin/reservations/:id/reject`     Refuser une demande

  `PATCH`                 `/admin/reservations/:id/start`      Démarrer la prestation

  `PATCH`                 `/admin/reservations/:id/complete`   Terminer la prestation

  `PATCH`                 `/admin/reservations/:id/cancel`     Effectuer une
                                                               annulation autorisée

  `GET`                   `/admin/reservations/:id/payments`   Consulter les paiements
                                                               associés

  `GET`                   `/admin/commissions`                 Consulter le suivi des
                                                               commissions
  ------------------------------------------------------------------------------------

Les routes de paiement et de webhook sont séparées. Toutes les routes
administratives appliquent une authentification et des autorisations
explicites.

## 12. Organisation du backend

Séparer les responsabilités :

-   **API :** routes, contrôleurs, validation des entrées,
    authentification et autorisations.
-   **Services métier :** création, disponibilité, calcul du prix,
    confirmation, annulation et commissions.
-   **Administration :** gestion des établissements, demandes, tarifs,
    disponibilités, paiements et rapports.
-   **Persistance :** modèles, transactions, contraintes d'intégrité et
    journalisation.

Les contrôleurs ne doivent pas contenir toute la logique métier. Les
règles centrales doivent être dans les services, réutilisables depuis
les interfaces client et administration.

## 13. Critères d'acceptation

-   [ ] Un client peut créer une réservation valide.
-   [ ] Le backend refuse les dates et données incohérentes.
-   [ ] Le prix est recalculé côté serveur et son détail est conservé.
-   [ ] Les disponibilités sont contrôlées avant confirmation.
-   [ ] Deux demandes concurrentes ne peuvent pas dépasser la capacité
    d'une ressource.
-   [ ] L'administrateur peut vérifier, confirmer, refuser et annuler
    une réservation.
-   [ ] Paiements et remboursements sont suivis indépendamment des
    statuts de réservation.
-   [ ] Les commissions suivent le contrat partenaire.
-   [ ] Notifications et actions administratives sont traçables.
-   [ ] Un client ne peut pas accéder aux réservations d'un autre.
-   [ ] Les erreurs de paiement et les tentatives répétées ne provoquent
    pas de doubles opérations.
-   [ ] Les règles de réservation et d'annulation sont présentées au
    client avant sa confirmation.

## 14. Décision pour la première version

Pour la première version de BestRev :

-   gestion centrale des établissements et tarifs par l'administration ;
-   confirmation manuelle par BestRev ;
-   règles tarifaires configurables par établissement et par catégorie ;
-   paiement configurable selon le partenaire ;
-   suivi distinct des réservations, paiements, remboursements et
    commissions ;
-   modèle de données prêt à accueillir un espace Owner plus tard.

Le but initial est de valider l'acquisition de clients, la qualité du
processus de réservation et la valeur apportée aux partenaires avant
d'automatiser davantage.

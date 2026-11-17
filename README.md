## Connexion Google et Facebook

Les routes OAuth sont séparées des routes d'authentification classiques :

- `POST /api/v1/auth/google` reçoit un `id_token` Google.
- `POST /api/v1/auth/facebook` reçoit un `access_token` Facebook.

Le frontend doit d'abord obtenir le jeton avec le SDK du fournisseur, puis
l'envoyer à l'API. Le backend vérifie le jeton auprès du fournisseur et renvoie
ses propres `access_token` et `refresh_token`.

Configurer ces variables d'environnement côté backend :

```env

FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
```

`GOOGLE_CLIENT_ID` doit correspondre à l'audience du jeton envoyé par le
frontend. Le secret Facebook reste uniquement côté serveur. Un compte existant
associé à un autre fournisseur n'est pas lié automatiquement; il faut d'abord
se connecter avec son mode actuel.

## Inscription et validation des propriétaires

- `POST /api/v1/auth/signup/proprietaire` crée un compte propriétaire et démarre
  la vérification d'adresse email par OTP. Un propriétaire ne peut pas se
  connecter ni soumettre son dossier avant d'avoir vérifié son adresse.
- Après vérification et connexion, `POST /api/v1/proprietaire/applications`
  reçoit en `multipart/form-data` les champs `registry_document` et
  `partnership_document`. Les formats PDF, JPG et PNG sont acceptés, jusqu'à
  10 Mo par fichier.
- `GET /api/v1/proprietaire/applications/me` retourne l'état du dernier dossier.
- L'administration consulte les dossiers avec
  `GET /api/v1/admin/owner-applications` et les approuve ou rejette avec
  `PATCH /api/v1/admin/owner-applications/{application_id}`. Un rejet nécessite
  un `rejection_reason`.

Les documents sont conservés comme fichiers privés; les liens de téléchargement
retournés dans les réponses expirent après dix minutes. Un dossier rejeté peut
être soumis à nouveau, et chaque soumission ainsi que sa décision restent
historisées.

## Gestion des établissements par les propriétaires

Après approbation de son dossier, le propriétaire utilise les routes
`/api/v1/owners/establishments` avec son jeton d'accès pour créer, consulter,
modifier, publier ou masquer ses établissements. Les photos, équipements
associés et conditions de paiement se gèrent également sous cette route.
Chaque opération est limitée aux établissements du propriétaire connecté.

Les propriétaires peuvent uniquement gérer et publier des hébergements. Les
restaurants et lieux de loisirs, ainsi que leurs données associées, relèvent
exclusivement de l'administration. L'administration gère les catégories, lieux et référentiels globaux
d'équipements et de conditions de paiement. Les propriétaires peuvent gérer
des sous-catégories uniquement sous une catégorie d'hébergement et associer les
équipements et conditions existants à leurs propres hébergements.
Les opérations de création et de modification sur
`/api/v1/admin/categories` utilisent `multipart/form-data`; le champ fichier
facultatif `img` accepte une image JPEG, PNG ou WebP de 5 Mo maximum. Les images
sont stockées sur Cloudinary et leurs URL sont renvoyées dans les réponses des
catégories. Un PATCH sans fichier conserve l'image existante; l'endpoint
`DELETE /api/v1/admin/categories/{category_id}/image` la supprime.

## Gestion administrative des restaurants et lieux de loisirs

L'administration gère ces établissements via
`/api/v1/admin/managed-establishments`. La création et la modification
réutilisent les schémas `EstablishmentCreate` et `EstablishmentPatch`; seules
les catégories de restaurant et de loisirs sont acceptées sur cette route.
Elle permet de lister, consulter, créer, modifier et supprimer ces
établissements. Un établissement créé par l'administration est publié
immédiatement; le changement de statut ne dispose pas d'une route dédiée.
Les routes d'administration existantes restent disponibles pour leurs photos,
équipements, réservations, paiements et données client.

L'accès aux adresses et coordonnées précises des restaurants et lieux de loisirs
est débloqué par un paiement unique de 500 FCFA par compte client. Les noms,
descriptions, tarifs, photos et villes restent publics. Avant l'achat, l'adresse
et les coordonnées GPS sont masquées dans les fiches, les favoris et les
réservations; les résultats protégés ne sont pas proposés par la recherche
géographique de proximité.

Le paiement se fait via KKiaPay et nécessite un compte client connecté :

- `POST /api/v1/payments/location-access/checkout` démarre le paiement avec le
  champ `payment_method` (`MOBILE_MONEY` ou `CARTE_BANCAIRE`) et un en-tête
  `Idempotency-Key`.
- `POST /api/v1/payments/location-access/confirm` vérifie la transaction auprès
  de KKiaPay; l'accès est accordé uniquement après confirmation serveur du
  montant exact de 500 XOF.
- `GET /api/v1/payments/location-access` indique si l'accès est actif.

Appliquer la migration avant de déployer ces routes avec
`alembic upgrade head`.

## Emails transactionnels

Les emails sont envoyés via Resend depuis `app/emails/email.py`; les services
appellent le dispatcher `app/services/notifi_dispatcher.py` après validation
des opérations. Les échecs d'envoi sont journalisés sans annuler l'action
métier. Les événements couverts comprennent :

- inscription, vérification de compte, renvoi d'OTP, demande de réinitialisation
  et changement de mot de passe;
- réception du dossier par le propriétaire, notification des administrateurs
  actifs lors d'une nouvelle soumission, approbation ou rejet d'un dossier
  propriétaire;
- création, confirmation, refus, annulation et fin d'une réservation;
- confirmation de paiement, activation de l'accès aux localisations et
  remboursement.

Les titres, statuts et informations principales sont mis en évidence en vert
dans les emails HTML.

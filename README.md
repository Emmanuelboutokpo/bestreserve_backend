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

Les catégories et sous-catégories restent gérées par l'administration. Celle-ci
gère également les référentiels globaux d'équipements et de conditions de
paiement; les propriétaires peuvent uniquement associer ces éléments à leurs
propres établissements.

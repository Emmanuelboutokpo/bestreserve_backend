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

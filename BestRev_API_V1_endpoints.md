

**### 6.2 Autorisation**



\`\`\`ts

CUSTOMER: ["booking:create", "booking:read-own", "favorite:create", "review:create", "profile:update-own"]

OWNER:    ["establishment:create", "establishment:update-own", "availability:update-own", "booking:read-own", "stats:read-own"]

ADMIN:    ["user:\*", "establishment:\*", "booking:\*", "validation:\*", "statistics:read", "settings:update"]

\`\`\`



**### 6.3 Sécurité des données**



\| Mesure | Détail |

\|---|---|

\| TLS | 1.3 obligatoire |

\| Chiffrement au repos | AES-256 |

\| Champs sensibles | Chiffrés (2FA secret) |

\| Backups | Chiffrés, 30j rétention |

\| Logs | Rotation quotidienne, 90j |



**### 6.4 Anti-fraude**



\| Mesure | Détail |

\|---|---|

\| Rate limiting | 100 req/min/IP |

\| Brute force | Blocage après 5 tentatives |

\| Bot detection | Cloudflare Turnstile |

\| 3D Secure | Paiements carte |



**### 6.5 RGPD**



\| Droit | Endpoint |

\|---|---|

\| Accès | \`GET /api/profile/export\` |

\| Rectification | \`PUT /api/profile\` |

\| Effacement | \`DELETE /api/profile\` |

\| Portabilité | \`GET /api/profile/export?format=json\` |

\| Opposition | \`PUT /api/profile/consents\` |



**---**



**## 7. Scalabilité**



**### 7.1 Base de données**



\- **\*\*UUID v7\*\*** (tri temporel, distribué)

\- **\*\*Index partiels\*\*** \`WHERE deleted_at IS NULL\`

\- **\*\*Index trigramme\*\*** pour recherche full-text

\- **\*\*Partitioning\*\*** sur \`activity_logs\`, \`payments\`, \`audit_logs\`

\- **\*\*Read replicas\*\*** pour lectures

\- **\*\*PgBouncer\*\*** pour connection pooling

\- **\*\*Redis\*\*** pour cache



**### 7.2 Application**



\- **\*\*Stateless\*\*** (JWT, pas de session serveur)

\- **\*\*Horizontal scaling\*\*** (containers)

\- **\*\*CDN\*\*** pour assets

\- **\*\*Pagination cursor-based\*\***

\- **\*\*Background jobs\*\*** (BullMQ)

\- **\*\*Circuit breaker\*\***



**### 7.3 Stockage**



\- **\*\*Images\*\*** : S3 / R2 + CDN

\- **\*\*Documents\*\*** : S3 chiffré

\- **\*\*Backups\*\*** : S3 Glacier

\- **\*\*Logs\*\*** : Elasticsearch



**### 7.4 Monitoring**



\- Prometheus + Grafana

\- Sentry

\- OpenTelemetry

\- UptimeRobot



**---**



**## 8. Endpoints API — Version 1

### 8.1 Principes V1

La version 1 de BestRev comprend deux rôles applicatifs :

- **CLIENT** : utilisateur final qui consulte les établissements, gère son profil, ses favoris, ses réservations et ses avis.
- **ADMIN** : administrateur de la plateforme qui supervise les utilisateurs, établissements, réservations, validations et paramètres.

> **OWNER n'est pas disponible en V1.**
>
> Les fonctionnalités de gestion directe d'établissement par un propriétaire sont donc exclues des endpoints V1. L'architecture pourra être étendue ultérieurement avec un rôle `OWNER`.

### 8.2 Niveaux d'accès

| Niveau | Signification |
|---|---|
| PUBLIC | Accessible sans authentification |
| AUTH | Utilisateur authentifié |
| CLIENT | Authentifié avec le rôle `CLIENT` |
| ADMIN | Authentifié avec le rôle `ADMIN` |

Les endpoints `CLIENT` utilisent l'identité du token JWT. Un client ne fournit pas son propre `user_id` pour accéder à ses données : le backend utilise `current_user.id`.

Pour les ressources administrées, l'autorisation est vérifiée côté serveur. Un utilisateur ne peut jamais accéder aux données d'un autre utilisateur simplement en modifiant un identifiant dans l'URL.

---

### 8.3 🔐 Authentification — PUBLIC / AUTH

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | PUBLIC | Créer un compte |
| POST | `/api/v1/auth/verify-otp` | PUBLIC | Vérifier l'email |
| POST | `/api/v1/auth/resend-otp` | PUBLIC | Renvoyer le code |
| POST | `/api/v1/auth/login` | PUBLIC | Se connecter |
| POST | `/api/v1/auth/google` | PUBLIC | Connexion Google |
| POST | `/api/v1/auth/facebook` | PUBLIC | Connexion Facebook |
| POST | `/api/v1/auth/forgot-password` | PUBLIC | Demander une réinitialisation |
| POST | `/api/v1/auth/reset-password` | PUBLIC | Réinitialiser le mot de passe |
| POST | `/api/v1/auth/logout` | AUTH | Se déconnecter |
| GET | `/api/v1/auth/refresh-token` | AUTH | Renouveler le token |
| GET | `/api/v1/auth/me` | AUTH | Obtenir l'utilisateur connecté |

---

# 8.4 👤 Utilisateur / CLIENT — Mon compte

Cette section concerne uniquement les actions que l'utilisateur authentifié peut effectuer sur **ses propres données**.

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| GET | `/api/v1/users/me` | CLIENT | Consulter son compte |
| PATCH | `/api/v1/users/me` | CLIENT | Modifier ses informations |
| DELETE | `/api/v1/users/me` | CLIENT | Demander/supprimer son compte |
| PUT | `/api/v1/users/me/password` | CLIENT | Modifier son mot de passe |
| POST | `/api/v1/users/me/avatar` | CLIENT | Ajouter/modifier son avatar |
| DELETE | `/api/v1/users/me/avatar` | CLIENT | Supprimer son avatar |
| GET | `/api/v1/users/me/notifications` | CLIENT | Consulter ses notifications |
| PATCH | `/api/v1/users/me/notifications/{id}/read` | CLIENT | Marquer une notification comme lue |
| PATCH | `/api/v1/users/me/notifications/read-all` | CLIENT | Tout marquer comme lu |
| GET | `/api/v1/users/me/export` | CLIENT | Exporter ses données |
| GET | `/api/v1/users/me/consents` | CLIENT | Consulter ses consentements |
| PUT | `/api/v1/users/me/consents` | CLIENT | Modifier ses consentements |

### Contrats et protections

- Toutes les routes utilisent l'identifiant `sub` du JWT; aucun `user_id` fourni par le client n'est accepté. Le compte doit être actif, non supprimé et avoir le même rôle/version de session que dans le token.
- `PATCH /users/me` accepte uniquement `firstName`, `lastName`, `phone`, `bio`, `country_code`, `city`, `language` et `currency`. L'email, le rôle, le statut et le fournisseur ne sont jamais modifiables par cette route.
- `PUT /users/me/password` exige `current_password`, `new_password` et `confirm_password`. Le nouveau mot de passe fait au moins 12 caractères et contient une majuscule, une minuscule, un chiffre et un caractère spécial. Le changement invalide les sessions précédentes.
- `DELETE /users/me` exige `{"confirmation":"DELETE","current_password":"..."}` pour un compte local, ou `{"confirmation":"DELETE","provider_token":"..."}` pour Google/Facebook. Les données de profil sont anonymisées; les favoris, notifications, consentements et journaux personnels sont supprimés.
- `POST /users/me/avatar` attend un fichier multipart `avatar`, limité à 5 Mo et vérifié comme JPEG, PNG ou WebP. L'image est stockée dans Cloudinary.
- Les notifications sont paginées avec `limit` (1 à 100, défaut 20) et `offset`. Une notification n'est lue/modifiée que si elle appartient à l'utilisateur authentifié.
- Les consentements modifiables sont `marketing_email`, `marketing_sms`, `analytics` et `personalization`; chaque valeur doit être booléenne.
- `GET /users/me/export` retourne les informations du compte, du profil, les consentements, réservations, paiements, favoris, avis, notifications et journaux liés à l'utilisateur.

### Règle d'autorisation

```text
CLIENT → uniquement ses propres données
```

Exemple :

```text
GET /api/v1/users/me
```

retourne l'utilisateur correspondant au JWT.

Il n'existe pas en V1 de :

```text
GET /api/v1/users/{id}
```

accessible au CLIENT.

---

# 8.5 👨‍💼 Administration des utilisateurs

Ces endpoints sont exclusivement réservés à `ADMIN`.

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| GET | `/api/v1/admin/users` | ADMIN | Lister les utilisateurs |
| GET | `/api/v1/admin/users/{id}` | ADMIN | Consulter un utilisateur |
| POST | `/api/v1/admin/users` | ADMIN | Créer un utilisateur |
| PATCH | `/api/v1/admin/users/{id}` | ADMIN | Modifier un utilisateur |
| DELETE | `/api/v1/admin/users/{id}` | ADMIN | Supprimer/désactiver un utilisateur |
| PATCH | `/api/v1/admin/users/{id}/role` | ADMIN | Modifier le rôle |
| PATCH | `/api/v1/admin/users/{id}/status` | ADMIN | Modifier le statut |
| GET | `/api/v1/admin/users/{id}/reservations` | ADMIN | Consulter les réservations d'un utilisateur |
| GET | `/api/v1/admin/users/{id}/favorites` | ADMIN | Consulter ses favoris |
| GET | `/api/v1/admin/users/{id}/activity` | ADMIN | Consulter son activité |
| GET | `/api/v1/admin/users/stats` | ADMIN | Statistiques utilisateurs |

> Les endpoints d'administration ne doivent jamais être confondus avec `/users/me`.

---

# 8.6 🌍 Géographie

## Public

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| GET | `/api/v1/locations` | PUBLIC | Lister/rechercher les lieux |
| GET | `/api/v1/locations/{id}` | PUBLIC | Détails d'un lieu |
| GET | `/api/v1/locations/{id}/children` | PUBLIC | Lieux enfants |
| GET | `/api/v1/locations/{id}/tree` | PUBLIC | Arbre géographique |
| GET | `/api/v1/locations/{id}/ancestors` | PUBLIC | Ancêtres |
| GET | `/api/v1/locations/search` | PUBLIC | Rechercher un lieu |
| GET | `/api/v1/locations/nearby` | PUBLIC | Lieux proches |
| GET | `/api/v1/locations/countries` | PUBLIC | Liste des pays |
| GET | `/api/v1/locations/countries/{code}/regions` | PUBLIC | Régions d'un pays |
| GET | `/api/v1/locations/countries/{code}/cities` | PUBLIC | Villes d'un pays |

## ADMIN

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| POST | `/api/v1/admin/locations` | ADMIN | Créer un lieu |
| PATCH | `/api/v1/admin/locations/{id}` | ADMIN | Modifier un lieu |
| DELETE | `/api/v1/admin/locations/{id}` | ADMIN | Supprimer un lieu |
| POST | `/api/v1/admin/locations/import` | ADMIN | Importer des lieux |
| GET | `/api/v1/admin/locations/export` | ADMIN | Exporter les lieux |

---

# 8.7 📂 Catégories et sous-catégories

## Public

| Méthode | Endpoint | Accès |
|---|---|---|
| GET | `/api/v1/categories` | PUBLIC |
| GET | `/api/v1/categories/{slug}` | PUBLIC |
| GET | `/api/v1/categories/{id}/subcategories` | PUBLIC |
| GET | `/api/v1/subcategories` | PUBLIC |
| GET | `/api/v1/subcategories/{slug}` | PUBLIC |

## ADMIN

| Méthode | Endpoint | Accès |
|---|---|---|
| POST | `/api/v1/admin/categories` | ADMIN |
| PATCH | `/api/v1/admin/categories/{id}` | ADMIN |
| DELETE | `/api/v1/admin/categories/{id}` | ADMIN |
| POST | `/api/v1/admin/categories/{id}/subcategories` | ADMIN |
| PATCH | `/api/v1/admin/subcategories/{id}` | ADMIN |
| DELETE | `/api/v1/admin/subcategories/{id}` | ADMIN |

---

# 8.8 🏢 Établissements

## Consultation — PUBLIC

En V1, les établissements sont gérés par l'administration. Les utilisateurs peuvent uniquement les consulter.

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| GET | `/api/v1/establishments` | PUBLIC | Liste des établissements |
| GET | `/api/v1/establishments/{slug}` | PUBLIC | Détails |
| GET | `/api/v1/establishments/{id}/photos` | PUBLIC | Photos |
| GET | `/api/v1/establishments/{id}/amenities` | PUBLIC | Équipements |
| GET | `/api/v1/establishments/{id}/reviews` | PUBLIC | Avis |
| GET | `/api/v1/establishments/{id}/availabilities` | PUBLIC | Disponibilités |
| GET | `/api/v1/establishments/{id}/similar` | PUBLIC | Établissements similaires |
| GET | `/api/v1/establishments/search` | PUBLIC | Recherche |

## ADMIN — Gestion

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| POST | `/api/v1/admin/establishments` | ADMIN | Créer |
| PATCH | `/api/v1/admin/establishments/{id}` | ADMIN | Modifier |
| DELETE | `/api/v1/admin/establishments/{id}` | ADMIN | Supprimer |
| PATCH | `/api/v1/admin/establishments/{id}/status` | ADMIN | Modifier le statut |
| PATCH | `/api/v1/admin/establishments/{id}/availability` | ADMIN | Modifier la disponibilité |

### Médias

| Méthode | Endpoint | Accès |
|---|---|---|
| POST | `/api/v1/admin/establishments/{id}/photos` | ADMIN |
| DELETE | `/api/v1/admin/photos/{id}` | ADMIN |
| PATCH | `/api/v1/admin/photos/{id}/cover` | ADMIN |
| POST | `/api/v1/admin/upload` | ADMIN |

---

# 8.9 🛠️ Équipements

## Public

```http
GET /api/v1/amenities
```

## ADMIN

```http
POST   /api/v1/admin/amenities
PATCH  /api/v1/admin/amenities/{id}
DELETE /api/v1/admin/amenities/{id}

POST   /api/v1/admin/establishments/{id}/amenities
DELETE /api/v1/admin/establishments/{id}/amenities/{amenityId}
```

---

# 8.10 📅 Disponibilités

En V1, la gestion des disponibilités appartient à l'administration.

## Public

```http
GET /api/v1/establishments/{id}/availabilities
```

## ADMIN

```http
POST   /api/v1/admin/establishments/{id}/availabilities
PUT    /api/v1/admin/availabilities/{id}
DELETE /api/v1/admin/availabilities/{id}
POST   /api/v1/admin/establishments/{id}/availabilities/bulk
```

---

# 8.11 ❤️ Favoris — CLIENT

Un client peut gérer uniquement ses propres favoris.

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| GET | `/api/v1/users/me/favorites` | CLIENT | Mes favoris |
| POST | `/api/v1/users/me/favorites/{establishmentId}` | CLIENT | Ajouter |
| DELETE | `/api/v1/users/me/favorites/{establishmentId}` | CLIENT | Retirer |
| DELETE | `/api/v1/users/me/favorites` | CLIENT | Supprimer tous les favoris |

---

# 8.12 📆 Réservations

## CLIENT

| Méthode | Endpoint | Accès | Action |
|---|---|---|---|
| GET | `/api/v1/users/me/reservations` | CLIENT | Mes réservations |
| GET | `/api/v1/users/me/reservations/{reference}` | CLIENT | Détails |
| POST | `/api/v1/reservations` | CLIENT | Créer une réservation |
| PUT | `/api/v1/users/me/reservations/{id}` | CLIENT | Modifier selon règles métier |
| POST | `/api/v1/users/me/reservations/{id}/cancel` | CLIENT | Annuler |
| GET | `/api/v1/reservations/check-availability` | PUBLIC | Vérifier disponibilité |
| POST | `/api/v1/reservations/quote` | PUBLIC | Obtenir un devis |

Le backend vérifie toujours :

```text
reservation.user_id == current_user.id
```

pour les opérations d'un client sur une réservation.

## ADMIN

| Méthode | Endpoint | Accès |
|---|---|---|
| GET | `/api/v1/admin/reservations` | ADMIN |
| GET | `/api/v1/admin/reservations/{id}` | ADMIN |
| PATCH | `/api/v1/admin/reservations/{id}/status` | ADMIN |
| GET | `/api/v1/admin/reservations/stats` | ADMIN |
| POST | `/api/v1/admin/reservations/{id}/refund` | ADMIN |

---

# 8.13 💳 Paiements

## CLIENT

| Méthode | Endpoint | Accès |
|---|---|---|
| POST | `/api/v1/payments/checkout` | CLIENT |
| POST | `/api/v1/payments/confirm` | CLIENT |
| GET | `/api/v1/payments/{reference}` | CLIENT |
| GET | `/api/v1/users/me/reservations/{id}/invoice` | CLIENT |

## Webhooks — PUBLIC mais authentifiés par le fournisseur

```http
POST /api/v1/payments/webhook/stripe
POST /api/v1/payments/webhook/fedapay
POST /api/v1/payments/webhook/kkpays
```

> Ces endpoints ne doivent pas utiliser une autorisation JWT classique. Ils doivent vérifier la signature du webhook du prestataire.

## ADMIN

```http
POST /api/v1/admin/payments/{id}/refund
```

---

# 8.14 ⭐ Avis

## Public

```http
GET /api/v1/establishments/{id}/reviews
```

## CLIENT

| Méthode | Endpoint | Action |
|---|---|---|
| POST | `/api/v1/establishments/{id}/reviews` | Créer un avis |
| PUT | `/api/v1/reviews/{id}` | Modifier son avis |
| DELETE | `/api/v1/reviews/{id}` | Supprimer son avis |
| POST | `/api/v1/reviews/{id}/report` | Signaler un avis |

Le backend vérifie notamment que le client a effectivement effectué la réservation concernée avant d'autoriser la création de l'avis.

## ADMIN

```http
GET    /api/v1/admin/reviews
DELETE /api/v1/admin/reviews/{id}
PATCH  /api/v1/admin/reviews/{id}/approve
```

---

# 8.15 🔔 Notifications

## CLIENT

```http
GET    /api/v1/users/me/notifications
GET    /api/v1/users/me/notifications/unread-count
PATCH  /api/v1/users/me/notifications/{id}/read
PATCH  /api/v1/users/me/notifications/read-all
DELETE /api/v1/users/me/notifications/{id}
POST   /api/v1/users/me/notifications/subscribe
```

## ADMIN

```http
GET  /api/v1/admin/notifications
POST /api/v1/admin/notifications
```

---

# 8.16 ✅ Validations

En V1, puisque les établissements sont administrés par BestRev, les validations sont entièrement du côté ADMIN.

```http
GET   /api/v1/admin/validations
GET   /api/v1/admin/validations/{id}
PATCH /api/v1/admin/validations/{id}/approve
PATCH /api/v1/admin/validations/{id}/reject
PATCH /api/v1/admin/validations/{id}/revision
GET   /api/v1/admin/validations/stats
GET   /api/v1/admin/validations/{id}/documents
POST  /api/v1/admin/validations/{id}/documents
DELETE /api/v1/admin/documents/{id}
GET   /api/v1/admin/validations/export
```

---

# 8.17 📊 Statistiques — ADMIN

```http
GET /api/v1/admin/stats/overview
GET /api/v1/admin/stats/users
GET /api/v1/admin/stats/establishments
GET /api/v1/admin/stats/reservations
GET /api/v1/admin/stats/revenue
GET /api/v1/admin/stats/top-destinations
GET /api/v1/admin/stats/top-establishments
GET /api/v1/admin/stats/recent-activities
GET /api/v1/admin/stats/charts/reservations
GET /api/v1/admin/stats/charts/categories
GET /api/v1/admin/stats/charts/revenue
GET /api/v1/admin/stats/export
```

---

# 8.18 ⚙️ Paramètres — ADMIN

```http
GET  /api/v1/admin/settings
GET  /api/v1/admin/settings/{key}
PUT  /api/v1/admin/settings
GET  /api/v1/admin/settings/services/status
POST /api/v1/admin/settings/maintenance
```

---

# 8.19 🔒 Sécurité / Audit — ADMIN

```http
GET    /api/v1/admin/audit-logs
GET    /api/v1/admin/audit-logs/{id}
GET    /api/v1/admin/security/sessions
DELETE /api/v1/admin/security/sessions/{id}
GET    /api/v1/admin/security/rate-limits
POST   /api/v1/admin/security/unblock
GET    /api/v1/admin/security/suspicious
```

---

# 8.20 🔍 Recherche

Les recherches publiques sont accessibles sans compte.

```http
GET /api/v1/search
GET /api/v1/search/suggestions
GET /api/v1/search/nearby
GET /api/v1/search/popular
```

---

# 8.21 🌐 Endpoints publics

```http
GET  /api/v1/public/sitemap
GET  /api/v1/public/robots
POST /api/v1/public/contact
POST /api/v1/public/newsletter
GET  /api/v1/public/faq
```

---

# 8.22 🔧 Système

```http
GET /api/v1/health
GET /api/v1/version
GET /api/v1/metrics
```

`/health` et `/version` peuvent être publics. L'accès à `/metrics` devra être protégé en production.

---

# 8.23 Matrice finale des rôles

| Module | PUBLIC | CLIENT | ADMIN |
|---|:---:|:---:|:---:|
| Auth | ✅ | ✅ | ✅ |
| Mon compte | ❌ | ✅ | ✅* |
| Géographie lecture | ✅ | ✅ | ✅ |
| Géographie gestion | ❌ | ❌ | ✅ |
| Catégories lecture | ✅ | ✅ | ✅ |
| Catégories gestion | ❌ | ❌ | ✅ |
| Établissements lecture | ✅ | ✅ | ✅ |
| Établissements gestion | ❌ | ❌ | ✅ |
| Amenities lecture | ✅ | ✅ | ✅ |
| Amenities gestion | ❌ | ❌ | ✅ |
| Disponibilités lecture | ✅ | ✅ | ✅ |
| Disponibilités gestion | ❌ | ❌ | ✅ |
| Favoris | ❌ | ✅ | ❌ |
| Réservations création | ❌ | ✅ | ❌ |
| Mes réservations | ❌ | ✅ | ❌ |
| Toutes les réservations | ❌ | ❌ | ✅ |
| Paiements | ❌ | ✅ | ✅* |
| Avis création | ❌ | ✅ | ❌ |
| Avis modération | ❌ | ❌ | ✅ |
| Notifications personnelles | ❌ | ✅ | ❌ |
| Validations | ❌ | ❌ | ✅ |
| Statistiques | ❌ | ❌ | ✅ |
| Paramètres plateforme | ❌ | ❌ | ✅ |
| Audit / sécurité | ❌ | ❌ | ✅ |

`*` uniquement pour les opérations administratives prévues.

---

# 8.24 Ce qui est explicitement exclu de V1

Les endpoints suivants ne font **pas partie de la V1** :

```text
/api/v1/owner/...
```

notamment :

```text
/api/v1/owner/establishments
/api/v1/owner/reservations
/api/v1/owner/statistics
/api/v1/owner/revenue
```

Il n'y a donc aucune permission :

```text
OWNER
establishment:create
establishment:update-own
availability:update-own
stats:read-own
```

dans la V1.

Le modèle de données peut néanmoins conserver les éléments nécessaires à une future évolution vers `OWNER`, sans exposer les endpoints correspondants.

---

## 8.25 Architecture d'autorisation

La logique d'autorisation V1 doit être organisée ainsi :

```text
JWT
 │
 ▼
get_current_user()
 │
 ├── PUBLIC
 │
 ├── CLIENT
 │     └── accès à ses propres ressources
 │
 └── ADMIN
       └── accès aux ressources administratives
```

Et pour chaque endpoint sensible :

```text
Authentification
      ↓
Vérification du rôle
      ↓
Vérification de propriété de la ressource
      ↓
Service métier
      ↓
Repository
      ↓
Database
```

Exemple pour une réservation :

```text
CLIENT
  ↓
GET /api/v1/users/me/reservations/BR-123
  ↓
JWT → user_id = 8f...
  ↓
reservation.user_id == 8f...
  ↓
✅ accès
```

Alors qu'un autre client :

```text
JWT → user_id = 91...
  ↓
reservation.user_id == 8f...
  ↓
❌ 403 Forbidden
```

Pour ADMIN :

```text
JWT
 ↓
role == ADMIN
 ↓
GET /api/v1/admin/reservations
 ↓
✅ accès global
```




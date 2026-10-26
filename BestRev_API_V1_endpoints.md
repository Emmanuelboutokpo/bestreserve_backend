# BestRev / LandReservation — MCD final fusionné

> Version 3.0 — Fusion de :
> - Ton document BestRev (métier riche : ratings, KYC, transactions)
> - Notre version (sécurité : rate limits, soft delete, jobs)
> - Table `locations` générique (scalabilité mondiale)

---

## 📑 SOMMAIRE

1. [Principes de conception](#1-principes)
2. [Vue d'ensemble](#2-vue-densemble)
3. [Liste des tables](#3-liste-des-tables)
4. [Détail des tables](#4-détail)
5. [Relations & cardinalités](#5-relations)
6. [Enums](#6-enums)
7. [Sécurité](#7-sécurité)
8. [Scalabilité](#8-scalabilité)
9. [Endpoints API](#9-endpoints)

---

## 1. Principes de conception

| Principe | Application |
|---|---|
| **Scalabilité mondiale** | `locations` générique (pays → quartiers) |
| **Sécurité par défaut** | Soft delete, rate limits, 2FA, anti-bruteforce |
| **Traçabilité** | `created_at`, `updated_at`, `deleted_at` partout |
| **Multi-devises** | `currency` ISO 4217 (XOF, EUR, USD) |
| **Multi-langues** | `language` ISO 639-1 (fr, en) |
| **Idempotence** | UUID v7 (tri temporel, distribué) |
| **Audit** | `activity_logs` + `validation_decisions` |
| **RGPD** | Soft delete + anonymisation |

---

## 2. Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│  1. IDENTITÉ & ACTEURS                                      │
│     users, profile, favorites,        
│     recent_views, notifications                             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  2. RÉFÉRENTIELS & TERRITOIRE                               │
│     locations, categories, subcategories,                   │
│     amenities, payment_conditions                           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  3. ÉTABLISSEMENTS & OFFRE                                  │
│     establishments, photos,                         │
│     establishment_amenities, establishment_payment_conditions│
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  4. CONFORMITÉ & KYC                                        │
│     validation_documents            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  5. RÉSERVATION & EXPLOITATION                              │
│     reservations, transactions, reviews     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  6. ADMIN & SYSTÈME                                         │
│     platform_settings, contact_messages, activity_logs,     │
│     rate_limits, jobs                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Liste des tables (32 tables)

### 🌍 Référentiels (1 table)
| # | Table |
|---|---|
| 1 | `locations` |

### 🏢 Offre (5 tables)
| # | Table |
|---|---|
| 2 | `categories` |
| 3 | `subcategories` |
| 4 | `amenities` |
| 5 | `payment_conditions` |
| 6 | `establishments` |

### 🖼️ Médias (2 tables)
| # | Table |
|---|---|
| 7 | `photos` |

### 🔗 Liaisons N-N (2 tables)
| # | Table |
|---|---|
| 9 | `establishment_amenities` |
| 10 | `establishment_payment_conditions` |

### ✅ Conformité KYC (2 tables)
| # | Table |
|---|---|
| 11 | `validation_documents` |
| 12 | `validation_decisions` |


### 👥 Utilisateurs (6 tables)
| # | Table |
|---|---|
| 14 | `users` |
| 16 | `profile` |
| 17 | `favorites` |
| 18 | `recent_views` |
| 19 | `notifications` |

### 📆 Réservations (3 tables)
| # | Table |
|---|---|
| 20 | `reservations` |
| 21 | `transactions` |
| 22 | `reviews` |

### 📊 Admin & Système (10 tables)
| # | Table |
|---|---|
| 23 | `platform_settings` |
| 24 | `contact_messages` |
| 25 | `faq` |
| 26 | `activity_logs` |
| 27 | `rate_limits` |
| 28 | `jobs` |
| 29 | `api_keys` |
| 30 | `webhooks` |
| 31 | `consents` |
| 32 | `service_statuses` |

**Total : 32 tables**

---

## 4. Détail des tables

### 🌍 4.1 `locations` (table générique mondiale)

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(150) | NOT NULL |
| slug | VARCHAR(180) | UNIQUE |
| type | ENUM | COUNTRY \| REGION \| CITY \| DISTRICT \| NEIGHBORHOOD |
| parent_id | UUID | FK → locations.id, NULL si COUNTRY |
| country_code | VARCHAR(3) | NOT NULL (ISO 3166-1 alpha-3) |
| latitude | DECIMAL(10,6) | |
| longitude | DECIMAL(10,6) | |
| timezone | VARCHAR(50) | |
| population | BIGINT | |
| metadata | JSONB | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | NULL |

**Index** :
```sql
CREATE INDEX idx_locations_type ON locations(type);
CREATE INDEX idx_locations_parent ON locations(parent_id);
CREATE INDEX idx_locations_country ON locations(country_code);
CREATE INDEX idx_locations_active ON locations(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_locations_name_trgm ON locations USING gin(name gin_trgm_ops);
CREATE INDEX idx_locations_coords ON locations(latitude, longitude);
```

---

### 🏢 4.2 `categories`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(50) | NOT NULL |
| slug | VARCHAR(50) | UNIQUE |
| icon | VARCHAR(50) | |
| has_subcategories | BOOLEAN | DEFAULT TRUE |
| description | TEXT | |
| display_order | INT | DEFAULT 0 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | NULL |

---

### 🏢 4.3 `subcategories`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| category_id | UUID | FK → categories.id |
| name | VARCHAR(50) | NOT NULL |
| slug | VARCHAR(50) | UNIQUE |
| icon | VARCHAR(50) | |
| display_order | INT | DEFAULT 0 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | NULL |

---

### 🏢 4.4 `amenities`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(100) | NOT NULL |
| slug | VARCHAR(100) | UNIQUE |
| icon | VARCHAR(50) | |
| category | VARCHAR(50) | |
| created_at | TIMESTAMP | |

---

### 🏢 4.5 `payment_conditions`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(100) | NOT NULL |
| description | TEXT | |
| created_at | TIMESTAMP | |

---

### 🏢 4.6 `establishments`

| Champ | Type | Contrainte | Description |
|---|---|---|---|
| id | UUID | PK | |
| owner_id | UUID | FK → users.id | Propriétaire |
| tenant_id | UUID | FK → users.id, NULL | Locataire longue durée |
| category_id | UUID | FK → categories.id | |
| subcategory_id | UUID | FK → subcategories.id | |
| location_id | UUID | FK → locations.id | ⚠️ 1 seule FK géo |
| name | VARCHAR(200) | NOT NULL | |
| slug | VARCHAR(200) | UNIQUE | |
| description | TEXT | | |
| address | VARCHAR(255) | | |
| latitude | DECIMAL(10,6) | | |
| longitude | DECIMAL(10,6) | | |
| status | ENUM | | PUBLIE, EN_ATTENTE, REJETE, SUSPENDU |
| availability_status | ENUM | | AVAILABLE, RENTED, UNAVAILABLE |
| price_per_night | DECIMAL(12,2) | | |
| price_per_month | DECIMAL(12,2) | | |
| price_unit | ENUM | | nuit, personne, mois |
| currency | VARCHAR(3) | DEFAULT 'XOF' | |
| bedrooms | INT | | |
| bathrooms | INT | | |
| beds | INT | | |
| bed_type | VARCHAR(50) | | |
| area | DECIMAL(8,2) | | |
| max_guests | INT | | |
| rating | DECIMAL(3,2) | | |
| review_count | INT | DEFAULT 0 | |
| ratings_accuracy | DECIMAL(3,2) | | |
| ratings_cleanliness | DECIMAL(3,2) | | |
| ratings_checkin | DECIMAL(3,2) | | |
| ratings_communication | DECIMAL(3,2) | | |
| ratings_location | DECIMAL(3,2) | | |
| ratings_value | DECIMAL(3,2) | | |
| cuisine_type | VARCHAR(100) | | |
| opening_hours | VARCHAR(100) | | |
| phone | VARCHAR(30) | | |
| website | VARCHAR(255) | | |
| published_at | TIMESTAMP | | |
| created_by | UUID | FK → users.id | |
| updated_by | UUID | FK → users.id | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |
| deleted_at | TIMESTAMP | NULL | |

**Index** :
```sql
CREATE INDEX idx_establishments_owner ON establishments(owner_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_establishments_location ON establishments(location_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_establishments_category ON establishments(category_id, subcategory_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_establishments_status ON establishments(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_establishments_price ON establishments(price_per_night) WHERE deleted_at IS NULL;
CREATE INDEX idx_establishments_slug ON establishments(slug);
CREATE INDEX idx_establishments_name_trgm ON establishments USING gin(name gin_trgm_ops);
CREATE INDEX idx_establishments_coords ON establishments(latitude, longitude);
```

---

### 🖼️ 4.7 `photos`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| establishment_id | UUID | FK → establishments.id |
| url | VARCHAR(500) | NOT NULL |
| storage_key | VARCHAR(500) | |
| width_ratio | INT | |
| height_ratio | INT | |
| is_cover | BOOLEAN | DEFAULT FALSE |
| display_order | INT | DEFAULT 0 |
| created_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | NULL |

---

### 🖼️ 4.8 `videos`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| establishment_id | UUID | FK → establishments.id |
| title | VARCHAR(200) | |
| url | VARCHAR(500) | |
| thumbnail_url | VARCHAR(500) | |
| duration | VARCHAR(10) | |
| display_order | INT | DEFAULT 0 |
| created_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | NULL |

---

### 🔗 4.9 `establishment_amenities`

| Champ | Type | Contrainte |
|---|---|---|
| establishment_id | UUID | FK → establishments.id |
| amenity_id | UUID | FK → amenities.id |
| PK | (establishment_id, amenity_id) | |

---

### 🔗 4.10 `establishment_payment_conditions`

| Champ | Type | Contrainte |
|---|---|---|
| establishment_id | UUID | FK → establishments.id |
| payment_condition_id | UUID | FK → payment_conditions.id |
| PK | (establishment_id, payment_condition_id) | |

---

### ✅ 4.11 `validation_documents`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| establishment_id | UUID | FK → establishments.id |
| owner_id | UUID | FK → users.id |
| name | VARCHAR(200) | |
| type | ENUM | registre, piece_identite, attestation_fiscale, certificat_hygiene, titre_propriete, autre |
| file_name | VARCHAR(200) | |
| file_size | VARCHAR(20) | |
| file_url | VARCHAR(500) | |
| mime_type | VARCHAR(100) | |
| status | ENUM | EN_ATTENTE, VALIDE, REJETE |
| submitted_at | TIMESTAMP | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### ✅ 4.12 `validation_decisions`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| establishment_id | UUID | FK → establishments.id |
| admin_id | UUID | FK → users.id |
| previous_status | ENUM | EN_ATTENTE, EN_REVISION, VALIDE, REJETE |
| new_status | ENUM | EN_ATTENTE, EN_REVISION, VALIDE, REJETE |
| comment | TEXT | |
| decided_at | TIMESTAMP | |

---

### 📅 4.13 `availabilities`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| establishment_id | UUID | FK → establishments.id |
| date | DATE | NOT NULL |
| is_blocked | BOOLEAN | DEFAULT FALSE |
| price_override | DECIMAL(12,2) | NULL |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Index** :
```sql
CREATE UNIQUE INDEX idx_availabilities_est_date ON availabilities(establishment_id, date);
```

---

### 👥 4.14 `users`

| Champ | Type | Contrainte | Description |
|---|---|---|---|
| id | UUID | PK | |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(100) | NOT NULL | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | |
| email_verified_at | TIMESTAMP | NULL | |
| phone | VARCHAR(30) | UNIQUE | |
| phone_verified_at | TIMESTAMP | NULL | |
| password_hash | VARCHAR(255) | | Argon2id |
| password_changed_at | TIMESTAMP | NULL | |
| failed_login_attempts | INT | DEFAULT 0 | |
| locked_until | TIMESTAMP | NULL | |
| role | ENUM | NOT NULL | CLIENT, PROPRIETAIRE, ADMIN |
| status | ENUM | DEFAULT 'ACTIF' | ACTIF, INACTIF, EN_ATTENTE, SUSPENDU |
| provider | ENUM | DEFAULT 'LOCAL' | LOCAL, GOOGLE, FACEBOOK, PHONE |
| provider_id | VARCHAR(255) | NULL | |
| avatar_url | VARCHAR(500) | NULL | |
| country_code | VARCHAR(3) | NULL | |
| two_factor_enabled | BOOLEAN | DEFAULT FALSE | |
| two_factor_secret | VARCHAR(255) | NULL | Chiffré |
| registration_date | TIMESTAMP | DEFAULT NOW() | |
| last_login_at | TIMESTAMP | NULL | |
| created_by | UUID | FK → users.id | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |
| deleted_at | TIMESTAMP | NULL | |

**Index** :
```sql
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_phone ON users(phone) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_role ON users(role) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_status ON users(status) WHERE deleted_at IS NULL;
```

---

### 👥 4.15 `user_preferences`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id, UNIQUE |
| language | VARCHAR(5) | DEFAULT 'fr' |
| currency | VARCHAR(3) | DEFAULT 'XOF' |
| email_notifications | BOOLEAN | DEFAULT TRUE |
| push_notifications | BOOLEAN | DEFAULT TRUE |
| marketing_opt_in | BOOLEAN | DEFAULT FALSE |
| theme | VARCHAR(10) | DEFAULT 'light' |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### 👥 4.16 `sessions`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| token_hash | VARCHAR(255) | UNIQUE |
| refresh_token_hash | VARCHAR(255) | |
| ip_address | INET | |
| user_agent | TEXT | |
| device_fingerprint | VARCHAR(255) | |
| expires_at | TIMESTAMP | NOT NULL |
| revoked_at | TIMESTAMP | NULL |
| created_at | TIMESTAMP | |

---

### 👥 4.17 `favorites`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| establishment_id | UUID | FK → establishments.id |
| note | TEXT | NULL |
| created_at | TIMESTAMP | |

**Index** :
```sql
CREATE UNIQUE INDEX idx_favorites_user_est ON favorites(user_id, establishment_id);
```

---

### 👥 4.18 `recent_views`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| establishment_id | UUID | FK → establishments.id |
| viewed_at | TIMESTAMP | DEFAULT NOW() |

**Index** :
```sql
CREATE INDEX idx_recent_views_user ON recent_views(user_id, viewed_at DESC);
CREATE UNIQUE INDEX idx_recent_views_user_est ON recent_views(user_id, establishment_id);
```

---

### 👥 4.19 `notifications`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| type | ENUM | booking, payment, reminder, review, validation, system |
| title | VARCHAR(200) | |
| description | TEXT | |
| link_url | VARCHAR(500) | NULL |
| is_read | BOOLEAN | DEFAULT FALSE |
| read_at | TIMESTAMP | NULL |
| created_at | TIMESTAMP | |

**Index** :
```sql
CREATE INDEX idx_notifications_user ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications(user_id) WHERE is_read = FALSE;
```

---

### 📆 4.20 `reservations`

| Champ | Type | Contrainte | Description |
|---|---|---|---|
| id | UUID | PK | |
| reference | VARCHAR(30) | UNIQUE | #BR-2026-0012 |
| user_id | UUID | FK → users.id | Client |
| establishment_id | UUID | FK → establishments.id | |
| category | ENUM | HEBERGEMENT, RESTAURANT, LOISIR | |
| start_date | DATE | | |
| end_date | DATE | | |
| nights | INT | | |
| adults | INT | | |
| children | INT | | |
| room_or_unit | VARCHAR(100) | | |
| options | JSONB | | |
| special_requests | TEXT | | |
| client_first_name | VARCHAR(100) | Dénormalisé | |
| client_last_name | VARCHAR(100) | Dénormalisé | |
| client_email | VARCHAR(255) | Dénormalisé | |
| client_phone | VARCHAR(30) | Dénormalisé | |
| client_country | VARCHAR(3) | Dénormalisé | |
| subtotal_amount | DECIMAL(12,2) | | |
| service_fee | DECIMAL(12,2) | DEFAULT 0 | |
| total_amount | DECIMAL(12,2) | | |
| currency | VARCHAR(3) | | |
| payment_method | ENUM | CARTE_BANCAIRE, MOBILE_MONEY, VIREMENT | |
| payment_status | ENUM | EN_ATTENTE, PAYE, REMBOURSE, ECHOUE | |
| payment_provider | VARCHAR(30) | fedapay, kkiapay, stripe, manual | |
| payment_ref | VARCHAR(100) | NULL | |
| paid_at | TIMESTAMP | NULL | |
| status | ENUM | EN_ATTENTE, CONFIRMEE, EN_COURS, TERMINEE, ANNULEE | |
| cancellation_reason | VARCHAR(100) | NULL | |
| cancelled_at | TIMESTAMP | NULL | |
| created_at | TIMESTAMP | | |
| updated_at | TIMESTAMP | | |
| deleted_at | TIMESTAMP | NULL | |

**Index** :
```sql
CREATE INDEX idx_reservations_user ON reservations(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reservations_est ON reservations(establishment_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reservations_status ON reservations(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_reservations_dates ON reservations(start_date, end_date);
CREATE INDEX idx_reservations_reference ON reservations(reference);
```

---

### 📆 4.21 `transactions`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| reservation_id | UUID | FK → reservations.id |
| user_id | UUID | FK → users.id |
| transaction_ref | VARCHAR(100) | UNIQUE |
| provider | VARCHAR(30) | fedapay, kkiapay, stripe |
| provider_transaction_id | VARCHAR(255) | UNIQUE |
| amount | DECIMAL(12,2) | |
| currency | VARCHAR(3) | |
| status | ENUM | EN_ATTENTE, PAYE, REMBOURSE, ECHOUE |
| type | ENUM | PAYMENT, REFUND |
| payment_channel | VARCHAR(50) | |
| metadata | JSONB | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### 📆 4.22 `reviews`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| establishment_id | UUID | FK → establishments.id |
| user_id | UUID | FK → users.id |
| reservation_id | UUID | FK → reservations.id, NULL |
| rating | INT | 1-5 |
| accuracy | INT | 1-5 |
| cleanliness | INT | 1-5 |
| checkin | INT | 1-5 |
| communication | INT | 1-5 |
| location | INT | 1-5 |
| value | INT | 1-5 |
| comment | TEXT | |
| is_approved | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | NULL |

**Index** :
```sql
CREATE INDEX idx_reviews_est ON reviews(establishment_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reviews_user ON reviews(user_id) WHERE deleted_at IS NULL;
```

---

### 📊 4.23 `platform_settings`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| section | VARCHAR(50) | general, payment, notifications, security |
| key | VARCHAR(100) | UNIQUE |
| value | TEXT | |
| type | VARCHAR(20) | string, number, boolean, json |
| description | TEXT | |
| updated_by | UUID | FK → users.id |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**Index** :
```sql
CREATE UNIQUE INDEX idx_settings_key ON platform_settings(key);
CREATE INDEX idx_settings_section ON platform_settings(section);
```

---

### 📊 4.24 `contact_messages`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| first_name | VARCHAR(100) | |
| last_name | VARCHAR(100) | |
| email | VARCHAR(255) | |
| phone | VARCHAR(30) | |
| subject | ENUM | general, partenariat, support, presse, autre |
| message | TEXT | |
| status | ENUM | NON_LU, EN_COURS, TRAITE |
| reply_notes | TEXT | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### 📊 4.25 `faq`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| question | TEXT | |
| answer | TEXT | |
| category | VARCHAR(50) | |
| display_order | INT | DEFAULT 0 |
| is_published | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

### 📊 4.26 `activity_logs`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NULL |
| action | VARCHAR(100) | |
| entity_type | VARCHAR(50) | |
| entity_id | UUID | |
| description | TEXT | |
| ip_address | INET | |
| user_agent | TEXT | |
| created_at | TIMESTAMP | |

**Index** :
```sql
CREATE INDEX idx_activity_logs_user ON activity_logs(user_id, created_at DESC);
CREATE INDEX idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
```

---

### 📊 4.27 `rate_limits`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| key | VARCHAR(255) | UNIQUE |
| count | INT | DEFAULT 0 |
| window_start | TIMESTAMP | |
| blocked_until | TIMESTAMP | NULL |

---

### 📊 4.28 `jobs`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| type | VARCHAR(50) | send_email, export_csv, resize_image |
| payload | JSONB | |
| status | ENUM | PENDING, RUNNING, DONE, FAILED |
| attempts | INT | DEFAULT 0 |
| max_attempts | INT | DEFAULT 3 |
| scheduled_at | TIMESTAMP | |
| started_at | TIMESTAMP | NULL |
| completed_at | TIMESTAMP | NULL |
| error | TEXT | NULL |
| created_at | TIMESTAMP | |

**Index** :
```sql
CREATE INDEX idx_jobs_status ON jobs(status, scheduled_at) WHERE status = 'PENDING';
```

---

### 📊 4.29 `api_keys`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| name | VARCHAR(100) | |
| key_hash | VARCHAR(255) | UNIQUE |
| scopes | TEXT[] | |
| last_used_at | TIMESTAMP | NULL |
| expires_at | TIMESTAMP | NULL |
| revoked_at | TIMESTAMP | NULL |
| created_at | TIMESTAMP | |

---

### 📊 4.30 `webhooks`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| url | VARCHAR(500) | |
| events | TEXT[] | |
| secret_hash | VARCHAR(255) | |
| is_active | BOOLEAN | DEFAULT TRUE |
| last_triggered_at | TIMESTAMP | NULL |
| created_at | TIMESTAMP | |

---

### 📊 4.31 `consents`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| type | VARCHAR(50) | terms, privacy, marketing |
| granted | BOOLEAN | |
| ip_address | INET | |
| user_agent | TEXT | |
| granted_at | TIMESTAMP | |
| revoked_at | TIMESTAMP | NULL |

---

### 📊 4.32 `service_statuses`

| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(100) | |
| status | ENUM | OPERATIONAL, DEGRADED, DOWN |
| last_check | TIMESTAMP | |
| details | JSONB | |

---

## 5. Relations & cardinalités

| Relation | Type |
|---|---|
| `locations.parent_id → locations.id` | Auto-référence |
| `locations → establishments` | 1-N |
| `categories → subcategories` | 1-N |
| `categories → establishments` | 1-N |
| `subcategories → establishments` | 1-N |
| `users (OWNER) → establishments` | 1-N |
| `users (TENANT) → establishments` | 1-N |
| `establishments → photos` | 1-N |
| `establishments → videos` | 1-N |
| `establishments ↔ amenities` | N-N |
| `establishments ↔ payment_conditions` | N-N |
| `establishments → validation_documents` | 1-N |
| `establishments → validation_decisions` | 1-N |
| `establishments → availabilities` | 1-N |
| `users → user_preferences` | 1-1 |
| `users → sessions` | 1-N |
| `users → favorites` | 1-N |
| `users → recent_views` | 1-N |
| `users → notifications` | 1-N |
| `users → api_keys` | 1-N |
| `users → webhooks` | 1-N |
| `users → consents` | 1-N |
| `users (CLIENT) → reservations` | 1-N |
| `establishments → reservations` | 1-N |
| `reservations → transactions` | 1-N |
| `reservations → reviews` | 1-1 |
| `establishments → reviews` | 1-N |
| `users (ADMIN) → validation_decisions` | 1-N |
| `users → activity_logs` | 1-N |

---

## 6. Enums

```ts
UserRole                 : CLIENT | PROPRIETAIRE | ADMIN
UserStatus               : ACTIF | INACTIF | EN_ATTENTE | SUSPENDU
UserProvider             : LOCAL | GOOGLE | FACEBOOK | PHONE
LocationType             : COUNTRY | REGION | CITY | DISTRICT | NEIGHBORHOOD
EstablishmentStatus      : PUBLIE | EN_ATTENTE | REJETE | SUSPENDU
AvailabilityStatus       : AVAILABLE | RENTED | UNAVAILABLE
PriceUnit                : nuit | personne | mois
ValidationStatus         : EN_ATTENTE | EN_REVISION | VALIDE | REJETE
DocumentType             : registre | piece_identite | attestation_fiscale | certificat_hygiene | titre_propriete | autre
ReservationStatus        : EN_ATTENTE | CONFIRMEE | EN_COURS | TERMINEE | ANNULEE
PaymentMethod            : CARTE_BANCAIRE | MOBILE_MONEY | VIREMENT
PaymentStatus            : EN_ATTENTE | PAYE | REMBOURSE | ECHOUE
PaymentProvider          : fedapay | kkiapay | stripe | manual
TransactionType          : PAYMENT | REFUND
NotificationType         : booking | payment | reminder | review | validation | system
ContactSubject           : general | partenariat | support | presse | autre
ContactStatus            : NON_LU | EN_COURS | TRAITE
JobStatus                : PENDING | RUNNING | DONE | FAILED
ServiceStatus            : OPERATIONAL | DEGRADED | DOWN
```

---

## 7. Sécurité

### 7.1 Authentification
| Mesure | Détail |
|---|---|
| Hash | Argon2id |
| JWT | Access 15 min + Refresh 7 jours |
| Tokens | Hashés en DB (SHA-256) |
| 2FA | TOTP |
| OAuth | Google, Facebook |
| OTP | Twilio |
| Anti-bruteforce | `failed_login_attempts` + `locked_until` |

### 7.2 Autorisation
| Rôle | Permissions |
|---|---|
| CLIENT | booking:create, favorite:create, review:create, profile:update-own |
| PROPRIETAIRE | establishment:create, establishment:update-own, availability:update-own, stats:read-own |
| ADMIN | `*` (toutes) |

### 7.3 Protection
| Mesure | Détail |
|---|---|
| Rate limiting | 100 req/min/IP |
| TLS | 1.3 obligatoire |
| Chiffrement | AES-256 au repos |
| Soft delete | `deleted_at` partout |
| Audit | `activity_logs` |
| RGPD | `consents` + export + anonymisation |

---

## 8. Scalabilité

| Aspect | Solution |
|---|---|
| **IDs** | UUID v7 (tri temporel) |
| **Index** | Partiels (`WHERE deleted_at IS NULL`) + trigramme |
| **Cache** | Redis |
| **Files** | S3 / R2 + CDN |
| **Jobs** | BullMQ / Redis |
| **DB** | PostgreSQL + PostGIS |
| **Replicas** | Read replicas |
| **Monitoring** | Prometheus + Sentry |

---

## 9. Endpoints API

Voir le fichier `endpoints.md` pour la liste complète (~200 endpoints).

**Groupes principaux** :
- `/api/v1/auth` — Authentification (11)
- `/api/v1/users` — Profil & préférences (8)
- `/api/v1/favorites` — Favoris (6)
- `/api/v1/recent-views` — Historique (3)
- `/api/v1/notifications` — Notifications (6)
- `/api/v1/geo` — Géographie (7)
- `/api/v1/taxonomies` — Catégories (4)
- `/api/v1/amenities` — Équipements (2)
- `/api/v1/payment-conditions` — Conditions (1)
- `/api/v1/establishments` — Établissements (10)
- `/api/v1/establishments/:id/availabilities` — Dispos (2)
- `/api/v1/reviews` — Avis (4)
- `/api/v1/reservations` — Réservations (9)
- `/api/v1/payments` — Paiements (5)
- `/api/v1/owner` — Espace propriétaire (19)
- `/api/v1/admin/*` — Admin (60+)
- `/api/v1/contact` — Contact (6)
- `/api/v1/upload` — Upload (3)

**Total : ~200 endpoints**

---

*Document final — Version 3.0*
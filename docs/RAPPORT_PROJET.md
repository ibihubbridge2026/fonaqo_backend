# RAPPORT DE PROJET — FONAQO
## Rapport Technique Complet

**Dernière mise à jour :** 21 Juin 2026  
**Version :** 3.0 — État complet post-corrections audit

---

## TABLE DES MATIÈRES

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture Technique](#2-architecture-technique)
3. [Modèles de Données](#3-modèles-de-données)
4. [Authentification & Sécurité](#4-authentification--sécurité)
5. [Gestion des Missions](#5-gestion-des-missions)
6. [Système Financier (Wallet & Escrow)](#6-système-financier-wallet--escrow)
7. [Chat Temps Réel](#7-chat-temps-réel)
8. [KYC & Badge Professionnel](#8-kyc--badge-professionnel)
9. [Système de Notation](#9-système-de-notation)
10. [Favoris & Fidélité](#10-favoris--fidélité)
11. [SuperAdmin Dashboard](#11-superadmin-dashboard)
12. [Notifications](#12-notifications)
13. [Rate Limiting & Performance](#13-rate-limiting--performance)
14. [Application Flutter Mobile](#14-application-flutter-mobile)
15. [Journal des Bugs Corrigés](#15-journal-des-bugs-corrigés)
16. [Installation & Configuration](#16-installation--configuration)
17. [Recommandations Production](#17-recommandations-production)

---

## 1. VUE D'ENSEMBLE

**FONAQO** est une plateforme de mise en relation entre **clients** (personnes ayant besoin d'un service) et **agents terrain** (prestataires locaux), accessible via une application mobile Flutter et gérée via un dashboard web SuperAdmin.

### Modèle économique

| Acteur | Rôle |
|---|---|
| **Client** | Crée une mission, paye en amont, valide la preuve |
| **Agent terrain** | Accepte et réalise la mission, reçoit 88 % du montant |
| **FONAQO** | Plateforme — 10 % de commission |
| **Réserve** | 2 % technique / assurance |
| **Influenceur** (optionnel) | 2 % prélevés sur la part FONACO si actif |

### Stack Technique

| Couche | Technologie | Version |
|---|---|---|
| Mobile | Flutter (Dart) | 3.x |
| Backend API | Django + Django REST Framework | 6.0.5 |
| Base de données | PostgreSQL + PostGIS | 16 |
| Cache | Redis | 7 |
| WebSocket | Django Channels + Daphne | 4.x |
| Auth | JWT (`djangorestframework-simplejwt`) | — |
| Email | Django SMTP + Templates HTML | — |
| Paiement | FeexPay (stub robuste) | — |
| Push | Firebase Cloud Messaging (FCM) | — |
| PDF | ReportLab | — |
| QR Code | `qrcode` Python | — |
| Rate Limiting | `django-ratelimit` | 4.1.0 |
| Cache Django | `django-redis` | 7.0.0 |

---

## 2. ARCHITECTURE TECHNIQUE

### 2.1 Backend (`fonaqo_back/`)

```
config/
├── settings.py       — Configuration globale (BDD, Redis, JWT, email, cache)
├── urls.py           — Routage principal URL
└── asgi.py           — Point d'entrée ASGI (WebSocket + HTTP)

apps/
├── accounts/         — Utilisateurs, Agents, Clients, KYC, Badge, Fidélité
│   ├── models.py         — User, AgentProfile, ClientProfile, FavoriteAgent, ClientRewardProfile
│   ├── views.py          — Login (5/min), Register (3/min), Profile, Favoris, Rewards
│   ├── serializers.py    — LoginSerializer (ACCOUNT_SUSPENDED), RegisterSerializer
│   ├── backends.py       — PhoneEmailBackend (login email/tél/username)
│   ├── agent_codes.py    — Génération AGT-00001 avec verrou DB
│   ├── pro_badge.py      — Génération badge PDF (ReportLab) avec QR code
│   ├── badge_views.py    — API download badge
│   ├── favorites_views.py — API toggle/list favoris
│   └── loyalty_service.py — LoyaltyService : points, niveaux, badges clients
│
├── missions/         — Cycle de vie missions, escrow, preuve photo, facturation
│   ├── models.py         — Mission, MissionProof, MissionTimelineEvent, AgentStatistics
│   │                       MaterialWithdrawalRequest, VoiceMissionRequest
│   │                       Index: (status,-created_at), (client,status), (agent,status)
│   ├── views.py          — MissionViewSet (accept, start, proof, validate, cancel, invoice)
│   └── serializers.py    — MissionDetailSerializer, MissionProofSerializer
│
├── chat/             — Conversations, Messages, WebSocket, Présence
│   ├── consumers.py      — ChatConsumer (WS: rate limit 10 conn/min/user, close 4408)
│   ├── views.py          — ConversationViewSet, MessageViewSet, TypingStatusViewSet
│   └── models.py         — Conversation, Message, TypingStatus, UserPresence
│
├── escrow/           — Séquestre des fonds
│   ├── services.py       — EscrowService (lock_on_accept, release_on_complete, cancel_penalize)
│   └── models.py         — Escrow, EscrowSplitRecord
│
├── wallets/          — Portefeuilles et transactions
│   ├── models.py         — Wallet, Transaction (types: MISSION, BADGE_FEE, WITHDRAWAL, etc.)
│   └── payout_service.py — PayoutService : demandes de retrait
│
├── payments/         — Intégration FeexPay
│   └── views.py          — WithdrawalViewSet, webhook dépôt
│
├── ratings/          — Notation bilatérale
│   └── models.py         — Rating (mission, reviewer, reviewee, rating_type, score, comment)
│
├── notifications/    — Notifications in-app
│   └── models.py         — InAppNotification (user, type, message, is_read, action_target)
│
├── disputes/         — Litiges
│   └── models.py         — Dispute, DisputeEvidence
│
├── boosts/           — Plans de visibilité boost
│   └── models.py         — BoostPlan, AgentBoost
│
├── statistics/       — Statistiques agents
│   └── models.py         — AgentStatistics
│
├── leboncoin/        — Annuaire artisans (indépendant des agents)
│   └── models.py         — LocalListing (catégorie, tarif, disponibilité)
│
├── opportunities/    — Opportunités matchées
│   └── models.py         — Opportunity
│
├── ai_search/        — Recherche IA (MistralAI)
│   └── views.py          — Endpoints recherche intelligente
│
└── core/             — Infrastructure commune
    ├── models.py         — PlatformConfiguration, PasswordResetRequest, AdminAuditLog
    ├── middleware.py     — AccountSuspensionMiddleware, StandardizeJsonResponse
    ├── email_service.py  — Emails HTML (bienvenue, KYC, badge, suspension, réactivation)
    ├── admin_views.py    — Vues HTML SuperAdmin (dashboard, agents, clients, config)
    ├── staff_views.py    — API staff (KYC, suspension, badge, pwd reset)
    └── kyc_views.py      — Queue KYC, approbation, rejet

templates/
├── super_admin/      — Dashboard HTML (agents, clients, missions, config, boosts)
│   ├── gestion_agents.html  — Tableau agents avec icônes actions
│   └── _admin_modals.html   — Modales (KYC drawer, row detail, confirm)
└── emails/           — Templates HTML + TXT emails

static/super_admin/admin.js  — Dashboard JS natif (~1 500 lignes)
```

### 2.2 Frontend Flutter (`fonaco/lib/`)

```
core/
├── api/
│   ├── base_client.dart       — Dio + intercepteurs JWT auto-refresh
│   └── api_config.dart        — baseUrl, timeouts
├── providers/
│   ├── auth_provider.dart     — AuthProvider (checkAuth, accountSuspended, user)
│   └── favorites_provider.dart — FavoritesProvider (optimistic UI + sync API)
├── routes/
│   └── app_router.dart        — GoRouter + guards (suspended, KYC lock)
└── services/
    └── cache_service.dart     — Hive local cache (clé par userId)

features/
├── auth/
│   ├── login_screen.dart
│   ├── register_screen.dart   — CGU checkbox obligatoire
│   ├── account_suspended_screen.dart — Écran bloquant plein écran
│   └── forgot_password_screen.dart
│
├── agent/
│   ├── dashboard/             — Tableau de bord agent
│   ├── missions/              — Détail mission agent (accept, start, proof)
│   └── profile/
│       ├── agent_profile_screen.dart
│       ├── agent_personal_info_screen.dart — Photo profil (1 fois = step KYC)
│       ├── kyc_lock_screen.dart
│       └── kyc_submit_screen.dart — Upload pièce ID + selfie
│
├── client/
│   ├── home/                  — Dashboard client
│   ├── missions/
│   │   ├── mission_detail_screen.dart — Refresh auto 10s, preuve photo, validation, chat modal
│   │   └── create_mission_screen.dart
│   ├── agents_screen.dart     — Liste + favoris
│   └── repositories/
│       └── favorites_repository.dart
│
├── chat/
│   ├── chat_list_screen.dart
│   └── chat_detail_screen.dart — WebSocket temps réel
│
├── rating/
│   └── rating_screen.dart     — Modale étoiles post-mission
│
└── wallet/
    └── wallet_screen.dart     — Solde + transactions
```

---

## 3. MODÈLES DE DONNÉES

### 3.1 Utilisateur (`User`)

```python
User (AbstractBaseUser)
├── id (UUID, PK)
├── phone_number (unique)
├── email (unique, optionnel)
├── username (unique)
├── is_agent (bool)
├── is_client (bool)
├── is_active (bool) — False = compte suspendu
├── profile_picture (ImageField)
├── kycStatus (NONE/SUBMITTED/APPROVED/REJECTED)
├── reliability_score, punctuality_score, completion_rate
└── witness_* (champs témoins)
```

### 3.2 Profil Agent (`AgentProfile`)

```python
AgentProfile
├── user (OneToOne → User)
├── agent_code (AGT-XXXXX, unique, généré à l'approbation KYC)
├── is_internal (bool — Agent FONACO interne)
├── is_verified (bool — KYC approuvé)
├── kyc_status (NONE/SUBMITTED/APPROVED/REJECTED)
├── id_card_photo, selfie_photo (KYC documents)
├── badge_status (NONE/PENDING/APPROVED/REJECTED)
├── average_rating, ratings_count
├── completion_rate, response_time_avg, ranking_score
└── veteran_boost_claimed (bool — pass vétéran unique)
```

### 3.3 Mission

```python
Mission
├── id (UUID, PK)
├── client (FK → User)
├── agent (FK → User, nullable)
├── target_agent_username (assignation ciblée)
├── title, description
├── tags (M2M → Tag)
├── location (PointField — PostGIS)
├── address
├── price, service_fee, labor_cost, material_cost, purchase_amount, service_amount
├── status (PENDING/ACCEPTED/ON_THE_WAY/ARRIVED/IN_PROGRESS/IN_PROGRESS_REVIEW/COMPLETED/CANCELLED/DISPUTED)
├── tracking_code (unique)
├── start_photo, end_photo (preuves)
├── client_rating, agent_rating
├── created_at, updated_at
└── Meta: indexes [(status,-created_at), (client,status), (agent,status)]
```

### 3.4 Wallet & Transaction

```python
Wallet
├── user (OneToOne → User)
└── balance (Decimal)

Transaction
├── wallet (FK → Wallet)
├── transaction_type (MISSION_PAYMENT/BADGE_FEE/ESCROW_LOCK/WITHDRAWAL/etc.)
├── amount (Decimal)
├── mission (FK → Mission, nullable)
└── created_at
```

### 3.5 Escrow

```python
Escrow
├── mission (OneToOne → Mission)
├── amount (Decimal)
└── status (HELD/RELEASED/REFUNDED)

EscrowSplitRecord
├── escrow (FK → Escrow)
├── recipient (FK → User)
├── amount (Decimal)
├── role (AGENT/PLATFORM/RESERVE/INFLUENCER)
└── created_at
```

### 3.6 Conversation & Message

```python
Conversation
├── id (UUID)
├── mission (FK → Mission)
├── client, agent (FK → User)
├── is_archived
└── negotiation_fields...

Message
├── conversation (FK → Conversation)
├── sender (FK → User)
├── message_type (TEXT/AUDIO/IMAGE/SYSTEM)
├── content, media_file, audio_file
├── delivery_status (SENT/DELIVERED/READ)
└── Meta: index [(conversation,-created_at)]
```

---

## 4. AUTHENTIFICATION & SÉCURITÉ

### 4.1 Flux de Connexion

```
[Flutter] POST /auth/login/ {phone_or_email, password}
    ↓ Rate limit: 5/min/IP
    ↓ PhoneEmailBackend.authenticate()
    ↓ Si is_active=False → 403 ACCOUNT_SUSPENDED
    ↓ Si valide → JWT access + refresh tokens
    ↓ [Flutter] stocke tokens → AppRouter redirige vers Dashboard
```

### 4.2 Flux d'Inscription

```
[Flutter] POST /auth/register/ {phone, username, password, role, email?}
    ↓ Rate limit: 3/min/IP
    ↓ Validation unicité phone/email/username
    ↓ Création User (is_agent=True ou is_client=True)
    ↓ Email de bienvenue (async Celery)
    ↓ JWT tokens retournés
```

### 4.3 Account Suspendu

```
SuperAdmin suspend → User.is_active = False + email envoyé
    ↓
[Middleware] AccountSuspensionMiddleware → toute requête /api/ → 403 ACCOUNT_SUSPENDED
    ↓
[Flutter] base_client.dart détecte 403 + code "ACCOUNT_SUSPENDED"
    ↓
AuthProvider._accountSuspended = true
    ↓
AuthGuard → redirect vers AccountSuspendedScreen (plein écran, bloquant)
```

### 4.4 Rate Limiting

| Endpoint | Limite | Clé |
|---|---|---|
| `POST /auth/login/` | 5 req/min | IP |
| `POST /auth/register/` | 3 req/min | IP |
| WebSocket `connect()` | 10 conn/min | user.id |

---

## 5. GESTION DES MISSIONS

### 5.1 Cycle de Vie Complet

```
PENDING
  ↓ Agent accepte (accept/) — Escrow créé, fonds bloqués
ACCEPTED
  ↓ Agent démarre trajet (start_journey/)
ON_THE_WAY
  ↓ Agent arrive (arrive/)
ARRIVED
  ↓ Agent démarre mission (start/)
IN_PROGRESS
  ↓ Agent soumet photo preuve (submit_proof/)
IN_PROGRESS_REVIEW
  ↓ Client valide (validate_completion/) — Fonds libérés
COMPLETED

Parallèle: CANCELLED (pénalité 15%/5%/80%) | DISPUTED (litige)
```

### 5.2 Quotas Missions Actives

| Profil Agent | Missions max | Condition |
|---|---|---|
| Standard | 2 | Par défaut |
| Boosté | 5 | Plan Boost actif |
| Pass Vétéran | 5 (3 jours) | 21e mission complétée (unique à vie) |

### 5.3 Côté Flutter (Client)

- **Rafraîchissement auto** : Timer 10 secondes dans `MissionDetailScreen`
- **Preuve photo** : URL `end_photo_url` affichée quand `IN_PROGRESS_REVIEW`
- **Bouton validation** : Apparaît automatiquement si `status == IN_PROGRESS_REVIEW`
- **Chat modal** : Bouton ouvre un `DraggableScrollableSheet` avec `ChatDetailScreen` intégré
- **Facture PDF** : Bouton download depuis `GET /missions/<id>/invoice/`

### 5.4 Assignation Ciblée

- Champ `target_agent_username` sur `Mission`
- Si renseigné, seul cet agent peut accepter la mission
- Vérifié dans `MissionViewSet.accept()` avec `select_for_update()`

---

## 6. SYSTÈME FINANCIER (WALLET & ESCROW)

### 6.1 Flux de Paiement

```
1. Client crée mission avec prix X FCFA
2. Agent accepte → EscrowService.lock_on_accept()
   - Wallet client débité de X FCFA
   - Escrow créé avec status HELD
3. Mission COMPLETED → EscrowService.release_on_complete()
   - Agent : +88% (ou -2% si influenceur)
   - FONACO : +10% (ou +8% si influenceur)
   - Réserve : +2%
   - Influenceur (si actif) : +2%
   - EscrowSplitRecord créé par bénéficiaire
```

### 6.2 Pénalité d'Annulation

```
Mission déjà ACCEPTED → client annule
   - Agent : +15% (indemnisation)
   - FONACO : +5% (frais admin)
   - Client : remboursement 80%
```

### 6.3 Retrait

```
Agent → POST /wallets/withdraw/ {amount, channel}
   ↓
PayoutService.request_withdrawal()
   ↓
Demande en attente → Staff approuve → FeexPay payout
```

---

## 7. CHAT TEMPS RÉEL

### 7.1 Architecture WebSocket

```
Flutter ChatDetailScreen
    ↓ WebSocket ws://host/ws/chat/<conversation_id>/?token=<JWT>
    ↓ TokenAuthMiddleware → valide JWT → user attaché
    ↓ Vérification ownership (client ou agent de la conversation)
    ↓ Rate limit: 10 connexions/min/user → close(4408) si dépassé
    ↓ ChatConsumer connecté → group chat_<conversation_id>
    ↓ group user_<user_id> pour notifications perso
```

### 7.2 Types de Messages

| Type | Description |
|---|---|
| `TEXT` | Message texte simple |
| `AUDIO` | Message vocal (fichier audio) |
| `IMAGE` | Photo (media_file) |
| `SYSTEM` | Message système (changement statut mission) |

### 7.3 Fonctionnalités

- **Typing indicator** : expire après 5 secondes (`TYPING_EXPIRY_SECONDS = 5`)
- **Statut livraison** : `SENT` → `DELIVERED` → `READ`
- **Présence** : `UserPresence.last_seen` + endpoint `/heartbeat/` (toutes les 30-60s)
- **Négociation prix** : Champs dédiés dans `Conversation`
- **Messages système** : Auto-envoyés lors des transitions de statut mission

---

## 8. KYC & BADGE PROFESSIONNEL

### 8.1 Processus KYC Complet

```
Étape 1 : Photo de profil (1 seule fois — côté Flutter)
   ↓ AgentPersonalInfoScreen → restriction si photo déjà uploadée + KYC != NONE
Étape 2 : Soumission documents
   ↓ POST /agent/kyc/submit/ {id_card_photo, selfie_photo}
   ↓ AgentProfile.kyc_status = SUBMITTED
Étape 3 : Revue SuperAdmin
   ↓ Queue KYC dans dashboard admin
   ↓ Approbation → kyc_status = APPROVED + code AGT-XXXXX généré + email agent
   ↓ Rejet → kyc_status = REJECTED + email avec motif
```

### 8.2 Badge Professionnel

```
Agent KYC approuvé → Demande badge
   ↓ POST /agent/badge/request/
   ↓ badge_status = PENDING
SuperAdmin valide badge
   ↓ Génération PDF (pro_badge.py — ReportLab)
   ↓ Badge format carte 85.6×54mm
   ↓ Photo agent (cercle) + nom + spécialité + ID + téléphone + zone
   ↓ "AGENT CERTIFIÉ ★" si is_internal=True
   ↓ QR code → /vitrine/agent/<uuid>/
   ↓ badge_status = APPROVED + email agent
Agent télécharge
   ↓ GET /agent/badge/download/ → fichier PDF
```

> **Note :** Le paiement de 1 000 FCFA pour le badge a été **supprimé**. Le badge est gratuit, généré par l'admin et imprimé côté FONAQO.

### 8.3 Vitrine Publique (scan QR)

`GET /vitrine/agent/<uuid>/` — Sans authentification

Affiche :
- Nom, prénom, avatar, code agent, zone
- Statut certifié (avec ou sans ★)
- Nombre de missions COMPLETED
- Montant cumulé encaissé (depuis `EscrowSplitRecord`)
- Note moyenne + nombre de notes

---

## 9. SYSTÈME DE NOTATION

### 9.1 Principe Bilatéral

- **Client note Agent** : `rating_type = CLIENT_RATES_AGENT`
- **Agent note Client** : `rating_type = AGENT_RATES_CLIENT`
- Score : 1 à 5 étoiles + commentaire optionnel
- Accessible seulement si mission `COMPLETED`
- Contrainte unique : `(mission, reviewer, rating_type)` — une seule note par couple

### 9.2 Calcul Automatique

Signal `post_save`/`post_delete` sur `Rating` :
- Recalcul `AgentProfile.average_rating` + `ratings_count`
- Recalcul `ClientProfile.average_rating` + `ratings_count`

### 9.3 Côté Flutter

- `RatingScreen` : étoiles interactives 1-5 + champ commentaire
- Modale affichée **automatiquement** quand mission passe à `COMPLETED`
- `RatingRepository` → `POST /missions/<id>/rate/`

---

## 10. FAVORIS & FIDÉLITÉ

### 10.1 Favoris

**Stratégie hybride Hive + API :**

```
Ouverture écran favoris
   ↓ GET /client/favorites/ → liste agents favoris
   ↓ Écriture dans Hive (clé: "favorite_agents_<userId>")
   ↓ Affichage UI

Clic cœur (toggle)
   ↓ Mise à jour UI + Hive instantanément (optimiste)
   ↓ POST /client/favorites/toggle/ {agent_id} async
   ↓ Si échec → revert UI + Hive
```

**Isolation** : Clé Hive par `userId` — chaque compte a ses propres favoris.

### 10.2 Programme Fidélité Client

| Badge | Condition |
|---|---|
| 🎯 Première Mission | 1ère mission complétée |
| ⭐ Client Fidèle | 5 missions complétées |
| 👑 VIP | 10 missions complétées |
| 💰 Gros Dépenseur | Mission > 10 000 FCFA |
| 💎 Super Dépenseur | 3 missions > 10 000 FCFA |

- Points attribués automatiquement via signal sur `COMPLETED`
- Niveaux 1-10 basés sur les points
- Endpoint : `GET /client/rewards/`

---

## 11. SUPERADMIN DASHBOARD

### 11.1 Pages et Accès

| Page | URL | Rôle minimum |
|---|---|---|
| KPIs Dashboard | `/admin-dashboard/` | Manager |
| Gestion Agents | `/admin-dashboard/users/agents/` | Manager |
| Gestion Clients | `/admin-dashboard/users/clients/` | Manager |
| Missions | `/admin-dashboard/missions/` | Manager |
| Artisans (LeBonCoin) | `/admin-dashboard/artisans/` | SuperAdmin |
| Boosts | `/admin-dashboard/boosts/` | SuperAdmin |
| Configuration | `/admin-dashboard/config/` | SuperAdmin |
| Réinit. SMS | `/admin-dashboard/password-resets/` | SuperAdmin |
| Staff | `/admin-dashboard/staff/` | SuperAdmin |
| Audit | `/admin-dashboard/audit/` | SuperAdmin |
| Influenceurs | `/admin-dashboard/influenceurs/` | Manager |

### 11.2 Actions Disponibles sur les Agents

Boutons dans le tableau des agents (avec icônes) :
- 👁️ **Voir détail** — Modal avec toutes les informations
- 📄 **KYC documents** — Affiché seulement si `kyc_status == SUBMITTED` ou `PENDING`
- 🏅 **Valider badge** — Affiché seulement si `badge_status == PENDING`
- 🏢 **Toggle interne** — Bascule `is_internal`
- 📖 **Annuaire** — Promouvoir dans LeBonCoin (si KYC approuvé)
- 🚫 **Suspendre** — `is_active = False` + email
- ✅ **Réactiver** — `is_active = True` + email

### 11.3 Configuration Dynamique

- Plans Boost : prix et durée modifiables via modal PATCH
- `PlatformConfiguration` : pourcentages escrow, frais, etc.
- Réinitialisations SMS : génération mot de passe temporaire copié dans le presse-papiers

### 11.4 Emails Automatiques

| Déclencheur | Template |
|---|---|
| Inscription | `welcome.html` |
| KYC approuvé | `kyc_approved.html` |
| KYC rejeté | `kyc_rejected.html` |
| Badge approuvé | `badge_approved.html` |
| Compte suspendu | `account_suspended.html` |
| Compte réactivé | `account_reactivated.html` |
| Mot de passe reset | `password_reset.html` |

---

## 12. NOTIFICATIONS

### 12.1 Notifications Push (FCM)

- Token FCM envoyé au backend à la connexion
- Notifications push sur événements clés :
  - Nouvelle mission disponible (agents)
  - Acceptation mission (client)
  - Changement de statut
  - Nouveau message chat

### 12.2 Notifications In-App

Modèle `InAppNotification` :
- `user`, `type`, `message`, `is_read`, `action_target`
- Endpoint : `GET /notifications/` — liste non lues
- `POST /notifications/<id>/read/` — marquer comme lu
- `GET /notifications/unread_count/` — badge compteur

---

## 13. RATE LIMITING & PERFORMANCE

### 13.1 Rate Limiting Implémenté

```python
# apps/accounts/views.py
@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request): ...

@ratelimit(key='ip', rate='3/m', method='POST')
def register_view(request): ...

# apps/chat/consumers.py
rate_limit_key = f'ws_rate_limit:{self.user.id}'
connection_count = cache.get(rate_limit_key, 0)
if connection_count >= 10:
    await self.close(code=4408)
    return
cache.set(rate_limit_key, connection_count + 1, 60)
```

### 13.2 Index Base de Données

```python
# apps/missions/models.py — Mission.Meta
indexes = [
    models.Index(fields=['status', '-created_at']),  # Filtrage par statut
    models.Index(fields=['client', 'status']),         # Missions d'un client
    models.Index(fields=['agent', 'status']),          # Missions d'un agent
]
```

### 13.3 Optimisations QuerySet

```python
# MissionViewSet.list()
qs = Mission.objects.filter(...)\
    .select_related('client', 'agent')\
    .prefetch_related('tags')\
    .order_by('-created_at')

# DisputeViewSet.get_queryset()
Dispute.objects.select_related(
    'mission', 'opened_by', 'assigned_to', 'resolved_by'
)
```

### 13.4 Cache Redis

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",  # DB 1 pour cache
        "KEY_PREFIX": "fonaqo",
    }
}
# DB 0 : Channel layers (WebSocket)
# DB 1 : Cache applicatif (rate limiting, futur)
```

---

## 14. APPLICATION FLUTTER MOBILE

### 14.1 Flux Principal Client

```
SplashScreen
  ↓ checkAuth() → si accountSuspended → AccountSuspendedScreen
  ↓ si non authentifié → LoginScreen
  ↓ si authentifié → ClientHomeScreen

ClientHomeScreen
  ├── Mes Missions (liste + création)
  ├── Agents Favoris
  └── Litiges

Mission sélectionnée → ClientMissionDetailScreen
  ├── Timer 10s → refresh statut auto
  ├── Si IN_PROGRESS_REVIEW → afficher photo preuve + bouton Valider
  ├── Bouton Chat → modal DraggableScrollableSheet + ChatDetailScreen
  └── Si COMPLETED → RatingScreen (modale automatique)
```

### 14.2 Flux Principal Agent

```
AgentDashboardScreen
  ├── Missions disponibles (PENDING)
  ├── Mes missions en cours
  └── Historique

Mission sélectionnée → AgentMissionDetailScreen
  ├── Bouton Accepter (si PENDING + KYC approuvé)
  ├── Bouton Démarrer trajet → ON_THE_WAY
  ├── Bouton Je suis arrivé → ARRIVED
  ├── Bouton Démarrer mission → IN_PROGRESS
  ├── Soumettre preuve photo → IN_PROGRESS_REVIEW
  └── Attente validation client → COMPLETED
```

### 14.3 Flux KYC Agent

```
AgentPersonalInfoScreen
  ├── Upload photo profil (1 seule fois)
  └── Si KYC non commencé → KYCLockScreen
      └── → KYCSubmitScreen
          ├── Photo pièce d'identité
          └── Selfie avec pièce
              ↓ POST /agent/kyc/submit/
              ↓ Admin approuve
              ↓ Agent reçoit email + code AGT-XXXXX
```

---

## 15. JOURNAL DES BUGS CORRIGÉS

### Session 1 — Mai/Juin 2026

| # | Symptôme | Cause | Fix |
|---|---|---|---|
| 1 | 500 création mission | Argument `recurrence` inattendu dans serializer | Pop `recurrence` de `validated_data` |
| 2 | 400 libération fonds | Escrow manquant ou déjà libéré | Auto-création escrow + `select_for_update` |
| 3 | Section litige toujours visible | Pas de condition sur missions | `_missions.isNotEmpty` |
| 4 | Favoris partagés entre comptes | `CacheService` sans `userId` | Clé `favorite_agents_$userId` |
| 5 | `type string` dans conversations | `StringRelatedField` dans serializer | `SerializerMethodField` retournant objets |
| 6 | Chat ne démarre pas depuis mission | `userName` absent | Extraction depuis `conversation['client'/'agent']` |

### Session 2 — 20 Juin 2026

| # | Symptôme | Cause | Fix |
|---|---|---|---|
| 7 | Page réinit. blanche (erreur JS) | `const { ok, body }` shadowe DOM `body` | Renommé en `body: respData` |
| 8 | Comptes suspendus non bloqués | `AccountSuspensionMiddleware` absent du MIDDLEWARE | Enregistré après `AuthenticationMiddleware` |
| 9 | `ACCOUNT_SUSPENDED` non propagé Flutter | `ApiErrorType` ne couvrait pas le 403 | `ApiErrorType.accountSuspended` ajouté |
| 10 | Restart app → pas de redirect suspendu | `checkAuth()` ignorait les exceptions | Catch `accountSuspended` → `_accountSuspended = true` |
| 11 | `AuthGuard` ne redirige pas | Pas de vérification `accountSuspended` | `if (authProvider.accountSuspended) redirect` |

### Session 3 — 21 Juin 2026

| # | Symptôme | Cause | Fix |
|---|---|---|---|
| 12 | `permission denied for django_migrations` | Tables appartenant à `root`, utilisateur `fonaqo` sans droits | `REASSIGN OWNED BY root TO fonaqo` + recréation DB |
| 13 | `InconsistentMigrationHistory` | `chat.0001` appliqué avant `missions.0002` | Suppression entrée orpheline + réapplication clean |
| 14 | `django-ratelimit` bloqué (cache locmem) | `LocMemCache` non supporté par ratelimit | Migration vers `django-redis` + `RedisCache` |
| 15 | `django_ratelimit.E003` (cache non partagé) | Config CACHES manquante | Ajout CACHES Redis dans `settings.py` |

---

## 16. INSTALLATION & CONFIGURATION

### 16.1 Prérequis

```bash
# Services requis
postgresql (+ postgis extension)
redis
python 3.14
flutter 3.x
```

### 16.2 Backend

```bash
cd fonaqo_back
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env minimal
APP_NAME=fonaqo
DEBUG=True
SECRET_KEY="your-secret-key"
DATABASE_URL=postgis://fonaqo:password@localhost:5432/fonaqo_db
REDIS_URL=redis://localhost:6379/0
MISTRAL_API_KEY=...

# Base de données
createdb fonaqo_db  # avec extension postgis
python manage.py migrate
python manage.py createsuperuser

# Lancement
python manage.py runserver 0.0.0.0:8000
```

### 16.3 Frontend Flutter

```bash
cd fonaco
flutter pub get
# Configurer lib/core/config/api_config.dart → baseUrl
flutter run
```

### 16.4 Variables d'Environnement Clés

| Variable | Description | Valeur dev |
|---|---|---|
| `DATABASE_URL` | URL PostgreSQL/PostGIS | `postgis://fonaqo:pwd@localhost:5432/fonaqo_db` |
| `REDIS_URL` | URL Redis (channels + cache) | `redis://localhost:6379/0` |
| `SECRET_KEY` | Clé secrète Django | Depuis `.env` |
| `DEBUG` | Mode debug | `True` en dev, `False` en prod |
| `MISTRAL_API_KEY` | IA recherche missions | Clé API Mistral |
| `FEEXPAY_API_KEY` | Paiements FeexPay | À configurer |
| `FIREBASE_KEY_PATH` | FCM notifications | Chemin vers `firebase-auth.json` |
| `SENTRY_DSN` | Monitoring erreurs | Optionnel |

---

## 17. RECOMMANDATIONS PRODUCTION

### 🔴 Bloquant (Avant toute mise en production)

1. **Validation uploads** — Whitelist extensions + vérification MIME + limite taille 10 Mo
2. **JWT durées** — Access: 1h max, Refresh: 7 jours max
3. **BLACKLIST_AFTER_ROTATION** — Activer pour invalider les anciens tokens
4. **SECRET_KEY** — Générer une clé forte aléatoire, jamais en dur

### 🟡 Important (Court terme post-lancement)

5. **Rate limiting étendu** — Création mission, paiements, retrait
6. **only()/defer()** — Réduire payload des endpoints list
7. **Pagination complète** — Tous les ViewSets
8. **Validation géographique** — Vérifier que l'agent est dans une zone réaliste
9. **Upload UUID** — Nommer tous les fichiers avec UUID pour éviter prédiction
10. **S3 ou volume dédié** — Stocker les médias hors du serveur Django

### 🟢 Évolutions Futures

11. **RS256** — Migration vers asymétrique pour JWT
12. **Firebase Analytics** — Tracking comportement utilisateurs
13. **Tests de charge** — k6 ou Locust avant lancement
14. **Multi-langue** — Flutter `intl`
15. **APM** — Sentry déjà configuré, activer en prod
16. **Mission vocale** — Finaliser le flux complet

---

*Dernière mise à jour : 21 Juin 2026 — Post-corrections audit v2.0*  
*Backend : 100 % complet · Flutter : 85 % · Bloquants prod : 4*

# Analyse Routes Flutter vs Backend
**Date**: 30 mai 2026

---

## 1. Routes Flutter → Backend Mapping

### 1.1 Agent Repository (`agent_repository.dart`)

| Route Flutter | Route Backend | Status |
|---------------|---------------|--------|
| `wallets/balance/` | ✅ `wallets/balance_view` | OK |
| `missions/available/` | ✅ `missions/available` | OK |
| `accounts/agent/status/` | ✅ `accounts/agent_status_view` | OK |
| `missions/{id}/accept/` | ✅ `missions/accept` | OK |
| `missions/{id}/start_mission/` | ✅ `missions/start_mission` | OK |
| `missions/{id}/update_steps/` | ✅ `missions/update_steps` | OK |
| `missions/{id}/submit_completion/` | ✅ `missions/submit_completion` | OK |
| `missions/{id}/validate_completion/` | ✅ `missions/validate_completion` | OK |
| `missions/{id}/open_dispute/` | ✅ `missions/open_dispute` | OK |
| `wallets/transactions/` | ✅ `wallets/transactions_view` | OK |
| `payments/withdraw/` | ❌ `payments/urls.py` vide | **MANQUANT** |
| `missions/{id}/rate/` | ✅ `missions/rate_mission` | OK |
| `missions/statistics/` | ✅ `missions/dashboard_stats` | OK |
| `boosts/purchase/` | ✅ `boosts/` (ViewSet) | OK |
| `missions/history/` | ✅ `missions/history` | OK |

### 1.2 Client Repository (`mission_repository.dart`)

| Route Flutter | Route Backend | Status |
|---------------|---------------|--------|
| `missions/available/` | ✅ `missions/available` | OK |
| `missions/` | ✅ `missions/list` | OK |
| `missions/{id}/` | ✅ `missions/retrieve` | OK |
| `missions/{id}/accept/` | ✅ `missions/accept` | OK |
| `missions/{id}/start_mission/` | ✅ `missions/start_mission` | OK |
| `missions/{id}/mark_completed_live/` | ✅ `missions/mark_completed_live` | OK |
| `accounts/agents/suggestions/` | ✅ `accounts/agent_suggestions_view` | OK |
| `/opportunities/` | ✅ `opportunities/` (ViewSet) | OK |
| `/ai/search/` | ✅ `ai_search/search/` (ViewSet) | OK |

### 1.3 Autres Providers Flutter

| Provider | Route Flutter | Route Backend | Status |
|----------|---------------|---------------|--------|
| `opportunity_provider.dart` | `/opportunities/` | ✅ `opportunities/` | OK |
| `ai_search_provider.dart` | `/ai/search/` | ✅ `ai_search/search/` | OK |

---

## 2. Routes Backend sans Correspondance Flutter

Les apps backend suivantes ont des ViewSets mais ne sont pas (ou peu) utilisées côté Flutter :

| App Backend | Routes | Usage Flutter |
|-------------|--------|---------------|
| `escrow/` | escrow operations | Non détecté |
| `notifications/` | notifications list | Non détecté |
| `disputes/` | disputes CRUD | Non détecté |
| `statistics/` | agent statistics | Partiellement (missions/statistics/) |
| `services/` | categories list | ✅ utilisé |

---

## 3. Routes Flutter sans Backend

| Route Flutter | Problème | Action Requise |
|----------------|----------|----------------|
| `payments/withdraw/` | `payments/urls.py` vide | Implémenter endpoint withdrawal |

---

## 4. Screens Flutter par Profil

### 4.1 Agent Screens (14 screens)

| Screen | Fonctionnalité | Backend Routes |
|--------|----------------|----------------|
| `agent_active_mission_screen.dart` | Mission en cours | `missions/{id}/`, `missions/{id}/start_mission/`, `missions/{id}/update_steps/` |
| `agent_boost_screen.dart` | Boosts de visibilité | `boosts/purchase/` |
| `agent_chat_screen.dart` | Chat mission | WS `/ws/chat/{mission_id}/` |
| `agent_dashboard_screen.dart` | Dashboard agent | `missions/statistics/`, `wallets/balance/` |
| `agent_main_screen.dart` | Écran principal agent | - |
| `agent_main_shell.dart` | Shell navigation agent | - |
| `agent_mission_detail_screen.dart` | Détails mission | `missions/{id}/` |
| `agent_mission_history_screen.dart` | Historique missions | `missions/history/` |
| `agent_missions_explorer_screen.dart` | Explorateur missions | `missions/available/` |
| `agent_notifications_screen.dart` | Notifications agent | `notifications/` (non utilisé) |
| `agent_profile_screen.dart` | Profil agent | `accounts/profile/` |
| `agent_settings_screen.dart` | Paramètres agent | - |
| `agent_wallet_screen.dart` | Wallet agent | `wallets/balance/`, `wallets/transactions/` |
| `ai_mission_search_screen.dart` | Recherche IA missions | `/ai/search/` |

### 4.2 Client Screens (4 screens)

| Screen | Fonctionnalité | Backend Routes |
|--------|----------------|----------------|
| `mission_tracking_screen.dart` | Tracking mission en cours | `missions/{id}/`, WS `/ws/gps/{mission_id}/` |
| `ai_search_screen.dart` | Recherche IA | `/ai/search/` |
| `opportunity_screen.dart` | Opportunités | `/opportunities/` |
| `agent_profile_screen.dart` | Profil agent consulté | `accounts/agents/suggestions/` |

**Note**: Le client a aussi des screens dans `client/home/`, `client/missions/`, `client/profile/` (non listés ici car dans sous-dossiers).

---

## 5. Recommandations

### 5.1 Priorité Haute
- **Implémenter `payments/withdraw/`** : Endpoint manquant pour retrait wallet

### 5.2 Priorité Moyenne
- **Utiliser `notifications/`** : Connecter `agent_notifications_screen.dart` au backend
- **Utiliser `disputes/`** : Connecter litiges (écran existant dans `features/litiges/`)
- **Utiliser `escrow/`** : Intégrer logique séquestre pour paiements sécurisés

### 5.3 Priorité Basse
- **Audit `statistics/`** : Vérifier si tous les endpoints sont utilisés
- **Nettoyer apps inutilisées** : Si certaines apps backend ne sont jamais utilisées, les retirer

---

## 6. Nettoyage Effectué

### 6.1 Fichiers Supprimés
- ✅ `scripts/seed_database.py` (dupliqué, remplacé par `seed_v2.py`)
- ✅ `run_seed.py` (script wrapper inutile)
- ✅ `Dockerfile copy` (fichier dupliqué)
- ✅ `backend_contributions/` (apps dupliquées de `apps/`)

### 6.2 Seed Principal
- **Script principal**: `scripts/seed_v2.py`
- **Commande**: `docker compose exec web python manage.py shell < scripts/seed_v2.py`

---

**Conclusion**: 1 endpoint manquant (`payments/withdraw/`), 3 apps backend sous-utilisées (notifications, disputes, escrow).

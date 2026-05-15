# 📦 FONAQO Backend - Contributions Complémentaires

Ce dossier contient les modèles et fonctionnalités manquants à ajouter au dépôt principal `fonaqo_backend`.

## 📋 Fonctionnalités Ajoutées

### 1. **Boosts / Visibilité Agent** (`boosts/`)
- Système d'achat de boosts pour augmenter la visibilité des agents
- Plans (Day, Week, Month)
- Suivi du temps restant
- Intégration wallet

### 2. **Messaging / Chat Temps Réel** (`messaging/`)
- Messages texte et vocaux
- Support images/pièces jointes
- Statuts (lu, envoyé, reçu)
- Conversations agent-client

### 3. **Litiges / Disputes** (`disputes/`)
- Ouverture de litiges par clients
- Gestion par admin/support
- Historique et résolution
- Impact sur notes agents

### 4. **Missions Enhanced** (`missions_enhanced/`)
- Upload multiple de preuves photos
- Timeline détaillée avec timestamps
- Statistiques agents avancées

---

## 🚀 Installation

1. Copier les dossiers dans votre projet Django `fonaqo_backend/apps/`
2. Ajouter aux `INSTALLED_APPS` dans `settings.py` :
```python
INSTALLED_APPS = [
    # ... apps existantes
    'apps.boosts',
    'apps.messaging',
    'apps.disputes',
    'apps.missions_enhanced',
]
```

3. Créer les migrations :
```bash
python manage.py makemigrations boosts messaging disputes missions_enhanced
python manage.py migrate
```

4. Inclure les URLs dans `urls.py` principal :
```python
from django.urls import path, include

urlpatterns = [
    # ... URLs existantes
    path('api/boosts/', include('apps.boosts.urls')),
    path('api/chat/', include('apps.messaging.urls')),
    path('api/disputes/', include('apps.disputes.urls')),
]
```

---

## 📡 Endpoints API Créés

### Boosts
- `GET /api/boosts/plans/` - Liste des plans disponibles
- `POST /api/boosts/purchase/` - Acheter un boost
- `GET /api/boosts/active/` - Boost actif de l'agent
- `GET /api/boosts/history/` - Historique des boosts

### Chat
- `GET /api/chat/conversations/` - Liste des conversations
- `GET /api/chat/<conversation_id>/messages/` - Messages d'une conversation
- `POST /api/chat/<conversation_id>/send/` - Envoyer un message
- `WS /ws/chat/<conversation_id>/` - WebSocket pour temps réel

### Litiges
- `POST /api/missions/<id>/open_dispute/` - Ouvrir un litige
- `GET /api/disputes/my-disputes/` - Litiges d'un utilisateur
- `PUT /api/disputes/<id>/resolve/` - Résoudre un litige (admin)
- `GET /api/disputes/stats/` - Statistiques litiges (admin)

---

## 🔧 Prérequis

- Django 4.2+
- Django Channels (pour WebSocket chat)
- Pillow (pour gestion images)
- Redis (pour WebSocket backend)

## 📝 Notes

Ces modules sont conçus pour être compatibles avec l'architecture existante de `fonaqo_backend`.
Les modèles utilisent les relations ForeignKey vers les modèles existants (AgentProfile, Mission, etc.).

# Boosts App - FONAQO Backend

Application Django pour gérer le système de boosts de visibilité des agents.

## Modèles

- **BoostPlan**: Plans disponibles (Day, Week, Month)
- **AgentBoost**: Instances de boosts achetées par les agents

## Installation

1. Déplacer ce dossier dans `apps/boosts/` du projet backend
2. Ajouter `'apps.boosts'` dans `INSTALLED_APPS`
3. Exécuter `python manage.py makemigrations boosts`
4. Exécuter `python manage.py migrate`

## API Endpoints (à implémenter dans views.py)

```python
# GET /api/boosts/plans/ - Liste des plans actifs
# POST /api/boosts/purchase/ - Acheter un boost
# GET /api/boosts/active/ - Boost actif de l'agent connecté
# GET /api/boosts/history/ - Historique complet
```

## Data Fixtures (exemple)

```json
[
  {
    "model": "boosts.boostplan",
    "fields": {
      "name": "Day Boost",
      "duration_hours": 24,
      "price": "5000.00",
      "description": "Boostez votre visibilité pendant 24h",
      "visibility_multiplier": 2.0,
      "is_active": true
    }
  },
  {
    "model": "boosts.boostplan",
    "fields": {
      "name": "Week Boost",
      "duration_hours": 168,
      "price": "25000.00",
      "description": "Boostez votre visibilité pendant 7 jours",
      "visibility_multiplier": 2.5,
      "is_active": true
    }
  },
  {
    "model": "boosts.boostplan",
    "fields": {
      "name": "Month Boost",
      "duration_hours": 720,
      "price": "80000.00",
      "description": "Boostez votre visibilité pendant 30 jours",
      "visibility_multiplier": 3.0,
      "is_active": true
    }
  }
]
```

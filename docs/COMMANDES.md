# 📜 GUIDE DES COMMANDES FONAQO (BACKEND) - V2

Ce document est ta référence pour installer, piloter et maintenir le backend FONAQO. Il couvre tout le cycle de vie, du premier démarrage au débogage des tâches de fond.

---

## 🛠️ 1. Démarrage des Services (De A à Z)
*Suivez ces étapes lors de la première installation ou après un reset complet du projet.*

1. **Environnement** : Créez votre fichier de configuration locale.
   - `cp .env.example .env` (Puis remplissez les variables à l'intérieur).
2. **Build & Launch** : Construisez les images et lancez les conteneurs (Postgres, Redis, Django, Celery).
   - `docker compose up --build -d`
3. **Base de Données** : Appliquez les schémas SQL à la base de données.
   - `make migrate`
4. **Données de Test** : Chargez les catégories de services et les niveaux d'agents initiaux.
   - `make seed`
5. **Accès Admin** : Créez votre compte administrateur pour le back-office (`http://localhost:8000/admin`).
   - `docker compose exec web python manage.py createsuperuser`

---

## 🐘 2. Commandes Django (Utilitaires)
*À exécuter pour interagir avec le framework et modifier la structure du projet.*

| Action | Commande | Quand l'utiliser ? |
| :--- | :--- | :--- |
| **Nouvelle Migration** | `docker compose exec web python manage.py makemigrations` | Après avoir ajouté ou modifié un champ dans `models.py`. |
| **Vérifier les erreurs** | `docker compose exec web python manage.py check` | Pour détecter des erreurs de syntaxe ou de configuration. |
| **Console Interactive** | `make shell` | Pour tester des morceaux de code ou manipuler des objets. |
| **Changer de Password** | `docker compose exec web python manage.py changepassword <username>` | En cas d'oubli de mot de passe admin. |
| **Fichiers Statiques** | `docker compose exec web python manage.py collectstatic` | Avant un déploiement en production. |

---

## ⚙️ 3. Gestion de Celery & Redis (Background Tasks)
*Indispensable pour débugger les notifications push et les calculs de scores.*

- **Logs des Workers** (Notifications & Missions) :
  - `docker compose logs -f worker`
- **Logs de Celery Beat** (Tâches planifiées/Nettoyage) :
  - `docker compose logs -f beat`
- **Purger les tâches** (Annuler tout ce qui est en file d'attente) :
  - `docker compose exec web celery -A config purge`
- **Vérifier Redis** :
  - `docker compose exec redis redis-cli ping` (Doit répondre `PONG`).

---

## 🚀 4. Raccourcis Quotidiens (Makefile)
*Les commandes les plus utilisées pour gagner du temps.*

- `make run` : Lance tout le projet (Daphne, Workers, DB, Redis).
- `make stop` : Éteint tous les services proprement.
- `make test` : Lance la suite de tests unitaires (Pytest).
- `make migrate` : Raccourci pour `python manage.py migrate`.

---

## 🧹 5. Nettoyage & Maintenance
- **Reset Complet (Supprime tout, DB incluse)** :
  - `docker compose down -v` (Attention : supprime les données de la base).
- **Nettoyer les caches Python** :
  - `find . -name "__pycache__" -delete`
- **Réinitialiser le scheduler Celery** :
  - `rm celerybeat-schedule.db` (À faire si les tâches planifiées ne se lancent plus).

---

## 📁 6. Organisation des Fichiers de Documentation
- `/docs/DOCUMENTATION.md` : Architecture globale et Contrats API.
- `/docs/FLUTTER_QUICKSTART.md` : Guide d'intégration pour l'équipe mobile.
- `/docs/COMMANDES.md` : Ce fichier (Guide d'exploitation).


# =========================
# DOCKER - COMMANDES UTILES
# =========================

# Démarrer tous les services
docker compose up -d

# Démarrer uniquement le service web
docker compose up -d web

# Vérifier que les containers sont UP
docker compose ps

# Voir les logs du service web
docker compose logs -f web

# Redémarrer le service web
docker compose restart web

# Arrêter tous les services
docker compose stop


# =========================
# DJANGO / STATIC FILES
# =========================

# Collecter les fichiers CSS/static
docker compose exec web python manage.py collectstatic --noinput

# Seeder des données
docker compose exec web python manage.py seed_data password123


# =========================
# POSTGRESQL / PORT 5432
# =========================

# Arrêter PostgreSQL local Ubuntu
# (utile si le port 5432 est déjà utilisé)
sudo systemctl stop postgresql

# Voir qui utilise le port 5432
sudo lsof -i :5432

# Tuer le processus qui utilise le port 5432
sudo fuser -k 5432/tcp


# =========================
# DJANGO - CHANGER MOT DE PASSE
# =========================

# Méthode 1 : commande Django
docker compose exec web python manage.py changepassword 0195748884


# Méthode 2 : via shell Django
docker compose exec web python manage.py shell



****************************************

# 1. On arrête tout et on supprime les réseaux orphelins
docker compose down --remove-orphans

# 2. On nettoie les réseaux Docker inutilisés (confirme par 'y' si demandé)
docker network prune -f

# 3. On relance tout
docker compose up -d

sudo systemctl stop redis-server
# Tue de force tout ce qui utilise le port 6379
sudo fuser -k 6379/tcp

docker compose logs -f web
# FONAQO Backend Documentation

## 1) Architecture Technique

FONAQO est construit autour de:

- **Django + Django REST Framework** pour les API HTTP.
- **PostgreSQL/PostGIS** pour les donnees transactionnelles et geospatiales.
- **Redis** pour le broker Celery et les channels websockets.
- **Django Channels (ASGI + Daphne)** pour le temps reel.
- **Celery + Celery Beat** pour les traitements asynchrones et planifies.

### Composants

- `web`: application ASGI exposee via `daphne`.
- `worker`: execution des taches Celery.
- `beat`: scheduler de taches periodiques.
- `db`: PostgreSQL + extension PostGIS.
- `redis`: bus temps reel + file de messages.

---

## 2) Contrat API HTTP

Toutes les reponses JSON suivent maintenant le schema standard:

```json
{
  "status": "success|error",
  "message": "human readable message",
  "data": {},
  "errors": {}
}
```

### Regles

- **Succes (2xx/3xx)**:
  - `status = "success"`
  - `data` contient le payload metier
  - `errors = {}`
- **Erreur (4xx/5xx)**:
  - `status = "error"`
  - `data = {}`
  - `errors` contient les details techniques (validation, permissions, etc.)

### Exemples

Succes:

```json
{
  "status": "success",
  "message": "Mission acceptée.",
  "data": {
    "id": "..."
  },
  "errors": {}
}
```

Erreur:

```json
{
  "status": "error",
  "message": "Non autorisé.",
  "data": {},
  "errors": {
    "detail": "Non autorisé."
  }
}
```

### Codes erreurs recommandes pour Flutter

- `400`: validation/payload incorrect.
- `401`: non authentifie.
- `403`: authentifie mais non autorise.
- `404`: ressource inexistante.
- `409`: conflit metier.
- `500`: erreur interne.

---

## 3) WebSockets

Les sockets sont proteges: seul le **client** ou l'**agent** lies a la mission peuvent se connecter.

## 3.1 Chat Socket

- **URL**: `ws/chat/<mission_id>/`
- **Auth**: utilisateur connecte obligatoire
- **Autorisation**: mission.client ou mission.agent uniquement

### Payloads entrants

Message:

```json
{
  "type": "message",
  "message": "Bonjour"
}
```

Typing:

```json
{
  "type": "typing",
  "is_typing": true
}
```

### Payloads sortants

Message:

```json
{
  "message": "Bonjour",
  "sender": "agent_001"
}
```

Typing:

```json
{
  "type": "typing",
  "sender": "agent_001",
  "is_typing": true
}
```

## 3.2 GPS Socket

- **URL**: `ws/gps/<mission_id>/`
- **Auth**: utilisateur connecte obligatoire
- **Autorisation de connexion**: mission.client ou mission.agent
- **Publication GPS**: **agent uniquement**

### Payload entrant (agent)

```json
{
  "lat": 6.372,
  "lng": 2.391
}
```

### Payload sortant

```json
{
  "type": "gps_update",
  "lat": 6.372,
  "lng": 2.391
}
```

---

## 4) Variables d'Environnement

Configurer ces variables dans `.env` (voir `.env.example`):

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `REDIS_URL`
- `SENTRY_DSN`
- `SENTRY_TRACES_SAMPLE_RATE`
- `SENTRY_SEND_DEFAULT_PII`
- `FIREBASE_KEY_PATH`

---

## 5) Deploiement Docker

## Prerequis

- Docker + Docker Compose installes.
- Fichier `.env` configure.

## Demarrage

```bash
docker compose up --build
```

## Services exposes

- API ASGI: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Commandes utiles

Appliquer les migrations:

```bash
docker compose exec web python manage.py migrate
```

Check Django:

```bash
docker compose exec web python manage.py check
```

Seeder:

```bash
docker compose exec web python manage.py seed_data
```

---

## 6) Notes de Fiabilite

- Les transferts monetaire critiques utilisent `transaction.atomic()`.
- Les wallets sont verrouilles via `select_for_update()` pour eviter les race conditions.
- Les statuts metier principaux sont centralises dans `apps/core/choices.py`.

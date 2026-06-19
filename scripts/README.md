# Scripts utilitaires

Le seeding est centralisé dans **`apps/core/seed.py`**, invoqué via :

```bash
docker compose exec web python manage.py seed_data [password] [--flush]
# ou
make seed
make reset-seed   # flush + seed
```

Ne pas ajouter de scripts seed parallèles — étendre `apps/core/seed.py` uniquement.

"""
Settings de test : utilise SpatiaLite (SQLite + libspatialite) pour éviter
de nécessiter un serveur PostgreSQL/PostGIS lors des tests unitaires.
"""
from config.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.spatialite",
        "NAME": ":memory:",
    }
}

# Désactiver les migrations lourdes pour accélérer les tests
# (les tables sont créées directement depuis les modèles)
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Accélérer le hashing des mots de passe en tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Désactiver les tâches Celery/caches non critiques
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Ne pas écrire sur disque
DEFAULT_FILE_STORAGE = "django.core.files.storage.InMemoryStorage"

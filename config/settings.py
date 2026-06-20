import os
from datetime import timedelta
from pathlib import Path

import environ
import firebase_admin
import sentry_sdk
from celery.schedules import crontab
from firebase_admin import credentials
from sentry_sdk.integrations.django import DjangoIntegration


BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")


# Celery Config
CELERY_BROKER_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = "Africa/Porto-Novo"

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.2),
        send_default_pii=env.bool("SENTRY_SEND_DEFAULT_PII", default=False),
    )


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="unsafe-dev-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

if DEBUG:
    ALLOWED_HOSTS = ["*", "192.168.1.73", "localhost", "127.0.0.1"]
    CORS_ALLOW_ALL_ORIGINS = True
else:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://192.168.1.73:8000", "http://localhost:8000"],
)
# Application definition

INSTALLED_APPS = [
    'daphne', # Doit être en premier !
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis', # Pour PostGIS (Tracking GPS)

    # Third Party
    'rest_framework',
    'corsheaders',
    'channels', # Pour les WebSockets
    'fcm_django',

    # Local Apps (nos modules — AppConfig explicites)
    'apps.core.apps.CoreConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.missions.apps.MissionsConfig',
    'apps.wallets.apps.WalletsConfig',
    'apps.payments.apps.PaymentsConfig',
    'apps.escrow.apps.EscrowConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.services.apps.ServicesConfig',
    # Chat App (WebSocket)
    'apps.chat.apps.ChatConfig',
    
    # NOUVELLES APPS
    'apps.ai_search.apps.AiSearchConfig',
    'apps.opportunities.apps.OpportunitiesConfig',
    'apps.boosts.apps.BoostsConfig',
    'apps.disputes.apps.DisputesConfig',
    'apps.statistics.apps.StatisticsConfig',
    'apps.leboncoin.apps.LeboncoinConfig',
    'apps.ratings.apps.RatingsConfig',

    #celery
    'django_celery_results',
    'django_celery_beat',
    'simple_history'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.AccountSuspensionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.staff_redirect_middleware.StaffDashboardRedirectMiddleware',
]

ROOT_URLCONF = 'config.urls'

LOGIN_URL = '/admin-portal/login/'
LOGIN_REDIRECT_URL = '/admin-dashboard/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": env("POSTGRES_DB", default="fonaqo_db"),
            "USER": env("POSTGRES_USER", default="root"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="postgres"),
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.PhoneEmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# URL utilisée pour accéder aux fichiers via le navigateur
MEDIA_URL = '/media/'

# Dossier physique sur ton disque dur où les fichiers seront stockés
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

ASGI_APPLICATION = "config.asgi.application" # Pour les WebSockets (daphne)

# Pour le développement local (nécessite Redis installé ou via Docker)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
        "hosts": [env("REDIS_URL", default="redis://127.0.0.1:6379/0")],
        },
    },
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "apps.core.renderers.StandardizedJSONRenderer",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.standardized_exception_handler",

    # 1. PAGINATION (Point 1)
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,

    # 2. FILTERING & SEARCH (Point 2 & 3)
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],

    # 3. DOCUMENTATION (Swagger - Étape 3)
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    # 4. AUTHENTICATION & THROTTLING
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # 5. THROTTLING (Point 4)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    # 6. THROTTLING RATES (Point 4)
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',   # Limite pour les utilisateurs non connectés
        'user': '1000/day',  # Limite pour les clients/agents connectés
        'burst': '10/minute', # Protection contre le spam rapide
    }
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FONAQO API",
    "DESCRIPTION": "Backend for Mission & Services Platform",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Configuration Email pour MailDev (développement)
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = env('EMAIL_HOST', default='localhost')
EMAIL_PORT = env.int('EMAIL_PORT', default=1025)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@fonaco.com')

CELERY_BEAT_SCHEDULE = {
    'cleanup-missions-every-30-mins': {
        'task': 'apps.missions.tasks.cleanup_expired_missions',
        'schedule': crontab(minute='*/30'),
    },
}

FIREBASE_KEY_PATH = os.path.join(BASE_DIR, 'firebase-auth.json')
FIREBASE_KEY_PATH = env("FIREBASE_KEY_PATH", default=FIREBASE_KEY_PATH)

# Initialisation de Firebase
if os.path.exists(FIREBASE_KEY_PATH):
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred)

# Mistral AI Configuration (Recherche IA)
MISTRAL_API_KEY = env("MISTRAL_API_KEY", default="")

# FeexPay (Mobile Money Bénin)
FEEXPAY_API_KEY = env('FEEXPAY_API_KEY', default='')
FEEXPAY_WEBHOOK_SECRET = env('FEEXPAY_WEBHOOK_SECRET', default='')
FEEXPAY_BASE_URL = env('FEEXPAY_BASE_URL', default='https://api.feexpay.me/backend')
FEEXPAY_CALLBACK_URL = env('FEEXPAY_CALLBACK_URL', default='')
FEEXPAY_SANDBOX = env.bool('FEEXPAY_SANDBOX', default=True)
FEEXPAY_CHECKOUT_URL_TEMPLATE = env('FEEXPAY_CHECKOUT_URL_TEMPLATE', default='')

# Vitrine web invité
SITE_BASE_URL = env('SITE_BASE_URL', default='http://localhost:8000')
GOOGLE_PLACES_API_KEY = env('GOOGLE_PLACES_API_KEY', default='')

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=365),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
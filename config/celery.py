import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('fonaqo')

# On utilise les réglages Django pour configurer Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Détection automatique des tâches dans tes apps (tasks.py)
app.autodiscover_tasks()
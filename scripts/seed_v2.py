#!/usr/bin/env python3
"""
Script de seeding FONAQO — délègue à apps.core.seed (même logique que manage.py seed_data).
Utilisation : docker compose exec web python scripts/seed_v2.py
              docker compose exec web python manage.py seed_data password123 --flush
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.core.seed import DEFAULT_PASSWORD, run_seed  # noqa: E402


def main():
    password = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PASSWORD
    run_seed(password=password)


if __name__ == "__main__":
    main()

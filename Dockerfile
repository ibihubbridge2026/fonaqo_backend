FROM python:3.12-slim

# Dépendances système pour PostGIS et Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie et installation forcée
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY . .

# On s'assure que les scripts sont exécutables
RUN chmod +x /app/manage.py

EXPOSE 8000
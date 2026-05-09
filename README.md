# FONAQO Backend

Backend officiel de **FONAQO**, une plateforme intelligente de services terrain et de conciergerie permettant de connecter des clients à des agents de proximité pour :

- files d’attente,
- démarches administratives,
- livraisons,
- services urbains,
- assistance terrain,
- micro-services géolocalisés.

---

# Vision

FONAQO digitalise les services de proximité en Afrique en combinant :

- géolocalisation temps réel,
- escrow sécurisé,
- wallet intégré,
- KYC avancé,
- tracking GPS,
- matching intelligent,
- notifications temps réel,
- architecture scalable.

---

# Core Features

## Accounts & Authentication

- JWT Authentication
- UUID-based users
- Agent / Client roles
- Social login ready
- OTP architecture ready
- Agent verification workflow
- KYC system
- Referral system
- AI reliability scoring
- Multi-level agents

---

## Missions System

- Geolocation with PostGIS
- Nearby mission discovery
- Real-time mission tracking
- Mission timeline
- Smart matching structure
- QR code validation
- Proof-of-work photo uploads
- Mission status workflow
- Expertise tags

---

## Wallet & Escrow

- Wallet system
- Escrow balance management
- Automatic mission payout
- Transaction history
- Withdrawal requests
- Boost purchases
- Referral commissions
- Insurance fee structures

---

## Real-time Chat

- Django Channels + WebSockets
- Direct conversations
- Mission-based chat
- Read receipts
- Anti-fraud filtering
- Phone number masking

---

## Notifications

- Firebase Cloud Messaging (FCM)
- Real-time alerts
- Mission notifications
- Status updates
- Geo-based notifications

---

## Security

- Role-based permissions
- Audit logging
- Rate limiting
- Secure QR validation
- Escrow protection
- Fraud prevention structure

---

# Tech Stack

## Backend
- Python
- Django
- Django REST Framework

## Realtime
- Django Channels
- Redis
- WebSockets

## Database
- PostgreSQL
- PostGIS

## Async Tasks
- Celery
- Redis

## Authentication
- JWT (SimpleJWT)

## Storage
- Cloudinary / S3 ready

## Notifications
- Firebase FCM

---

# Project Structure

```txt
fonaqo_back/
├── apps/
│   ├── accounts/       # Auth, KYC, Niveaux
│   ├── missions/       # Missions, Timeline, Boosts, Disputes, Tags
│   ├── wallet/         # Portefeuille & Escrow (ou séparés)
│   ├── services/       # Catégories & Offres agents
│   ├── chat/           # WebSockets & Messages
│   └── notifications/  # Firebase Cloud Messaging
├── config/             # settings.py, asgi.py, wsgi.py
├── templates/          # Admin Dashboard HTML
├── media/              # (Photos stockées ici)
├── static/             # (Fichiers statiques admin)
├── requirements/       # base.txt
├── manage.py
└── .gitignore          

```

---

# ⚙️ Installation

## 1. Clone repository

```bash
git clone https://github.com/yourusername/fonaqo_backend.git
cd fonaqo_backend
```

## 2. Create virtual environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / Mac

```bash
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create `.env`

```env
DEBUG=True

SECRET_KEY=your_secret_key

DATABASE_URL=postgresql://postgres:password@localhost:5432/fonaqo

REDIS_URL=redis://127.0.0.1:6379

ALLOWED_HOSTS=127.0.0.1,localhost
```

---

# PostgreSQL + PostGIS

```sql
CREATE DATABASE fonaqo;

CREATE EXTENSION postgis;
```

---

# Run Migrations

```bash
python manage.py migrate
```

# Create Superuser

```bash
python manage.py createsuperuser
```

# Run Server

```bash
python manage.py runserver
```

# ⚡ Run Redis

```bash
redis-server
```

# ⚡ Run Celery

```bash
celery -A config worker -l info
```

---

# API Structure

```txt
/api/v1/auth/
/api/v1/accounts/
/api/v1/missions/
/api/v1/services/
/api/v1/wallet/
/api/v1/chat/
/api/v1/notifications/
```

---

# Authentication

```http
Authorization: Bearer your_access_token
```

---

# Mission Workflow

```txt
Mission Created
↓
Agent Accepts
↓
Escrow Locked
↓
Agent Tracking Active
↓
Proof Upload
↓
QR Validation
↓
Mission Completed
↓
Escrow Released
↓
Wallet Credited
```

---

# AI-Ready Architecture

The backend is structured to support:
- smart service search
- AI recommendations
- fraud detection
- predictive scoring
- intelligent matching

---

# Admin Dashboard

Features:
- revenue tracking
- escrow monitoring
- KYC validation
- dispute management
- analytics
- fraud monitoring

---

# Mobile App

Frontend mobile application is built with:
- Flutter
- Clean Architecture
- Real-time tracking
- Firebase Notifications

---

# Future Improvements

- AI-powered mission matching
- Voice-based search
- Smart pricing engine
- Multi-country support
- Advanced analytics
- Insurance integrations
- Enterprise dashboard

---

# Development Status

## Current Status
Backend Core Architecture Completed ✅

### Completed Modules
- Accounts
- Missions
- Wallet
- Escrow
- Chat
- Notifications
- KYC
- Boosts
- Admin Dashboard
- Tracking System

### In Progress
- API Endpoints
- Celery Tasks
- Recommendation Engine
- Ratings System

---

# Contributing

1. Fork repository
2. Create feature branch
3. Commit changes
4. Open Pull Request

---

# License

Private
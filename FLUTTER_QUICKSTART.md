# 🚀 FONAQO - Guide Intégration Flutter

## 🔗 Connexion au Serveur
- **Base URL (Local)**: `http://<TON_IP_LOCALE>:8000/api/v1/`
- **WebSockets Chat**: `ws://<TON_IP_LOCALE>:8000/ws/chat/<mission_id>/`
- **WebSockets GPS**: `ws://<TON_IP_LOCALE>:8000/ws/gps/<mission_id>/`

## 📦 Format des Réponses (Standardisé)
Toutes les API renvoient :
- `status`: "success" ou "error"
- `message`: Texte à afficher à l'utilisateur
- `data`: Objet ou Liste de données
- `errors`: Détails si status == "error"

## 🚦 Statuts Mission (Enums)
Utiliser exactement ces strings :
- `PENDING`, `ACCEPTED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`

## 🔑 Authentification
- Utiliser le header : `Authorization: Bearer <token>`
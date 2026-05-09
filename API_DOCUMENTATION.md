# 🚀 FONAQO API Documentation (v1)
**Base URL:** `http://<server-ip>/api/v1/`

## 🔑 Authentification
| Endpoint | Méthode | Description |
| :--- | :--- | :--- |
| `accounts/register/` | POST | Inscription (phone_number, password, role). |
| `accounts/login/` | POST | Retourne le Token JWT. |
| `accounts/profile/` | GET/PATCH | Gérer les infos KYC, Score et fcm_token. |

## 📋 Missions & Timeline
| Endpoint | Méthode | Description |
| :--- | :--- | :--- |
| `missions/` | GET | Liste des missions PENDING (Query params: `lat`, `lng`). |
| `missions/` | POST | Créer une mission (Client). |
| `missions/{id}/accept/` | POST | L'agent accepte la mission (Fonds bloqués). |
| `missions/{id}/update_steps/` | POST | Mise à jour Timeline (Status + Latitude + Longitude). |
| `missions/{id}/submit_completion/` | POST | Agent envoie la photo de preuve (`end_photo`). |
| `missions/{id}/validate_completion/` | POST | Client valide via `method: QR_SCAN` ou `CLIENT_CLICK`. |
| `missions/{id}/open_dispute/` | POST | Ouvre un litige et gèle l'argent. |

## 💰 Wallet & Payments
| Endpoint | Méthode | Description |
| :--- | :--- | :--- |
| `wallets/me/` | GET | Voir solde disponible et solde séquestre. |
| `wallets/transactions/` | GET | Historique (Dépôts, Gains, Boosts). |
| `payments/deposit/` | POST | Recharger via MoMo/Flooz. |

## 🏷️ Services & Recherche
| Endpoint | Méthode | Description |
| :--- | :--- | :--- |
| `services/categories/` | GET | Liste des catégories (SBEE, Mairie, Marché...). |
| `services/search/` | GET | Recherche intelligente (Query param: `q`). |

## 🛠 Spécifications Techniques
- **Auth:** Utiliser le Header `Authorization: Bearer <token>`.
- **Géo:** Les positions sont au format **GeoJSON**.
- **Images:** Utiliser `multipart/form-data` pour les uploads.
# 🚀 FONAQO Backend - Deployment Checklist

## 📋 PRÉ-DÉPLOIEMENT

### ✅ Vérifications obligatoires
- [ ] Backup de la base de données existante
- [ ] Backup du code actuel (git tag)
- [ ] Vérifier que toutes les dépendances sont dans `requirements.txt`
- [ ] S'assurer que les variables d'environnement sont correctes

---

## 🔧 COMMANDES DE DÉPLOIEMENT

### 1. **Activation de l'environnement virtuel**
```bash
# Si vous utilisez venv
source venv/bin/activate

# Si vous utilisez conda
conda activate fonaqo_back
```

### 2. **Installation des dépendances**
```bash
pip install -r requirements.txt
```

### 3. **Création des migrations pour les nouvelles apps**
```bash
# Créer les migrations pour les 5 nouvelles apps
python manage.py makemigrations boosts
python manage.py makemigrations disputes
python manage.py makemigrations chat_enhanced
python manage.py makemigrations missions_enhanced
python manage.py makemigrations statistics

# Optionnel: Créer toutes les migrations d'un coup
python manage.py makemigrations
```

### 4. **Application des migrations**
```bash
# Appliquer toutes les migrations
python manage.py migrate

# Vérifier l'état des migrations
python manage.py showmigrations
```

### 5. **Collecte des fichiers statiques**
```bash
python manage.py collectstatic --noinput
```

### 6. **Création des données initiales**
```bash
# Charger les données de base si nécessaire
python manage.py loaddata fixtures/initial_data.json

# Créer un superutilisateur si besoin
python manage.py createsuperuser
```

### 7. **Tests de validation**
```bash
# Lancer les tests des nouvelles apps
python manage.py test apps.boosts
python manage.py test apps.disputes
python manage.py test apps.chat_enhanced
python manage.py test apps.missions_enhanced
python manage.py test apps.statistics

# Lancer tous les tests
python manage.py test
```

---

## 🧪 VÉRIFICATIONS POST-DÉPLOIEMENT

### 1. **Vérification des endpoints**
```bash
# Test de santé des nouvelles APIs
curl -X GET http://localhost:8000/api/v1/boosts/plans/
curl -X GET http://localhost:8000/api/v1/disputes/
curl -X GET http://localhost://8000/api/v1/chat-enhanced/conversations/
curl -X GET http://localhost:8000/api/v1/missions-enhanced/proofs/
curl -X GET http://localhost:8000/api/v1/statistics/
```

### 2. **Vérification de la documentation API**
```bash
# Accéder à la documentation Swagger
http://localhost:8000/api/docs/
```

### 3. **Vérification des permissions**
```bash
# Tester sans authentification (doit retourner 401)
curl -X GET http://localhost:8000/api/v1/boosts/plans/

# Tester avec authentification
curl -X GET http://localhost:8000/api/v1/boosts/plans/ \
  -H "Authorization: Bearer VOTRE_TOKEN"
```

---

## 🔄 REDÉMARRAGE DES SERVICES

### **Django Development Server**
```bash
# Arrêter le serveur (Ctrl+C)
# Redémarrer
python manage.py runserver
```

### **Production (Gunicorn/Nginx)**
```bash
# Redémarrer Gunicorn
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# Vérifier les logs
sudo journalctl -u gunicorn -f
```

---

## 🚨 DÉPANNAGE

### **Problèmes courants**

#### Migration échouée
```bash
# Afficher les erreurs de migration
python manage.py migrate --verbosity=2

# Forcer une migration spécifique
python manage.py migrate boosts 0001 --fake
```

#### Imports manquants
```bash
# Vérifier les imports manquants
python manage.py check
```

#### Permissions refusées
```bash
# Vérifier les permissions
python manage.py shell
>>> from rest_framework.permissions import IsAuthenticated
>>> print("Imports OK")
```

---

## 📊 MONITORING POST-DÉPLOIEMENT

### **Logs à surveiller**
- Django logs: `logs/django.log`
- Gunicorn logs: `/var/log/gunicorn/`
- Nginx logs: `/var/log/nginx/`

### **Métriques à vérifier**
- Temps de réponse des APIs
- Taux d'erreur 401/403
- Utilisation mémoire/CPU

---

## 🎯 VALIDATION FINALE

### Checklist de validation
- [ ] Toutes les migrations appliquées avec succès
- [ ] Les 5 nouvelles apps répondent correctement
- [ ] La documentation API est accessible
- [ ] Les permissions fonctionnent (401 sans token)
- [ ] Les tests passent avec succès
- [ ] Les fichiers statiques sont servis
- [ ] Le serveur est stable

---

## 📝 NOTES IMPORTANTES

### **Nouveaux modèles créés**
- `BoostPlan`, `AgentBoost` (boosts)
- `Dispute`, `DisputeEvidence`, `DisputeComment` (disputes)
- `Conversation`, `Message`, `TypingStatus` (chat_enhanced)
- `MissionProof`, `MissionTimelineEvent`, `AgentStatistics` (missions_enhanced)
- `AgentStatistics` (statistics)

### **Nouveaux endpoints**
- 66 nouveaux endpoints API au total
- Préfixe: `/api/v1/` déjà configuré
- Permissions: `IsAuthenticated` par défaut

### **Dépendances ajoutées**
- `openai`, `numpy`, `scikit-learn`, `geopy` (déjà dans requirements.txt)

---

## 🚀 **GO!**

Une fois toutes ces étapes validées, vous pouvez pousser sur GitHub :

```bash
git add .
git commit -m "feat: Add 5 new backend apps (Boosts, Disputes, Chat Enhanced, Missions Enhanced, Statistics)"
git push origin main
```

**✅ Le backend est prêt pour la production !**

#!/bin/bash

# Script de déploiement des contributions backend FONAQO
# Usage: bash deploy_to_fonaqo.sh

echo "🚀 Déploiement des contributions backend FONAQO..."

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "manage.py" ]; then
    echo -e "${RED}Erreur: Ce script doit être exécuté depuis la racine du projet fonaqo_backend${NC}"
    echo "Usage:"
    echo "  cd /chemin/vers/fonaqo_backend"
    echo "  bash /workspace/backend_contributions/scripts/deploy_to_fonaqo.sh"
    exit 1
fi

echo -e "${GREEN}✓ Projet Django détecté${NC}"

# 1. Copier les applications
echo -e "${YELLOW}📦 Copie des applications...${NC}"
cp -r /workspace/backend_contributions/apps/* ./apps/ 2>/dev/null || {
    echo -e "${RED}✗ Erreur lors de la copie des apps${NC}"
    exit 1
}
echo -e "${GREEN}✓ Applications copiées${NC}"

# 2. Mettre à jour settings.py
echo -e "${YELLOW}⚙️  Mise à jour de settings.py...${NC}"

# Vérifier si les apps sont déjà dans INSTALLED_APPS
if grep -q "apps.ai_search" settings.py; then
    echo -e "${GREEN}✓ apps.ai_search déjà présent${NC}"
else
    sed -i "/^INSTALLED_APPS = \[/a\    'apps.ai_search'," settings.py
    echo -e "${GREEN}✓ apps.ai_search ajouté${NC}"
fi

if grep -q "apps.opportunities" settings.py; then
    echo -e "${GREEN}✓ apps.opportunities déjà présent${NC}"
else
    sed -i "/^INSTALLED_APPS = \[/a\    'apps.opportunities'," settings.py
    echo -e "${GREEN}✓ apps.opportunities ajouté${NC}"
fi

# 3. Mettre à jour urls.py
echo -e "${YELLOW}🔗 Mise à jour de urls.py...${NC}"

if grep -q "ai/" urls.py; then
    echo -e "${GREEN}✓ URL ai/ déjà présente${NC}"
else
    sed -i "/urlpatterns = \[/a\    path('api/ai/', include('apps.ai_search.urls'))," urls.py
    echo -e "${GREEN}✓ URL ai/ ajoutée${NC}"
fi

if grep -q "opportunities/" urls.py; then
    echo -e "${GREEN}✓ URL opportunities/ déjà présente${NC}"
else
    sed -i "/urlpatterns = \[/a\    path('api/opportunities/', include('apps.opportunities.urls'))," urls.py
    echo -e "${GREEN}✓ URL opportunities/ ajoutée${NC}"
fi

# 4. Lancer les migrations
echo -e "${YELLOW}🗄️  Exécution des migrations...${NC}"
python manage.py makemigrations apps.ai_search apps.opportunities
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migrations créées${NC}"
else
    echo -e "${RED}✗ Erreur lors de la création des migrations${NC}"
    exit 1
fi

python manage.py migrate
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migrations appliquées${NC}"
else
    echo -e "${RED}✗ Erreur lors de l'application des migrations${NC}"
    exit 1
fi

# 5. Créer des données de test (optionnel)
echo -e "${YELLOW}📝 Création de données de test...${NC}"
cat << 'EOF' | python manage.py shell
from apps.opportunities.models import Opportunity

# Créer quelques opportunités de test
if Opportunity.objects.count() == 0:
    Opportunity.objects.create(
        title='Standard Chartered CI',
        description='Services bancaires complets',
        category='banque',
        location='Plateau, Abidjan',
        price_range='À partir de 0 FCFA',
        rating=4.9,
        is_open=True
    )
    
    Opportunity.objects.create(
        title='Express Delivery Plus',
        description='Livraison rapide de documents',
        category='livraison',
        location='Cocody, Abidjan',
        price_range='2 500 FCFA / km',
        rating=4.7,
        is_open=True
    )
    
    print('✓ Données de test créées')
else:
    print('✓ Des opportunités existent déjà')
EOF

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}🎉 Déploiement terminé avec succès !${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}Prochaines étapes :${NC}"
echo "1. Tester les endpoints :"
echo "   curl http://localhost:8000/api/opportunities/"
echo "   curl -X POST http://localhost:8000/api/ai/search-agents/ -H 'Content-Type: application/json' -d '{\"query\": \"Besoin aide banque\"}'"
echo ""
echo "2. Démarrer le serveur :"
echo "   python manage.py runserver"
echo ""

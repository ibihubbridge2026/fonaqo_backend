#!/usr/bin/env python
"""
Script pour peupler la base de données avec des agents répartis géographiquement
Exécuter avec: python manage.py shell < seed_agents.py
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.models import User

# Coordonnées réelles des villes ivoiriennes
AGENT_LOCATIONS = [
    # Abidjan et environs
    {"name": "Kouadio Yves", "email": "agent1@fonaqo.ci", "phone": "+2250700000001", "city": "Abidjan", "lat": 5.3600, "lng": -3.9788, "address": "Plateau, Abidjan"},
    {"name": "Bamba Mohamed", "email": "agent2@fonaqo.ci", "phone": "+2250700000002", "city": "Abidjan", "lat": 5.3599, "lng": -3.9786, "address": "Cocody, Abidjan"},
    {"name": "Touré Aminata", "email": "agent3@fonaqo.ci", "phone": "+2250700000003", "city": "Abidjan", "lat": 5.3601, "lng": -3.9790, "address": "Yopougon, Abidjan"},
    {"name": "Koné Bakary", "email": "agent4@fonaqo.ci", "phone": "+2250700000004", "city": "Abidjan", "lat": 5.3598, "lng": -3.9785, "address": "Treichville, Abidjan"},
    {"name": "Sangaré Fatou", "email": "agent5@fonaqo.ci", "phone": "+2250700000005", "city": "Abidjan", "lat": 5.3602, "lng": -3.9789, "address": "Marcory, Abidjan"},
    
    # Grand-Bassam
    {"name": "Assamoi Jean", "email": "agent6@fonaqo.ci", "phone": "+2250700000006", "city": "Grand-Bassam", "lat": 5.2111, "lng": -3.7444, "address": "Grand-Bassam Centre"},
    
    # San Pedro
    {"name": "Lago Paul", "email": "agent7@fonaqo.ci", "phone": "+2250700000007", "city": "San Pedro", "lat": 4.7500, "lng": -6.6167, "address": "Port de San Pedro"},
    
    # Bouaké
    {"name": "Koné Mamadou", "email": "agent8@fonaqo.ci", "phone": "+2250700000008", "city": "Bouaké", "lat": 7.7833, "lng": -5.0833, "address": "Centre-ville, Bouaké"},
    
    # Yamoussoukro
    {"name": "Bédie Yao", "email": "agent9@fonaqo.ci", "phone": "+2250700000009", "city": "Yamoussoukro", "lat": 6.8167, "lng": -5.2833, "address": "Yamoussoukro Centre"},
    
    # Daloa
    {"name": "Ouattara Mariam", "email": "agent10@fonaqo.ci", "phone": "+2250700000010", "city": "Daloa", "lat": 6.8667, "lng": -6.4500, "address": "Daloa Marché"},
    
    # Korhogo
    {"name": "Soro Adama", "email": "agent11@fonaqo.ci", "phone": "+2250700000011", "city": "Korhogo", "lat": 9.4500, "lng": -5.3833, "address": "Korhogo Centre"},
    
    # Gagnoa
    {"name": "Gbahi Etienne", "email": "agent12@fonaqo.ci", "phone": "+2250700000012", "city": "Gagnoa", "lat": 6.1333, "lng": -5.9333, "address": "Gagnoa Ville"},
    
    # Man
    {"name": "Kouamé Ben", "email": "agent13@fonaqo.ci", "phone": "+2250700000013", "city": "Man", "lat": 7.4000, "lng": -7.5500, "address": "Man Centre"},
    
    # Soubré
    {"name": "Yeo Koffi", "email": "agent14@fonaqo.ci", "phone": "+2250700000014", "city": "Soubré", "lat": 5.8167, "lng": -6.6167, "address": "Soubré Marché"},
    
    # Séguela
    {"name": "Konan Awa", "email": "agent15@fonaqo.ci", "phone": "+2250700000015", "city": "Séguela", "lat": 8.0167, "lng": -6.6667, "address": "Séguela Centre"},
]

def create_agents():
    """Crée des agents avec leurs coordonnées géographiques"""
    User = get_user_model()
    created_count = 0
    
    for agent_data in AGENT_LOCATIONS:
        # Vérifier si l'agent existe déjà
        if User.objects.filter(email=agent_data['email']).exists():
            print(f"Agent {agent_data['email']} existe déjà, skip...")
            continue
        
        # Créer l'agent
        agent = User.objects.create_user(
            email=agent_data['email'],
            phone_number=agent_data['phone'],
            first_name=agent_data['name'].split()[0],
            last_name=' '.join(agent_data['name'].split()[1:]) if len(agent_data['name'].split()) > 1 else '',
            password='Agent123!',  # Mot de passe par défaut
            is_agent=True,
            is_verified=True,  # Tous les agents sont vérifiés pour le seed
            latitude=agent_data['lat'],
            longitude=agent_data['lng'],
            address=agent_data['address'],
            city=agent_data['city'],
            profile_picture=f'https://picsum.photos/seed/{agent_data["email"]}/200/200.jpg'
        )
        
        created_count += 1
        print(f"✅ Agent créé: {agent.name} à {agent.city}")
    
    print(f"\n🎉 {created_count} agents créés avec succès!")
    print(f"📍 Agents répartis dans {len(set(loc['city'] for loc in AGENT_LOCATIONS))} villes")

def create_sample_missions():
    """Crée quelques missions de test"""
    from apps.missions.models import Mission, MissionStatus
    from apps.accounts.models import User
    
    # Récupérer les agents
    agents = User.objects.filter(is_agent=True, is_verified=True)
    if not agents.exists():
        print("❌ Aucun agent trouvé. Exécutez d'abord create_agents()")
        return
    
    # Récupérer ou créer un client
    client_email = "client_test@fonaqo.ci"
    if not User.objects.filter(email=client_email).exists():
        client = User.objects.create_user(
            email=client_email,
            phone_number="+2250700000099",
            first_name="Client",
            last_name="Test",
            password='Client123!',
            is_agent=False
        )
    else:
        client = User.objects.get(email=client_email)
    
    # Créer quelques missions
    missions_data = [
        {
            "title": "Livraison de documents à Cocody",
            "description": "Besoin de livrer des documents importants au bureau de Cocody",
            "category": "Livraison",
            "price": 2500.0,
            "address": "Cocody, Abidjan",
            "latitude": 5.3599,
            "longitude": -3.9786,
        },
        {
            "title": "Course urgente à Plateau",
            "description": "Récupérer un colis au Plateau et le livrer à Yopougon",
            "category": "Course",
            "price": 3500.0,
            "address": "Plateau, Abidjan",
            "latitude": 5.3600,
            "longitude": -3.9788,
        },
        {
            "title": "Achat au marché de Grand-Bassam",
            "description": "Acheter des produits spécifiques au marché de Grand-Bassam",
            "category": "Achat",
            "price": 4000.0,
            "address": "Grand-Bassam",
            "latitude": 5.2111,
            "longitude": -3.7444,
        },
    ]
    
    created_count = 0
    for mission_data in missions_data:
        if Mission.objects.filter(title=mission_data['title']).exists():
            print(f"Mission '{mission_data['title']}' existe déjà, skip...")
            continue
        
        mission = Mission.objects.create(
            client=client,
            title=mission_data['title'],
            description=mission_data['description'],
            category=mission_data['category'],
            price=mission_data['price'],
            address=mission_data['address'],
            latitude=mission_data['latitude'],
            longitude=mission_data['longitude'],
            status=MissionStatus.PENDING
        )
        
        created_count += 1
        print(f"✅ Mission créée: {mission.title}")
    
    print(f"\n🎉 {created_count} missions créées avec succès!")

if __name__ == "__main__":
    print("🌱 Création des agents et missions de test...")
    print("=" * 50)
    
    create_agents()
    print()
    create_sample_missions()
    
    print("\n✨ Seed terminé! Vous pouvez maintenant tester les suggestions d'agents.")

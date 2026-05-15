from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.missions.models import Mission, MissionStatus

User = get_user_model()

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

class Command(BaseCommand):
    help = 'Crée des agents de test répartis géographiquement en Côte d\'Ivoire'

    def handle(self, *args, **options):
        self.stdout.write("🌱 Création des agents de test...")
        self.stdout.write("=" * 50)
        
        created_count = 0
        
        for agent_data in AGENT_LOCATIONS:
            # Vérifier si l'agent existe déjà
            if User.objects.filter(email=agent_data['email']).exists():
                self.stdout.write(f"Agent {agent_data['email']} existe déjà, skip...")
                continue
            
            # Créer l'agent
            name_parts = agent_data['name'].split()
            agent = User.objects.create_user(
                username=agent_data['email'],  # Utiliser email comme username
                email=agent_data['email'],
                phone_number=agent_data['phone'],
                first_name=name_parts[0],
                last_name=' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
                password='Agent123!',  # Mot de passe par défaut
                is_agent=True,
                is_verified=True,  # Tous les agents sont vérifiés pour le seed
            )
            
            # Mettre à jour les champs additionnels
            agent.latitude = agent_data['lat']
            agent.longitude = agent_data['lng']
            agent.address = agent_data['address']
            agent.city = agent_data['city']
            agent.profile_picture = f'https://picsum.photos/seed/{agent_data["email"]}/200/200.jpg'
            agent.save()
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"✅ Agent créé: {agent.get_full_name()} à {agent.city}"))
        
        self.stdout.write(f"\n🎉 {created_count} agents créés avec succès!")
        self.stdout.write(f"📍 Agents répartis dans {len(set(loc['city'] for loc in AGENT_LOCATIONS))} villes")
        
        # Créer un client de test
        client_email = "client_test@fonaqo.ci"
        if not User.objects.filter(email=client_email).exists():
            client = User.objects.create_user(
                username=client_email,
                email=client_email,
                phone_number="+2250700000099",
                first_name="Client",
                last_name="Test",
                password='Client123!',
                is_agent=False
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Client test créé: {client.email}"))
        
        # Créer quelques missions de test
        self.create_sample_missions()
        
        self.stdout.write(self.style.SUCCESS("\n✨ Seed terminé! Vous pouvez maintenant tester les suggestions d'agents."))

    def create_sample_missions(self):
        """Crée quelques missions de test"""
        from django.contrib.gis.geos import Point
        client = User.objects.get(email="client_test@fonaqo.ci")
        
        missions_data = [
            {
                "title": "Livraison de documents à Cocody",
                "description": "Besoin de livrer des documents importants au bureau de Cocody",
                "price": 2500.0,
                "address": "Cocody, Abidjan",
                "latitude": 5.3599,
                "longitude": -3.9786,
            },
            {
                "title": "Course urgente à Plateau",
                "description": "Récupérer un colis au Plateau et le livrer à Yopougon",
                "price": 3500.0,
                "address": "Plateau, Abidjan",
                "latitude": 5.3600,
                "longitude": -3.9788,
            },
            {
                "title": "Achat au marché de Grand-Bassam",
                "description": "Acheter des produits spécifiques au marché de Grand-Bassam",
                "price": 4000.0,
                "address": "Grand-Bassam",
                "latitude": 5.2111,
                "longitude": -3.7444,
            },
        ]
        
        created_count = 0
        for mission_data in missions_data:
            if Mission.objects.filter(title=mission_data['title']).exists():
                self.stdout.write(f"Mission '{mission_data['title']}' existe déjà, skip...")
                continue
            
            # Créer un point géographique
            location_point = Point(mission_data['longitude'], mission_data['latitude'])
            
            mission = Mission.objects.create(
                client=client,
                title=mission_data['title'],
                description=mission_data['description'],
                price=mission_data['price'],
                address=mission_data['address'],
                location=location_point,
                status=MissionStatus.PENDING
            )
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"✅ Mission créée: {mission.title}"))
        
        self.stdout.write(f"\n🎉 {created_count} missions créées avec succès!")

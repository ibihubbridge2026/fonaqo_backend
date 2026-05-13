import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from faker import Faker
from apps.wallets.models import Wallet
from apps.missions.models import Mission
from apps.core.choices import MissionStatus

User = get_user_model()
fake = Faker(['fr_FR'])

class Command(BaseCommand):
    help = "Génère des données fictives pour le développement Flutter"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("🚀 Début du seeding..."))

        # 1. Récupération ou création d'utilisateurs
        users = list(User.objects.all())
        if len(users) < 10:
            # Créer des agents avec positions GPS réelles à Cotonou
            cotonou_locations = [
                {"name": "Fidjrossè", "lat": 6.3676, "lng": 2.4412},
                {"name": "Cadjehoun", "lat": 6.3834, "lng": 2.4483},
                {"name": "Akpakpa", "lat": 6.3724, "lng": 2.4532},
            ]
            
            for i in range(10):
                location = random.choice(cotonou_locations)
                phone = f"01{random.randint(10000000, 99999999)}"
                user = User.objects.create_user(
                    phone_number=phone,
                    username=fake.user_name(),
                    email=fake.email(),
                    is_verified=True,
                    password="password123"
                )
                
                # Créer un profil agent avec position GPS
                from apps.agents.models import AgentProfile
                AgentProfile.objects.create(
                    user=user,
                    bio=fake.text(max_nb_chars=100),
                    rating=round(random.uniform(3.5, 5.0), 1),
                    total_missions=random.randint(5, 50),
                    is_available=True,
                    latitude=location["lat"],
                    longitude=location["lng"],
                    address=f"{location['name']}, Cotonou, Bénin"
                )
                users.append(user)

        # 2. CRUCIAL : On remplit les portefeuilles d'abord !
        self.stdout.write("💰 Remplissage des portefeuilles pour éviter les erreurs d'Escrow...")
        for user in users:
            wallet, _ = Wallet.objects.get_or_create(user=user)
            wallet.balance = 1000000 # On donne 1 million à tout le monde pour le test
            wallet.save()

        # 3. Création des Missions
        self.stdout.write("📝 Création des missions...")
        # Coordonnées GPS réelles de Cotonou pour les agents
        cotonou_locations = [
            {"name": "Fidjrossè", "lat": 6.3676, "lng": 2.4412},
            {"name": "Cadjehoun", "lat": 6.3834, "lng": 2.4483},
            {"name": "Akpakpa", "lat": 6.3724, "lng": 2.4532},
        ]
        
        for i in range(15):
            location = random.choice(cotonou_locations)
            random_point = Point(location["lat"], location["lng"]) 
            
            # On choisit un client au hasard parmi nos utilisateurs riches
            client = random.choice(users)
            
            try:
                Mission.objects.create(
                    client=client,
                    title=fake.sentence(nb_words=4),
                    description=fake.text(max_nb_chars=200),
                    address=fake.address(),
                    location=random_point,
                    price=5000, # Petit prix pour être sûr que ça passe
                    service_fee=500,
                    status=MissionStatus.PENDING
                )
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f"❌ Échec pour une mission : {e}"))

        self.stdout.write(self.style.SUCCESS(f"✨ Seed terminé ! Le dév Flutter va être content."))
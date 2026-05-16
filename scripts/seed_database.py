#!/usr/bin/env python3
"""
Script de seeding de la base de données FONACO
Crée les comptes de test et les données initiales pour le développement
Utilisation: python manage.py shell < scripts/seed_database.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
import random

# Configuration de l'environnement Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from apps.accounts.models import User
from apps.missions.models import Mission, MissionTimeline
from apps.wallets.models import Wallet, Transaction as WalletTransaction
from apps.services.models import Service, ServiceCategory
from apps.statistics.models import UserRating, AgentStats
from apps.payments.models import Payment
from apps.disputes.models import Dispute

User = get_user_model()

def create_admin_user():
    """Crée le compte administrateur unique"""
    print("👤 Création du compte administrateur...")
    
    try:
        admin_user = User.objects.create_user(
            phone='0150088210',
            password='password123',
            email='admin@fonaco.bj',
            first_name='Super',
            last_name='Admin',
            role='SUPER_ADMIN',
            is_verified=True,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        
        # Créer son wallet
        Wallet.objects.create(
            user=admin_user,
            balance=100000.0,  # 100 000 FCFA pour les tests
            currency='XOF'
        )
        
        print(f"✅ Admin créé: {admin_user.phone}")
        return admin_user
        
    except Exception as e:
        print(f"⚠️  Erreur création admin: {e}")
        return None

def create_test_clients():
    """Crée 2 comptes clients test positionnés à Cotonou"""
    print("👥 Création des comptes clients test...")
    
    clients_data = [
        {
            'phone': '0101010101',
            'password': 'password123',
            'email': 'client1@fonaco.bj',
            'first_name': 'Jean',
            'last_name': 'Client',
            'role': 'CLIENT',
            'latitude': 6.3735,  # Cadjèhoun, Cotonou
            'longitude': 2.3904,
            'address': 'Cadjèhoun, Cotonou, Bénin'
        },
        {
            'phone': '0202020202',
            'password': 'password123',
            'email': 'client2@fonaco.bj',
            'first_name': 'Marie',
            'last_name': 'Client',
            'role': 'CLIENT',
            'latitude': 6.3515,  # Fidjrossè, Cotonou
            'longitude': 2.4133,
            'address': 'Fidjrossè, Cotonou, Bénin'
        }
    ]
    
    clients = []
    
    for client_data in clients_data:
        try:
            client = User.objects.create_user(
                phone=client_data['phone'],
                password=client_data['password'],
                email=client_data['email'],
                first_name=client_data['first_name'],
                last_name=client_data['last_name'],
                role=client_data['role'],
                is_verified=True,
                is_active=True,
                latitude=client_data['latitude'],
                longitude=client_data['longitude'],
                address=client_data['address'],
            )
               
            # Créer son wallet
            Wallet.objects.create(
                user=client,
                balance=50000.0,  # 50 000 FCFA pour les tests  
                currency='XOF'
            )
            
            print(f"✅ Client créé: {client.phone} ({client.address})")
            clients.append(client)
            
        except Exception as e:
            print(f"⚠️  Erreur création client {client_data['phone']}: {e}")
    
    return clients

def create_test_agents():
    """Crée 2 comptes agents test positionnés dans la même zone"""
    print("🚚 Création des comptes agents test...")
    
    agents_data = [
        {
            'phone': '0303030303', 
            'password': 'password123',
            'email': 'agent1@fonaco.bj',
            'first_name': 'Paul',
            'last_name': 'Agent',
            'role': 'AGENT',
            'latitude': 6.3735,  # Cadjèhoun, Cotonou
            'longitude': 2.3904,
            'address': 'Cadjèhoun, Cotonou, Bénin',
            'specialty': 'Livraison Express',
            'is_online': True,
            'is_available': True,
        },
        {
            'phone': '0404040404',
            'password': 'password123',
            'email': 'agent2@fonaco.bj',
            'first_name': 'Sophie',
            'last_name': 'Agent',
            'role': 'AGENT',
            'latitude': 6.3515,  # Fidjrossè, Cotonou
            'longitude': 2.4133,
            'address': 'Fidjrossè, Cotonou, Bénin',
            'specialty': 'Courses Personnelles',
            'is_online': True,
            'is_available': True,
        }
    ]
    
    agents = []
    
    for agent_data in agents_data:
        try:
            agent = User.objects.create_user(
                phone=agent_data['phone'],
                password=agent_data['password'],
                email=agent_data['email'],
                first_name=agent_data['first_name'],
                last_name=agent_data['last_name'],
                role=agent_data['role'],
                is_verified=True,
                is_active=True,
                latitude=agent_data['latitude'],
                longitude=agent_data['longitude'],
                address=agent_data['address'],
                specialty=agent_data['specialty'],
                is_online=agent_data['is_online'],
                is_available=agent_data['is_available'],
            )
            
            # Créer son wallet
            Wallet.objects.create(
                user=agent,
                balance=25000.0,  # 25 000 FCFA pour les tests
                currency='XOF'
            )
            
            # Créer ses statistiques agent
            AgentStats.objects.create(
                agent=agent,
                total_missions_completed=0,
                total_earnings=0.0,
                average_rating=5.0,
                response_time_minutes=5,
                completion_rate=100.0,
            )
            
            print(f"✅ Agent créé: {agent.phone} ({agent.address}) - {agent.specialty}")
            agents.append(agent)
            
        except Exception as e:
            print(f"⚠️  Erreur création agent {agent_data['phone']}: {e}")
    
    return agents

def create_service_categories():
    """Crée les catégories de services"""
    print("📂 Création des catégories de services...")
    
    categories_data = [
        {'name': 'Livraison', 'description': 'Services de livraison express', 'icon': 'delivery'},
        {'name': 'Courses', 'description': 'Courses personnelles et achats', 'icon': 'shopping'},
        {'name': 'Transport', 'description': 'Transport de personnes et biens', 'icon': 'directions_car'},
        {'name': 'Assistance', 'description': 'Services d\'assistance technique', 'icon': 'support'},
        {'name': 'Ménage', 'description': 'Services de nettoyage et entretien', 'icon': 'cleaning'},
        {'name': 'Garde', 'description': 'Garde d\'enfants et animaux', 'icon': 'pets'},
    ]
    
    categories = []
    
    for cat_data in categories_data:
        try:
            category = ServiceCategory.objects.create(
                name=cat_data['name'],
                description=cat_data['description'],
                icon=cat_data['icon'],
                is_active=True,
            )
            print(f"✅ Catégorie créée: {category.name}")
            categories.append(category)
            
        except Exception as e:
            print(f"⚠️  Erreur création catégorie {cat_data['name']}: {e}")
    
    return categories

def create_test_missions(clients, agents):
    """Crée la matrice de missions de test (6 missions au total)"""
    print("📋 Création de la matrice de missions de test...")
    
    missions = []
    
    # 2 Missions COMPLETED (Terminées)
    completed_missions_data = [
        {
            'client': clients[0],
            'title': 'Livraison de documents urgents',
            'description': 'Livraison de documents administratifs au ministère',
            'category': 'Livraison',
            'pickup_address': 'Cadjèhoun, Cotonou',
            'delivery_address': 'Plateau, Cotonou',
            'budget': 3000.0,
            'status': 'COMPLETED',
            'created_at': datetime.now() - timedelta(days=5),
            'completed_at': datetime.now() - timedelta(days=4),
            'assigned_agent': agents[0],
            'rating': 5,
            'comment': 'Excellent service, rapide et professionnel',
        },
        {
            'client': clients[1],
            'title': 'Courses au supermarché',
            'description': 'Achats de provisions pour la semaine',
            'category': 'Courses',
            'pickup_address': 'Fidjrossè, Cotonou',
            'delivery_address': 'Fidjrossè, Cotonou',
            'budget': 5000.0,
            'status': 'COMPLETED',
            'created_at': datetime.now() - timedelta(days=3),
            'completed_at': datetime.now() - timedelta(days=2),
            'assigned_agent': agents[1],
            'rating': 4,
            'comment': 'Bon service, un peu cher mais efficace',
        },
    ]
    
    # 2 Missions CANCELED (Annulées)
    canceled_missions_data = [
        {
            'client': clients[0],
            'title': 'Transport aéroport',
            'description': 'Transport vers l\'aéroport de Cotonou',
            'category': 'Transport',
            'pickup_address': 'Cadjèhoun, Cotonou',
            'delivery_address': 'Aéroport Cadjèhoun',
            'budget': 8000.0,
            'status': 'CANCELED',
            'created_at': datetime.now() - timedelta(days=2),
            'canceled_at': datetime.now() - timedelta(days=1),
            'cancellation_reason': 'Vol annulé par le client',
            'assigned_agent': agents[1],
        },
        {
            'client': clients[1],
            'title': 'Ménage d\'appartement',
            'description': 'Nettoyage complet d\'un 3 pièces',
            'category': 'Ménage',
            'pickup_address': 'Fidjrossè, Cotonou',
            'delivery_address': 'Fidjrossè, Cotonou',
            'budget': 10000.0,
            'status': 'CANCELED',
            'created_at': datetime.now() - timedelta(days=1),
            'canceled_at': datetime.now() - timedelta(hours=12),
            'cancellation_reason': 'Indisponibilité de l\'agent',
            'assigned_agent': agents[0],
        },
    ]
    
    # 2 Missions PENDING/IN_PROGRESS (En attente/En cours)
    active_missions_data = [
        {
            'client': clients[0],
            'title': 'Livraison repas chaud',
            'description': 'Livraison de repas commandés au restaurant',
            'category': 'Livraison',
            'pickup_address': 'Cadjèhoun, Cotonou',
            'delivery_address': 'Fidjrossè, Cotonou',
            'budget': 2000.0,
            'status': 'IN_PROGRESS',
            'created_at': datetime.now() - timedelta(hours=2),
            'assigned_agent': agents[1],
            'started_at': datetime.now() - timedelta(hours=1),
        },
        {
            'client': clients[1],
            'title': 'Garde d\'enfants soirée',
            'description': 'Garde de 2 enfants pour soirée sortante',
            'category': 'Garde',
            'pickup_address': 'Fidjrossè, Cotonou',
            'delivery_address': 'Fidjrossè, Cotonou',
            'budget': 15000.0,
            'status': 'PENDING',
            'created_at': datetime.now() - timedelta(minutes=30),
        },
    ]
    
    all_missions_data = completed_missions_data + canceled_missions_data + active_missions_data
    
    for mission_data in all_missions_data:
        try:
            mission = Mission.objects.create(
                client=mission_data['client'],
                title=mission_data['title'],
                description=mission_data['description'],
                category=mission_data['category'],
                pickup_address=mission_data['pickup_address'],
                delivery_address=mission_data['delivery_address'],
                budget=mission_data['budget'],
                status=mission_data['status'],
                created_at=mission_data['created_at'],
                pickup_latitude=clients[0].latitude if mission_data['client'] == clients[0] else clients[1].latitude,
                pickup_longitude=clients[0].longitude if mission_data['client'] == clients[0] else clients[1].longitude,
                delivery_latitude=clients[1].latitude if mission_data['client'] == clients[0] else clients[0].latitude,
                delivery_longitude=clients[1].longitude if mission_data['client'] == clients[0] else clients[0].longitude,
            )
            
            # Ajouter les timestamps spécifiques
            if 'completed_at' in mission_data:
                mission.completed_at = mission_data['completed_at']
            if 'canceled_at' in mission_data:
                mission.canceled_at = mission_data['canceled_at']
                mission.cancellation_reason = mission_data['cancellation_reason']
            if 'started_at' in mission_data:
                mission.started_at = mission_data['started_at']
            
            mission.save()
            
            # Créer le timeline de la mission si assigné
            if 'assigned_agent' in mission_data:
                # Timeline de début de mission
                if mission.status in ['COMPLETED', 'IN_PROGRESS']:
                    MissionTimeline.objects.create(
                        mission=mission,
                        status='ACCEPTED',
                        message='Mission acceptée par l\'agent',
                        created_at=mission_data.get('started_at', mission_data['created_at']),
                        created_by=mission_data['assigned_agent'],
                    )
                
                # Timeline de début de travail
                if mission.status == 'IN_PROGRESS':
                    MissionTimeline.objects.create(
                        mission=mission,
                        status='IN_PROGRESS',
                        message='Début de la mission',
                        location=f'POINT({mission_data["assigned_agent"].longitude} {mission_data["assigned_agent"].latitude})',
                        created_at=datetime.now(),
                        created_by=mission_data['assigned_agent'],
                    )
            
            # Créer l'évaluation si terminée
            if 'rating' in mission_data:
                UserRating.objects.create(
                    mission=mission,
                    client=mission.client,
                    agent=mission_data['assigned_agent'],
                    rating=mission_data['rating'],
                    comment=mission_data['comment'],
                    created_at=mission_data['completed_at'],
                )
                
                # Mettre à jour les statistiques de l'agent
                agent_stats = AgentStats.objects.get(agent=mission_data['assigned_agent'])
                agent_stats.total_missions_completed += 1
                agent_stats.total_earnings += mission.budget * 0.8  # 80% pour l'agent
                agent_stats.average_rating = ((agent_stats.average_rating * (agent_stats.total_missions_completed - 1)) + mission_data['rating']) / agent_stats.total_missions_completed
                agent_stats.save()
            
            # Créer les transactions wallet
            if mission.status == 'COMPLETED':
                # Transaction pour le client (débit)
                WalletTransaction.objects.create(
                    wallet=mission.client.wallet,
                    amount=-mission.budget,
                    transaction_type='MISSION_PAYMENT',
                    description=f'Paiement mission: {mission.title}',
                    reference=f'MISSION_{mission.id}',
                    created_at=mission_data['completed_at'],
                )
                
                # Transaction pour l'agent (crédit)
                WalletTransaction.objects.create(
                    wallet=mission_data['assigned_agent'].wallet,
                    amount=mission.budget * 0.8,
                    transaction_type='MISSION_EARNING',
                    description=f'Gain mission: {mission.title}',
                    reference=f'MISSION_{mission.id}_EARNING',
                    created_at=mission_data['completed_at'],
                )
                
                # Mettre à jour les soldes
                mission.client.wallet.balance -= mission.budget
                mission.client.wallet.save()
                
                mission_data['assigned_agent'].wallet.balance += mission.budget * 0.8
                mission_data['assigned_agent'].wallet.save()
            
            print(f"✅ Mission créée: {mission.title} ({mission.status})")
            missions.append(mission)
            
        except Exception as e:
            print(f"⚠️  Erreur création mission {mission_data['title']}: {e}")
    
    return missions

def create_test_services():
    """Crée des services de test variés pour l'écran services"""
    print("🛠️  Création des services de test...")
    
    services_data = [
        # Services Livraison
        {
            'name': 'Livraison Express',
            'description': 'Livraison rapide de colis et documents en moins de 2h',
            'category': 'Livraison',
            'base_price': 1500.0,
            'estimated_duration': 30,
            'is_active': True,
        },
        {
            'name': 'Livraison Standard',
            'description': 'Livraison économique de colis et documents',
            'category': 'Livraison',
            'base_price': 800.0,
            'estimated_duration': 120,
            'is_active': True,
        },
        
        # Services Courses
        {
            'name': 'Courses Supermarché',
            'description': 'Aide pour vos courses et achats au supermarché',
            'category': 'Courses',
            'base_price': 2000.0,
            'estimated_duration': 60,
            'is_active': True,
        },
        {
            'name': 'Courses Pharmacie',
            'description': 'Achat et livraison de médicaments',
            'category': 'Courses',
            'base_price': 1200.0,
            'estimated_duration': 45,
            'is_active': True,
        },
        
        # Services Transport
        {
            'name': 'Navette Aéroport',
            'description': 'Transport vers et depuis l\'aéroport',
            'category': 'Transport',
            'base_price': 5000.0,
            'estimated_duration': 60,
            'is_active': True,
        },
        {
            'name': 'Transport Urbain',
            'description': 'Déplacements en ville confortables et sécurisés',
            'category': 'Transport',
            'base_price': 3000.0,
            'estimated_duration': 45,
            'is_active': True,
        },
        
        # Services Assistance
        {
            'name': 'Support Informatique',
            'description': 'Dépannage et assistance technique informatique',
            'category': 'Assistance',
            'base_price': 4000.0,
            'estimated_duration': 90,
            'is_active': True,
        },
        {
            'name': 'Installation Équipement',
            'description': 'Installation et configuration d\'équipements',
            'category': 'Assistance',
            'base_price': 3500.0,
            'estimated_duration': 120,
            'is_active': True,
        },
        
        # Services Ménage
        {
            'name': 'Ménage Complet',
            'description': 'Nettoyage complet de votre logement ou bureau',
            'category': 'Ménage',
            'base_price': 6000.0,
            'estimated_duration': 180,
            'is_active': True,
        },
        {
            'name': 'Ménage Express',
            'description': 'Nettoyage rapide et efficace',
            'category': 'Ménage',
            'base_price': 3500.0,
            'estimated_duration': 90,
            'is_active': True,
        },
        
        # Services Garde
        {
            'name': 'Garde Enfants',
            'description': 'Babysitting et garde d\'enfants à domicile',
            'category': 'Garde',
            'base_price': 2500.0,
            'estimated_duration': 240,
            'is_active': True,
        },
        {
            'name': 'Garde Animaux',
            'description': 'Promenade et garde d\'animaux domestiques',
            'category': 'Garde',
            'base_price': 1500.0,
            'estimated_duration': 60,
            'is_active': True,
        },
    ]
    
    services = []
    
    for service_data in services_data:
        try:
            category = ServiceCategory.objects.get(name=service_data['category'])
            service = Service.objects.create(
                name=service_data['name'],
                description=service_data['description'],
                category=category,
                base_price=service_data['base_price'],
                estimated_duration=service_data['estimated_duration'],
                is_active=service_data['is_active'],
            )
            print(f"✅ Service créé: {service.name}")
            services.append(service)
            
        except Exception as e:
            print(f"⚠️  Erreur création service {service_data['name']}: {e}")
    
    return services

def main():
    """Fonction principale"""
    print("=" * 60)
    print("🌱 SCRIPT DE SEEDING DE LA BASE FONACO")
    print("=" * 60)
    
    try:
        with transaction.atomic():
            print("\n🚀 Démarrage du seeding...")
            
            # 1. Créer l'administrateur
            admin = create_admin_user()
            
            # 2. Créer les clients test
            clients = create_test_clients()
            
            # 3. Créer les agents test
            agents = create_test_agents()
            
            # 4. Créer les catégories de services
            categories = create_service_categories()
            
            # 5. Créer les services de test
            services = create_test_services()
            
            # 6. Créer la matrice de missions de test
            missions = create_test_missions(clients, agents)
            
            print("\n" + "=" * 60)
            print("🎉 SEEDING TERMINÉ AVEC SUCCÈS!")
            print(f"📊 Résumé:")
            print(f"   👤 Admin: 1")
            print(f"   👥 Clients: {len(clients)}")
            print(f"   🚚 Agents: {len(agents)}")
            print(f"   📂 Catégories: {len(categories)}")
            print(f"   🛠️  Services: {len(services)}")
            print(f"   📋 Missions: {len(missions)}")
            print(f"      - COMPLETED: 2")
            print(f"      - CANCELED: 2")
            print(f"      - PENDING/IN_PROGRESS: 2")
            print(f"\n🔑 Comptes de test:")
            print(f"   Admin: 0150088210 / password123")
            print(f"   Client 1: 0101010101 / password123")
            print(f"   Client 2: 0202020202 / password123")
            print(f"   Agent 1: 0303030303 / password123")
            print(f"   Agent 2: 0404040404 / password123")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        print("🔄 Annulation des transactions...")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script de seeding FONAQO v2 — aligné sur les modèles réels.
Utilisation : docker compose exec web python scripts/seed_v2.py
"""
import os
import sys
import uuid
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point

from apps.wallets.models import Wallet, Transaction as WalletTransaction
from apps.services.models import Category, AgentService
from apps.missions.models import Mission, MissionTimelineEvent, AgentStatistics

User = get_user_model()


# ---------------------------------------------------------------------------
# Coordonnées Cotonou / Calavi
# ---------------------------------------------------------------------------
COORDS = {
    'cadjehoun':  (6.3735,  2.3904),
    'fidjrosse':  (6.3515,  2.4133),
    'calavi':     (6.4000,  2.3422),
    'plateau':    (6.3670,  2.4280),
}


def get_or_create_wallet(user, balance=25000.0):
    wallet, created = Wallet.objects.get_or_create(
        user=user,
        defaults={'balance': balance}
    )
    if not created and float(wallet.balance) == 0:
        wallet.balance = balance
        wallet.save(update_fields=['balance'])
    return wallet


def create_admin():
    print("\n👤 Admin...")
    user, created = User.objects.get_or_create(
        phone_number='+2290150088210',
        defaults={
            'username': 'admin_fonaqo',
            'email': 'admin@fonaqo.bj',
            'first_name': 'Super',
            'last_name': 'Admin',
            'is_staff': True,
            'is_superuser': True,
            'is_verified': True,
            'is_active': True,
        }
    )
    if created:
        user.set_password('password123')
        user.save()
        print("  ✅ Admin créé")
    else:
        print("  ℹ️  Admin déjà existant")
    get_or_create_wallet(user, 100000.0)
    return user


def create_clients():
    print("\n👥 Clients...")
    data = [
        dict(
            phone_number='+2290101010101',
            username='client_jean',
            email='jean.client@fonaqo.bj',
            first_name='Jean',
            last_name='Kossou',
            is_client=True,
            is_agent=False,
            latitude=COORDS['cadjehoun'][0],
            longitude=COORDS['cadjehoun'][1],
            address='Cadjèhoun, Cotonou, Bénin',
            city='Cotonou',
        ),
        dict(
            phone_number='+2290202020202',
            username='client_marie',
            email='marie.client@fonaqo.bj',
            first_name='Marie',
            last_name='Adjovi',
            is_client=True,
            is_agent=False,
            latitude=COORDS['fidjrosse'][0],
            longitude=COORDS['fidjrosse'][1],
            address='Fidjrossè, Cotonou, Bénin',
            city='Cotonou',
        ),
    ]
    clients = []
    for d in data:
        phone = d.pop('phone_number')
        password = 'password123'
        user, created = User.objects.get_or_create(phone_number=phone, defaults={**d})
        if created:
            user.set_password(password)
            user.save()
            print(f"  ✅ Client créé : {user.username}")
        else:
            print(f"  ℹ️  Client existant : {user.username}")
        get_or_create_wallet(user, 50000.0)
        clients.append(user)
    return clients


def create_agents():
    print("\n🚴 Agents...")
    data = [
        dict(
            phone_number='+2290303030303',
            username='agent_paul',
            email='paul.agent@fonaqo.bj',
            first_name='Paul',
            last_name='Gbaguidi',
            is_agent=True,
            is_client=False,
            is_online=True,
            is_verified=True,
            latitude=COORDS['cadjehoun'][0] + 0.003,
            longitude=COORDS['cadjehoun'][1] + 0.002,
            address='Cadjèhoun, Cotonou, Bénin',
            city='Cotonou',
        ),
        dict(
            phone_number='+2290404040404',
            username='agent_sophie',
            email='sophie.agent@fonaqo.bj',
            first_name='Sophie',
            last_name='Dossou',
            is_agent=True,
            is_client=False,
            is_online=True,
            is_verified=True,
            latitude=COORDS['fidjrosse'][0] + 0.002,
            longitude=COORDS['fidjrosse'][1] - 0.003,
            address='Fidjrossè, Cotonou, Bénin',
            city='Cotonou',
        ),
    ]
    agents = []
    for d in data:
        phone = d.pop('phone_number')
        user, created = User.objects.get_or_create(phone_number=phone, defaults={**d})
        if created:
            user.set_password('password123')
            user.save()
            print(f"  ✅ Agent créé : {user.username}")
        else:
            print(f"  ℹ️  Agent existant : {user.username}")
        get_or_create_wallet(user, 25000.0)
        AgentStatistics.objects.get_or_create(
            agent=user,
            defaults={'total_missions': 0, 'completed_missions': 0, 'total_earnings': 0, 'average_rating': 4.5}
        )
        agents.append(user)
    return agents


def create_categories():
    print("\n📂 Catégories...")
    cats_data = [
        ('Livraison', 'livraison, colis, express, documents, transport'),
        ('Courses', 'courses, achats, supermarché, provisions, shopping'),
        ('Transport', 'transport, navette, déplacement, taxi, aéroport'),
        ('Assistance', 'assistance, dépannage, support, technique, aide'),
        ('Ménage', 'ménage, nettoyage, entretien, propreté, maison'),
        ('Garde', 'garde, enfants, animaux, babysitting, nounou'),
    ]
    cats = []
    for name, kw in cats_data:
        cat, created = Category.objects.get_or_create(name=name, defaults={'keywords': kw})
        cats.append(cat)
        print(f"  {'✅' if created else 'ℹ️ '} {name}")
    return cats


def create_mission(client, agent, title, description, address, coords, price, status):
    lat, lng = coords
    mission = Mission.objects.create(
        client=client,
        agent=agent,
        title=title,
        description=description,
        address=address,
        location=Point(lng, lat, srid=4326),
        price=price,
        service_fee=round(price * 0.05, 2),
        status=status,
    )
    return mission


def create_wallet_transaction(wallet, amount, tx_type, description, mission):
    ref = f"MISSION_{mission.id}_{tx_type}_{uuid.uuid4().hex[:8]}"
    WalletTransaction.objects.create(
        wallet=wallet,
        amount=amount,
        transaction_type=tx_type,
        description=description,
        reference=ref,
    )


def create_missions(clients, agents):
    print("\n📋 Missions (matrice étendue)...")

    c1, c2 = clients[0], clients[1]
    a1, a2 = agents[0], agents[1]

    specs = [
        # --- 3 COMPLETED ---
        dict(
            client=c1, agent=a1,
            title='Livraison de documents urgents',
            description='Livraison de documents administratifs au Ministère des Finances, Plateau.',
            address='Cadjèhoun → Plateau, Cotonou',
            coords=COORDS['cadjehoun'],
            price=3000.0,
            status='COMPLETED',
        ),
        dict(
            client=c2, agent=a2,
            title='Courses au supermarché Erevan',
            description='Achats de provisions pour la semaine : alimentaire et hygiène.',
            address='Fidjrossè, Cotonou',
            coords=COORDS['fidjrosse'],
            price=5000.0,
            status='COMPLETED',
        ),
        dict(
            client=c1, agent=a2,
            title='Réparation plomberie urgente',
            description='Réparation fuite dans la salle de bain.',
            address='Cadjèhoun, Cotonou',
            coords=COORDS['cadjehoun'],
            price=7000.0,
            status='COMPLETED',
        ),
        # --- 2 CANCELLED ---
        dict(
            client=c1, agent=a2,
            title='Transport aéroport international',
            description="Transport vers l'aéroport de Cadjèhoun — vol annulé par le client.",
            address='Cadjèhoun → Aéroport, Cotonou',
            coords=COORDS['cadjehoun'],
            price=8000.0,
            status='CANCELLED',
        ),
        dict(
            client=c2, agent=a1,
            title="Ménage d'appartement 3 pièces",
            description='Nettoyage complet — mission annulée : indisponibilité agent.',
            address='Fidjrossè, Cotonou',
            coords=COORDS['fidjrosse'],
            price=10000.0,
            status='CANCELLED',
        ),
        # --- 2 IN_PROGRESS ---
        dict(
            client=c1, agent=a2,
            title='Livraison repas chaud — Buvette Calavi',
            description='Livraison de repas commandés au restaurant vers Fidjrossè.',
            address='Cadjèhoun → Fidjrossè, Cotonou',
            coords=COORDS['cadjehoun'],
            price=2000.0,
            status='IN_PROGRESS',
        ),
        dict(
            client=c2, agent=a1,
            title='Garde d\'animaux — week-end',
            description='Garde de 2 chiens et 1 chat du vendredi soir au dimanche soir.',
            address='Fidjrossè, Cotonou',
            coords=COORDS['fidjrosse'],
            price=8000.0,
            status='IN_PROGRESS',
        ),
        # --- 3 PENDING (sans agent, visible pour tous les agents) ---
        dict(
            client=c2, agent=None,
            title='Garde d\'enfants — soirée du samedi',
            description='Garde de 2 enfants (6 et 9 ans) de 19h à minuit.',
            address='Fidjrossè, Cotonou',
            coords=COORDS['fidjrosse'],
            price=15000.0,
            status='PENDING',
        ),
        dict(
            client=c1, agent=None,
            title='Déménagement meubles',
            description='Transport de 5 meubles vers nouveau logement Calavi.',
            address='Cadjèhoun → Calavi',
            coords=COORDS['cadjehoun'],
            price=12000.0,
            status='PENDING',
        ),
        dict(
            client=c2, agent=None,
            title='Aide administrative — carte d\'identité',
            description='Accompagnement pour renouvellement carte d\'identité à la mairie.',
            address='Plateau, Cotonou',
            coords=COORDS['plateau'],
            price=4000.0,
            status='PENDING',
        ),
    ]

    missions = []
    for s in specs:
        try:
            mission = create_mission(
                client=s['client'],
                agent=s['agent'],
                title=s['title'],
                description=s['description'],
                address=s['address'],
                coords=s['coords'],
                price=s['price'],
                status=s['status'],
            )

            # Timeline events
            MissionTimelineEvent.objects.create(
                mission=mission, event_type='created',
                performed_by=s['client'],
                notes='Mission créée par le client.'
            )
            if s['status'] in ('COMPLETED', 'IN_PROGRESS', 'CANCELLED') and s['agent']:
                MissionTimelineEvent.objects.create(
                    mission=mission, event_type='accepted',
                    performed_by=s['agent'],
                    notes='Mission acceptée par l\'agent.'
                )
            if s['status'] == 'IN_PROGRESS' and s['agent']:
                MissionTimelineEvent.objects.create(
                    mission=mission, event_type='in_progress',
                    performed_by=s['agent'],
                    notes='Mission en cours.',
                    location_lat=s['coords'][0],
                    location_lng=s['coords'][1],
                )
            if s['status'] == 'COMPLETED' and s['agent']:
                MissionTimelineEvent.objects.create(
                    mission=mission, event_type='completed',
                    performed_by=s['agent'],
                    notes='Mission terminée avec succès.'
                )
                # Transactions wallet
                client_wallet = get_or_create_wallet(s['client'])
                agent_wallet = get_or_create_wallet(s['agent'])
                agent_share = Decimal(str(round(s['price'] * 0.8, 2)))
                create_wallet_transaction(client_wallet, -Decimal(str(s['price'])), 'MISSION_PAYMENT',
                                          f"Paiement mission: {mission.title}", mission)
                create_wallet_transaction(agent_wallet, agent_share, 'MISSION_PAYMENT',
                                          f"Gain mission: {mission.title}", mission)
                stats = AgentStatistics.objects.get(agent=s['agent'])
                stats.total_missions += 1
                stats.completed_missions += 1
                stats.total_earnings += agent_share
                stats.save(update_fields=['total_missions', 'completed_missions', 'total_earnings'])

            if s['status'] == 'CANCELLED':
                MissionTimelineEvent.objects.create(
                    mission=mission, event_type='cancelled',
                    performed_by=s['client'],
                    notes='Mission annulée.'
                )

            print(f"  ✅ [{mission.status:12s}] {mission.title[:50]}")
            missions.append(mission)
        except Exception as e:
            print(f"  ❌ Erreur mission '{s['title']}': {e}")

    return missions


def create_services(agents, categories):
    print("\n🛠️  Services...")
    cat_map = {c.name: c for c in categories}
    specs = [
        (agents[0], 'Livraison', 'Livraison Express Cotonou', 1500),
        (agents[0], 'Courses', 'Courses & Provisions', 2000),
        (agents[0], 'Transport', 'Navette Aéroport', 5000),
        (agents[1], 'Livraison', 'Livraison Standard', 800),
        (agents[1], 'Ménage', 'Ménage Complet Appartement', 6000),
        (agents[1], 'Garde', 'Garde Enfants & Babysitting', 2500),
    ]
    for agent, cat_name, title, price in specs:
        cat = cat_map.get(cat_name)
        if not cat:
            continue
        _, created = AgentService.objects.get_or_create(
            agent=agent, category=cat, title=title,
            defaults={'base_price': price, 'experience_years': 2, 'is_active': True}
        )
        print(f"  {'✅' if created else 'ℹ️ '} {title} — {agent.first_name}")


def main():
    print("=" * 60)
    print("🌱  SEEDING FONAQO v2")
    print("=" * 60)
    try:
        with transaction.atomic():
            admin = create_admin()
            clients = create_clients()
            agents = create_agents()
            categories = create_categories()
            create_services(agents, categories)
            missions = create_missions(clients, agents)

            print("\n" + "=" * 60)
            print("🎉  SEEDING TERMINÉ AVEC SUCCÈS")
            print(f"   👤 Admin   : +2290150088210 / password123")
            print(f"   👥 Client1 : +2290101010101 / password123")
            print(f"   👥 Client2 : +2290202020202 / password123")
            print(f"   🚴 Agent1  : +2290303030303 / password123")
            print(f"   🚴 Agent2  : +2290404040404 / password123")
            print(f"   📋 Missions: {len(missions)} (3 COMPLETED, 2 CANCELLED, 2 IN_PROGRESS, 3 PENDING)")
            print("=" * 60)
    except Exception as e:
        import traceback
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

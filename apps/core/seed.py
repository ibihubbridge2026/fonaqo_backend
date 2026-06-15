"""
Moteur de seeding FONAQO — source unique pour `manage.py seed_data` et scripts/seed_v2.py.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from apps.core.choices import AgentKYCStatus, AgentLevelName, MissionStatus
from apps.accounts.models import AgentProfile
from apps.boosts.models import BoostPlan
from apps.missions.models import AgentLevel, AgentStatistics, Mission, MissionTimelineEvent
from apps.services.models import AgentService, Category
from apps.wallets.models import Transaction as WalletTransaction
from apps.wallets.models import Wallet

User = get_user_model()

DEFAULT_PASSWORD = "password123"

COORDS = {
    "cadjehoun": (6.3735, 2.3904),
    "fidjrosse": (6.3515, 2.4133),
    "calavi": (6.4000, 2.3422),
    "plateau": (6.3670, 2.4280),
    "marcory": (6.3400, 2.4050),
    "cocody": (6.3850, 2.3650),
}


def get_or_create_wallet(user, balance=25000.0):
    wallet, created = Wallet.objects.get_or_create(user=user, defaults={"balance": balance})
    if not created and float(wallet.balance) == 0:
        wallet.balance = balance
        wallet.save(update_fields=["balance"])
    return wallet


def create_boost_plans():
    """Plans alignés sur AgentBoostScreen Flutter (Day / Week / Month)."""
    specs = [
        {
            "name": "Day Boost",
            "duration_hours": 24,
            "price": Decimal("200.00"),
            "description": "Boost 24h — visibilité accrue sur les nouvelles missions",
            "visibility_multiplier": Decimal("1.5"),
        },
        {
            "name": "Week Boost",
            "duration_hours": 24 * 7,
            "price": Decimal("1000.00"),
            "description": "Boost 7 jours — priorité sur le flux missions",
            "visibility_multiplier": Decimal("2.0"),
        },
        {
            "name": "Month Boost",
            "duration_hours": 24 * 30,
            "price": Decimal("2000.00"),
            "description": "Boost 30 jours — visibilité maximale",
            "visibility_multiplier": Decimal("2.5"),
        },
    ]
    plans = []
    for spec in specs:
        plan, _ = BoostPlan.objects.get_or_create(
            name=spec["name"],
            defaults=spec,
        )
        plans.append(plan)
    return plans


def create_agent_levels():
    levels = {}
    for name in AgentLevelName:
        level, _ = AgentLevel.objects.get_or_create(
            name=name.value,
            defaults={"min_missions": 0, "priority_boost": 1.0},
        )
        levels[name.value] = level
    return levels


def create_categories():
    cats_data = [
        ("Livraison", "livraison, colis, express, documents, transport"),
        ("Courses", "courses, achats, supermarché, provisions, shopping"),
        ("Transport", "transport, navette, déplacement, taxi, aéroport"),
        ("Assistance", "assistance, dépannage, support, technique, aide"),
        ("Ménage", "ménage, nettoyage, entretien, propreté, maison"),
        ("Garde", "garde, enfants, animaux, babysitting, nounou"),
        ("Plomberie", "plomberie, fuite, robinet, tuyau, sanitaire"),
        ("Électricité", "électricité, lumière, ampoule, prise, câble"),
        ("Bricolage", "bricolage, réparation, montage, assemblage, outils"),
        ("Administratif", "administratif, papiers, documents, formalités, mairie"),
        ("Informatique", "informatique, ordinateur, internet, wifi, réseau"),
        ("Jardinage", "jardinage, jardin, plante, tonte, entretien extérieur"),
        ("Maçonnerie", "maçon, construction, fondation, mur, ciment"),
        ("Menuiserie", "menuiserie, bois, meuble, ébénisterie"),
    ]
    cats = []
    for name, kw in cats_data:
        cat, _ = Category.objects.get_or_create(name=name, defaults={"keywords": kw})
        cats.append(cat)
    return cats


def _create_user(phone, password, defaults):
    user, created = User.objects.get_or_create(phone_number=phone, defaults=defaults)
    if created:
        user.set_password(password)
        user.save()
    return user, created


def create_admin(password):
    user, created = _create_user(
        "+2290150088210",
        password,
        {
            "username": "admin_fonaqo",
            "email": "admin@fonaqo.bj",
            "first_name": "Super",
            "last_name": "Admin",
            "is_staff": True,
            "is_superuser": True,
            "is_verified": True,
            "is_active": True,
            "is_client": False,
            "is_agent": False,
        },
    )
    get_or_create_wallet(user, 100000.0)
    return user, created


def create_clients(password):
    specs = [
        {
            "phone_number": "+2290101010101",
            "username": "client_jean",
            "email": "jean.client@fonaqo.bj",
            "first_name": "Jean",
            "last_name": "Kossou",
            "latitude": COORDS["cadjehoun"][0],
            "longitude": COORDS["cadjehoun"][1],
            "address": "Cadjèhoun, Cotonou, Bénin",
            "city": "Cotonou",
        },
        {
            "phone_number": "+2290202020202",
            "username": "client_marie",
            "email": "marie.client@fonaqo.bj",
            "first_name": "Marie",
            "last_name": "Adjovi",
            "latitude": COORDS["fidjrosse"][0],
            "longitude": COORDS["fidjrosse"][1],
            "address": "Fidjrossè, Cotonou, Bénin",
            "city": "Cotonou",
        },
    ]
    clients = []
    for spec in specs:
        phone = spec.pop("phone_number")
        user, _ = _create_user(
            phone,
            password,
            {**spec, "is_client": True, "is_agent": False, "is_verified": True},
        )
        get_or_create_wallet(user, 50000.0)
        clients.append(user)
    return clients


def create_agents(password, levels):
    expert = levels.get(AgentLevelName.EXPERT.value)
    verified = levels.get(AgentLevelName.VERIFIED.value)

    specs = [
        {
            "phone_number": "+2290303030303",
            "username": "agent_paul",
            "email": "paul.agent@fonaqo.bj",
            "first_name": "Paul",
            "last_name": "Gbaguidi",
            "reliability_score": 92.0,
            "latitude": COORDS["cadjehoun"][0] + 0.003,
            "longitude": COORDS["cadjehoun"][1] + 0.002,
            "address": "Cadjèhoun, Cotonou",
            "city": "Cotonou",
            "level": expert,
            "services": [("Livraison", "Livraison Express Cotonou", 1500), ("Courses", "Courses & Provisions", 2000)],
        },
        {
            "phone_number": "+2290404040404",
            "username": "agent_sophie",
            "email": "sophie.agent@fonaqo.bj",
            "first_name": "Sophie",
            "last_name": "Dossou",
            "reliability_score": 95.0,
            "latitude": COORDS["fidjrosse"][0] + 0.002,
            "longitude": COORDS["fidjrosse"][1] - 0.003,
            "address": "Fidjrossè, Cotonou",
            "city": "Cotonou",
            "level": expert,
            "services": [("Ménage", "Ménage Complet Appartement", 6000), ("Garde", "Garde Enfants & Babysitting", 2500)],
        },
        {
            "phone_number": "+2290505050505",
            "username": "agent_kouassi",
            "email": "kouassi.konan@fonaqo.bj",
            "first_name": "Kouassi",
            "last_name": "Konan",
            "reliability_score": 96.0,
            "latitude": COORDS["cocody"][0],
            "longitude": COORDS["cocody"][1],
            "address": "Cocody, Abidjan",
            "city": "Abidjan",
            "level": expert,
            "services": [("Maçonnerie", "Maçonnerie résidentielle", 8000), ("Bricolage", "Réparations structurelles", 5000)],
        },
        {
            "phone_number": "+2290606060606",
            "username": "agent_aminata",
            "email": "aminata.diallo@fonaqo.bj",
            "first_name": "Aminata",
            "last_name": "Diallo",
            "reliability_score": 94.0,
            "latitude": COORDS["marcory"][0],
            "longitude": COORDS["marcory"][1],
            "address": "Marcory, Abidjan",
            "city": "Abidjan",
            "level": verified,
            "services": [("Électricité", "Installations électriques", 4500), ("Informatique", "Réseau & domotique", 3500)],
        },
        {
            "phone_number": "+2290707070707",
            "username": "agent_yao",
            "email": "yao.koffi@fonaqo.bj",
            "first_name": "Yao",
            "last_name": "Koffi",
            "reliability_score": 91.0,
            "latitude": COORDS["plateau"][0],
            "longitude": COORDS["plateau"][1],
            "address": "Plateau, Cotonou",
            "city": "Cotonou",
            "level": verified,
            "services": [("Plomberie", "Dépannage plomberie 24/7", 5500)],
        },
        {
            "phone_number": "+2290808080808",
            "username": "agent_fatou",
            "email": "fatou.sow@fonaqo.bj",
            "first_name": "Fatou",
            "last_name": "Sow",
            "reliability_score": 89.0,
            "latitude": COORDS["calavi"][0],
            "longitude": COORDS["calavi"][1],
            "address": "Calavi, Bénin",
            "city": "Calavi",
            "level": verified,
            "services": [("Menuiserie", "Mobilier sur mesure", 7000), ("Bricolage", "Montage & finitions", 4000)],
        },
        {
            "phone_number": "+2290909090909",
            "username": "agent_ibrahim",
            "email": "ibrahim.traore@fonaqo.bj",
            "first_name": "Ibrahim",
            "last_name": "Traoré",
            "reliability_score": 88.0,
            "latitude": COORDS["cadjehoun"][0] - 0.004,
            "longitude": COORDS["cadjehoun"][1] + 0.005,
            "address": "Akpakpa, Cotonou",
            "city": "Cotonou",
            "level": verified,
            "services": [("Informatique", "Support informatique", 3000), ("Assistance", "Assistance technique", 2500)],
        },
        {
            "phone_number": "+2291010101010",
            "username": "agent_aicha",
            "email": "aicha.mensah@fonaqo.bj",
            "first_name": "Aïcha",
            "last_name": "Mensah",
            "reliability_score": 93.0,
            "latitude": COORDS["fidjrosse"][0] - 0.003,
            "longitude": COORDS["fidjrosse"][1] + 0.004,
            "address": "Fidjrossè, Cotonou",
            "city": "Cotonou",
            "level": expert,
            "services": [("Ménage", "Ménage premium", 5500), ("Jardinage", "Entretien jardin", 4000)],
        },
    ]

    agents = []
    for spec in specs:
        services = spec.pop("services")
        phone = spec.pop("phone_number")
        user, _ = _create_user(
            phone,
            password,
            {
                **spec,
                "is_agent": True,
                "is_client": False,
                "is_online": True,
                "is_verified": True,
                "kyc_status": "VERIFIED",
            },
        )
        get_or_create_wallet(user, 25000.0)
        AgentProfile.objects.get_or_create(
            user=user,
            defaults={"kyc_status": AgentKYCStatus.APPROVED},
        )
        AgentStatistics.objects.get_or_create(
            agent=user,
            defaults={
                "total_missions": 0,
                "completed_missions": 0,
                "total_earnings": Decimal("0"),
                "average_rating": Decimal("4.5"),
            },
        )
        agents.append((user, services))
    return agents


def create_services(agents_with_services, categories):
    cat_map = {c.name: c for c in categories}
    for agent, services in agents_with_services:
        for cat_name, title, price in services:
            cat = cat_map.get(cat_name)
            if not cat:
                continue
            AgentService.objects.get_or_create(
                agent=agent,
                category=cat,
                title=title,
                defaults={
                    "base_price": price,
                    "experience_years": 3,
                    "is_active": True,
                    "successful_missions": 12,
                },
            )


def create_mission(client, agent, title, description, address, coords, price, status):
    lat, lng = coords
    return Mission.objects.create(
        client=client,
        agent=agent,
        title=title,
        description=description,
        address=address,
        location=Point(lng, lat, srid=4326),
        price=price,
        service_fee=round(price * Decimal("0.05"), 2),
        status=status,
    )


def create_wallet_transaction(wallet, amount, tx_type, description, mission):
    ref = f"MISSION_{mission.id}_{tx_type}_{uuid.uuid4().hex[:8]}"
    WalletTransaction.objects.create(
        wallet=wallet,
        amount=amount,
        transaction_type=tx_type,
        description=description,
        reference=ref,
        mission=mission,
    )


def create_missions(clients, agents_flat):
    c1, c2 = clients[0], clients[1]
    a1, a2, a3, a4 = agents_flat[0], agents_flat[1], agents_flat[2], agents_flat[3]

    specs = [
        dict(client=c1, agent=a1, title="Livraison de documents urgents", description="Livraison administrative au Plateau.", address="Cadjèhoun → Plateau, Cotonou", coords=COORDS["cadjehoun"], price=Decimal("3000"), status=MissionStatus.COMPLETED),
        dict(client=c2, agent=a2, title="Courses au supermarché Erevan", description="Provisions alimentaires et hygiène.", address="Fidjrossè, Cotonou", coords=COORDS["fidjrosse"], price=Decimal("5000"), status=MissionStatus.COMPLETED),
        dict(client=c1, agent=a3, title="Réparation plomberie urgente", description="Réparation fuite salle de bain.", address="Cadjèhoun, Cotonou", coords=COORDS["cadjehoun"], price=Decimal("7000"), status=MissionStatus.COMPLETED),
        dict(client=c1, agent=a4, title="Transport aéroport international", description="Vol annulé par le client.", address="Cadjèhoun → Aéroport", coords=COORDS["cadjehoun"], price=Decimal("8000"), status=MissionStatus.CANCELLED),
        dict(client=c2, agent=a1, title="Ménage d'appartement 3 pièces", description="Mission annulée : indisponibilité agent.", address="Fidjrossè, Cotonou", coords=COORDS["fidjrosse"], price=Decimal("10000"), status=MissionStatus.CANCELLED),
        dict(client=c1, agent=a2, title="Livraison repas chaud — Buvette Calavi", description="Repas vers Fidjrossè.", address="Cadjèhoun → Fidjrossè", coords=COORDS["cadjehoun"], price=Decimal("2000"), status=MissionStatus.IN_PROGRESS),
        dict(client=c2, agent=a1, title="Garde d'animaux — week-end", description="Garde chiens et chat.", address="Fidjrossè, Cotonou", coords=COORDS["fidjrosse"], price=Decimal("8000"), status=MissionStatus.IN_PROGRESS),
        dict(client=c2, agent=None, title="Garde d'enfants — soirée du samedi", description="Garde 2 enfants 19h-minuit.", address="Fidjrossè, Cotonou", coords=COORDS["fidjrosse"], price=Decimal("15000"), status=MissionStatus.PENDING),
        dict(client=c1, agent=None, title="Déménagement meubles", description="Transport 5 meubles vers Calavi.", address="Cadjèhoun → Calavi", coords=COORDS["cadjehoun"], price=Decimal("12000"), status=MissionStatus.PENDING),
        dict(client=c2, agent=None, title="Aide administrative — carte d'identité", description="Accompagnement mairie.", address="Plateau, Cotonou", coords=COORDS["plateau"], price=Decimal("4000"), status=MissionStatus.PENDING),
        dict(client=c1, agent=a3, title="Installation électrique cuisine", description="Pose prises et éclairage.", address="Cocody, Abidjan", coords=COORDS["cocody"], price=Decimal("9000"), status=MissionStatus.ACCEPTED),
        dict(client=c2, agent=a4, title="Menuiserie porte sur mesure", description="Fabrication porte intérieure.", address="Calavi, Bénin", coords=COORDS["calavi"], price=Decimal("11000"), status=MissionStatus.ON_THE_WAY),
    ]

    missions = []
    for s in specs:
        mission = create_mission(**s)
        MissionTimelineEvent.objects.create(
            mission=mission,
            event_type="created",
            performed_by=s["client"],
            notes="Mission créée par le client.",
        )
        if s["agent"] and s["status"] != MissionStatus.PENDING:
            MissionTimelineEvent.objects.create(
                mission=mission,
                event_type="accepted",
                performed_by=s["agent"],
                notes="Mission acceptée par l'agent.",
            )
        if s["status"] == MissionStatus.COMPLETED and s["agent"]:
            MissionTimelineEvent.objects.create(
                mission=mission,
                event_type="completed",
                performed_by=s["agent"],
                notes="Mission terminée avec succès.",
            )
            client_wallet = get_or_create_wallet(s["client"])
            agent_wallet = get_or_create_wallet(s["agent"])
            agent_share = round(float(s["price"]) * 0.8, 2)
            create_wallet_transaction(
                client_wallet,
                -s["price"],
                WalletTransaction.TransactionType.MISSION_PAYMENT,
                f"Paiement mission: {mission.title}",
                mission,
            )
            create_wallet_transaction(
                agent_wallet,
                Decimal(str(agent_share)),
                WalletTransaction.TransactionType.MISSION_PAYMENT,
                f"Gain mission: {mission.title}",
                mission,
            )
            stats = AgentStatistics.objects.get(agent=s["agent"])
            stats.total_missions += 1
            stats.completed_missions += 1
            stats.total_earnings += Decimal(str(agent_share))
            stats.save(update_fields=["total_missions", "completed_missions", "total_earnings"])
        if s["status"] == MissionStatus.CANCELLED:
            MissionTimelineEvent.objects.create(
                mission=mission,
                event_type="cancelled",
                performed_by=s["client"],
                notes="Mission annulée.",
            )
        missions.append(mission)
    return missions


def run_seed(password: str = DEFAULT_PASSWORD, stdout=None):
    """Exécute le seed complet. Retourne un résumé dict."""
    write = stdout.write if stdout else print

    with transaction.atomic():
        levels = create_agent_levels()
        create_boost_plans()
        admin, admin_created = create_admin(password)
        clients = create_clients(password)
        agents_with_services = create_agents(password, levels)
        categories = create_categories()
        create_services(agents_with_services, categories)
        agents_flat = [a for a, _ in agents_with_services]
        missions = create_missions(clients, agents_flat)

    summary = {
        "admin_phone": "+2290150088210",
        "client_phones": ["+2290101010101", "+2290202020202"],
        "agent_count": len(agents_flat),
        "mission_count": len(missions),
        "verified_agents": len(agents_flat),
        "password": password,
        "admin_created": admin_created,
    }

    write("\n" + "=" * 60)
    write("SEEDING FONAQO — terminé")
    write(f"  Admin    : {summary['admin_phone']} / {password}")
    write(f"  Clients  : {', '.join(summary['client_phones'])} / {password}")
    write(f"  Agents   : {summary['agent_count']} vérifiés (annuaire public/artisans/)")
    write(f"  Missions : {summary['mission_count']}")
    write("=" * 60 + "\n")
    return summary

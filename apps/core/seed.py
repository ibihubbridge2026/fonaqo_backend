"""
Initialisation minimale FONAQO — un seul compte SuperAdmin.

Usage :
  python manage.py seed_data [password] [--flush]
  make seed          # crée l'admin si absent
  make reset-seed    # flush + admin unique
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from apps.core.choices import AgentKYCStatus, AgentLevelName, EscrowStatus, MissionStatus
from apps.accounts.models import AgentProfile
from apps.boosts.models import BoostPlan
from apps.core.models import AdminAuditLog, AdminNotification, PlatformConfiguration
from apps.core.services import FEES_CONFIDENTIAL_KEY, FEES_URGENT_KEY
from apps.missions.models import AgentLevel, AgentStatistics, Mission, MissionTimelineEvent
from apps.services.models import AgentService, Category
from apps.wallets.models import Transaction as WalletTransaction
from apps.wallets.models import Wallet

User = get_user_model()

ADMIN_USERNAME = "admin_test"
ADMIN_PHONE = "+22960000001"
DEFAULT_PASSWORD = "Fonaco2026!"

# Legacy demo seed (non invoqué par run_seed)
UAT_ADMIN_USERNAME = ADMIN_USERNAME
UAT_ADMIN_PASSWORD = DEFAULT_PASSWORD
UAT_AGENT_USERNAME = "agent_terrain"
UAT_AGENT_PASSWORD = "Agent2026!"

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


def create_platform_config():
    """Frais dynamiques plateforme (PlatformConfiguration)."""
    PlatformConfiguration.objects.update_or_create(
        key=FEES_URGENT_KEY,
        defaults={'value': '500', 'description': 'Frais mission urgente (FCFA)'},
    )
    PlatformConfiguration.objects.update_or_create(
        key=FEES_CONFIDENTIAL_KEY,
        defaults={'value': '500', 'description': 'Frais agent interne / confidentiel (FCFA)'},
    )


def create_uat_accounts(stdout=None):
    """
    Comptes dédiés UAT / démo SuperAdmin web + agent avec wallet crédité.
    Mots de passe fixes (distincts du seed demo password123).
    """
    write = stdout.write if stdout else print

    admin, admin_created = User.objects.get_or_create(
        username=UAT_ADMIN_USERNAME,
        defaults={
            'email': 'admin@fonaqo.com',
            'phone_number': '+22960000001',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
            'is_client': False,
            'is_agent': False,
        },
    )
    if admin_created or not admin.check_password(UAT_ADMIN_PASSWORD):
        admin.set_password(UAT_ADMIN_PASSWORD)
        admin.save()

    agent, agent_created = User.objects.get_or_create(
        username=UAT_AGENT_USERNAME,
        defaults={
            'email': 'agent@fonaqo.com',
            'phone_number': '+22960000002',
            'is_agent': True,
            'is_client': False,
            'is_verified': True,
            'is_active': True,
        },
    )
    if agent_created or not agent.check_password(UAT_AGENT_PASSWORD):
        agent.set_password(UAT_AGENT_PASSWORD)
        agent.save()

    profile, _ = AgentProfile.objects.get_or_create(user=agent)
    profile.kyc_status = AgentKYCStatus.APPROVED
    profile.save(update_fields=['kyc_status', 'updated_at'])

    wallet = get_or_create_wallet(agent, 25000.0)
    wallet.balance = Decimal('25000')
    wallet.save(update_fields=['balance', 'updated_at'])

    write(f"  UAT Admin  : {UAT_ADMIN_USERNAME} / {UAT_ADMIN_PASSWORD}  → /admin-portal/login/")
    write(f"  UAT Agent  : {UAT_AGENT_USERNAME} / {UAT_AGENT_PASSWORD}  (KYC OK, 25k FCFA)")
    return admin, agent


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


def create_escrow_and_dashboard_data(missions, admin_user):
    """Escrow, splits 88/10/2, codes suivi, alertes admin pour le tableau de bord."""
    from apps.escrow.models import Escrow, EscrowSplitRecord

    active_statuses = {
        MissionStatus.ACCEPTED,
        MissionStatus.ON_THE_WAY,
        MissionStatus.IN_PROGRESS,
        MissionStatus.PENDING,
    }
    seq = 4829
    for mission in missions:
        if not mission.tracking_code:
            mission.tracking_code = f'FNC-{seq}-BJ'
            mission.save(update_fields=['tracking_code'])
            seq += 1

        if mission.status == MissionStatus.CANCELLED:
            continue

        escrow_status = EscrowStatus.RELEASED if mission.status == MissionStatus.COMPLETED else EscrowStatus.HELD
        escrow, _ = Escrow.objects.get_or_create(
            mission=mission,
            defaults={'amount': mission.price, 'status': escrow_status},
        )

        if mission.status == MissionStatus.COMPLETED and mission.agent_id:
            total = float(mission.price)
            splits = [
                (EscrowSplitRecord.BeneficiaryType.AGENT, round(total * 0.88, 2), mission.agent),
                (EscrowSplitRecord.BeneficiaryType.PLATFORM, round(total * 0.10, 2), None),
                (EscrowSplitRecord.BeneficiaryType.INFLUENCER, round(total * 0.02, 2), None),
            ]
            for bt, amt, user in splits:
                EscrowSplitRecord.objects.get_or_create(
                    mission=mission,
                    beneficiary_type=bt,
                    defaults={
                        'amount_fcfa': Decimal(str(amt)),
                        'beneficiary_user': user,
                    },
                )

    pending = [m for m in missions if m.status == MissionStatus.PENDING and not m.agent_id]
    if pending:
        AdminNotification.objects.get_or_create(
            title='Missions sans agent',
            mission=pending[0],
            defaults={
                'category': AdminNotification.Category.MISSION_UNASSIGNED,
                'severity': AdminNotification.Severity.WARNING,
                'message': f'{len(pending)} mission(s) en attente d\'assignation agent.',
            },
        )

    if admin_user:
        AdminAuditLog.objects.get_or_create(
            admin=admin_user,
            action='SEED_DASHBOARD',
            target_type='platform',
            target_id='seed',
            defaults={'detail': 'Données démo tableau de bord SuperAdmin initialisées.'},
        )


def create_only_admin(password: str = DEFAULT_PASSWORD, stdout=None):
    """Crée ou met à jour le unique compte SuperAdmin."""
    write = stdout.write if stdout else print

    admin, created = User.objects.get_or_create(
        username=ADMIN_USERNAME,
        defaults={
            'email': 'admin@fonaqo.com',
            'phone_number': ADMIN_PHONE,
            'first_name': 'Super',
            'last_name': 'Admin',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
            'is_verified': True,
            'is_client': False,
            'is_agent': False,
        },
    )
    if created or not admin.check_password(password):
        admin.set_password(password)
        admin.save()
    elif not admin.phone_number:
        admin.phone_number = ADMIN_PHONE
        admin.save(update_fields=['phone_number'])

    write(f"  Admin : {ADMIN_USERNAME} / {ADMIN_PHONE} / {password}  → /admin-portal/login/")
    return admin, created


def run_seed(password: str = DEFAULT_PASSWORD, stdout=None):
    """Vide optionnellement puis enregistre uniquement le compte SuperAdmin."""
    write = stdout.write if stdout else print

    with transaction.atomic():
        admin, admin_created = create_only_admin(password, stdout=stdout)

    summary = {
        'username': ADMIN_USERNAME,
        'phone_number': ADMIN_PHONE,
        'password': password,
        'admin_created': admin_created,
        'admin_id': str(admin.id),
    }

    write("\n" + "=" * 60)
    write("INIT FONAQO — admin unique enregistré")
    write(f"  Login    : {ADMIN_USERNAME}")
    write(f"  Téléphone: {ADMIN_PHONE}")
    write(f"  Mot de passe : {password}")
    write("=" * 60 + "\n")
    return summary

"""
Données de démonstration : superuser, agents vérifiés, clients + wallets, missions.
Usage: python manage.py seed_data
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point

from apps.core.choices import AgentLevelName, KYCStatus, MissionStatus
from apps.missions.models import AgentLevel, Mission, Tag
from apps.services.models import AgentService, Category
from apps.wallets.models import Wallet

User = get_user_model()


def _point_cotonou():
    return Point(2.4318, 6.3725, srid=4326)


class Command(BaseCommand):
    help = "Génère superuser, agents, clients, wallets et missions de démo."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seed FONAQO — démarrage…"))

        for name, boost in (
            (AgentLevelName.NOVICE, 1.0),
            (AgentLevelName.VERIFIED, 1.2),
            (AgentLevelName.EXPERT, 1.5),
        ):
            AgentLevel.objects.get_or_create(
                name=name,
                defaults={"min_missions": 0, "priority_boost": boost},
            )

        level_expert = AgentLevel.objects.filter(name=AgentLevelName.EXPERT).first()

        categories_data = [
            ("SBEE", "électricité, compteur, facture SBEE"),
            ("SONEB", "eau, branchement, facture SONEB"),
            ("Mairie", "acte de naissance, légalisation, état civil"),
            ("Police", "casier judiciaire, légalisation"),
            ("Impôts", "quitus, déclaration fiscale"),
            ("Courses", "marché, pharmacie, livraison"),
        ]
        categories = []
        for name, kw in categories_data:
            c, _ = Category.objects.get_or_create(name=name, defaults={"keywords": kw})
            categories.append(c)

        tag_specs = [
            ("administratif", "administratif"),
            ("energie", "energie"),
            ("urgence", "urgence"),
            ("logistique", "logistique"),
            ("premium", "premium"),
        ]
        tags = []
        for name, slug in tag_specs:
            t, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
            tags.append(t)

        # --- Superuser ---
        if not User.objects.filter(username="hardyaugustin").exists():
            User.objects.create_superuser(
                phone_number="0135828755",
                email="hardyaugustin@seed.fonaco.local",
                username="hardyaugustin",
                password="password123",
                first_name="Hardy",
                last_name="Augustin",
            )
            self.stdout.write(self.style.SUCCESS("Superuser hardyaugustin créé."))
        else:
            u = User.objects.get(username="hardyaugustin")
            u.set_password("password123")
            u.phone_number = "0135828755"
            u.save(update_fields=["password", "phone_number"])
            self.stdout.write("Superuser hardyaugustin mis à jour (mot de passe).")

        agents = []
        agent_defs = [
            ("agent_koffi", "0191000001", "Koffi", "Alain", [0, 1, 2]),
            ("agent_ayele", "0191000002", "Ayeley", "Rose", [1, 3]),
            ("agent_jules", "0191000003", "Jules", "Martin", [2, 4]),
            ("agent_fatou", "0191000004", "Fatou", "Zinsou", [0, 5]),
            ("agent_yves", "0191000005", "Yves", "Dossou", [3, 4, 5]),
        ]
        for username, phone, fn, ln, cat_idxs in agent_defs:
            user, created = User.objects.get_or_create(
                phone_number=phone,
                defaults={
                    "username": username,
                    "email": f"{username}@seed.fonaco.local",
                    "first_name": fn,
                    "last_name": ln,
                    "is_agent": True,
                    "is_client": False,
                    "is_verified": True,
                    "kyc_status": KYCStatus.VERIFIED,
                    "level": level_expert,
                },
            )
            if created:
                user.set_password("password123")
                user.save()
            else:
                User.objects.filter(pk=user.pk).update(
                    is_agent=True,
                    is_client=False,
                    is_verified=True,
                    kyc_status=KYCStatus.VERIFIED,
                    level=level_expert,
                )
                user.refresh_from_db()
            agents.append(user)

            for i in cat_idxs:
                cat = categories[i % len(categories)]
                AgentService.objects.get_or_create(
                    agent=user,
                    category=cat,
                    defaults={
                        "title": f"Intervention {cat.name}",
                        "base_price": Decimal(5000 + i * 1500),
                        "is_active": True,
                        "experience_years": 2 + i,
                        "successful_missions": 10 + i * 5,
                    },
                )

        clients = []
        for n in range(1, 6):
            phone = f"019200000{n}"
            username = f"client_demo_{n}"
            user, created = User.objects.get_or_create(
                phone_number=phone,
                defaults={
                    "username": username,
                    "email": f"{username}@seed.fonaco.local",
                    "first_name": f"Client{n}",
                    "last_name": "Démo",
                    "is_agent": False,
                    "is_client": True,
                    "is_verified": True,
                    "kyc_status": KYCStatus.VERIFIED,
                },
            )
            if created:
                user.set_password("password123")
                user.save()
            clients.append(user)

        for u in agents + clients:
            w, _ = Wallet.objects.get_or_create(user=u)
            w.balance = Decimal("750000.00")
            w.escrow_balance = Decimal("0.00")
            w.save()

        su = User.objects.get(username="hardyaugustin")
        w, _ = Wallet.objects.get_or_create(user=su)
        w.balance = Decimal("1000000.00")
        w.save()

        loc = _point_cotonou()
        mission_specs = [
            (
                clients[0],
                None,
                MissionStatus.PENDING,
                "File Mairie — acte de naissance",
                "File d'attente Mairie de Cotonou",
                Decimal("15000"),
            ),
            (
                clients[1],
                agents[0],
                MissionStatus.ACCEPTED,
                "Service SBEE — mise à jour compteur",
                "Rendez-vous agence SBEE Akpakpa",
                Decimal("22000"),
            ),
            (
                clients[2],
                None,
                MissionStatus.PENDING,
                "File Police — casier",
                "Demande de casier judiciaire",
                Decimal("8000"),
            ),
            (
                clients[3],
                agents[1],
                MissionStatus.ACCEPTED,
                "Courses & pharmacie",
                "Liste de courses + retrait médicaments",
                Decimal("12000"),
            ),
            (
                clients[4],
                None,
                MissionStatus.PENDING,
                "Impôts — quitus",
                "Obtenir quitus fiscal au centre des impôts",
                Decimal("18000"),
            ),
        ]

        client_ids = [c.pk for c in clients]
        Mission.objects.filter(client_id__in=client_ids).delete()

        for idx, (client, agent, status, title, desc, price) in enumerate(mission_specs):
            fee = (price * Decimal("0.10")).quantize(Decimal("0.01"))
            m = Mission.objects.create(
                client=client,
                agent=agent,
                title=title,
                description=desc,
                address="Cotonou, Bénin",
                location=loc,
                price=price,
                service_fee=fee,
                status=status,
                requires_procuration=False,
            )
            m.tags.add(tags[idx % len(tags)])

        self.stdout.write(self.style.SUCCESS("Seed terminé : agents, clients, missions OK."))

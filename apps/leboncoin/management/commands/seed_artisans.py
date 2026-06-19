"""Seed artisans LeBonCoin pour démonstration."""
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.leboncoin.models import LocalListing


ARTISAN_SPECS = [
    {
        "name": "Koffi Mensah",
        "specialty": "Plomberie",
        "description": "Dépannage plomberie résidentielle et commerciale.",
        "address": "Cadjèhoun, Cotonou",
        "city": "Cotonou",
        "district": "Cadjèhoun",
        "phone": "+22997001122",
        "website_url": "",
        "lat": 6.3735,
        "lng": 2.3904,
    },
    {
        "name": "Aminata Diallo",
        "specialty": "Électricité",
        "description": "Installations électriques et dépannage 24/7.",
        "address": "Marcory, Abidjan",
        "city": "Abidjan",
        "district": "Marcory",
        "phone": "+22996003344",
        "website_url": "https://aminata-elec.example",
        "lat": 6.3400,
        "lng": 2.4050,
    },
    {
        "name": "Yao Konan",
        "specialty": "Maçonnerie",
        "description": "Construction et rénovation de bâtiments.",
        "address": "Cocody, Abidjan",
        "city": "Abidjan",
        "district": "Cocody",
        "phone": "+22995005566",
        "website_url": "",
        "lat": 6.3850,
        "lng": 2.3650,
    },
    {
        "name": "Fatou Sow",
        "specialty": "Menuiserie",
        "description": "Mobilier sur mesure et agencement intérieur.",
        "address": "Calavi, Bénin",
        "city": "Calavi",
        "district": "Calavi",
        "phone": "+22994007788",
        "phone_whatsapp": "+22994007788",
        "website_url": "",
        "lat": 6.4000,
        "lng": 2.3422,
    },
    {
        "name": "Ibrahim Traoré",
        "specialty": "Climatisation",
        "description": "Installation et entretien de climatiseurs.",
        "address": "Plateau, Cotonou",
        "city": "Cotonou",
        "district": "Plateau",
        "phone": "+22993009900",
        "website_url": "https://ibrahim-clim.example",
        "lat": 6.3670,
        "lng": 2.4280,
    },
]


class Command(BaseCommand):
    help = "Génère des artisans de test pour la carte LeBonCoin."

    def handle(self, *args, **options):
        created = 0
        for spec in ARTISAN_SPECS:
            whatsapp = spec.get("phone_whatsapp", spec["phone"])
            tags = [spec["specialty"], spec["city"]]
            obj, was_created = LocalListing.objects.get_or_create(
                name=spec["name"],
                specialty=spec["specialty"],
                defaults={
                    "category": LocalListing.Category.ARTISAN,
                    "description": spec["description"],
                    "address": spec["address"],
                    "city": spec["city"],
                    "district": spec["district"],
                    "phone": spec["phone"],
                    "website_url": spec.get("website_url", ""),
                    "location": Point(spec["lng"], spec["lat"], srid=4326),
                    "rating": Decimal("4.5"),
                    "is_featured": True,
                    "is_active": True,
                    "tags": tags + [f"whatsapp:{whatsapp}"],
                },
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed artisans terminé — {created} créé(s), "
                f"{len(ARTISAN_SPECS)} au total."
            )
        )

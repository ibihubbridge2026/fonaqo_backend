from django.core.management.base import BaseCommand
from apps.services.models import Category
from apps.missions.models import AgentLevel

class Command(BaseCommand):
    help = 'Peuple la base avec les catégories et niveaux de base'

    def handle(self, *args, **kwargs):
        # 1. Catégories
        categories = [
            {'name': 'SBEE', 'keywords': 'électricité, facture, courant, compteur'},
            {'name': 'SONEB', 'keywords': 'eau, facture, fuite, plomberie'},
            {'name': 'Mairie', 'keywords': 'acte de naissance, légalisation, papiers'},
            {'name': 'Courses & Livraison', 'keywords': 'marché, colis, repas, pharmacie'},
        ]
        for cat in categories:
            Category.objects.get_or_create(name=cat['name'], defaults={'keywords': cat['keywords']})
        
        # 2. Niveaux Agents
        levels = [
            {'name': 'Novice', 'min_missions': 0},
            {'name': 'Expert', 'min_missions': 50},
            {'name': 'Pro', 'min_missions': 150},
        ]
        for lvl in levels:
            AgentLevel.objects.get_or_create(name=lvl['name'], defaults={'min_missions': lvl['min_missions']})

        self.stdout.write(self.style.SUCCESS('Base de données peuplée avec succès !'))
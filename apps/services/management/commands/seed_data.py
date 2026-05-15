from django.core.management.base import BaseCommand
from apps.services.models import Category
from apps.missions.models import AgentLevel

class Command(BaseCommand):
    help = 'Peuple la base avec les catégories et niveaux de base'

    def handle(self, *args, **kwargs):
        # 1. Catégories de services
        categories = [
            # Services publics
            {'name': 'SBEE', 'keywords': 'électricité, facture, courant, compteur, panne'},
            {'name': 'SONEB', 'keywords': 'eau, facture, fuite, plomberie, robinet'},
            {'name': 'Mairie', 'keywords': 'acte de naissance, légalisation, papiers, administratif'},
            {'name': 'CNI', 'keywords': 'carte identité, biométrie, renouvellement'},
            {'name': 'Impôts', 'keywords': 'déclaration, fiscal, impôt, taxes'},
            
            # Services de livraison et courses
            {'name': 'Courses & Livraison', 'keywords': 'marché, colis, repas, pharmacie, supermarché'},
            {'name': 'Livraison Rapide', 'keywords': 'express, urgent, rapide, immédiat'},
            {'name': 'Transport', 'keywords': 'taxi, transport, déplacement, voiture, moto'},
            
            # Services techniques
            {'name': 'Informatique', 'keywords': 'ordinateur, smartphone, internet, réparation, installation'},
            {'name': 'Électronique', 'keywords': 'télévision, appareil, réparation, dépannage'},
            {'name': 'Plomberie', 'keywords': 'fuite, robinet, canalisation, WC, douche'},
            {'name': 'Électricité', 'keywords': 'panne, installation, tableau, disjoncteur, câblage'},
            {'name': 'Climatisation', 'keywords': 'clim, split, entretien, installation, réparation'},
            
            # Services de maison et jardin
            {'name': 'Ménage', 'keywords': 'nettoyage, ménage, entretien, maison, appartement'},
            {'name': 'Jardinage', 'keywords': 'jardin, pelouse, taille, plantation, arrosage'},
            {'name': 'Bricolage', 'keywords': 'bricolage, réparation, montage, fixation, peinture'},
            {'name': 'Déménagement', 'keywords': 'déménagement, transport, cartons, meubles, camion'},
            
            # Services personnels et professionnels
            {'name': 'Assistance Personnelle', 'keywords': 'aide, personne âgée, enfant, accompagnement'},
            {'name': 'Garde d\'enfants', 'keywords': 'babysitting, garde, nounou, crèche, enfants'},
            {'name': 'Coiffure & Beauté', 'keywords': 'coiffeur, beauté, massage, soin, esthétique'},
            {'name': 'Réparation Auto', 'keywords': 'voiture, mécanique, pneu, vidange, entretien'},
            
            # Services administratifs et légaux
            {'name': 'Traduction', 'keywords': 'traduction, langue, document, officiel, interprète'},
            {'name': 'Comptabilité', 'keywords': 'comptabilité, facture, déclaration, TVA, impôts'},
            {'name': 'Juridique', 'keywords': 'avocat, conseil, contrat, litige, légal'},
            
            # Services événementiels
            {'name': 'Événements', 'keywords': 'mariage, fête, événement, organisation, décoration'},
            {'name': 'Photographie', 'keywords': 'photo, vidéo, shooting, portrait, événement'},
            {'name': 'Catering', 'keywords': 'traiteur, repas, événement, buffet, cuisine'},
            
            # Services divers
            {'name': 'Tutorat', 'keywords': 'cours, soutien, scolaire, mathématiques, français'},
            {'name': 'Coaching Sportif', 'keywords': 'sport, fitness, musculation, entraînement, coach'},
            {'name': 'Petits Boulots', 'keywords': 'aide, main d\'œuvre, occasionnel, temporaire, assistance'},
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
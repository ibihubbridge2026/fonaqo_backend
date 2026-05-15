import re
from django.db.models import Q
from apps.missions.models import Mission
from accounts.models import AgentProfile

class AISearchService:
    """
    Service d'analyse de langage naturel pour la recherche.
    Version simple (keywords matching). 
    Pour production : intégrer OpenAI API ou modèle NLP.
    """
    
    @staticmethod
    def analyze_query(query: str, user_type: str) -> dict:
        """Analyse la requête et extrait les intentions"""
        query_lower = query.lower()
        
        analysis = {
            'service_type': None,
            'location': None,
            'urgency': 'normal',
            'timeframe': None,
        }
        
        # Détection type de service
        services_keywords = {
            'banque': ['banque', 'boa', 'sgbci', 'retrait', 'virement', 'file'],
            'livraison': ['livraison', 'colis', 'document', 'porter'],
            'menage': ['ménage', 'nettoyage', 'entretien', 'maison'],
            'courses': ['course', 'supermarché', 'acheter', 'nourriture'],
            'bricolage': ['bricolage', 'réparation', 'électricien', 'plomberie'],
        }
        
        for service, keywords in services_keywords.items():
            if any(kw in query_lower for kw in keywords):
                analysis['service_type'] = service
                break
        
        # Détection urgence
        if any(word in query_lower for word in ['urgent', 'rapide', 'vite', 'maintenant']):
            analysis['urgency'] = 'high'
        
        # Détection localisation (simplifié)
        locations = ['cocody', 'plateau', 'yopougon', 'abidjan', 'marcory']
        for loc in locations:
            if loc in query_lower:
                analysis['location'] = loc
                break
        
        # Génération phrase analyse
        timeframe = "disponible rapidement"
        if 'demain' in query_lower:
            timeframe = "disponible demain"
        elif 'matin' in query_lower:
            timeframe = "disponible demain matin"
        
        analysis['timeframe'] = timeframe
        
        return analysis
    
    @staticmethod
    def find_agents_for_client(query: str, user) -> list:
        """Trouve des agents pertinents pour un client"""
        analysis = AISearchService.analyze_query(query, 'client')
        
        filters = Q(is_verified=True)
        
        if analysis['service_type']:
            filters &= Q(specialty__icontains=analysis['service_type'])
        
        # Recherche base
        agents = AgentProfile.objects.filter(filters).select_related('user')[:5]
        
        results = []
        for agent in agents:
            is_top = agent.rating >= 4.8 and agent.completed_missions > 50
            results.append({
                'id': agent.id,
                'name': f"{agent.user.first_name} {agent.user.last_name}",
                'avatar_url': agent.profile_picture.url if agent.profile_picture else '',
                'rating': float(agent.rating),
                'specialty': agent.specialty or 'Service général',
                'completed_missions': agent.completed_missions,
                'estimated_price': f"{agent.hourly_rate or 5000} FCFA",
                'is_top_choice': is_top,
            })
        
        return results
    
    @staticmethod
    def find_missions_for_agent(query: str, user) -> list:
        """Trouve des missions pertinentes pour un agent"""
        analysis = AISearchService.analyze_query(query, 'agent')
        
        filters = Q(status='pending')
        
        if analysis['service_type']:
            filters &= Q(service_type=analysis['service_type'])
        
        if analysis['urgency'] == 'high':
            filters &= Q(is_urgent=True)
        
        missions = Mission.objects.filter(filters).select_related('client')[:10]
        
        results = []
        for mission in missions:
            results.append({
                'id': mission.id,
                'title': mission.title,
                'location': mission.pickup_address,
                'price': f"{mission.price} FCFA",
                'distance': '2.5 km',  # À calculer avec géolocalisation
                'type': mission.get_service_type_display(),
                'is_urgent': mission.is_urgent,
            })
        
        return results

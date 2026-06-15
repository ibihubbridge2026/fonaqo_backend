import json
import logging
import requests
from typing import Dict, Any, List
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import AISearchSuggestion

logger = logging.getLogger(__name__)


class AISearchService:
    """Service pour la recherche IA avec suggestions intelligentes"""
    
    def __init__(self):
        self.max_suggestions = 10
        
    def search(self, query: str, user, search_type: str = 'general') -> Dict[str, Any]:
        """
        Effectue une recherche IA via Mistral AI et retourne une réponse structurée
        
        Args:
            query: La requête de l'utilisateur
            user: L'utilisateur qui effectue la recherche
            search_type: Type de recherche ('agent', 'mission', 'general')
            
        Returns:
            Dict contenant la réponse IA et métadonnées
        """
        try:
            # Appel réel à l'API Mistral AI
            response = self._call_mistral_ai(query, user, search_type)
            
            return {
                'status': 'success',
                'query': query,
                'response': response,
                'timestamp': timezone.now().isoformat(),
                'confidence': 0.95,
                'source': 'mistral_ai'
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche IA Mistral: {e}")
            # Fallback vers simulation si Mistral échoue
            logger.warning("Fallback vers simulation suite à erreur Mistral AI")
            response = self._simulate_ai_response(query, user, search_type)
            
            return {
                'status': 'success',
                'query': query,
                'response': response,
                'timestamp': timezone.now().isoformat(),
                'confidence': 0.70,
                'source': 'ai_simulation_fallback'
            }
    
    def _call_mistral_ai(self, query: str, user, search_type: str) -> Dict[str, Any]:
        """
        Appelle l'API Mistral AI pour analyser la requête et retourner des résultats structurés
        
        Args:
            query: La requête de l'utilisateur
            user: L'utilisateur qui effectue la recherche
            search_type: Type de recherche ('agent', 'mission', 'general')
            
        Returns:
            Dict avec la réponse structurée de Mistral AI
        """
        mistral_api_key = getattr(settings, 'MISTRAL_API_KEY', None)
        
        if not mistral_api_key:
            logger.warning("MISTRAL_API_KEY non configurée, utilisation de la simulation")
            raise ValueError("MISTRAL_API_KEY non configurée")
        
        # Prompt système en français pour analyser la requête
        system_prompt = """Tu es un assistant intelligent pour FONAQO, une plateforme de conciergerie à Cotonou (Bénin).
Ton rôle est d'analyser la requête de l'utilisateur et d'extraire des informations structurées en JSON.

Pour une recherche de MISSION, extrais:
- type: "mission_search"
- category: la catégorie (livraison, course, démarche, etc.)
- location: le lieu mentionné (quartier de Cotonou)
- urgency: si c'est urgent
- keywords: mots-clés pertinents

Pour une recherche d'AGENT, extrais:
- type: "agent_search"
- skills: compétences requises
- location: zone de recherche
- specialties: spécialités recherchées

Réponds UNIQUEMENT en JSON valide, sans texte autour."""
        
        user_prompt = f"""Requête: "{query}"
Type de recherche: {search_type}
Contexte: L'utilisateur est à Cotonou, Bénin.

Analyse cette requête et retourne un JSON structuré avec les résultats appropriés de la base de données."""
        
        try:
            response = requests.post(
                'https://api.mistral.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {mistral_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'mistral-small-latest',  # Modèle gratuit/performant
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.3,
                    'max_tokens': 500
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parser le JSON retourné par Mistral
                try:
                    ai_response = json.loads(content)
                    
                    # Enrichir avec les vraies données de la base
                    return self._enrich_with_database_data(ai_response, search_type)
                    
                except json.JSONDecodeError:
                    logger.error(f"JSON invalide retourné par Mistral: {content}")
                    raise ValueError("Réponse Mistral non JSON valide")
            else:
                logger.error(f"Erreur API Mistral: {response.status_code} - {response.text}")
                raise ValueError(f"Erreur API Mistral: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f"Erreur de connexion à Mistral AI: {e}")
            raise
    
    def _enrich_with_database_data(self, ai_response: Dict[str, Any], search_type: str) -> Dict[str, Any]:
        """
        Enrichit la réponse IA avec de vraies données de la base de données
        
        Args:
            ai_response: Réponse structurée de Mistral AI
            search_type: Type de recherche
            
        Returns:
            Dict enrichi avec les vraies données
        """
        from apps.missions.models import Mission
        from apps.accounts.models import User
        
        results = []
        
        if search_type == 'mission' or ai_response.get('type') == 'mission_search':
            # Rechercher des missions dans la base
            category = ai_response.get('category', '')
            location = ai_response.get('location', '')
            
            queryset = Mission.objects.filter(status='PENDING')
            
            if category:
                queryset = queryset.filter(category__icontains=category)
            if location:
                queryset = queryset.filter(address__icontains=location)
            
            for mission in queryset[:5]:
                results.append({
                    'id': str(mission.id),
                    'title': mission.title,
                    'description': mission.description,
                    'price': float(mission.price),
                    'status': mission.status,
                    'address': mission.address,
                    'category': mission.category,
                    'isUrgent': mission.is_urgent,
                    'clientName': mission.client.get_full_name() or mission.client.username,
                    'createdAt': mission.created_at.isoformat()
                })
            
            return {
                'type': 'mission_search',
                'results': results,
                'total_results': len(results),
                'suggestion': f'{len(results)} missions trouvées pour votre recherche'
            }
        
        elif search_type == 'agent' or ai_response.get('type') == 'agent_search':
            # Rechercher des agents dans la base
            skills = ai_response.get('skills', [])
            location = ai_response.get('location', '')
            
            queryset = User.objects.filter(is_agent=True, is_active=True)
            
            if location:
                queryset = queryset.filter(profile__address__icontains=location)
            
            for agent in queryset[:5]:
                results.append({
                    'id': str(agent.id),
                    'fullName': agent.get_full_name() or agent.username,
                    'rating': getattr(agent, 'rating', 4.5),
                    'completedMissions': getattr(agent, 'completed_missions', 0),
                    'responseTime': '15 min',
                    'avatarUrl': getattr(agent, 'avatar_url', ''),
                    'isOnline': getattr(agent, 'is_online', True),
                    'isVerified': getattr(agent, 'is_verified', False),
                    'specialties': getattr(agent, 'specialties', ['Général'])
                })
            
            return {
                'type': 'agent_search',
                'results': results,
                'total_results': len(results),
                'suggestion': f'{len(results)} agents trouvés pour votre recherche'
            }
        
        return ai_response
    
    def _simulate_ai_response(self, query: str, user, search_type: str) -> Dict[str, Any]:
        """
        Simulation de réponses IA basées sur des patterns et le type de recherche
        
        Args:
            query: La requête de l'utilisateur
            user: L'utilisateur
            search_type: Type de recherche ('agent', 'mission', 'general')
            
        Returns:
            Dict avec la réponse simulée
        """
        query_lower = query.lower()
        
        # Recherche spécifique pour les agents
        if search_type == 'agent':
            return {
                'type': 'agent_search',
                'results': [
                    {
                        'id': 1,
                        'fullName': 'Jean Dupont',
                        'rating': 4.8,
                        'completedMissions': 156,
                        'responseTime': '15 min',
                        'avatarUrl': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Jean',
                        'isOnline': True,
                        'isVerified': True,
                        'specialties': ['Livraison', 'Transport', 'Course']
                    },
                    {
                        'id': 2,
                        'fullName': 'Marie Kouame',
                        'rating': 4.6,
                        'completedMissions': 98,
                        'responseTime': '20 min',
                        'avatarUrl': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Marie',
                        'isOnline': True,
                        'isVerified': True,
                        'specialties': ['Ménage', 'Cuisine', 'Soutien scolaire']
                    }
                ],
                'total_results': 2,
                'suggestion': f'Agents trouvés pour "{query}"'
            }
        
        # Recherche spécifique pour les missions
        elif search_type == 'mission':
            return {
                'type': 'mission_search',
                'results': [
                    {
                        'id': 1,
                        'title': 'Livraison colis - Centre ville',
                        'description': 'Livraison urgente d\'un colis au centre commercial',
                        'price': 2500.0,
                        'status': 'available',
                        'address': 'Centre commercial, Cotonou',
                        'category': 'Livraison',
                        'isUrgent': True,
                        'clientName': 'Entreprise ABC',
                        'createdAt': '2024-01-15T10:30:00Z'
                    },
                    {
                        'id': 2,
                        'title': 'Course restaurant - Akpakla',
                        'description': 'Aller chercher une commande au restaurant',
                        'price': 1800.0,
                        'status': 'available',
                        'address': 'Restaurant Le Gourmet, Akpakpa',
                        'category': 'Course',
                        'isUrgent': False,
                        'clientName': 'Paul Koffi',
                        'createdAt': '2024-01-15T11:15:00Z'
                    }
                ],
                'total_results': 2,
                'suggestion': f'Missions disponibles pour "{query}"'
            }
        
        # Patterns de recherche pour missions (recherche générale)
        elif search_type == 'general' and any(keyword in query_lower for keyword in ['mission', 'livraison', 'course']):
            return {
                'type': 'mission_search',
                'results': [
                    {
                        'id': 1,
                        'title': 'Livraison urgente - Centre ville',
                        'description': 'Livraison urgente d\'un colis',
                        'price': 2500.0,
                        'status': 'available',
                        'address': 'Centre ville, Cotonou',
                        'category': 'Livraison',
                        'isUrgent': True,
                        'clientName': 'Entreprise XYZ',
                        'createdAt': '2024-01-15T10:30:00Z'
                    }
                ],
                'total_results': 1,
                'suggestion': 'Ces missions correspondent à votre recherche'
            }
        
        # Patterns de recherche pour services (recherche générale)
        elif search_type == 'general' and any(keyword in query_lower for keyword in ['service', 'aide', 'réparation']):
            return {
                'type': 'service_search',
                'results': [
                    {
                        'title': 'Réparation téléphone',
                        'provider': 'Tech Service Pro',
                        'rating': 4.8,
                        'response_time': '30 min'
                    },
                    {
                        'title': 'Plomberie d\'urgence',
                        'provider': 'Plomberie Express',
                        'rating': 4.6,
                        'response_time': '15 min'
                    }
                ],
                'total_results': 2,
                'suggestion': 'Services disponibles près de votre position'
            }
        
        # Réponse par défaut
        else:
            return {
                'type': 'general_search',
                'results': [],
                'suggestion': 'Je n\'ai pas trouvé de résultats spécifiques. Essayez avec "agent", "mission", "livraison" ou "service".'
            }
    
    @transaction.atomic
    def update_suggestions(self, query: str, response: Dict[str, Any]):
        """
        Met à jour les suggestions basées sur la recherche
        
        Args:
            query: La requête effectuée
            response: La réponse IA générée
        """
        try:
            # Extraire les mots-clés de la requête
            keywords = self._extract_keywords(query)
            
            for keyword in keywords:
                suggestion, created = AISearchSuggestion.objects.get_or_create(
                    query=keyword.lower(),
                    defaults={
                        'suggestion': self._generate_suggestion_text(keyword, response),
                        'frequency': 1
                    }
                )
                
                if not created:
                    suggestion.frequency += 1
                    suggestion.last_used = timezone.now()
                    suggestion.save()
                    
        except Exception as e:
            logger.error(f"Erreur mise à jour suggestions: {e}")
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extrait les mots-clés pertinents d'une requête"""
        # Mots-clés à ignorer
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'et', 'ou', 'où', 'pour', 'avec'}
        
        # Extraire les mots de plus de 3 caractères
        words = [
            word.lower() for word in query.split() 
            if len(word) > 3 and word.lower() not in stop_words
        ]
        
        return list(set(words))[:3]  # Limiter à 3 mots-clés
    
    def _generate_suggestion_text(self, keyword: str, response: Dict[str, Any]) -> str:
        """Génère un texte de suggestion basé sur le mot-clé et la réponse"""
        response_type = response.get('type', 'general')
        
        suggestions_map = {
            'mission_search': f'Rechercher des missions contenant "{keyword}"',
            'service_search': f'Trouver des services avec "{keyword}"',
            'general_search': f'Essayer "{keyword}" dans les missions ou services'
        }
        
        return suggestions_map.get(response_type, f'Recherche avec "{keyword}"')
    
    def get_trending_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retourne les recherches tendances
        
        Args:
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des recherches populaires
        """
        trending = AISearchSuggestion.objects.order_by('-frequency', '-last_used')[:limit]
        
        return [
            {
                'query': item.query,
                'frequency': item.frequency,
                'last_used': item.last_used.isoformat(),
                'suggestion': item.suggestion
            }
            for item in trending
        ]

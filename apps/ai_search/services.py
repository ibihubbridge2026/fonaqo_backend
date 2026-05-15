import json
import logging
from typing import Dict, Any, List
from django.db import transaction
from django.utils import timezone
from .models import AISearchSuggestion

logger = logging.getLogger(__name__)


class AISearchService:
    """Service pour la recherche IA avec suggestions intelligentes"""
    
    def __init__(self):
        self.max_suggestions = 10
        
    def search(self, query: str, user) -> Dict[str, Any]:
        """
        Effectue une recherche IA et retourne une réponse structurée
        
        Args:
            query: La requête de l'utilisateur
            user: L'utilisateur qui effectue la recherche
            
        Returns:
            Dict contenant la réponse IA et métadonnées
        """
        try:
            # TODO: Intégrer avec un vrai service IA (OpenAI, Claude, etc.)
            # Pour l'instant, simulation de réponses intelligentes
            
            response = self._simulate_ai_response(query, user)
            
            return {
                'status': 'success',
                'query': query,
                'response': response,
                'timestamp': timezone.now().isoformat(),
                'confidence': 0.85,
                'source': 'ai_simulation'
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche IA: {e}")
            return {
                'status': 'error',
                'error': 'Service de recherche IA indisponible',
                'query': query,
                'timestamp': timezone.now().isoformat()
            }
    
    def _simulate_ai_response(self, query: str, user) -> Dict[str, Any]:
        """
        Simulation de réponses IA basées sur des patterns
        
        Args:
            query: La requête de l'utilisateur
            user: L'utilisateur
            
        Returns:
            Dict avec la réponse simulée
        """
        query_lower = query.lower()
        
        # Patterns de recherche pour missions
        if any(keyword in query_lower for keyword in ['mission', 'livraison', 'course']):
            return {
                'type': 'mission_search',
                'results': [
                    {
                        'title': 'Livraison urgente - Centre ville',
                        'distance': '2.3 km',
                        'price': '2500 FCFA',
                        'urgency': 'high'
                    },
                    {
                        'title': 'Course restaurant - Akpakla',
                        'distance': '5.1 km', 
                        'price': '1800 FCFA',
                        'urgency': 'medium'
                    }
                ],
                'total_results': 2,
                'suggestion': 'Ces missions correspondent à votre recherche'
            }
        
        # Patterns de recherche pour services
        elif any(keyword in query_lower for keyword in ['service', 'aide', 'réparation']):
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
                'suggestion': 'Je n\'ai pas trouvé de résultats spécifiques. Essayez avec "mission", "livraison" ou "service".'
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

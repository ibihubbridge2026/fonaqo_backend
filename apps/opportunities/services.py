"""
Services pour la gestion des opportunités
"""

import logging
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from .models import Opportunity, OpportunityApplication, OpportunityMatch

logger = logging.getLogger(__name__)


class OpportunityMatchingService:
    """Service pour le matching intelligent des opportunités"""
    
    def __init__(self):
        self.max_distance_km = 50  # Distance maximale pour le matching
        self.min_score_threshold = 0.6  # Score minimum pour considérer un match
    
    def find_matching_opportunities(self, user_profile, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Trouve les opportunités qui correspondent au profil de l'utilisateur
        
        Args:
            user_profile: Profil de l'utilisateur (agent ou client)
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des opportunités correspondantes avec scores de matching
        """
        try:
            # Obtenir la localisation de l'utilisateur
            user_location = self._get_user_location(user_profile)
            if not user_location:
                return []
            
            # Récupérer les opportunités disponibles
            available_opportunities = Opportunity.objects.filter(
                status='available',
                expires_at__gt=timezone.now()
            ).annotate(
                distance=Distance('location', user_location)
            ).filter(
                distance__lte=D(km=self.max_distance_km)
            ).order_by('distance')
            
            # Calculer les scores de matching
            matching_results = []
            for opportunity in available_opportunities[:limit]:
                score = self._calculate_matching_score(user_profile, opportunity)
                
                if score >= self.min_score_threshold:
                    matching_results.append({
                        'opportunity': opportunity,
                        'score': score,
                        'distance_km': opportunity.distance.km,
                        'matching_reasons': self._get_matching_reasons(user_profile, opportunity)
                    })
            
            # Trier par score de matching
            matching_results.sort(key=lambda x: x['score'], reverse=True)
            
            return matching_results
            
        except Exception as e:
            logger.error(f"Erreur lors du matching d'opportunités: {e}")
            return []
    
    def _get_user_location(self, user_profile) -> Optional[Point]:
        """Extrait la localisation du profil utilisateur"""
        try:
            if hasattr(user_profile, 'location') and user_profile.location:
                return user_profile.location
            elif hasattr(user_profile, 'latitude') and hasattr(user_profile, 'longitude'):
                return Point(user_profile.longitude, user_profile.latitude)
            return None
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de la localisation: {e}")
            return None
    
    def _calculate_matching_score(self, user_profile, opportunity) -> float:
        """
        Calcule le score de matching entre un profil et une opportunité
        
        Returns:
            Score entre 0.0 et 1.0
        """
        score = 0.0
        
        # Score basé sur la distance (40% du poids)
        if hasattr(opportunity, 'distance'):
            distance_km = opportunity.distance.km
            distance_score = max(0, 1 - (distance_km / self.max_distance_km))
            score += distance_score * 0.4
        
        # Score basé sur les compétences (30% du poids)
        skills_score = self._calculate_skills_match(user_profile, opportunity)
        score += skills_score * 0.3
        
        # Score basé sur la disponibilité (20% du poids)
        availability_score = self._calculate_availability_match(user_profile, opportunity)
        score += availability_score * 0.2
        
        # Score basé sur l'historique (10% du poids)
        history_score = self._calculate_history_match(user_profile, opportunity)
        score += history_score * 0.1
        
        return min(score, 1.0)
    
    def _calculate_skills_match(self, user_profile, opportunity) -> float:
        """Calcule le score de matching basé sur les compétences"""
        try:
            user_skills = set()
            opportunity_skills = set()
            
            # Extraire les compétences de l'utilisateur
            if hasattr(user_profile, 'skills'):
                user_skills.update(user_profile.skills)
            elif hasattr(user_profile, 'specialties'):
                user_skills.update(user_profile.specialties)
            
            # Extraire les compétences requises pour l'opportunité
            if hasattr(opportunity, 'required_skills'):
                opportunity_skills.update(opportunity.required_skills)
            elif hasattr(opportunity, 'category'):
                opportunity_skills.add(opportunity.category)
            
            if not opportunity_skills:
                return 0.5  # Score neutre si pas de compétences requises
            
            # Calculer le pourcentage de compétences correspondantes
            matching_skills = user_skills.intersection(opportunity_skills)
            if opportunity_skills:
                return len(matching_skills) / len(opportunity_skills)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des compétences: {e}")
            return 0.0
    
    def _calculate_availability_match(self, user_profile, opportunity) -> float:
        """Calcule le score de matching basé sur la disponibilité"""
        try:
            # Vérifier si l'utilisateur est disponible
            if hasattr(user_profile, 'is_available') and not user_profile.is_available:
                return 0.0
            
            # Vérifier les plages horaires
            if hasattr(opportunity, 'start_time') and hasattr(user_profile, 'available_hours'):
                # Logique simplifiée pour la disponibilité horaire
                return 0.8
            
            # Score par défaut si pas de contraintes spécifiques
            return 0.7
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul de disponibilité: {e}")
            return 0.0
    
    def _calculate_history_match(self, user_profile, opportunity) -> float:
        """Calcule le score basé sur l'historique des interactions"""
        try:
            # Vérifier les missions complétées similaires
            if hasattr(user_profile, 'completed_missions_count'):
                completed_count = user_profile.completed_missions_count
                # Plus d'expérience = meilleur score
                return min(completed_count / 100, 1.0)
            
            return 0.3  # Score par défaut
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul de l'historique: {e}")
            return 0.0
    
    def _get_matching_reasons(self, user_profile, opportunity) -> List[str]:
        """Retourne les raisons du matching pour l'affichage dans l'UI"""
        reasons = []
        
        try:
            # Raison liée à la distance
            if hasattr(opportunity, 'distance'):
                distance_km = opportunity.distance.km
                if distance_km < 5:
                    reasons.append("Très proche de votre position")
                elif distance_km < 15:
                    reasons.append("Proche de votre position")
            
            # Raison liée aux compétences
            skills_match = self._calculate_skills_match(user_profile, opportunity)
            if skills_match > 0.8:
                reasons.append("Compétences parfaitement adaptées")
            elif skills_match > 0.5:
                reasons.append("Compétences correspondantes")
            
            # Raison liée à la disponibilité
            if hasattr(user_profile, 'is_available') and user_profile.is_available:
                reasons.append("Disponible immédiatement")
            
            # Raison liée à l'expérience
            if hasattr(user_profile, 'completed_missions_count'):
                if user_profile.completed_missions_count > 50:
                    reasons.append("Expérience pertinente")
                elif user_profile.completed_missions_count > 10:
                    reasons.append("Bonne expérience")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération des raisons: {e}")
        
        return reasons[:3]  # Limiter à 3 raisons maximum
    
    @transaction.atomic
    def create_opportunity_match(self, user, opportunity, score: float) -> OpportunityMatch:
        """
        Crée une nouvelle correspondance entre un utilisateur et une opportunité
        
        Args:
            user: L'utilisateur
            opportunity: L'opportunité
            score: Le score de matching
            
        Returns:
            L'objet OpportunityMatch créé
        """
        try:
            # Vérifier si une correspondance existe déjà
            existing_match = OpportunityMatch.objects.filter(
                user=user,
                opportunity=opportunity
            ).first()
            
            if existing_match:
                # Mettre à jour le score existant
                existing_match.score = score
                existing_match.updated_at = timezone.now()
                existing_match.save()
                return existing_match
            
            # Créer une nouvelle correspondance
            match = OpportunityMatch.objects.create(
                user=user,
                opportunity=opportunity,
                score=score,
                status='pending'
            )
            
            logger.info(f"Nouveau match créé: user={user.id}, opportunity={opportunity.id}, score={score}")
            return match
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du match: {e}")
            raise
    
    def get_recommended_opportunities(self, user, limit: int = 20) -> List[Opportunity]:
        """
        Retourne les opportunités recommandées pour un utilisateur
        
        Args:
            user: L'utilisateur
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des opportunités recommandées
        """
        try:
            # Obtenir le profil de l'utilisateur
            user_profile = self._get_user_profile(user)
            if not user_profile:
                return Opportunity.objects.none()
            
            # Trouver les correspondances
            matching_results = self.find_matching_opportunities(user_profile, limit)
            
            # Extraire les opportunités
            recommended_opportunities = [
                result['opportunity'] for result in matching_results
            ]
            
            return recommended_opportunities
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des recommandations: {e}")
            return Opportunity.objects.none()
    
    def _get_user_profile(self, user):
        """Obtient le profil approprié de l'utilisateur"""
        try:
            # Essayer de récupérer le profil agent
            if hasattr(user, 'agentprofile'):
                return user.agentprofile
            # Essayer de récupérer le profil client
            elif hasattr(user, 'clientprofile'):
                return user.clientprofile
            # Retourner l'utilisateur lui-même si pas de profil spécifique
            return user
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du profil: {e}")
            return user

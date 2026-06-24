"""Service de gestion du programme de fidélité clients."""

from decimal import Decimal
from django.db import transaction
from apps.accounts.models import ClientRewardProfile
from apps.missions.models import Mission


class LoyaltyService:
    """Service pour gérer les points et badges de fidélité des clients."""

    # Configuration des points
    POINTS_PER_MISSION = 10  # Points de base par mission complétée
    POINTS_PER_1000_FCFA = 5  # Points bonus pour missions > 10k FCFA
    HIGH_VALUE_THRESHOLD = Decimal('10000.00')  # Seuil mission haute valeur

    # Configuration des badges clients
    CLIENT_BADGES = {
        'first_mission': {'name': 'Première Mission', 'icon': '🎯', 'condition': lambda p: p.total_missions_completed >= 1},
        'loyal_client': {'name': 'Client Fidèle', 'icon': '⭐', 'condition': lambda p: p.total_missions_completed >= 10},
        'vip_client': {'name': 'VIP', 'icon': '👑', 'condition': lambda p: p.total_missions_completed >= 50},
        'big_spender': {'name': 'Gros Dépenseur', 'icon': '💰', 'condition': lambda p: p.total_spent >= Decimal('100000.00')},
        'super_spender': {'name': 'Super Dépenseur', 'icon': '💎', 'condition': lambda p: p.total_spent >= Decimal('500000.00')},
    }

    @staticmethod
    def get_or_create_profile(user):
        """Récupère ou crée le profil de fidélité d'un client."""
        if not user.is_client:
            return None
        profile, created = ClientRewardProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    @transaction.atomic
    def award_mission_points(mission: Mission):
        """Attribue des points à un client pour une mission complétée (idempotent)."""
        if mission.status != 'COMPLETED' or not mission.client:
            return

        # Idempotency: charger la mission avec verrou pour éviter double attribution
        mission = Mission.objects.select_for_update().get(pk=mission.pk)
        if mission.loyalty_points_awarded:
            return

        profile = LoyaltyService.get_or_create_profile(mission.client)
        if not profile:
            return

        # Points de base
        points = LoyaltyService.POINTS_PER_MISSION

        # Bonus haute valeur
        if mission.price >= LoyaltyService.HIGH_VALUE_THRESHOLD:
            extra_points = int((mission.price / Decimal('1000.00')) * LoyaltyService.POINTS_PER_1000_FCFA)
            points += extra_points

        # Mettre à jour le profil
        profile.add_points(points, reason=f'Mission complétée: {mission.id}')
        profile.total_missions_completed += 1
        profile.total_spent += mission.price

        # Vérifier et débloquer les badges
        LoyaltyService._check_and_unlock_badges(profile)

        profile.save(update_fields=['total_missions_completed', 'total_spent', 'badges_unlocked', 'updated_at'])

        # Marquer la mission comme déjà traitée (idempotent)
        Mission.objects.filter(pk=mission.pk).update(loyalty_points_awarded=True)

    @staticmethod
    def _check_and_unlock_badges(profile: ClientRewardProfile):
        """Vérifie et débloque les badges éligibles."""
        for badge_id, badge_info in LoyaltyService.CLIENT_BADGES.items():
            if badge_id not in profile.badges_unlocked:
                if badge_info['condition'](profile):
                    profile.badges_unlocked.append(badge_id)

    @staticmethod
    def get_client_rewards(user):
        """Retourne les récompenses d'un client (points, niveau, badges)."""
        profile = LoyaltyService.get_or_create_profile(user)
        if not profile:
            return None

        # Construire la liste des badges avec détails
        badges = []
        for badge_id in profile.badges_unlocked:
            if badge_id in LoyaltyService.CLIENT_BADGES:
                badge_info = LoyaltyService.CLIENT_BADGES[badge_id]
                badges.append({
                    'id': badge_id,
                    'name': badge_info['name'],
                    'icon': badge_info['icon'],
                })

        # Badges disponibles (non débloqués)
        available_badges = []
        for badge_id, badge_info in LoyaltyService.CLIENT_BADGES.items():
            if badge_id not in profile.badges_unlocked:
                available_badges.append({
                    'id': badge_id,
                    'name': badge_info['name'],
                    'icon': badge_info['icon'],
                })

        return {
            'points': profile.points,
            'level': profile.level,
            'total_missions_completed': profile.total_missions_completed,
            'total_spent': float(profile.total_spent),
            'badges_unlocked': badges,
            'available_badges': available_badges,
            'points_to_next_level': LoyaltyService._points_to_next_level(profile.level),
        }

    @staticmethod
    def _points_to_next_level(current_level: int) -> int:
        """Retourne le nombre de points nécessaires pour le niveau suivant."""
        level_thresholds = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500, float('inf')]
        if current_level >= 10:
            return 0
        return level_thresholds[current_level] - level_thresholds[current_level - 1]

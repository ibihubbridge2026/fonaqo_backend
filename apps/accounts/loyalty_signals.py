"""Signaux Django pour le programme de fidélité clients."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.missions.models import Mission
from apps.accounts.loyalty_service import LoyaltyService


@receiver(post_save, sender=Mission)
def award_loyalty_points_on_mission_completion(sender, instance, created, **kwargs):
    """Attribue des points de fidélité quand une mission est complétée."""
    if not created and instance.status == 'COMPLETED':
        LoyaltyService.award_mission_points(instance)

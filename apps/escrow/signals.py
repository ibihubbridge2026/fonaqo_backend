from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.missions.models import Mission
from .services import EscrowService

@receiver(post_save, sender=Mission)
def handle_mission_escrow(sender, instance, created, **kwargs):
    # Si la mission vient d'être acceptée par un agent
    if instance.status == Mission.MissionStatus.ACCEPTED and not hasattr(instance, 'escrow'):
        EscrowService.lock_funds(instance)
    
    # Si la mission est terminée, on libère les fonds
    elif instance.status == Mission.MissionStatus.COMPLETED and hasattr(instance, 'escrow'):
        if instance.escrow.status == 'HELD':
            EscrowService.release_funds(instance)
            
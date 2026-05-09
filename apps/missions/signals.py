from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Mission, MissionTimeline, AgentLevel
from apps.wallets.models import Wallet, Transaction
from apps.escrow.models import Escrow
from apps.core.choices import EscrowStatus, MissionStatus, TransactionStatus

@receiver(post_save, sender=Mission)
def handle_mission_status_change(sender, instance, created, **kwargs):
    """Gère les conséquences de chaque changement de statut d'une mission"""
    
    # 1. Création automatique d'une entrée dans la Timeline (Point 1)
    MissionTimeline.objects.create(
        mission=instance,
        status=instance.status,
        message=f"Statut mis à jour : {instance.get_status_display()}",
        created_by=instance.agent if instance.agent else instance.client
    )

    # 2. Logique de paiement final (Point 15)
    if instance.status == MissionStatus.COMPLETED:
        escrow = instance.escrow
        if escrow.status == EscrowStatus.HELD:
            # Libérer l'argent vers le wallet de l'agent
            agent_wallet = Wallet.objects.get(user=instance.agent)
            
            # Transfert financier
            agent_wallet.balance += instance.price
            agent_wallet.save()
            
            # Marquer le séquestre comme libéré
            escrow.status = EscrowStatus.RELEASED
            escrow.released_at = timezone.now()
            escrow.save()
            
            # Créer la transaction pour l'historique
            Transaction.objects.create(
                wallet=agent_wallet,
                amount=instance.price,
                transaction_type=Transaction.TransactionType.MISSION_PAYMENT,
                status=TransactionStatus.COMPLETED,
                description=f"Paiement reçu pour la mission : {instance.title}",
                mission=instance
            )
            
            # 3. MISE À JOUR DU SCORE & NIVEAU (Points 2 & 3)
            update_agent_stats_and_level(instance.agent)

def update_agent_stats_and_level(agent):
    """IA simple : recalcule le score et le niveau de l'agent"""
    from django.db.models import Avg, Count
    
    # Calcul du nombre de missions terminées
    completed_count = Mission.objects.filter(agent=agent, status=MissionStatus.COMPLETED).count()
    
    # Mise à jour du taux de complétion
    total_assigned = Mission.objects.filter(agent=agent).count()
    agent.completion_rate = (completed_count / total_assigned * 100) if total_assigned > 0 else 0
    
    # Logique de montée de niveau (Exemple : Novice -> Expert)
    levels = AgentLevel.objects.all().order_by('min_missions')
    for level in levels:
        if completed_count >= level.min_missions:
            agent.level = level
    
    agent.save()
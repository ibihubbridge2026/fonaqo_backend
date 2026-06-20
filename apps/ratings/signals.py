"""Signaux Django pour mise à jour automatique des moyennes de notation."""

from django.db.models import Avg, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Rating
from apps.accounts.models import AgentProfile, ClientProfile


@receiver(post_save, sender=Rating)
@receiver(post_delete, sender=Rating)
def update_reviewee_rating_stats(sender, instance, **kwargs):
    """Recalcule la moyenne et le nombre de notes du reviewee après création/suppression."""
    reviewee = instance.reviewee
    
    # Déterminer le profil à mettre à jour (agent ou client)
    if instance.rating_type == Rating.RatingType.CLIENT_RATES_AGENT:
        # Client note agent → mettre à jour AgentProfile
        try:
            profile = AgentProfile.objects.get(user=reviewee)
        except AgentProfile.DoesNotExist:
            return
    else:
        # Agent note client → mettre à jour ClientProfile
        try:
            profile = ClientProfile.objects.get(user=reviewee)
        except ClientProfile.DoesNotExist:
            return
    
    # Calculer la nouvelle moyenne et le nombre de notes
    ratings = Rating.objects.filter(
        reviewee=reviewee,
        rating_type=instance.rating_type,
    )
    
    stats = ratings.aggregate(
        avg_rating=Avg('score'),
        count=Count('id'),
    )
    
    profile.average_rating = stats['avg_rating'] or 0.00
    profile.ratings_count = stats['count'] or 0
    profile.save(update_fields=['average_rating', 'ratings_count', 'updated_at'])

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views import View


class VitrineGuestCreateView(View):
    """Page vitrine — création mission sans compte mobile."""

    def get(self, request):
        return render(request, 'vitrine/creer_mission_guest.html', {
            'google_places_api_key': getattr(settings, 'GOOGLE_PLACES_API_KEY', ''),
        })


class VitrineGuestTrackView(View):
    """Page vitrine — suivi mission par code FNC-XXXX-BJ."""

    def get(self, request):
        reference = request.GET.get('ref', '').strip()
        return render(request, 'vitrine/suivi_mission_guest.html', {
            'reference': reference,
            'google_places_api_key': getattr(settings, 'GOOGLE_PLACES_API_KEY', ''),
        })


class VitrineAgentPublicView(View):
    """Page vitrine publique — profil agent (scan QR badge)."""

    def get(self, request, agent_id):
        from decimal import Decimal
        from django.db.models import Sum

        from apps.accounts.models import AgentProfile
        from apps.core.choices import AgentBadgeStatus, MissionStatus
        from apps.escrow.models import EscrowSplitRecord
        from apps.missions.models import Mission
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = get_object_or_404(User, pk=agent_id, is_agent=True)
        profile, _ = AgentProfile.objects.get_or_create(user=user)

        completed_qs = Mission.objects.filter(agent=user, status=MissionStatus.COMPLETED)
        completed = completed_qs.count()

        # Montant cumulé encaissé (part agent dans EscrowSplitRecord)
        total_earnings_agg = EscrowSplitRecord.objects.filter(
            beneficiary_user=user,
            beneficiary_type=EscrowSplitRecord.BeneficiaryType.AGENT,
        ).aggregate(total=Sum('amount_fcfa'))
        total_earnings = total_earnings_agg['total'] or Decimal('0')

        # Note moyenne depuis le nouveau système de notation (profile.average_rating)
        avg_rating = profile.average_rating if profile.average_rating > 0 else None

        return render(request, 'vitrine/agent_public.html', {
            'agent': user,
            'profile': profile,
            'completed_missions': completed,
            'total_earnings': total_earnings,
            'avg_rating': avg_rating,
            'ratings_count': profile.ratings_count,
            'has_badge': profile.badge_status == AgentBadgeStatus.APPROVED,
            'is_internal': profile.is_internal,
            'is_certified': profile.badge_status == AgentBadgeStatus.APPROVED,
        })

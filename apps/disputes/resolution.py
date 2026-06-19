from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.core.choices import EscrowStatus, MissionStatus
from apps.disputes.models import Dispute
from apps.escrow.models import EscrowSplitRecord
from apps.escrow.services import EscrowService
from apps.notifications.services import NotificationService

from .services import notify_dispute_resolution


class DisputeResolutionService:
    """Moteur d'arbitrage SuperAdmin pour missions en litige."""

    REFUND_CLIENT = 'REFUND_CLIENT'
    PAY_AGENT = 'PAY_AGENT'
    ARBITRAGE_SPLIT = 'ARBITRAGE_SPLIT'

    @classmethod
    @transaction.atomic
    def resolve(cls, dispute, resolution_type: str, *, admin_user, notes: str = '',
                client_percent: Decimal | None = None, agent_percent: Decimal | None = None):
        mission = dispute.mission
        if mission.status != MissionStatus.DISPUTED:
            raise ValueError('La mission n\'est pas en litige')

        if resolution_type == cls.REFUND_CLIENT:
            cls._refund_client(dispute, notes)
        elif resolution_type == cls.PAY_AGENT:
            cls._pay_agent(dispute, notes)
        elif resolution_type == cls.ARBITRAGE_SPLIT:
            if client_percent is None or agent_percent is None:
                raise ValueError('client_percent et agent_percent requis')
            cls._arbitrage_split(
                dispute,
                notes,
                client_percent=Decimal(client_percent),
                agent_percent=Decimal(agent_percent),
            )
        else:
            raise ValueError(f'Type de résolution inconnu: {resolution_type}')

        dispute.resolution_notes = notes
        dispute.resolved_by = admin_user
        dispute.resolved_at = timezone.now()
        dispute.status = Dispute.Status.RESOLVED
        dispute.save(update_fields=[
            'resolution_notes', 'resolved_by', 'resolved_at', 'status', 'updated_at',
        ])

        notify_dispute_resolution(dispute)
        return dispute

    @classmethod
    def _refund_client(cls, dispute, notes: str):
        mission = dispute.mission
        if hasattr(mission, 'escrow') and mission.escrow.status == EscrowStatus.HELD:
            EscrowService.refund_to_client(
                mission,
                reason=notes or f'Litige #{dispute.id} — remboursement client',
            )
        mission.status = MissionStatus.CANCELLED
        mission.save(update_fields=['status', 'updated_at'])
        dispute.refund_amount = getattr(mission.escrow, 'amount', None) if hasattr(mission, 'escrow') else None
        dispute.save(update_fields=['refund_amount', 'updated_at'])

    @classmethod
    def _pay_agent(cls, dispute, notes: str):
        mission = dispute.mission
        if not mission.agent_id:
            raise ValueError('Aucun agent assigné à cette mission')
        EscrowService.release_to_agent(mission)
        mission.status = MissionStatus.COMPLETED
        mission.save(update_fields=['status', 'updated_at'])

    @classmethod
    def _arbitrage_split(cls, dispute, notes: str, *,
                         client_percent: Decimal, agent_percent: Decimal):
        from apps.wallets.models import Transaction, Wallet

        total_pct = client_percent + agent_percent
        if total_pct <= 0 or total_pct > Decimal('100'):
            raise ValueError('La somme des pourcentages doit être entre 1 et 100')

        mission = dispute.mission
        if not mission.agent_id:
            raise ValueError('Aucun agent assigné pour un split agent')

        try:
            escrow = mission.escrow
        except Exception as exc:
            raise ValueError('Aucun séquestre actif pour cette mission') from exc

        if escrow.status != EscrowStatus.HELD:
            raise ValueError('Le séquestre n\'est pas bloqué')

        gross = Decimal(escrow.amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        client_share = (gross * client_percent / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP,
        )
        agent_share = (gross * agent_percent / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP,
        )
        remainder = gross - client_share - agent_share
        if remainder > 0:
            client_share += remainder

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        agent_wallet = Wallet.objects.select_for_update().get(user=mission.agent)

        if client_wallet.escrow_balance < gross:
            raise ValueError('Solde séquestre insuffisant')

        client_wallet.escrow_balance -= gross
        client_wallet.balance += client_share
        client_wallet.save(update_fields=['balance', 'escrow_balance', 'updated_at'])

        agent_wallet.balance += agent_share
        agent_wallet.save(update_fields=['balance', 'updated_at'])

        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save(update_fields=['status', 'released_at'])

        if client_share > 0:
            EscrowSplitRecord.objects.create(
                mission=mission,
                beneficiary_type=EscrowSplitRecord.BeneficiaryType.CLIENT,
                amount_fcfa=client_share,
                beneficiary_user=mission.client,
            )
            Transaction.objects.create(
                wallet=client_wallet,
                mission=mission,
                amount=client_share,
                transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
                description=f'Arbitrage litige {dispute.id} — part client {client_percent}%',
            )

        if agent_share > 0:
            EscrowSplitRecord.objects.create(
                mission=mission,
                beneficiary_type=EscrowSplitRecord.BeneficiaryType.AGENT,
                amount_fcfa=agent_share,
                beneficiary_user=mission.agent,
            )
            Transaction.objects.create(
                wallet=agent_wallet,
                mission=mission,
                amount=agent_share,
                transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
                description=f'Arbitrage litige {dispute.id} — part agent {agent_percent}%',
            )

        mission.status = MissionStatus.COMPLETED
        mission.save(update_fields=['status', 'updated_at'])
        dispute.refund_amount = client_share
        dispute.penalty_amount = agent_share
        dispute.save(update_fields=['refund_amount', 'penalty_amount', 'updated_at'])

        for user in (mission.client, mission.agent):
            if user:
                NotificationService.send_to_user(
                    user,
                    'Litige arbitré',
                    f'Arbitrage appliqué sur la mission « {mission.title[:60]} ».',
                    data={'type': 'DISPUTE_ARBITRAGED', 'mission_id': str(mission.id)},
                )

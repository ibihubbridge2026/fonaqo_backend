from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.choices import EscrowStatus, TransactionStatus
from apps.wallets.models import Transaction, Wallet

from .models import Escrow


class EscrowService:
    """Source unique de vérité pour les flux financiers liés aux missions."""

    @staticmethod
    def escrow_amount(mission) -> Decimal:
        service = (
            mission.service_amount
            if mission.service_amount and mission.service_amount > 0
            else mission.price
        )
        return Decimal(service) + Decimal(mission.service_fee or 0)

    @staticmethod
    def total_required_balance(mission) -> Decimal:
        return EscrowService.escrow_amount(mission) + Decimal(
            mission.purchase_amount or 0
        )

    @staticmethod
    def assert_sufficient_balance(client, mission) -> None:
        wallet, _ = Wallet.objects.get_or_create(user=client)
        required = EscrowService.total_required_balance(mission)
        if wallet.balance < required:
            raise ValueError(
                f"Solde insuffisant. Requis: {required} FCFA, "
                f"disponible: {wallet.balance} FCFA"
            )

    @staticmethod
    @transaction.atomic
    def lock_on_accept(mission) -> Escrow:
        """Bloque les frais de prestation en séquestre à l'acceptation."""
        if hasattr(mission, "escrow") and mission.escrow.status == EscrowStatus.HELD:
            return mission.escrow

        EscrowService.assert_sufficient_balance(mission.client, mission)

        client_wallet, _ = Wallet.objects.get_or_create(user=mission.client)
        client_wallet = Wallet.objects.select_for_update().get(pk=client_wallet.pk)

        amount = EscrowService.escrow_amount(mission)
        client_wallet.balance -= amount
        client_wallet.escrow_balance += amount
        client_wallet.save(update_fields=["balance", "escrow_balance", "updated_at"])

        escrow = Escrow.objects.create(
            mission=mission,
            amount=amount,
            status=EscrowStatus.HELD,
        )

        Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=-amount,
            transaction_type=Transaction.TransactionType.ESCROW_LOCK,
            status=TransactionStatus.COMPLETED,
            description=f"Séquestre pour mission {mission.id}",
        )
        return escrow

    @staticmethod
    @transaction.atomic
    def release_purchase_to_agent(mission) -> None:
        """Transfère immédiatement le montant des achats à l'agent."""
        if not mission.agent:
            raise ValueError("Aucun agent assigné à cette mission")
        if mission.purchase_released or not mission.purchase_amount:
            return
        if mission.purchase_amount <= 0:
            return

        client_wallet, _ = Wallet.objects.get_or_create(user=mission.client)
        client_wallet = Wallet.objects.select_for_update().get(pk=client_wallet.pk)
        agent_wallet, _ = Wallet.objects.get_or_create(user=mission.agent)
        agent_wallet = Wallet.objects.select_for_update().get(pk=agent_wallet.pk)

        amount = Decimal(mission.purchase_amount)
        if client_wallet.balance < amount:
            raise ValueError("Solde client insuffisant pour débloquer les achats")

        client_wallet.balance -= amount
        client_wallet.save(update_fields=["balance", "updated_at"])
        agent_wallet.balance += amount
        agent_wallet.save(update_fields=["balance", "updated_at"])

        mission.purchase_released = True
        mission.save(update_fields=["purchase_released", "updated_at"])

        Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=-amount,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            description=f"Déblocage achats mission {mission.id}",
        )
        Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=amount,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            description=f"Réception achats mission {mission.id}",
        )

    @staticmethod
    @transaction.atomic
    def release_to_agent(mission) -> Escrow:
        """Libère le séquestre vers l'agent — idempotent si déjà libéré."""
        if not mission.agent:
            raise ValueError("Aucun agent assigné à cette mission")

        try:
            escrow = Escrow.objects.select_for_update().get(mission=mission)
        except Escrow.DoesNotExist:
            raise ValueError("Aucun séquestre trouvé pour cette mission")

        if escrow.status == EscrowStatus.RELEASED:
            return escrow

        if escrow.status != EscrowStatus.HELD:
            raise ValueError("Les fonds ne sont pas en état d'être libérés")

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        agent_wallet = Wallet.objects.select_for_update().get(user=mission.agent)

        if client_wallet.escrow_balance < escrow.amount:
            raise ValueError("Solde séquestre client insuffisant")

        client_wallet.escrow_balance -= escrow.amount
        client_wallet.save(update_fields=["escrow_balance", "updated_at"])
        agent_wallet.balance += escrow.amount
        agent_wallet.save(update_fields=["balance", "updated_at"])

        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save(update_fields=["status", "released_at"])

        Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=escrow.amount,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=f"Libération séquestre mission {mission.id}",
        )
        return escrow

    @staticmethod
    @transaction.atomic
    def refund_to_client(mission, reason: str = "") -> Escrow:
        """Rembourse le séquestre au client (annulation / litige)."""
        try:
            escrow = Escrow.objects.select_for_update().get(mission=mission)
        except Escrow.DoesNotExist:
            raise ValueError("Aucun séquestre trouvé pour cette mission")

        if escrow.status == EscrowStatus.REFUNDED:
            return escrow

        if escrow.status != EscrowStatus.HELD:
            raise ValueError("Les fonds ne peuvent pas être remboursés dans cet état")

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        client_wallet.escrow_balance -= escrow.amount
        client_wallet.balance += escrow.amount
        client_wallet.save(update_fields=["balance", "escrow_balance", "updated_at"])

        escrow.status = EscrowStatus.REFUNDED
        escrow.save(update_fields=["status"])

        Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=escrow.amount,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=reason or f"Remboursement séquestre mission {mission.id}",
        )
        return escrow

    @staticmethod
    @transaction.atomic
    def cancel_with_agent_compensation(
        mission,
        compensation_rate: Decimal = Decimal("0.20"),
    ) -> Escrow:
        """
        Annulation mission acceptée : compensation agent (20 %) + remboursement client (80 %).
        """
        if not mission.agent:
            raise ValueError("Aucun agent assigné à cette mission")

        try:
            escrow = Escrow.objects.select_for_update().get(mission=mission)
        except Escrow.DoesNotExist:
            raise ValueError("Aucun séquestre trouvé pour cette mission")

        if escrow.status != EscrowStatus.HELD:
            raise ValueError("Les fonds ne sont pas en séquestre")

        amount = Decimal(escrow.amount)
        agent_share = (amount * compensation_rate).quantize(Decimal("0.01"))
        client_share = amount - agent_share

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        agent_wallet = Wallet.objects.select_for_update().get(user=mission.agent)

        if client_wallet.escrow_balance < amount:
            raise ValueError("Solde séquestre client insuffisant")

        client_wallet.escrow_balance -= amount
        client_wallet.balance += client_share
        client_wallet.save(update_fields=["balance", "escrow_balance", "updated_at"])

        agent_wallet.balance += agent_share
        agent_wallet.save(update_fields=["balance", "updated_at"])

        escrow.status = EscrowStatus.REFUNDED
        escrow.save(update_fields=["status"])

        Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=agent_share,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=f"Dédommagement annulation (20 %) mission {mission.id}",
        )
        Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=client_share,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=f"Remboursement annulation (80 %) mission {mission.id}",
        )
        return escrow

    @staticmethod
    @transaction.atomic
    def apply_negotiated_price_increase(mission, delta: Decimal) -> None:
        """
        Prélève le supplément négocié sur le solde client et l'ajoute au séquestre si actif.
        """
        if delta <= 0:
            return

        client_wallet, _ = Wallet.objects.get_or_create(user=mission.client)
        client_wallet = Wallet.objects.select_for_update().get(pk=client_wallet.pk)

        if client_wallet.balance < delta:
            raise ValueError(
                f"Solde insuffisant. Requis: {delta} FCFA, "
                f"disponible: {client_wallet.balance} FCFA"
            )

        client_wallet.balance -= delta
        client_wallet.save(update_fields=["balance", "updated_at"])

        if hasattr(mission, "escrow") and mission.escrow.status == EscrowStatus.HELD:
            client_wallet.escrow_balance += delta
            client_wallet.save(update_fields=["escrow_balance", "updated_at"])
            escrow = Escrow.objects.select_for_update().get(mission=mission)
            escrow.amount += delta
            escrow.save(update_fields=["amount"])

        Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=-delta,
            transaction_type=Transaction.TransactionType.ESCROW_LOCK,
            status=TransactionStatus.COMPLETED,
            description=f"Avenant tarifaire mission {mission.id}",
        )

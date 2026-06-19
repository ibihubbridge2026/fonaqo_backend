from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.choices import EscrowStatus, TransactionStatus
from apps.wallets.models import Transaction, Wallet

from .models import Escrow, EscrowSplitRecord

User = get_user_model()
PLATFORM_COMMISSION_RATE = Decimal('0.10')
PLATFORM_USER_EMAIL = 'platform@fonaqo.system'
INFLUENCER_DEFAULT_RATE = Decimal('0.02')


def _mission_labor_cost(mission) -> Decimal:
    if getattr(mission, 'labor_cost', None) and mission.labor_cost > 0:
        return Decimal(mission.labor_cost)
    if getattr(mission, 'service_amount', None) and mission.service_amount > 0:
        return Decimal(mission.service_amount)
    return Decimal(mission.price or 0)


def _mission_material_cost(mission) -> Decimal:
    if getattr(mission, 'material_cost', None) and mission.material_cost > 0:
        return Decimal(mission.material_cost)
    return Decimal(mission.purchase_amount or 0)


def _get_active_client_influencer(client):
    from apps.accounts.models import ClientProfile
    try:
        profile = client.client_profile
    except ClientProfile.DoesNotExist:
        return None
    return profile.active_influencer


def _get_platform_wallet():
    """Portefeuille système FONACO pour les commissions plateforme."""
    platform_user, created = User.objects.get_or_create(
        email=PLATFORM_USER_EMAIL,
        defaults={
            'username': 'fonaqo_platform',
            'phone_number': '+2299999990001',
            'is_staff': True,
            'is_active': True,
            'is_client': False,
            'is_agent': False,
            'is_verified': True,
        },
    )
    if created:
        platform_user.set_unusable_password()
        platform_user.save(update_fields=['password'])
    wallet, _ = Wallet.objects.get_or_create(user=platform_user)
    return wallet


class EscrowService:
    """Source unique de vérité pour les flux financiers liés aux missions."""

    @staticmethod
    def escrow_amount(mission) -> Decimal:
        labor = _mission_labor_cost(mission)
        material = _mission_material_cost(mission)
        if labor > 0 or material > 0:
            return labor + material + Decimal(mission.service_fee or 0)
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

        gross = Decimal(escrow.amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        commission = (gross * PLATFORM_COMMISSION_RATE).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP,
        )
        net_agent = gross - commission

        influencer = _get_active_client_influencer(mission.client)
        influencer_share = Decimal('0')
        platform_share = commission
        if influencer:
            rate = Decimal(str(influencer.commission_rate or INFLUENCER_DEFAULT_RATE))
            influencer_share = (gross * rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )
            platform_share = commission - influencer_share
            if platform_share < 0:
                platform_share = Decimal('0')

        client_wallet.escrow_balance -= gross
        client_wallet.save(update_fields=["escrow_balance", "updated_at"])

        agent_wallet.balance += net_agent
        agent_wallet.save(update_fields=["balance", "updated_at"])

        platform_wallet = Wallet.objects.select_for_update().get(
            pk=_get_platform_wallet().pk,
        )
        platform_user = platform_wallet.user
        platform_wallet.balance += platform_share
        platform_wallet.save(update_fields=["balance", "updated_at"])

        if influencer and influencer_share > 0:
            from apps.accounts.models import Influencer
            inf = Influencer.objects.select_for_update().get(pk=influencer.pk)
            inf.earnings_balance += influencer_share.quantize(Decimal('1'))
            inf.save(update_fields=['earnings_balance'])

        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save(update_fields=["status", "released_at"])

        Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=net_agent,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=(
                f"Libération séquestre mission {mission.id} "
                f"(net 90 % après commission 10 %)"
            ),
        )
        Transaction.objects.create(
            wallet=platform_wallet,
            mission=mission,
            amount=platform_share,
            transaction_type=Transaction.TransactionType.INSURANCE_FEE,
            status=TransactionStatus.COMPLETED,
            description=f"Commission FONACO {platform_share} mission {mission.id}",
        )

        EscrowSplitRecord.objects.create(
            mission=mission,
            beneficiary_type=EscrowSplitRecord.BeneficiaryType.AGENT,
            amount_fcfa=net_agent,
            beneficiary_user=mission.agent,
        )
        if platform_share > 0:
            EscrowSplitRecord.objects.create(
                mission=mission,
                beneficiary_type=EscrowSplitRecord.BeneficiaryType.PLATFORM,
                amount_fcfa=platform_share,
                beneficiary_user=platform_user,
            )
        if influencer and influencer_share > 0:
            EscrowSplitRecord.objects.create(
                mission=mission,
                beneficiary_type=EscrowSplitRecord.BeneficiaryType.INFLUENCER,
                amount_fcfa=influencer_share,
                influencer=influencer,
            )

        return escrow

    @staticmethod
    @transaction.atomic
    def release_material_to_agent(mission, amount: Decimal | None = None) -> None:
        """Libère le montant matériel du séquestre vers l'agent (validation admin)."""
        if not mission.agent:
            raise ValueError("Aucun agent assigné à cette mission")
        if mission.material_released:
            return

        material = amount or _mission_material_cost(mission)
        material = Decimal(material).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if material <= 0:
            return

        try:
            escrow = Escrow.objects.select_for_update().get(mission=mission)
        except Escrow.DoesNotExist:
            raise ValueError("Aucun séquestre trouvé pour cette mission")

        if escrow.status != EscrowStatus.HELD:
            raise ValueError("Le séquestre n'est pas en état de libération matériel")

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        agent_wallet = Wallet.objects.select_for_update().get(user=mission.agent)

        if client_wallet.escrow_balance < material:
            raise ValueError("Solde séquestre insuffisant pour le matériel")
        if escrow.amount < material:
            raise ValueError("Montant matériel supérieur au séquestre")

        client_wallet.escrow_balance -= material
        client_wallet.save(update_fields=["escrow_balance", "updated_at"])
        agent_wallet.balance += material
        agent_wallet.save(update_fields=["balance", "updated_at"])

        escrow.amount -= material
        escrow.save(update_fields=["amount"])

        mission.material_released = True
        mission.purchase_released = True
        mission.save(update_fields=["material_released", "purchase_released", "updated_at"])

        Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=material,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            description=f"Déblocage matériel mission {mission.id}",
        )
        Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=-material,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=f"Sortie séquestre matériel mission {mission.id}",
        )

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

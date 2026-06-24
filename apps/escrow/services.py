from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.choices import EscrowStatus, MissionStatus, TransactionStatus
from apps.core.services import (
    PlatformConfigService,
    SPLIT_AGENT_PCT_KEY,
    SPLIT_PLATFORM_PCT_KEY,
)
from apps.wallets.models import Transaction, Wallet

from apps.finance import ledger_integration

from .models import Escrow, EscrowSplitRecord

User = get_user_model()
PLATFORM_USER_EMAIL = 'platform@fonaqo.system'
RESERVE_USER_EMAIL = 'reserve@fonaqo.system'
INFLUENCER_DEFAULT_RATE = Decimal('0.02')

# Legacy alias kept for backward compat
PLATFORM_COMMISSION_RATE = Decimal('0.10')


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
    """Legacy — conservé pour compatibilité éventuelle. Utiliser _get_agent_manager."""
    from apps.accounts.models import ClientProfile
    try:
        profile = client.client_profile
    except ClientProfile.DoesNotExist:
        return None
    return profile.active_influencer


def _get_agent_manager(agent):
    """Retourne le TeamManager actif de l'agent, ou None."""
    from apps.accounts.models import AgentProfile
    try:
        return agent.agent_profile.manager
    except (AgentProfile.DoesNotExist, AttributeError):
        return None


def _get_system_wallet(email: str, username: str, phone: str) -> Wallet:
    """Crée (si besoin) et retourne le portefeuille d'un compte système."""
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': username,
            'phone_number': phone,
            'is_staff': True,
            'is_active': True,
            'is_client': False,
            'is_agent': False,
            'is_verified': True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _get_platform_wallet() -> Wallet:
    """Portefeuille revenus plateforme FONACO (10 %)."""
    return _get_system_wallet(
        PLATFORM_USER_EMAIL, 'fonaqo_platform', '+2299999990001',
    )


def get_platform_wallet() -> Wallet:
    """API publique pour créditer les revenus plateforme (boost, etc.)."""
    return _get_platform_wallet()


def _get_reserve_wallet() -> Wallet:
    """Portefeuille réserve technique / assurance FONACO (2 %)."""
    return _get_system_wallet(
        RESERVE_USER_EMAIL, 'fonaqo_reserve', '+2299999990002',
    )


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
        # AUDIT FIX [P0] — select_for_update sur Mission pour éviter double-lock
        from apps.missions.models import Mission

        mission = Mission.objects.select_for_update().get(pk=mission.pk)

        if hasattr(mission, "escrow") and mission.escrow.status == EscrowStatus.HELD:
            return mission.escrow

        if mission.status not in (MissionStatus.ACCEPTED, MissionStatus.PENDING):
            raise ValueError(
                f"Mission {mission.id} déjà en statut {mission.status}, impossible de locker"
            )

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

        wallet_txn = Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=-amount,
            transaction_type=Transaction.TransactionType.ESCROW_LOCK,
            status=TransactionStatus.COMPLETED,
            description=f"Séquestre pour mission {mission.id}",
        )
        ledger_integration.record_escrow_lock(
            client_id=mission.client_id,
            mission_id=mission.id,
            amount=amount,
            wallet_transaction_id=wallet_txn.id,
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
        agent_txn = Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=amount,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            description=f"Réception achats mission {mission.id}",
        )
        ledger_integration.record_purchase_transfer_to_agent(
            agent_id=mission.agent_id,
            client_id=mission.client_id,
            mission_id=mission.id,
            amount=amount,
            wallet_transaction_id=agent_txn.id,
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

        # AUDIT FIX [P1] — Vérification intégrité des montants avant libération
        if gross <= 0:
            raise ValueError("Montant séquestre invalide")

        # --- Répartition configurable (défaut : 88 % / 10 % / 2 %) ---
        agent_pct = (
            PlatformConfigService.get_decimal(SPLIT_AGENT_PCT_KEY, '88') / Decimal('100')
        )
        platform_pct = (
            PlatformConfigService.get_decimal(SPLIT_PLATFORM_PCT_KEY, '10') / Decimal('100')
        )
        # La part restante (2 %) va à la réserve technique/assurance
        net_agent = (gross * agent_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        platform_base = (gross * platform_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        reserve_share = gross - net_agent - platform_base  # assure que total = 100 %

        # Si l'agent a un manager de brigade, sa commission (2 %) est prélevée sur la part plateforme
        team_manager = _get_agent_manager(mission.agent)
        manager_share = Decimal('0')
        if team_manager:
            rate = Decimal(str(team_manager.commission_rate or INFLUENCER_DEFAULT_RATE))
            manager_share = (gross * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            platform_share = max(Decimal('0'), platform_base - manager_share)
        else:
            platform_share = platform_base

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

        reserve_wallet = Wallet.objects.select_for_update().get(
            pk=_get_reserve_wallet().pk,
        )
        reserve_wallet.balance += reserve_share
        reserve_wallet.save(update_fields=["balance", "updated_at"])

        if team_manager and manager_share > 0:
            from apps.accounts.models import TeamManager
            mgr = TeamManager.objects.select_for_update().get(pk=team_manager.pk)
            mgr.earnings_balance += manager_share.quantize(Decimal('1'))
            mgr.save(update_fields=['earnings_balance'])
            ledger_integration.record_manager_commission(
                manager_id=team_manager.pk,
                mission_id=mission.id,
                amount=manager_share,
            )

        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save(update_fields=["status", "released_at"])

        agent_pct_display = int(agent_pct * 100)
        agent_txn = Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=net_agent,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=f"Paiement mission {mission.id} ({agent_pct_display} %)",
        )
        ledger_integration.record_escrow_release_to_agent(
            agent_id=mission.agent_id,
            client_id=mission.client_id,
            mission_id=mission.id,
            amount=net_agent,
            wallet_transaction_id=agent_txn.id,
        )
        if platform_share > 0:
            platform_txn = Transaction.objects.create(
                wallet=platform_wallet,
                mission=mission,
                amount=platform_share,
                transaction_type=Transaction.TransactionType.INSURANCE_FEE,
                status=TransactionStatus.COMPLETED,
                description=f"Revenus plateforme mission {mission.id}",
            )
            ledger_integration.record_platform_revenue(
                mission_id=mission.id,
                amount=platform_share,
                wallet_transaction_id=platform_txn.id,
                description=f"Revenus plateforme mission {mission.id}",
            )
        if reserve_share > 0:
            reserve_txn = Transaction.objects.create(
                wallet=reserve_wallet,
                mission=mission,
                amount=reserve_share,
                transaction_type=Transaction.TransactionType.INSURANCE_FEE,
                status=TransactionStatus.COMPLETED,
                description=f"Réserve technique mission {mission.id}",
            )
            ledger_integration.record_reserve_revenue(
                mission_id=mission.id,
                amount=reserve_share,
                wallet_transaction_id=reserve_txn.id,
                description=f"Réserve technique mission {mission.id}",
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
        if reserve_share > 0:
            EscrowSplitRecord.objects.create(
                mission=mission,
                beneficiary_type=EscrowSplitRecord.BeneficiaryType.PLATFORM,
                amount_fcfa=reserve_share,
                beneficiary_user=reserve_wallet.user,
            )
        if team_manager and manager_share > 0:
            EscrowSplitRecord.objects.create(
                mission=mission,
                beneficiary_type=EscrowSplitRecord.BeneficiaryType.MANAGER,
                amount_fcfa=manager_share,
                team_manager=team_manager,
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

        agent_txn = Transaction.objects.create(
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
        ledger_integration.record_material_release_to_agent(
            agent_id=mission.agent_id,
            client_id=mission.client_id,
            mission_id=mission.id,
            amount=material,
            wallet_transaction_id=agent_txn.id,
        )

    @staticmethod
    @transaction.atomic
    def refund_to_client(mission, reason: str = "", provider_transaction_id: str = None) -> Escrow:
        """Rembourse le séquestre au client (annulation / litige) avec idempotency."""
        try:
            escrow = Escrow.objects.select_for_update().get(mission=mission)
        except Escrow.DoesNotExist:
            raise ValueError("Aucun séquestre trouvé pour cette mission")

        if escrow.status == EscrowStatus.REFUNDED:
            return escrow

        if escrow.status != EscrowStatus.HELD:
            raise ValueError("Les fonds ne peuvent pas être remboursés dans cet état")

        # Idempotency : vérifier si ce provider_transaction_id a déjà été utilisé pour un remboursement
        if provider_transaction_id:
            existing_refund = Escrow.objects.filter(
                id=escrow.id,
                status=EscrowStatus.REFUNDED
            ).first()
            if existing_refund:
                # Vérifier si ce provider_transaction_id existe déjà dans les transactions liées
                tx_exists = Transaction.objects.filter(
                    reference__icontains=provider_transaction_id,
                    wallet__user=mission.client,
                    transaction_type=Transaction.TransactionType.ESCROW_RELEASE
                ).exists()
                if tx_exists:
                    return escrow

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        client_wallet.escrow_balance -= escrow.amount
        client_wallet.balance += escrow.amount
        client_wallet.save(update_fields=["balance", "escrow_balance", "updated_at"])

        escrow.status = EscrowStatus.REFUNDED
        escrow.save(update_fields=["status"])

        reference = f"REFUND-{escrow.id}"
        if provider_transaction_id:
            reference = f"REFUND-{provider_transaction_id}"

        refund_txn = Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=escrow.amount,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=reason or f"Remboursement séquestre mission {mission.id}",
            reference=reference,
        )
        ledger_integration.record_escrow_refund(
            client_id=mission.client_id,
            mission_id=mission.id,
            amount=escrow.amount,
            wallet_transaction_id=refund_txn.id,
            reference=reference,
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
        # Pénalité 20 % = 15 % agent + 5 % FONACO. Client récupère 80 %.
        fonaco_penalty = (amount * Decimal('0.05')).quantize(Decimal('0.01'))
        agent_share = (amount * Decimal('0.15')).quantize(Decimal('0.01'))
        client_share = amount - fonaco_penalty - agent_share

        client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        agent_wallet = Wallet.objects.select_for_update().get(user=mission.agent)

        if client_wallet.escrow_balance < amount:
            raise ValueError("Solde séquestre client insuffisant")

        client_wallet.escrow_balance -= amount
        client_wallet.balance += client_share
        client_wallet.save(update_fields=["balance", "escrow_balance", "updated_at"])

        agent_wallet.balance += agent_share
        agent_wallet.save(update_fields=["balance", "updated_at"])

        platform_wallet = Wallet.objects.select_for_update().get(
            pk=_get_platform_wallet().pk,
        )
        platform_wallet.balance += fonaco_penalty
        platform_wallet.save(update_fields=["balance", "updated_at"])

        escrow.status = EscrowStatus.REFUNDED
        escrow.save(update_fields=["status"])

        agent_txn = Transaction.objects.create(
            wallet=agent_wallet,
            mission=mission,
            amount=agent_share,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description="Indemnisation pour annulation de mission",
        )
        client_txn = Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=client_share,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            status=TransactionStatus.COMPLETED,
            description=f"Remboursement annulation mission {mission.id}",
        )
        platform_txn = None
        if fonaco_penalty > 0:
            platform_txn = Transaction.objects.create(
                wallet=platform_wallet,
                mission=mission,
                amount=fonaco_penalty,
                transaction_type=Transaction.TransactionType.INSURANCE_FEE,
                status=TransactionStatus.COMPLETED,
                description=f"Frais administratifs annulation mission {mission.id}",
            )
        ledger_integration.record_cancel_compensation(
            client_id=mission.client_id,
            agent_id=mission.agent_id,
            mission_id=mission.id,
            client_share=client_share,
            agent_share=agent_share,
            platform_share=fonaco_penalty,
            client_txn_id=client_txn.id,
            agent_txn_id=agent_txn.id,
            platform_txn_id=platform_txn.id if platform_txn else None,
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

        amend_txn = Transaction.objects.create(
            wallet=client_wallet,
            mission=mission,
            amount=-delta,
            transaction_type=Transaction.TransactionType.ESCROW_LOCK,
            status=TransactionStatus.COMPLETED,
            description=f"Avenant tarifaire mission {mission.id}",
        )
        if hasattr(mission, "escrow") and mission.escrow.status == EscrowStatus.HELD:
            ledger_integration.record_escrow_lock_increase(
                client_id=mission.client_id,
                mission_id=mission.id,
                amount=delta,
                wallet_transaction_id=amend_txn.id,
            )

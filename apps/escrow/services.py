from django.db import transaction
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction
from .models import Escrow
from apps.core.choices import EscrowStatus, TransactionStatus

class EscrowService:
    @staticmethod
    def lock_funds(mission):
        """Bloque l'argent du client vers le séquestre"""
        with transaction.atomic():
            client_wallet = Wallet.objects.select_for_update().get(user=mission.client)
        
            if client_wallet.balance < mission.price:
                raise ValueError("Solde insuffisant pour cette mission.")

            # 1. Déduire du solde réel du client
            client_wallet.balance -= mission.price
            client_wallet.save(update_fields=["balance", "updated_at"])

            # 2. Créer l'entrée Escrow
            escrow = Escrow.objects.create(
                mission=mission,
                amount=mission.price,
                status=EscrowStatus.HELD,
            )

            # 3. Créer la transaction de log
            Transaction.objects.create(
                wallet=client_wallet,
                amount=-mission.price,
                transaction_type=Transaction.TransactionType.ESCROW_LOCK,
                status=TransactionStatus.COMPLETED,
                description=f"Blocage pour mission: {mission.title}",
            )
            return escrow

    @staticmethod
    def release_funds(mission):
        """Libère l'argent du séquestre vers le portefeuille de l'agent"""
        with transaction.atomic():
            escrow = Escrow.objects.select_for_update().get(mission=mission)
            agent_wallet = Wallet.objects.select_for_update().get(user=mission.agent)

            if escrow.status != EscrowStatus.HELD:
                raise ValueError("Les fonds ne sont pas en état d'être libérés.")

            # 1. Ajouter au solde de l'agent
            agent_wallet.balance += escrow.amount
            agent_wallet.save(update_fields=["balance", "updated_at"])

            # 2. Mettre à jour l'Escrow
            escrow.status = EscrowStatus.RELEASED
            escrow.released_at = timezone.now()
            escrow.save(update_fields=["status", "released_at"])

            # 3. Créer la transaction de log pour l'agent
            Transaction.objects.create(
                wallet=agent_wallet,
                amount=escrow.amount,
                transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
                status=TransactionStatus.COMPLETED,
                description=f"Paiement reçu pour mission: {mission.title}",
            )
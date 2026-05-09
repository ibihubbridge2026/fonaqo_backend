from django.db import transaction
from django.utils import timezone
from apps.wallets.models import Wallet, Transaction
from .models import Escrow

class EscrowService:
    @staticmethod
    @transaction.atomic
    def lock_funds(mission):
        """Bloque l'argent du client vers le séquestre"""
        client_wallet = mission.client.wallet
        
        if client_wallet.balance < mission.price:
            raise ValueError("Solde insuffisant pour cette mission.")

        # 1. Déduire du solde réel du client
        client_wallet.balance -= mission.price
        client_wallet.save()

        # 2. Créer l'entrée Escrow
        escrow = Escrow.objects.create(
            mission=mission,
            amount=mission.price,
            status=Escrow.EscrowStatus.HELD
        )

        # 3. Créer la transaction de log
        Transaction.objects.create(
            wallet=client_wallet,
            amount=-mission.price,
            transaction_type=Transaction.TransactionType.ESCROW_LOCK,
            description=f"Blocage pour mission: {mission.title}"
        )
        return escrow

    @staticmethod
    @transaction.atomic
    def release_funds(mission):
        """Libère l'argent du séquestre vers le portefeuille de l'agent"""
        escrow = mission.escrow
        agent_wallet = mission.agent.wallet

        if escrow.status != Escrow.EscrowStatus.HELD:
            raise ValueError("Les fonds ne sont pas en état d'être libérés.")

        # 1. Ajouter au solde de l'agent
        agent_wallet.balance += escrow.amount
        agent_wallet.save()

        # 2. Mettre à jour l'Escrow
        escrow.status = Escrow.EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save()

        # 3. Créer la transaction de log pour l'agent
        Transaction.objects.create(
            wallet=agent_wallet,
            amount=escrow.amount,
            transaction_type=Transaction.TransactionType.ESCROW_RELEASE,
            description=f"Paiement reçu pour mission: {mission.title}"
        )
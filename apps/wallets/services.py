from django.db import transaction
from .models import Wallet, Transaction
from apps.core.choices import TransactionStatus

def transfer_funds(sender_wallet, receiver_wallet, amount):
    with transaction.atomic():
        # Verrouillage des 2 wallets pour eviter les race conditions.
        wallet_ids = sorted([sender_wallet.id, receiver_wallet.id], key=str)
        wallets = {
            wallet.id: wallet
            for wallet in Wallet.objects.select_for_update().filter(id__in=wallet_ids)
        }
        s_wallet = wallets[sender_wallet.id]
        r_wallet = wallets[receiver_wallet.id]
        
        if s_wallet.balance < amount:
            raise ValueError("Solde insuffisant")

        # 2. Débit / Crédit
        s_wallet.balance -= amount
        s_wallet.save(update_fields=["balance", "updated_at"])

        r_wallet.balance += amount
        r_wallet.save(update_fields=["balance", "updated_at"])

        # 3. Création de la preuve (Transaction)
        Transaction.objects.create(
            wallet=s_wallet,
            amount=-amount,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            description="Transfert sortant",
        )
        Transaction.objects.create(
            wallet=r_wallet,
            amount=amount,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            description="Transfert entrant",
        )
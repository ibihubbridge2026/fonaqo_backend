"""Exceptions métier finance / ledger."""


class ImmutableLedgerError(Exception):
    """Tentative de modification ou suppression d'une entrée ledger."""

    def __init__(self, message='LedgerEntry est append-only.'):
        super().__init__(message)

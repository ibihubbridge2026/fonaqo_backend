from django.db import models
from django.utils.translation import gettext_lazy as _


class MissionStatus(models.TextChoices):
    PENDING = "PENDING", _("En attente")
    ACCEPTED = "ACCEPTED", _("Acceptee")
    ON_THE_WAY = "ON_THE_WAY", _("En route")
    ARRIVED = "ARRIVED", _("Arrive sur place")
    IN_PROGRESS = "IN_PROGRESS", _("En cours")
    COMPLETED = "COMPLETED", _("Terminee")
    CANCELLED = "CANCELLED", _("Annulee")
    DISPUTED = "DISPUTED", _("En litige")


class TransactionStatus(models.TextChoices):
    PENDING = "PENDING", _("En attente")
    COMPLETED = "COMPLETED", _("Completee")
    FAILED = "FAILED", _("Echouee")
    CANCELLED = "CANCELLED", _("Annulee")


class KYCStatus(models.TextChoices):
    PENDING = "PENDING", _("En attente")
    SUBMITTED = "SUBMITTED", _("Soumis")
    VERIFIED = "VERIFIED", _("Verifie")
    REJECTED = "REJECTED", _("Rejete")


class AgentLevelName(models.TextChoices):
    NOVICE = "NOVICE", _("Novice")
    VERIFIED = "VERIFIED", _("Verifie")
    EXPERT = "EXPERT", _("Expert")


class EscrowStatus(models.TextChoices):
    HELD = "HELD", _("Fonds bloques")
    RELEASED = "RELEASED", _("Fonds liberes")
    REFUNDED = "REFUNDED", _("Rembourse au client")
    DISPUTED = "DISPUTED", _("En litige")


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", _("En attente")
    SUCCESS = "SUCCESS", _("Reussi")
    FAILED = "FAILED", _("Echoue")

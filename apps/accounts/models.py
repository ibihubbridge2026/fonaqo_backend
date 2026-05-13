import logging
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.choices import KYCStatus

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # --- Identité & Contact ---
    email = models.EmailField(_('adresse email'), unique=True, db_index=True)
    phone_number = models.CharField(_('numéro de téléphone'), max_length=20, unique=True, db_index=True, null=True, blank=True)
    
    # --- Rôles & Statut ---
    is_agent = models.BooleanField(_('est agent terrain'), default=False)
    is_client = models.BooleanField(_('est client'), default=True)
    is_verified = models.BooleanField(_('profil vérifié (KYC)'), default=False)
    kyc_status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.PENDING,
    )
    
    # --- Système de Niveaux & IA (Points 2 & 3) ---
    level = models.ForeignKey('missions.AgentLevel', on_delete=models.SET_NULL, null=True, blank=True)
    reliability_score = models.FloatField(default=100.0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    punctuality_score = models.FloatField(default=100.0)
    completion_rate = models.FloatField(default=0.0)
    
    # --- Parrainage (Point 10) ---
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    referral_code = models.CharField(max_length=20, unique=True, blank=True)

    # --- KYC complet pour Agent ---
    id_card_number = models.CharField(_('numéro de pièce ID'), max_length=64, blank=True)
    id_card_front = models.ImageField(_('Recto Pièce ID'), upload_to='kyc/ids/', blank=True, null=True)
    id_card_back = models.ImageField(_('Verso Pièce ID'), upload_to='kyc/ids/', blank=True, null=True)
    selfie_with_id = models.ImageField(_('Photo avec pièce en main'), upload_to='kyc/selfies/', blank=True, null=True)
    
    # Témoins
    witness_1_name = models.CharField(_('Nom Témoin 1'), max_length=255, blank=True)
    witness_1_phone = models.CharField(_('Tel Témoin 1'), max_length=20, blank=True)
    witness_2_name = models.CharField(_('Nom Témoin 2'), max_length=255, blank=True)
    witness_2_phone = models.CharField(_('Tel Témoin 2'), max_length=20, blank=True)

    profile_picture = models.ImageField(_('photo de profil'), upload_to='profiles/', blank=True, null=True)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['username', 'email']

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.phone_number or self.email.split("@")[0]
        if not self.referral_code:
            self.referral_code = str(uuid.uuid4())[:8].upper()

        logging.getLogger(__name__).debug(
            "Sauvegarde utilisateur phone=%s email=%s is_agent=%s",
            self.phone_number,
            self.email,
            self.is_agent,
        )

        super().save(*args, **kwargs)
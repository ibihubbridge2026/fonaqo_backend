import logging
import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.choices import AgentKYCStatus, AgentBadgeStatus, KYCStatus


class _UuidUpload:
    """Callable upload_to sérialisable qui renomme chaque fichier avec un UUID."""

    def __init__(self, subdir):
        self.subdir = subdir

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        return f'{self.subdir}/{uuid.uuid4().hex}{ext}'

    def deconstruct(self):
        return ('apps.accounts.models._UuidUpload', [self.subdir], {})


def _uuid_upload(subdir):
    """Retourne un callable upload_to UUID sérialisable par les migrations."""
    return _UuidUpload(subdir)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # --- Identité & Contact ---
    email = models.EmailField(_('adresse email'), unique=True, db_index=True)
    phone_number = models.CharField(_('numéro de téléphone'), max_length=20, unique=True, db_index=True, null=True, blank=True)
    
    # --- Rôles & Statut ---
    is_agent = models.BooleanField(_('est agent terrain'), default=False)
    is_client = models.BooleanField(_('est client'), default=True)
    is_guest = models.BooleanField(
        _('compte invité (web vitrine)'),
        default=False,
        help_text=_('Créé via le parcours web sans application mobile'),
    )
    is_verified = models.BooleanField(_('profil vérifié (KYC)'), default=False)
    is_online = models.BooleanField(_('est en ligne'), default=False)
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
    
    # Localisation géographique
    latitude = models.FloatField(_('latitude'), null=True, blank=True)
    longitude = models.FloatField(_('longitude'), null=True, blank=True)
    address = models.CharField(_('adresse'), max_length=500, blank=True)
    city = models.CharField(_('ville'), max_length=100, blank=True)
    service_domain = models.CharField(
        _('domaine / compétences agent'),
        max_length=255,
        blank=True,
    )
    expertises = models.CharField(
        _('expertises spécifiques agent'),
        max_length=500,
        blank=True,
        help_text=_('Liste séparée par des virgules'),
    )

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

    def __str__(self):
        # Prioriser l'email, puis le username, puis le phone_number
        if self.email:
            return self.email
        elif self.username:
            return self.username
        elif self.phone_number:
            return self.phone_number
        else:
            return f"User-{self.id}"


class FavoriteAgent(models.Model):
    """Agents favoris d'un client (sync multi-appareils)."""
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorite_agents',
    )
    agent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorited_by_clients',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'agent')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client_id} → {self.agent_id}"


class AgentProfile(models.Model):
    """Profil métier agent (KYC, documents)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='agent_profile',
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=AgentKYCStatus.choices,
        default=AgentKYCStatus.NONE,
    )
    id_card_photo = models.ImageField(
        _('photo recto pièce d\'identité'),
        upload_to=_uuid_upload('kyc/agent_ids'),
        blank=True,
        null=True,
    )
    selfie_photo = models.ImageField(
        _('selfie avec pièce'),
        upload_to=_uuid_upload('kyc/agent_selfies'),
        blank=True,
        null=True,
    )
    bio = models.TextField(
        _('biographie agent'),
        blank=True,
        null=True,
        help_text=_('Présentation publique de l\'agent'),
    )
    rejection_reason = models.TextField(_('motif rejet KYC'), blank=True, default='')
    agent_code = models.CharField(
        _('identifiant agent'),
        max_length=16,
        blank=True,
        default='',
        unique=True,
        db_index=True,
        help_text=_('Format AGT-00001'),
    )
    is_internal = models.BooleanField(
        _('agent interne'),
        default=False,
        help_text=_('Priorité suggestions client + badge certifié'),
    )
    badge_status = models.CharField(
        _('statut badge professionnel'),
        max_length=20,
        choices=AgentBadgeStatus.choices,
        default=AgentBadgeStatus.NONE,
    )
    badge_photo = models.ImageField(
        _('photo badge professionnel'),
        upload_to=_uuid_upload('badges/photos'),
        blank=True,
        null=True,
    )
    veteran_boost_claimed = models.BooleanField(
        _('pass boost vétéran réclamé'),
        default=False,
        help_text=_('Pass Boost Gratuit 3 jours octroyé automatiquement dès 21 missions COMPLETED'),
    )
    badge_paid = models.BooleanField(
        _('frais badge payés'),
        default=False,
        help_text=_('1 000 FCFA unique prélevés au moment de la première demande de badge'),
    )
    badge_requested_at = models.DateTimeField(null=True, blank=True)
    badge_approved_at = models.DateTimeField(null=True, blank=True)
    badge_rejection_reason = models.TextField(_('motif rejet badge'), blank=True, default='')
    average_rating = models.DecimalField(
        _('note moyenne'),
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text=_('Moyenne des notes reçues des clients (1-5)'),
    )
    ratings_count = models.IntegerField(
        _('nombre de notes'),
        default=0,
        help_text=_('Nombre total de notes reçues'),
    )
    completion_rate = models.FloatField(
        _('taux de complétion'),
        default=0.0,
        help_text=_('Pourcentage de missions complétées avec succès (0-100)'),
    )
    response_time_avg = models.FloatField(
        _('temps de réponse moyen'),
        default=0.0,
        help_text=_('Temps moyen en secondes entre notification et acceptation de mission'),
    )
    ranking_score = models.FloatField(
        _('score de classement'),
        default=0.0,
        help_text=_('Score métier calculé pour le classement des agents (0-100)'),
    )
    manager = models.ForeignKey(
        'TeamManager',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agents',
        verbose_name=_('manager de brigade'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('profil agent')
        verbose_name_plural = _('profils agents')

    def __str__(self):
        return f"AgentProfile({self.user_id}, kyc={self.kyc_status})"


class Influencer(models.Model):
    """Partenaire influenceur — code promo et commission sur les missions."""

    name = models.CharField(_('nom'), max_length=150)
    code_promo = models.CharField(
        _('code promo'),
        max_length=50,
        unique=True,
        db_index=True,
    )
    commission_rate = models.DecimalField(
        _('taux de commission'),
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.02'),
        help_text=_('Part du montant brut mission (ex: 0.02 = 2 %)'),
    )
    duration_years = models.PositiveIntegerField(
        _('durée du contrat (années)'),
        default=2,
    )
    earnings_balance = models.DecimalField(
        _('solde commissions'),
        max_digits=12,
        decimal_places=0,
        default=0,
    )
    referral_slug = models.SlugField(
        _('slug parrainage'),
        max_length=80,
        unique=True,
        null=True,
        blank=True,
        help_text=_('Deep link ex: INFLU_BENIN → fonaco.app/join/INFLU_BENIN'),
    )
    portal_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='influencer_portal',
        verbose_name=_('compte portail'),
    )
    contract_started_at = models.DateField(
        _('début contrat'),
        null=True,
        blank=True,
        help_text=_('Par défaut : date de création'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('influenceur')
        verbose_name_plural = _('influenceurs')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.referral_slug and self.code_promo:
            from django.utils.text import slugify
            self.referral_slug = slugify(self.code_promo).upper().replace('-', '_')[:80]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.code_promo})'

    def is_contract_active(self, linked_at) -> bool:
        if not linked_at:
            return False
        expiry = linked_at + timezone.timedelta(days=int(self.duration_years) * 365)
        return timezone.now() <= expiry

    @property
    def contract_start(self):
        return self.contract_started_at or (self.created_at.date() if self.created_at else None)

    @property
    def contract_end(self):
        start = self.contract_start
        if not start:
            return None
        return start + timezone.timedelta(days=int(self.duration_years) * 365)


class TeamManager(models.Model):
    """Manager de brigade — supervise un groupe d'agents, perçoit 2 % sur leurs missions."""

    name = models.CharField(_('nom'), max_length=150)
    commission_rate = models.DecimalField(
        _('taux de commission'),
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.02'),
        help_text=_('Part du montant brut mission perçue par le manager (ex: 0.02 = 2 %)'),
    )
    max_agents = models.PositiveIntegerField(
        _('capacité brigade'),
        default=10,
        help_text=_('Nombre maximum d\'agents dans la brigade'),
    )
    earnings_balance = models.DecimalField(
        _('solde commissions'),
        max_digits=12,
        decimal_places=0,
        default=0,
    )
    bio = models.TextField(_('présentation'), blank=True, default='')
    portal_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_manager_portal',
        verbose_name=_('compte portail'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('manager de brigade')
        verbose_name_plural = _('managers de brigade')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def agent_count(self):
        return self.agents.count()


class ClientRewardProfile(models.Model):
    """Profil de fidélité client — points, niveaux et badges."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='reward_profile',
    )
    points = models.IntegerField(
        _('points de fidélité'),
        default=0,
        help_text=_('Points accumulés par le client'),
    )
    level = models.IntegerField(
        _('niveau de fidélité'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_('Niveau de fidélité (1-10)'),
    )
    total_missions_completed = models.IntegerField(
        _('missions complétées'),
        default=0,
        help_text=_('Nombre total de missions complétées'),
    )
    total_spent = models.DecimalField(
        _('total dépensé'),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Montant total dépensé en missions'),
    )
    badges_unlocked = models.JSONField(
        _('badges débloqués'),
        default=list,
        blank=True,
        help_text=_('Liste des badges débloqués (IDs)'),
    )
    last_points_earned_at = models.DateTimeField(
        _('derniers points gagnés'),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('profil fidélité client')
        verbose_name_plural = _('profils fidélité clients')

    def __str__(self):
        return f"ClientRewardProfile({self.user.username}, level={self.level}, points={self.points})"

    def add_points(self, points: int, reason: str = ''):
        """Ajoute des points au client et met à jour le niveau si nécessaire."""
        self.points += points
        self.last_points_earned_at = timezone.now()
        self._update_level()
        self.save(update_fields=['points', 'level', 'last_points_earned_at', 'updated_at'])

    def _update_level(self):
        """Met à jour le niveau en fonction des points."""
        # Niveaux: 1 (0-99), 2 (100-299), 3 (300-599), 4 (600-999), 5 (1000-1499)
        # 6 (1500-2099), 7 (2100-2799), 8 (2800-3599), 9 (3600-4499), 10 (4500+)
        level_thresholds = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500]
        for i, threshold in enumerate(reversed(level_thresholds), start=1):
            if self.points >= threshold:
                self.level = 11 - i
                break

    def deduct_points(self, points: int, reason: str = ''):
        """Déduit des points du client."""
        if self.points < points:
            raise ValueError(f'Solde insuffisant: {self.points} points, requis: {points}')
        self.points -= points
        self.save(update_fields=['points', 'updated_at'])


class RewardItem(models.Model):
    """Catalogue de récompenses échangeables contre des points."""
    REWARD_TYPES = [
        ('DISCOUNT', _('Réduction mission')),
        ('FREE_MISSION', _('Mission gratuite')),
        ('BONUS', _('Bonus portefeuille')),
        ('GIFT', _('Cadeau physique')),
    ]

    name = models.CharField(_('nom'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    reward_type = models.CharField(_('type'), max_length=20, choices=REWARD_TYPES)
    points_cost = models.IntegerField(_('coût en points'), validators=[MinValueValidator(1)])
    value_fcfa = models.DecimalField(_('valeur FCFA'), max_digits=10, decimal_places=2, null=True, blank=True)
    icon = models.CharField(_('icône emoji'), max_length=10, blank=True)
    is_active = models.BooleanField(_('actif'), default=True)
    stock = models.IntegerField(_('stock disponible'), null=True, blank=True, help_text=_('Null = illimité'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('récompense')
        verbose_name_plural = _('récompenses')
        ordering = ['points_cost']

    def __str__(self):
        return f'{self.name} ({self.points_cost} pts)'


class RewardRedemption(models.Model):
    """Historique des redemptions de récompenses par les clients."""
    STATUS_CHOICES = [
        ('PENDING', _('En attente')),
        ('APPROVED', _('Approuvé')),
        ('REJECTED', _('Rejeté')),
        ('COMPLETED', _('Complété')),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reward_redemptions')
    reward = models.ForeignKey(RewardItem, on_delete=models.PROTECT, related_name='redemptions')
    points_spent = models.IntegerField(_('points dépensés'))
    status = models.CharField(_('statut'), max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(_('notes'), blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_redemptions')
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('redemption')
        verbose_name_plural = _('redemptions')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} → {self.reward.name} ({self.status})'


class InfluencerWithdrawalStatus(models.TextChoices):
    PENDING = 'PENDING', _('En attente')
    APPROVED = 'APPROVED', _('Approuvé')
    REJECTED = 'REJECTED', _('Rejeté')


class InfluencerWithdrawalRequest(models.Model):
    """Demande de retrait commission influenceur."""

    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='withdrawal_requests',
    )
    amount = models.DecimalField(_('montant'), max_digits=12, decimal_places=0)
    status = models.CharField(
        max_length=20,
        choices=InfluencerWithdrawalStatus.choices,
        default=InfluencerWithdrawalStatus.PENDING,
        db_index=True,
    )
    note = models.TextField(_('note influenceur'), blank=True)
    proof_file = models.FileField(
        _('preuve de versement'),
        upload_to='influencer/payout_proofs/',
        blank=True,
        null=True,
    )
    admin_note = models.TextField(_('note admin'), blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_influencer_withdrawals',
    )

    class Meta:
        ordering = ['-requested_at']
        verbose_name = _('demande retrait influenceur')
        verbose_name_plural = _('demandes retrait influenceurs')

    def __str__(self):
        return f'Retrait {self.amount} FCFA — {self.influencer.code_promo} ({self.status})'


class ClientProfile(models.Model):
    """Profil client (affiliation influenceur, préférences)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client_profile',
    )
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
    )
    influencer_linked_at = models.DateTimeField(
        _('date liaison influenceur'),
        null=True,
        blank=True,
    )
    referral_code_cache = models.CharField(
        _('code parrainage (deep link)'),
        max_length=80,
        blank=True,
        default='',
        help_text=_('Code influenceur capturé via deep link avant inscription'),
    )
    average_rating = models.DecimalField(
        _('note moyenne'),
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text=_('Moyenne des notes reçues des agents (1-5)'),
    )
    ratings_count = models.IntegerField(
        _('nombre de notes'),
        default=0,
        help_text=_('Nombre total de notes reçues'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('profil client')
        verbose_name_plural = _('profils clients')

    def __str__(self):
        return f'ClientProfile({self.user_id})'

    @property
    def active_influencer(self):
        if not self.influencer_id:
            return None
        linked = self.influencer_linked_at or self.created_at
        if self.influencer.is_contract_active(linked):
            return self.influencer
        return None
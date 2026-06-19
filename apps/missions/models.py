import uuid
from decimal import Decimal
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from simple_history.models import HistoricalRecords
from apps.core.choices import AgentLevelName, MissionStatus

# --- SYSTÈME DE TAGS & EXPERTISES (Point 5) ---
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.name
    
# --- SYSTÈME DE NIVEAUX (Point 2) ---
class AgentLevel(models.Model):
    name = models.CharField(max_length=50, choices=AgentLevelName.choices)
    min_missions = models.PositiveIntegerField(default=0)
    priority_boost = models.FloatField(default=1.0) # Multiplicateur de visibilité
    
    def __str__(self):
        return self.name

# --- MODÈLE MISSION PRINCIPAL ---
class Mission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='missions_ordered')
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='missions_assigned')
    
    # Détails & Géo
    title = models.CharField(max_length=255)
    description = models.TextField()
    tags = models.ManyToManyField(Tag, blank=True)
    location = gis_models.PointField(srid=4326)
    address = models.CharField(max_length=500)

    # Finances (Point 15 Analytics)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    purchase_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Montant dédié aux achats, débloqué immédiatement vers l'agent à l'acceptation",
    )
    service_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Frais de prestation conservés en séquestre jusqu'à la fin de la mission",
    )
    labor_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Montant main d'œuvre (séquestre jusqu'à complétion)",
    )
    material_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Montant matériel / fournitures (libéré sur validation admin)",
    )
    material_released = models.BooleanField(
        default=False,
        help_text="Indique si le montant matériel a été libéré à l'agent",
    )

    # État & Sécurité (Point 7)
    status = models.CharField(max_length=20, choices=MissionStatus.choices, default=MissionStatus.PENDING)
    tracking_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Code de suivi public (ex: FNC-4829-BJ)'),
    )
    qr_code_token = models.CharField(max_length=100, unique=True, blank=True)
    qr_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Logique conditionnelle (Module 2)
    target_agent_username = models.CharField(max_length=150, null=True, blank=True, help_text="Username de l'agent cible si assignation manuelle")
    is_urgent = models.BooleanField(default=False, help_text="Mission urgente : agents notifiés en priorité (+500 FCFA)")
    is_confidential = models.BooleanField(default=False, help_text="Agent interne Fonaqo : recruté et encadré par Fonaqo (+500 FCFA)")
    is_vocal_description = models.BooleanField(
        default=False,
        help_text="La description de la mission est un enregistrement vocal joint",
    )
    description_audio = models.FileField(
        upload_to='missions/voice/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name="Description vocale (audio)",
    )
    purchase_released = models.BooleanField(default=False, help_text="Indique si le montant des achats a déjà été transféré à l'agent")
    
    price_negotiation_allowed = models.BooleanField(
        default=False,
        help_text="Le client autorise l'agent à proposer un nouveau tarif via le chat",
    )

    # Preuves
    start_photo = models.ImageField(upload_to='missions/proofs/start/', null=True, blank=True)
    end_photo = models.ImageField(upload_to='missions/proofs/end/', null=True, blank=True)

    # Notation bidirectionnelle
    client_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Note donnée par le client à l'agent (1-5)"
    )
    agent_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Note donnée par l'agent au client (1-5)"
    )
    client_comment = models.TextField(blank=True, help_text="Commentaire du client sur l'agent")
    agent_comment = models.TextField(blank=True, help_text="Commentaire de l'agent sur le client")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.qr_code_token:
            self.qr_code_token = uuid.uuid4().hex
        labor = self.labor_cost or self.service_amount or Decimal('0')
        material = self.material_cost or self.purchase_amount or Decimal('0')
        if labor > 0 or material > 0:
            if not self.labor_cost and self.service_amount:
                self.labor_cost = self.service_amount
            if not self.material_cost and self.purchase_amount:
                self.material_cost = self.purchase_amount
            if not self.service_amount and self.labor_cost:
                self.service_amount = self.labor_cost
            if not self.purchase_amount and self.material_cost:
                self.purchase_amount = self.material_cost
            total = labor + material + (self.service_fee or Decimal('0'))
            if total > 0:
                self.price = total
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Mission {self.title[:50]}{'...' if len(self.title) > 50 else ''} ({self.id})"

# --- TIMELINE DE MISSION (Point 1) ---
class MissionTimeline(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='timeline')
    status = models.CharField(max_length=20, choices=MissionStatus.choices)
    message = models.CharField(max_length=255)
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    proof_photo = models.ImageField(upload_to='missions/timeline/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Timeline {self.status} - {self.mission.title[:30]}{'...' if len(self.mission.title) > 30 else ''}"

# --- MATCHING & RECOMMENDATION (Point 4) ---
class MissionRecommendation(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.FloatField() # Calculé par l'IA de matching
    reason = models.CharField(max_length=255) # Ex: "Proximité + Niveau Expert"
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        agent_name = self.agent.username or self.agent.email or f"Agent-{self.agent.id}"
        return f"Recommendation {agent_name} → {self.mission.title[:30]}{'...' if len(self.mission.title) > 30 else ''}"

# --- BOOSTS (Point 6) ---
class BoostPlan(models.Model):
    name = models.CharField(max_length=100)
    duration_hours = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    priority_score = models.FloatField(default=2.0)

    def __str__(self):
        return f"Boost {self.name} ({self.duration_hours}h) - {self.price} FCFA"

class AgentBoost(models.Model):
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(BoostPlan, on_delete=models.CASCADE)
    active_until = models.DateTimeField()
    zone = gis_models.PolygonField(srid=4326, null=True, blank=True) # Zone de boost géo

    def __str__(self):
        agent_name = self.agent.username or self.agent.email or f"Agent-{self.agent.id}"
        return f"Boost {agent_name} - {self.plan.name}"

# --- MODÈLES AMÉLIORÉS (MISSIONS ENHANCED) ---
class MissionProof(models.Model):
    """
    Preuves photo multiples pour une mission
    Permet à l'agent de télécharger plusieurs photos comme preuve
    """
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='proofs'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_proofs'
    )

    image = models.ImageField(
        upload_to='missions/proofs/%Y/%m/%d/',
        verbose_name="Photo preuve"
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Légende"
    )

    is_primary = models.BooleanField(
        default=False,
        help_text="Photo principale affichée en premier"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    class Meta:
        verbose_name = "Preuve Photo"
        verbose_name_plural = "Preuves Photos"
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f"Preuve pour mission {self.mission.id} - {self.created_at}"


class MissionTimelineEvent(models.Model):
    """
    Événements détaillés dans la timeline d'une mission
    Pour tracking précis avec timestamps
    """
    EVENT_TYPE_CHOICES = [
        ('created', 'Mission créée'),
        ('published', 'Mission publiée'),
        ('accepted', 'Mission acceptée'),
        ('agent_en_route', 'Agent en route'),
        ('agent_arrived', 'Agent arrivé sur place'),
        ('waiting', 'En attente'),
        ('in_progress', 'En cours de réalisation'),
        ('proofs_uploaded', 'Preuves téléchargées'),
        ('completed', 'Mission terminée'),
        ('validated', 'Mission validée par le client'),
        ('cancelled', 'Mission annulée'),
        ('disputed', 'Litige ouvert'),
    ]

    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='timeline_events'
    )

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES
    )

    occurred_at = models.DateTimeField(auto_now_add=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mission_timeline_events'
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes additionnelles"
    )

    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Latitude"
    )
    location_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Longitude"
    )

    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Données supplémentaires au format JSON"
    )

    class Meta:
        verbose_name = "Événement Timeline"
        verbose_name_plural = "Événements Timeline"
        ordering = ['occurred_at']
        indexes = [
            models.Index(fields=['mission', '-occurred_at']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - Mission {self.mission.id}"


class VoiceMissionRequest(models.Model):
    """
    Historique des demandes de mission par voix.
    Conserve audio, transcription, extraction IA et résultat pour audit/support.
    """
    STATUS_CHOICES = [
        ('processing', 'En cours'),
        ('complete', 'Complet'),
        ('incomplete', 'Incomplet'),
        ('duplicate', 'Doublon détecté'),
        ('error', 'Erreur'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='voice_requests',
    )
    audio_file = models.FileField(
        upload_to='voice_missions/%Y/%m/%d/',
        null=True, blank=True,
        help_text="Fichier audio original",
    )
    audio_hash = models.CharField(
        max_length=64, db_index=True, blank=True, default='',
        help_text="SHA-256 du fichier audio (anti-doublon upload)",
    )
    transcription = models.TextField(blank=True, default='')
    transcription_hash = models.CharField(
        max_length=64, db_index=True, blank=True, default='',
        help_text="SHA-256 de la transcription normalisée (anti-doublon)",
    )
    extracted_data = models.JSONField(null=True, blank=True)
    missing_fields = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    category_id_resolved = models.IntegerField(
        null=True, blank=True,
        help_text="ID services.Category résolu par find_best_category()",
    )
    category_name_resolved = models.CharField(max_length=100, blank=True, default='')
    mission = models.ForeignKey(
        'Mission',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='voice_requests',
        help_text="Mission créée depuis cette demande vocale (si confirmée)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Demande Mission Vocale"
        verbose_name_plural = "Demandes Mission Vocale"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'transcription_hash']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'audio_hash', 'transcription_hash'],
                name='unique_voice_request_hash',
                deferrable=models.Deferrable.DEFERRED,
            )
        ]

    def __str__(self):
        return f"VoiceReq {self.user.username} — {self.created_at:%Y-%m-%d %H:%M}"


class AgentStatistics(models.Model):
    """
    Statistiques des agents pour le dashboard
    """
    agent = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_statistics'
    )
    
    total_missions = models.PositiveIntegerField(default=0)
    completed_missions = models.PositiveIntegerField(default=0)
    cancelled_missions = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    current_streak = models.PositiveIntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Statistiques Agent"
        verbose_name_plural = "Statistiques Agents"
    
    def __str__(self):
        return f"Stats {self.agent.username or self.agent.email}"


class MaterialWithdrawalRequest(models.Model):
    """Demande de déblocage des fonds matériel par l'agent."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        APPROVED = 'APPROVED', _('Approuvée')
        REJECTED = 'REJECTED', _('Rejetée')

    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name='material_withdrawal_requests',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('demande déblocage matériel')
        verbose_name_plural = _('demandes déblocage matériel')

    def __str__(self):
        return f'MaterialWithdrawal({self.mission_id}, {self.status})'
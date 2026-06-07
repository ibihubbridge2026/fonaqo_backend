import uuid
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

    # État & Sécurité (Point 7)
    status = models.CharField(max_length=20, choices=MissionStatus.choices, default=MissionStatus.PENDING)
    qr_code_token = models.CharField(max_length=100, unique=True, blank=True)
    qr_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Logique conditionnelle (Module 2)
    requires_procuration = models.BooleanField(default=False, help_text="La mission nécessite une procuration")
    target_agent_username = models.CharField(max_length=150, null=True, blank=True, help_text="Username de l'agent cible si assignation manuelle")
    is_urgent = models.BooleanField(default=False, help_text="Mission urgente : agents notifiés en priorité (+500 FCFA)")
    is_confidential = models.BooleanField(default=False, help_text="Mission confidentielle : visible uniquement par les agents internes (+500 FCFA)")
    purchase_released = models.BooleanField(default=False, help_text="Indique si le montant des achats a déjà été transféré à l'agent")
    
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

# --- SYSTÈME DE LITIGES (Point 8) ---
class Dispute(models.Model):
    class DisputeStatus(models.TextChoices):
        OPEN = 'OPEN', _('Ouvert')
        IN_REVIEW = 'IN_REVIEW', _('En examen')
        RESOLVED = 'RESOLVED', _('Résolu')
        CLOSED = 'CLOSED', _('Fermé')

    mission = models.OneToOneField(Mission, on_delete=models.CASCADE, related_name='dispute_record')
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=DisputeStatus.choices, default=DisputeStatus.OPEN)
    admin_decision = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dispute {self.status} - {self.mission.title[:30]}{'...' if len(self.mission.title) > 30 else ''}"

class DisputeEvidence(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidences')
    file = models.FileField(upload_to='disputes/evidences/')
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"Evidence: {self.description[:30]}{'...' if len(self.description) > 30 else ''}"

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
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
    history = HistoricalRecords()
    
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
    
    # État & Sécurité (Point 7)
    status = models.CharField(max_length=20, choices=MissionStatus.choices, default=MissionStatus.PENDING)
    qr_code_token = models.CharField(max_length=100, unique=True, blank=True)
    qr_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Preuves
    start_photo = models.ImageField(upload_to='missions/proofs/start/', null=True, blank=True)
    end_photo = models.ImageField(upload_to='missions/proofs/end/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.qr_code_token:
            self.qr_code_token = uuid.uuid4().hex
        super().save(*args, **kwargs)

# --- TIMELINE DE MISSION (Point 1) ---
class MissionTimeline(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='timeline')
    status = models.CharField(max_length=20, choices=MissionStatus.choices)
    message = models.CharField(max_length=255)
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    proof_photo = models.ImageField(upload_to='missions/timeline/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

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

class DisputeEvidence(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidences')
    file = models.FileField(upload_to='disputes/evidences/')
    description = models.CharField(max_length=255)

# --- MATCHING & RECOMMENDATION (Point 4) ---
class MissionRecommendation(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.FloatField() # Calculé par l'IA de matching
    reason = models.CharField(max_length=255) # Ex: "Proximité + Niveau Expert"
    created_at = models.DateTimeField(auto_now_add=True)

# --- BOOSTS (Point 6) ---
class BoostPlan(models.Model):
    name = models.CharField(max_length=100)
    duration_hours = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    priority_score = models.FloatField(default=2.0)

class AgentBoost(models.Model):
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(BoostPlan, on_delete=models.CASCADE)
    active_until = models.DateTimeField()
    zone = gis_models.PolygonField(srid=4326, null=True, blank=True) # Zone de boost géo
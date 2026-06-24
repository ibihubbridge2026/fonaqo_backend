import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.core.validators import (
    validate_audio_upload,
    validate_chat_attachment,
    validate_chat_media,
)


class UserPresence(models.Model):
    """Présence en ligne d'un utilisateur (online / last_seen)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='presence',
    )
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Présence utilisateur"

    def mark_online(self):
        self.is_online = True
        self.last_seen = timezone.now()
        self.save(update_fields=['is_online', 'last_seen'])

    def mark_offline(self):
        self.is_online = False
        self.last_seen = timezone.now()
        self.save(update_fields=['is_online', 'last_seen'])

    def __str__(self):
        state = "online" if self.is_online else f"last seen {self.last_seen:%H:%M}"
        return f"{self.user.username} — {state}"


class Conversation(models.Model):
    """
    Conversation entre un client et un agent pour une mission spécifique
    """
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True,
        blank=True
    )

    # Participants
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_conversations'
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agent_conversations',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    # Métadonnées
    is_archived = models.BooleanField(default=False)
    client_last_read = models.DateTimeField(null=True, blank=True)
    agent_last_read = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ['-last_message_at', '-updated_at']
        unique_together = ['client', 'agent', 'mission']

    def __str__(self):
        return f"Conversation {self.client.username} - {self.agent.username}"

    @property
    def unread_count_client(self):
        """Nombre de messages non lus par le client"""
        if not self.client_last_read:
            return self.messages.filter(sender=self.agent).count()
        return self.messages.filter(
            sender=self.agent,
            created_at__gt=self.client_last_read
        ).count()

    @property
    def unread_count_agent(self):
        """Nombre de messages non lus par l'agent"""
        if not self.agent_last_read:
            return self.messages.filter(sender=self.client).count()
        return self.messages.filter(
            sender=self.client,
            created_at__gt=self.agent_last_read
        ).count()


class Message(models.Model):
    """
    Message individuel dans une conversation
    Supporte: texte, images, voix, fichiers, système
    """
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Texte'),
        ('image', 'Image'),
        ('voice', 'Vocal'),
        ('file', 'Fichier'),
        ('system', 'Système'),
        ('negotiation', 'Négociation tarif'),
    ]

    class NegotiationStatus(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        ACCEPTED = 'ACCEPTED', 'Acceptée'
        REJECTED = 'REJECTED', 'Refusée'

    class DeliveryStatus(models.TextChoices):
        PENDING   = 'pending',   'En attente'
        SENT      = 'sent',      'Envoyé'
        DELIVERED = 'delivered', 'Distribué'
        READ      = 'read',      'Lu'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )

    # Déduplication côté client (UUID généré par Flutter)
    client_message_id = models.UUIDField(
        null=True, blank=True, unique=True, db_index=True,
        help_text="UUID v4 généré côté Flutter pour déduplication",
    )

    message_type = models.CharField(
        max_length=15,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )

    content = models.TextField(blank=True, null=True)

    # Négociation tarifaire (message_type == 'negotiation')
    proposed_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Montant proposé (FCFA)',
    )
    negotiation_status = models.CharField(
        max_length=10,
        choices=NegotiationStatus.choices,
        null=True,
        blank=True,
    )

    # Pour images/fichiers — AUDIT FIX [P0] validation MIME/extension
    media_file = models.FileField(
        upload_to='chat_media/%Y/%m/%d/',
        null=True, blank=True,
        validators=[validate_chat_media],
    )

    # Pour messages vocaux — AUDIT FIX [P0]
    audio_file = models.FileField(
        upload_to='chat_voice/%Y/%m/%d/',
        null=True, blank=True,
        validators=[validate_audio_upload],
    )
    audio_duration = models.IntegerField(
        help_text="Durée en secondes",
        null=True, blank=True
    )

    # Statut de livraison (PENDING → SENT → DELIVERED → READ)
    delivery_status = models.CharField(
        max_length=10,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.SENT,
    )

    # Compat rétro-compatible avec l'ancien champ is_read
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            # AUDIT FIX [P1/P2] — indexes delivery et client_message_id
            models.Index(
                fields=['conversation', 'client_message_id'],
                name='message_conv_client_id_idx',
            ),
            models.Index(
                fields=['conversation', 'delivery_status', 'created_at'],
                name='message_delivery_idx',
            ),
        ]

    def __str__(self):
        type_label = self.get_message_type_display()
        return f"{type_label} de {self.sender.username} ({self.created_at})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        # Cohérence is_read ↔ delivery_status
        if self.delivery_status == self.DeliveryStatus.READ:
            self.is_read = True
            if not self.read_at:
                self.read_at = timezone.now()
        super().save(*args, **kwargs)
        if is_new:
            self.conversation.last_message_at = self.created_at
            self.conversation.save(update_fields=['last_message_at'])

    def mark_as_read(self):
        """Marque le message comme lu (rétro-compat + nouveau statut)."""
        self.is_read = True
        self.read_at = timezone.now()
        self.delivery_status = self.DeliveryStatus.READ
        self.save(update_fields=['is_read', 'read_at', 'delivery_status'])

    def mark_as_delivered(self):
        """Marque le message comme distribué."""
        if self.delivery_status == self.DeliveryStatus.SENT:
            self.delivered_at = timezone.now()
            self.delivery_status = self.DeliveryStatus.DELIVERED
            self.save(update_fields=['delivered_at', 'delivery_status'])


class TypingStatus(models.Model):
    """
    Statut "en train d'écrire" pour UX temps réel
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='typing_statuses'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    is_typing = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Expiration automatique du typing indicator (5 s d'inactivité)",
    )

    class Meta:
        verbose_name = "Statut de frappe"
        unique_together = ['conversation', 'user']

    @property
    def is_active(self) -> bool:
        """True si le typing n'a pas encore expiré."""
        if not self.is_typing:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class ChatAttachment(models.Model):
    """
    Pièces jointes d'un message : image, PDF, facture, reçu.
    Rétro-compatible : un Message peut avoir plusieurs attachments en plus
    des champs media_file / audio_file existants.
    """
    ATTACHMENT_TYPE_CHOICES = [
        ('image', 'Image'),
        ('pdf',   'PDF'),
        ('audio', 'Audio'),
        ('file',  'Fichier générique'),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    attachment_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPE_CHOICES, default='file')
    file = models.FileField(
        upload_to='chat_attachments/%Y/%m/%d/',
        validators=[validate_chat_attachment],
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="Taille en octets")
    mime_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce jointe chat"
        verbose_name_plural = "Pièces jointes chat"

    def __str__(self):
        return f"{self.attachment_type} — {self.original_filename or self.file.name}"

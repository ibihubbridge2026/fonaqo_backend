from django.db import models
from django.conf import settings
from django.utils import timezone

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
        related_name='agent_conversations'
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
    Supporte: texte, images, voix
    """
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Texte'),
        ('image', 'Image'),
        ('voice', 'Vocal'),
        ('file', 'Fichier'),
        ('system', 'Système'),
    ]

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
    
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )
    
    content = models.TextField(blank=True, null=True)  # Pour texte
    
    # Pour images/fichiers
    media_file = models.ImageField(
        upload_to='chat_media/%Y/%m/%d/',
        null=True,
        blank=True
    )
    
    # Pour messages vocaux
    audio_file = models.FileField(
        upload_to='chat_voice/%Y/%m/%d/',
        null=True,
        blank=True
    )
    audio_duration = models.IntegerField(
        help_text="Durée en secondes",
        null=True,
        blank=True
    )
    
    # Métadonnées
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
        ]

    def __str__(self):
        type_label = self.get_message_type_display()
        return f"{type_label} de {self.sender.username} ({self.created_at})"

    def save(self, *args, **kwargs):
        # Mise à jour automatique du last_message_at de la conversation
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        if is_new:
            self.conversation.last_message_at = self.created_at
            self.conversation.save(update_fields=['last_message_at'])

    def mark_as_read(self):
        """Marque le message comme lu"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


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

    class Meta:
        verbose_name = "Statut de frappe"
        unique_together = ['conversation', 'user']

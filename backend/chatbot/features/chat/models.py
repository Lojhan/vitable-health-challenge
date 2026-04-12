from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class ChatMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_USER, ROLE_USER),
        (ROLE_ASSISTANT, ROLE_ASSISTANT),
    ]

    class MessageKind(models.TextChoices):
        TEXT = 'text', 'Text'
        PROVIDERS = 'providers', 'Providers'
        AVAILABILITY = 'availability', 'Availability'
        APPOINTMENTS = 'appointments', 'Appointments'
        JSON = 'json', 'JSON'

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    message_kind = models.CharField(
        max_length=32,
        choices=MessageKind.choices,
        default=MessageKind.TEXT,
    )
    request_id = models.CharField(max_length=64, null=True, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(content__regex=r'^\s*$'),
                name='chat_message_content_not_blank',
            ),
            models.UniqueConstraint(
                fields=['session', 'request_id'],
                condition=models.Q(role='user') & ~models.Q(request_id__isnull=True),
                name='chat_user_request_id_unique_per_session',
            ),
        ]


class StructuredInteraction(models.Model):
    """Stores user selection state for structured UI components (provider picks, slot picks)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='structured_interactions',
    )
    interaction_id = models.CharField(max_length=128)
    kind = models.CharField(max_length=32)
    selection = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'interaction_id'],
                name='structured_interaction_user_unique',
            ),
        ]

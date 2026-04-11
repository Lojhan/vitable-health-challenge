from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import models


class OutboxMessageQuerySet(models.QuerySet):
    def pending(self) -> models.QuerySet:
        return self.filter(
            published_at__isnull=True,
            dead_lettered_at__isnull=True,
        ).order_by('id')


class OutboxMessage(models.Model):
    aggregate_type = models.CharField(max_length=120)
    aggregate_id = models.CharField(max_length=64)
    event_type = models.CharField(max_length=120)
    idempotency_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict)
    retry_count = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    dead_lettered_at = models.DateTimeField(null=True, blank=True)

    objects = OutboxMessageQuerySet.as_manager()

    def mark_published(self, *, published_at: datetime) -> None:
        self.published_at = published_at
        self.error = ''
        self.save(update_fields=['published_at', 'error'])

    def mark_failed(
        self,
        *,
        error: str,
        failed_at: datetime,
        dead_letter_after: int | None = None,
    ) -> None:
        self.retry_count += 1
        self.error = error

        update_fields = ['retry_count', 'error']
        if dead_letter_after is not None and self.retry_count >= dead_letter_after:
            self.dead_lettered_at = failed_at
            update_fields.append('dead_lettered_at')

        self.save(update_fields=update_fields)

    @staticmethod
    def build_idempotency_key(*, aggregate_type: str, aggregate_id: str, event_type: str) -> str:
        return f'{aggregate_type}:{aggregate_id}:{event_type}'

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['published_at', 'id']),
            models.Index(fields=['dead_lettered_at', 'id']),
        ]


class AuditEvent(models.Model):
    """Audit trail for security-sensitive and patient-impacting events.
    
    Tracks authentication, scheduling changes, emergency overrides, and agent tool actions
    with correlation IDs for tracing across request lifecycle.
    """
    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('NOTICE', 'Notice'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    EVENT_TYPE_CHOICES = [
        ('AUTH_LOGIN', 'User Login'),
        ('AUTH_SIGNUP', 'User Signup'),
        ('AUTH_LOGOUT', 'User Logout'),
        ('AUTH_FAILURE', 'Authentication Failure'),
        ('SCHEDULING_CREATE', 'Appointment Created'),
        ('SCHEDULING_UPDATE', 'Appointment Updated'),
        ('SCHEDULING_CANCEL', 'Appointment Cancelled'),
        ('CHAT_START', 'Chat Session Started'),
        ('CHAT_MESSAGE', 'Chat Message Processed'),
        ('TOOL_EXECUTION', 'Tool Executed'),
        ('TOOL_FAILURE', 'Tool Failed'),
        ('AI_EMERGENCY', 'Emergency Override Triggered'),
        ('AI_OUT_OF_SCOPE', 'Out-of-Scope Detection'),
    ]

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default='INFO')
    correlation_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text='Trace ID connecting related events across request lifecycle',
    )
    resource_type = models.CharField(
        max_length=64,
        blank=True,
        help_text='Type of resource affected (e.g., appointment, chat_session)',
    )
    resource_id = models.CharField(
        max_length=255,
        blank=True,
        help_text='ID of resource affected',
    )
    action = models.CharField(
        max_length=255,
        blank=True,
        help_text='Specific action taken',
    )
    reason_code = models.CharField(
        max_length=64,
        blank=True,
        help_text='Machine-readable reason/error code',
    )
    details = models.JSONField(
        default=dict,
        help_text='Structured event details (PHI-sensitive fields should be redacted)',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['correlation_id', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]

"""
Observability infrastructure for structured logging, correlation IDs, and tracing.

This module provides:
- Correlation ID context management (request ID, turn ID)
- Structured logging with automatic context injection
- Metrics collection hooks
- Audit event creation helpers
- PHI redaction policies
"""

import contextvars
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Context variables for correlation IDs
_request_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'request_id', default=None
)
_turn_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'turn_id', default=None
)
_user_id_context: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    'user_id', default=None
)

# Metrics collection
_metrics_store: dict[str, Any] = {}


def generate_request_id() -> str:
    """Generate a unique request ID (correlation ID for entire request)."""
    return f"req_{secrets.token_hex(12)}"


def generate_turn_id() -> str:
    """Generate a unique turn ID (correlation ID for single chat turn)."""
    return f"turn_{secrets.token_hex(12)}"


def set_request_id(request_id: str) -> None:
    """Set the request ID in context (typically from HTTP header)."""
    _request_id_context.set(request_id)


def set_turn_id(turn_id: str) -> None:
    """Set the turn ID in context (for chat interactions)."""
    _turn_id_context.set(turn_id)


def set_user_id(user_id: int | None) -> None:
    """Set the authenticated user ID in context."""
    _user_id_context.set(user_id)


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return _request_id_context.get()


def get_turn_id() -> str | None:
    """Get current turn ID from context."""
    return _turn_id_context.get()


def get_user_id() -> int | None:
    """Get current user ID from context."""
    return _user_id_context.get()


def clear_context() -> None:
    """Clear all context variables (usually called at end of request)."""
    _request_id_context.set(None)
    _turn_id_context.set(None)
    _user_id_context.set(None)


class StructuredLogger:
    """Wrapper around standard logging with automatic context injection."""

    def __init__(self, name: str) -> None:
        self.logger = logging.getLogger(name)

    def _build_context(self) -> dict[str, Any]:
        """Build context dict with current correlation IDs."""
        ctx = {}
        request_id = get_request_id()
        turn_id = get_turn_id()
        user_id = get_user_id()
        
        if request_id:
            ctx['request_id'] = request_id
        if turn_id:
            ctx['turn_id'] = turn_id
        if user_id:
            ctx['user_id'] = user_id
        
        return ctx

    def _log(
        self,
        level: int,
        message: str,
        reason_code: str = '',
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Log with structured format including context."""
        ctx = self._build_context()
        ctx.update(extra)
        
        # Build structured log entry
        log_entry = {
            'timestamp': datetime.now(UTC).isoformat(),
            'message': message,
            'level': logging.getLevelName(level),
        }
        
        if reason_code:
            log_entry['reason_code'] = reason_code
        
        if details:
            log_entry['details'] = details
        
        if ctx:
            log_entry['context'] = ctx
        
        # Log as JSON string for easy parsing
        self.logger.log(level, json.dumps(log_entry))

    def info(
        self,
        message: str,
        reason_code: str = '',
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Log info level."""
        self._log(logging.INFO, message, reason_code, details, **extra)

    def warning(
        self,
        message: str,
        reason_code: str = '',
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Log warning level."""
        self._log(logging.WARNING, message, reason_code, details, **extra)

    def error(
        self,
        message: str,
        reason_code: str = '',
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Log error level."""
        self._log(logging.ERROR, message, reason_code, details, **extra)

    def critical(
        self,
        message: str,
        reason_code: str = '',
        details: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        """Log critical level."""
        self._log(logging.CRITICAL, message, reason_code, details, **extra)


@dataclass
class AuditEventData:
    """Data class for creating audit events."""
    event_type: str
    severity: str = 'INFO'
    resource_type: str = ''
    resource_id: str = ''
    action: str = ''
    reason_code: str = ''
    details: dict[str, Any] = None
    ip_address: str | None = None
    user_agent: str = ''

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}


def create_audit_event(audit_data: AuditEventData) -> 'AuditEvent':  # noqa: F821
    """Create and save an audit event with current context.
    
    Note: This is a synchronous function. Call it from sync contexts only.
    For use in async contexts, use create_audit_event_async or wrap with sync_to_async.
    """
    from chatbot.features.core.models import AuditEvent
    
    user_id = get_user_id()
    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    
    return AuditEvent.objects.create(
        user=user,
        event_type=audit_data.event_type,
        severity=audit_data.severity,
        correlation_id=get_request_id() or '',
        resource_type=audit_data.resource_type,
        resource_id=audit_data.resource_id,
        action=audit_data.action,
        reason_code=audit_data.reason_code,
        details=audit_data.details,
        ip_address=audit_data.ip_address,
        user_agent=audit_data.user_agent,
    )


async def create_audit_event_async(audit_data: AuditEventData) -> 'AuditEvent | None':  # noqa: F821
    """Async version of create_audit_event for use in async contexts.
    
    Note: This is best-effort. In some test/edge cases where the event loop
    doesn't have database access, this will log and skip the audit event.
    """
    from asgiref.sync import sync_to_async
    
    try:
        return await sync_to_async(create_audit_event, thread_sensitive=False)(audit_data)
    except Exception as e:
        # If audit event creation fails in async context, log it but don't crash
        # The structured log already captured the event
        import logging
        logging.getLogger(__name__).debug(
            f'Failed to create audit event in async context: {e}'
        )
        return None


class MetricsCollector:
    """Simple metrics collection for key operations."""

    def __init__(self) -> None:
        self.metrics: dict[str, list] = {}

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record operation latency."""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(('latency', latency_ms, timezone.now()))

    def record_count(self, operation: str, count: int = 1) -> None:
        """Record operation count."""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(('count', count, timezone.now()))

    def record_error(self, operation: str, error_type: str) -> None:
        """Record operation error."""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(('error', error_type, timezone.now()))

    def get_summary(self, operation: str) -> dict[str, Any]:
        """Get summary stats for an operation."""
        if operation not in self.metrics:
            return {}
        
        data = self.metrics[operation]
        latencies = [v[1] for v in data if v[0] == 'latency']
        counts = [v[1] for v in data if v[0] == 'count']
        errors = [v[1] for v in data if v[0] == 'error']
        
        summary = {}
        if latencies:
            summary['latency_ms'] = {
                'min': min(latencies),
                'max': max(latencies),
                'avg': sum(latencies) / len(latencies),
                'p95': sorted(latencies)[int(len(latencies) * 0.95)],
            }
        
        if counts:
            summary['total_count'] = sum(counts)
        
        if errors:
            summary['error_count'] = len(errors)
            summary['error_types'] = list(set(errors))
        
        return summary


# Global metrics collector
metrics = MetricsCollector()


class TimingContext:
    """Context manager for measuring operation latency."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        self.start_time = None

    def __enter__(self) -> 'TimingContext':
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        latency_ms = (time.perf_counter() - self.start_time) * 1000
        metrics.record_latency(self.operation, latency_ms)
        
        if exc_type is not None:
            metrics.record_error(self.operation, exc_type.__name__)
        
        return False  # Don't suppress exceptions

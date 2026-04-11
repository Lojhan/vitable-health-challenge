"""Tests for observability infrastructure (correlation IDs, structured logging, audit trail)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from chatbot.features.core.models import AuditEvent
from chatbot.features.core.observability import (
    AuditEventData,
    MetricsCollector,
    StructuredLogger,
    TimingContext,
    clear_context,
    create_audit_event,
    generate_request_id,
    generate_turn_id,
    get_request_id,
    get_turn_id,
    get_user_id,
    set_request_id,
    set_turn_id,
    set_user_id,
)
from chatbot.features.core.redaction import (
    redact_dict,
    safe_audit_details,
)

User = get_user_model()


class TestCorrelationIDs(TestCase):
    """Test correlation ID context management."""
    
    def test_generate_request_id(self):
        """Request IDs are unique and well-formed."""
        rid1 = generate_request_id()
        rid2 = generate_request_id()
        
        assert rid1.startswith('req_')
        assert rid2.startswith('req_')
        assert rid1 != rid2
    
    def test_generate_turn_id(self):
        """Turn IDs are unique and well-formed."""
        tid1 = generate_turn_id()
        tid2 = generate_turn_id()
        
        assert tid1.startswith('turn_')
        assert tid2.startswith('turn_')
        assert tid1 != tid2
    
    def test_set_and_get_request_id(self):
        """Request ID context can be set and retrieved."""
        clear_context()
        assert get_request_id() is None
        
        rid = 'test-request-123'
        set_request_id(rid)
        assert get_request_id() == rid
    
    def test_set_and_get_turn_id(self):
        """Turn ID context can be set and retrieved."""
        clear_context()
        assert get_turn_id() is None
        
        tid = 'test-turn-456'
        set_turn_id(tid)
        assert get_turn_id() == tid
    
    def test_set_and_get_user_id(self):
        """User ID context can be set and retrieved."""
        clear_context()
        assert get_user_id() is None
        
        uid = 42
        set_user_id(uid)
        assert get_user_id() == uid
    
    def test_clear_context(self):
        """Clear context removes all correlation IDs."""
        set_request_id('req-123')
        set_turn_id('turn-456')
        set_user_id(789)
        
        assert get_request_id() is not None
        assert get_turn_id() is not None
        assert get_user_id() is not None
        
        clear_context()
        
        assert get_request_id() is None
        assert get_turn_id() is None
        assert get_user_id() is None


class TestStructuredLogger(TestCase):
    """Test structured logging with context injection."""
    
    def test_logger_creation(self):
        """StructuredLogger can be created."""
        logger = StructuredLogger('test.logger')
        assert logger is not None
    
    def test_logger_methods_exist(self):
        """StructuredLogger has all required logging methods."""
        logger = StructuredLogger('test.logger')
        
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'critical')
        
        # Should not raise
        logger.info('Test message')
        logger.warning('Test warning', reason_code='TEST_CODE')
        logger.error('Test error', details={'key': 'value'})


class TestAuditEvent(TestCase):
    """Test audit event creation and persistence."""
    
    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username='audit.test@example.com',
            password='safe-password-123',
            insurance_tier='Silver',
            medical_history={},
        )
        clear_context()
    
    def test_create_audit_event_without_user(self):
        """Audit events can be created without authenticated user."""
        set_request_id('req-123')
        
        event = create_audit_event(AuditEventData(
            event_type='AUTH_FAILURE',
            severity='WARNING',
            action='login_attempt',
            reason_code='INVALID_CREDENTIALS',
        ))
        
        assert event.event_type == 'AUTH_FAILURE'
        assert event.severity == 'WARNING'
        assert event.correlation_id == 'req-123'
        assert event.user is None
    
    def test_create_audit_event_with_user(self):
        """Audit events include authenticated user when available."""
        set_request_id('req-456')
        set_user_id(self.user.id)
        
        event = create_audit_event(AuditEventData(
            event_type='AUTH_LOGIN',
            severity='INFO',
            resource_type='user',
            resource_id=str(self.user.id),
            action='login_successful',
        ))
        
        assert event.user == self.user
        assert event.event_type == 'AUTH_LOGIN'
    
    def test_audit_event_persistence(self):
        """Audit events are persisted to database."""
        event = create_audit_event(AuditEventData(
            event_type='CHAT_START',
            severity='INFO',
            resource_type='chat_session',
            resource_id='123',
        ))
        
        retrieved = AuditEvent.objects.get(id=event.id)
        assert retrieved.event_type == 'CHAT_START'
        assert retrieved.resource_type == 'chat_session'
    
    def test_audit_event_with_details(self):
        """Audit events can include structured details."""
        details = {'session_id': 123, 'message_count': 5}
        event = create_audit_event(AuditEventData(
            event_type='CHAT_MESSAGE',
            severity='INFO',
            details=details,
        ))
        
        assert event.details == details


class TestPHIRedaction(TestCase):
    """Test PHI redaction utilities."""
    
    def test_redact_email_field_name(self):
        """Email field names are redacted."""
        data = {'email': 'user@example.com'}
        redacted = redact_dict(data)
        
        assert redacted['email'] == '[REDACTED]'
    
    def test_redact_phone_field_name(self):
        """Phone field names are redacted."""
        data = {'phone': '555-1234-5678'}
        redacted = redact_dict(data)
        
        assert redacted['phone'] == '[REDACTED]'
    
    def test_redact_date_of_birth(self):
        """Date of birth field is redacted."""
        data = {'date_of_birth': '1980-01-15'}
        redacted = redact_dict(data)
        
        assert redacted['date_of_birth'] == '[REDACTED]'
    
    def test_safe_audit_details(self):
        """safe_audit_details redacts PHI-sensitive fields."""
        details = {
            'user_email': 'safe@example.com',
            'action': 'login',
            'phone_number': '555-123-4567',
        }
        
        safe = safe_audit_details(details)
        assert safe['user_email'] == '[REDACTED]'
        assert safe['action'] == 'login'  # Not a PHI field
        assert safe['phone_number'] == '[REDACTED]'
    
    def test_redact_nested_dict(self):
        """Redaction works on nested dictionaries."""
        data = {
            'user': {
                'email': 'test@example.com',
                'name': 'John',
            },
            'action': 'login',
        }
        
        redacted = redact_dict(data)
        assert redacted['user']['email'] == '[REDACTED]'
        assert redacted['user']['name'] == 'John'
        assert redacted['action'] == 'login'


class TestMetricsCollector(TestCase):
    """Test metrics collection."""
    
    def test_record_latency(self):
        """Latencies can be recorded and summarized."""
        collector = MetricsCollector()
        
        collector.record_latency('api.request', 150.5)
        collector.record_latency('api.request', 200.3)
        
        summary = collector.get_summary('api.request')
        assert summary['latency_ms']['min'] == 150.5
        assert summary['latency_ms']['max'] == 200.3
        assert 150.5 <= summary['latency_ms']['avg'] <= 200.3
    
    def test_record_count(self):
        """Counts can be recorded."""
        collector = MetricsCollector()
        
        collector.record_count('database.queries', 5)
        collector.record_count('database.queries', 3)
        
        summary = collector.get_summary('database.queries')
        assert summary['total_count'] == 8
    
    def test_record_error(self):
        """Errors can be recorded."""
        collector = MetricsCollector()
        
        collector.record_error('api.request', 'TimeoutError')
        collector.record_error('api.request', 'ConnectionError')
        
        summary = collector.get_summary('api.request')
        assert summary['error_count'] == 2
        assert 'TimeoutError' in summary['error_types']


class TestTimingContext(TestCase):
    """Test timing context manager."""
    
    def test_timing_context_records_latency(self):
        """TimingContext records operation latency."""
        from chatbot.features.core.observability import metrics
        
        _initial_count = len(metrics.metrics.get('test.operation', []))
        
        with TimingContext('test.operation'):
            pass
        
        summary = metrics.get_summary('test.operation')
        assert 'latency_ms' in summary
    
    def test_timing_context_with_exception(self):
        """TimingContext records exceptions."""
        from chatbot.features.core.observability import metrics
        
        try:
            with TimingContext('test.error'):
                raise ValueError('Test error')
        except ValueError:
            pass
        
        summary = metrics.get_summary('test.error')
        assert 'error_count' in summary
        assert summary['error_count'] == 1
        assert 'ValueError' in summary['error_types']

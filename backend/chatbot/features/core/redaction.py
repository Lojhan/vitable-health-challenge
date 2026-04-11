"""
PHI (Protected Health Information) redaction utilities for logs and audit trails.

Handles masking/hashing of sensitive medical and personal information
to prevent accidental disclosure in logs and audit events.
"""

import hashlib
import re
from typing import Any

# Patterns for common PHI fields
PHI_PATTERNS = {
    'email': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    'phone': re.compile(r'[\d\-\(\)\+\s]{10,}'),
    'ssn': re.compile(r'\d{3}-\d{2}-\d{4}'),
    'medical_record': re.compile(r'MR\d+|mrn\d+', re.IGNORECASE),
    'blood_type': re.compile(r'\b(A|B|AB|O)[+-]?\b'),
    'date_of_birth': re.compile(r'\d{4}-\d{2}-\d{2}'),
}

# Fields that should always be redacted if present
PHI_FIELDS = {
    'ssn',
    'social_security_number',
    'date_of_birth',
    'dob',
    'drivers_license',
    'driver_license',
    'passport_number',
    'medical_record_number',
    'mrn',
    'insurance_id',
    'insurance_number',
    'phone',
    'phone_number',
    'email',
    'address',
    'credit_card',
    'bank_account',
    'sexual_orientation',
    'sexual_history',
    'drug_use',
    'mental_health_condition',
    'genetic_information',
}


def redact_value(value: Any) -> Any:
    """Redact a single value by replacing with [REDACTED]."""
    if isinstance(value, str):
        return '[REDACTED]'
    elif isinstance(value, dict):
        return redact_dict(value)
    elif isinstance(value, (list, tuple)):
        return redact_list(value)
    return value


def hash_value(value: str, salt: str = '') -> str:
    """Hash a value for one-way redaction while maintaining consistency."""
    salt_str = salt or 'medical_audit'
    h = hashlib.sha256(f'{value}{salt_str}'.encode()).hexdigest()
    return f'[HASH:{h[:8]}]'


def redact_dict(data: dict[str, Any], redact_patterns: bool = True) -> dict[str, Any]:
    """
    Recursively redact PHI from a dictionary.
    
    Args:
        data: Dictionary potentially containing PHI
        redact_patterns: If True, apply pattern-based redaction beyond field names
    
    Returns:
        Dictionary with PHI fields redacted
    """
    if not isinstance(data, dict):
        return data
    
    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if key matches PHI field names
        if key_lower in PHI_FIELDS:
            redacted[key] = redact_value(value)
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value, redact_patterns)
        elif isinstance(value, (list, tuple)):
            redacted[key] = redact_list(value, redact_patterns)
        elif isinstance(value, str) and redact_patterns:
            # Apply pattern-based redaction
            redacted_str = value
            for _pattern_name, pattern in PHI_PATTERNS.items():
                if pattern.search(redacted_str):
                    redacted_str = pattern.sub('[REDACTED]', redacted_str)
            redacted[key] = redacted_str
        else:
            redacted[key] = value
    
    return redacted


def redact_list(data: list, redact_patterns: bool = True) -> list:
    """Recursively redact PHI from a list."""
    return [
        redact_dict(item, redact_patterns) if isinstance(item, dict)
        else redact_list(item, redact_patterns) if isinstance(item, (list, tuple))
        else redact_value(item) if isinstance(item, str) and redact_patterns
        else item
        for item in data
    ]


def safe_audit_details(details: dict[str, Any]) -> dict[str, Any]:
    """
    Prepare audit event details by redacting PHI.
    
    Use this when creating audit events to ensure sensitive data is not stored.
    """
    return redact_dict(details, redact_patterns=True)


class RedactionPolicy:
    """Policy for when and how to redact PHI in different contexts."""
    
    # Audit logs always redact PHI
    AUDIT_REDACT = True
    
    # Application logs may log PHI (use carefully and follow data retention rules)
    LOG_REDACT = False
    
    # Structured logs should redact for external sinks (e.g., centralized logging)
    EXTERNAL_LOG_REDACT = True


def apply_redaction(
    data: dict[str, Any],
    redact: bool = True,
    context: str = 'audit',
) -> dict[str, Any]:
    """
    Apply redaction policy based on context.
    
    Args:
        data: Data to potentially redact
        redact: Whether to redact
        context: Where this is being used ('audit', 'log', 'external_log')
    
    Returns:
        Original or redacted data
    """
    if not redact:
        return data
    
    return safe_audit_details(data)

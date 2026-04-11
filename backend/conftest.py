"""Pytest configuration and fixtures for backend tests."""

import pytest
from django.test.utils import teardown_test_environment, setup_test_environment


@pytest.fixture(autouse=True)
def cleanup_observability_context():
    """Auto-cleanup observability context after each test to prevent test isolation issues."""
    yield
    # After test cleanup - clear observability context to ensure no stale context vars
    try:
        from chatbot.features.core.observability import clear_context
        clear_context()
    except (ImportError, RuntimeError):
        pass

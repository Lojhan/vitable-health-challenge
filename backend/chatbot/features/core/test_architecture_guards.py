from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding='utf-8')


def test_openrouter_agent_has_no_async_unsafe_env_toggle():
    content = _read('chatbot/features/ai/openrouter_agent.py')
    assert 'DJANGO_ALLOW_ASYNC_UNSAFE' not in content


def test_chat_api_tests_have_no_async_unsafe_env_toggle():
    content = _read('chatbot/test_api_chat.py')
    assert 'DJANGO_ALLOW_ASYNC_UNSAFE' not in content


def test_settings_has_no_hardcoded_legacy_secret_literal():
    content = _read('backend/settings.py')
    assert 'django-insecure-7#au@2^+ec)5@n&gqk^c@9k0(u3a=)baj#*cxr46!m*oxospnh' not in content

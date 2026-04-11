import pytest

from backend.runtime_config import SettingsValidationError, load_runtime_settings


def test_load_runtime_settings_uses_generated_dev_secret_when_debug_and_missing_secret_key():
    settings = load_runtime_settings(
        env={
            'DEBUG': 'true',
            'ALLOWED_HOSTS': 'localhost,127.0.0.1',
        },
        default_db_user='local-user',
    )

    assert settings.debug is True
    assert settings.secret_key
    assert settings.secret_key != 'django-insecure-7#au@2^+ec)5@n&gqk^c@9k0(u3a=)baj#*cxr46!m*oxospnh'


def test_load_runtime_settings_rejects_missing_secret_key_when_debug_is_false():
    with pytest.raises(SettingsValidationError, match='SECRET_KEY'):
        load_runtime_settings(
            env={
                'DEBUG': 'false',
                'ALLOWED_HOSTS': 'api.example.com',
            },
            default_db_user='deploy-user',
        )


def test_load_runtime_settings_rejects_wildcard_allowed_hosts_when_debug_is_false():
    with pytest.raises(SettingsValidationError, match='ALLOWED_HOSTS'):
        load_runtime_settings(
            env={
                'DEBUG': 'false',
                'SECRET_KEY': 'production-secret',
                'ALLOWED_HOSTS': '*',
            },
            default_db_user='deploy-user',
        )


def test_load_runtime_settings_rejects_open_cors_when_debug_is_false():
    with pytest.raises(SettingsValidationError, match='CORS_ALLOW_ALL_ORIGINS'):
        load_runtime_settings(
            env={
                'DEBUG': 'false',
                'SECRET_KEY': 'production-secret',
                'ALLOWED_HOSTS': 'api.example.com',
                'CORS_ALLOW_ALL_ORIGINS': 'true',
            },
            default_db_user='deploy-user',
        )


def test_load_runtime_settings_parses_hosts_and_database_defaults():
    settings = load_runtime_settings(
        env={
            'DEBUG': 'true',
            'SECRET_KEY': 'dev-secret',
            'ALLOWED_HOSTS': 'localhost, 127.0.0.1 ,example.test',
            'POSTGRES_DB': 'chatbot_db',
        },
        default_db_user='fallback-user',
    )

    assert settings.allowed_hosts == ['localhost', '127.0.0.1', 'example.test']
    assert settings.database.name == 'chatbot_db'
    assert settings.database.user == 'fallback-user'
    assert settings.database.password == ''
    assert settings.database.host == ''
    assert settings.database.port == ''

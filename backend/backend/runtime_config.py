from __future__ import annotations

import secrets
from dataclasses import dataclass


class SettingsValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DatabaseSettings:
    name: str
    user: str
    password: str
    host: str
    port: str


@dataclass(frozen=True)
class RuntimeSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]
    cors_allow_all_origins: bool
    database: DatabaseSettings


def _parse_bool(raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise SettingsValidationError(f'Invalid boolean value: {raw_value}')


def _parse_csv(raw_value: str | None, *, default: list[str]) -> list[str]:
    if raw_value is None:
        return default

    values = [item.strip() for item in raw_value.split(',')]
    return [item for item in values if item]


def load_runtime_settings(env: dict[str, str] | object, default_db_user: str) -> RuntimeSettings:
    get = env.get if hasattr(env, 'get') else lambda _key, default=None: default

    debug = _parse_bool(get('DEBUG'), default=True)

    secret_key = (get('SECRET_KEY') or '').strip()
    if not secret_key:
        if debug:
            secret_key = secrets.token_urlsafe(50)
        else:
            raise SettingsValidationError('SECRET_KEY is required when DEBUG is false')

    allowed_hosts = _parse_csv(get('ALLOWED_HOSTS'), default=['*'])
    if not allowed_hosts:
        allowed_hosts = ['*'] if debug else []

    cors_allow_all_origins = _parse_bool(
        get('CORS_ALLOW_ALL_ORIGINS'),
        default=debug,
    )

    if not debug:
        if not allowed_hosts or '*' in allowed_hosts:
            raise SettingsValidationError(
                'ALLOWED_HOSTS must be explicitly configured when DEBUG is false'
            )
        if cors_allow_all_origins:
            raise SettingsValidationError(
                'CORS_ALLOW_ALL_ORIGINS cannot be true when DEBUG is false'
            )

    database = DatabaseSettings(
        name=get('POSTGRES_DB', 'chatbot_db'),
        user=get('POSTGRES_USER', default_db_user),
        password=get('POSTGRES_PASSWORD', ''),
        host=get('POSTGRES_HOST', ''),
        port=get('POSTGRES_PORT', ''),
    )

    return RuntimeSettings(
        secret_key=secret_key,
        debug=debug,
        allowed_hosts=allowed_hosts,
        cors_allow_all_origins=cors_allow_all_origins,
        database=database,
    )

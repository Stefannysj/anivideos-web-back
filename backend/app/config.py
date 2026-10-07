from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(part.strip().rstrip('/') for part in raw.split(',') if part.strip())


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    session_cookie_name: str
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    cookie_secure: bool
    enable_docs: bool
    max_request_bytes: int
    rate_limit_requests: int
    auth_rate_limit_requests: int
    comment_rate_limit_requests: int
    rate_limit_window_seconds: int
    session_ttl_hours: int
    max_sessions_per_user: int
    hsts_max_age: int
    tmdb_read_token: str | None
    tmdb_region: str


def _validate_database_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {'postgresql', 'postgres'} or not parsed.hostname or not parsed.path:
        raise RuntimeError('DATABASE_URL must be a PostgreSQL URL.')
    return value


def load_settings() -> Settings:
    environment = os.getenv('ANIVIDEOS_ENV', 'development').strip().lower()
    if environment not in {'development', 'test', 'production'}:
        raise RuntimeError('ANIVIDEOS_ENV must be development, test or production.')

    database_url = _validate_database_url(os.getenv('DATABASE_URL', '').strip())
    allowed_origins = _csv(
        'ANIVIDEOS_ALLOWED_ORIGINS',
        'http://127.0.0.1:5173,http://localhost:5173',
    )
    allowed_hosts = _csv('ANIVIDEOS_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver')
    cookie_secure = _bool('ANIVIDEOS_COOKIE_SECURE', environment == 'production')

    if environment == 'production':
        if not cookie_secure:
            raise RuntimeError('ANIVIDEOS_COOKIE_SECURE must be enabled in production.')
        if any(origin.startswith('http://') for origin in allowed_origins):
            raise RuntimeError('Only HTTPS origins are allowed in production.')

    return Settings(
        environment=environment,
        database_url=database_url,
        session_cookie_name=os.getenv('ANIVIDEOS_SESSION_COOKIE', 'anivideos_session').strip(),
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
        cookie_secure=cookie_secure,
        enable_docs=_bool('ANIVIDEOS_ENABLE_DOCS', environment != 'production'),
        max_request_bytes=_int('ANIVIDEOS_MAX_REQUEST_BYTES', 262_144),
        rate_limit_requests=_int('ANIVIDEOS_RATE_LIMIT_REQUESTS', 180),
        auth_rate_limit_requests=_int('ANIVIDEOS_AUTH_RATE_LIMIT_REQUESTS', 12),
        comment_rate_limit_requests=_int('ANIVIDEOS_COMMENT_RATE_LIMIT_REQUESTS', 20),
        rate_limit_window_seconds=_int('ANIVIDEOS_RATE_LIMIT_WINDOW_SECONDS', 60),
        session_ttl_hours=_int('ANIVIDEOS_SESSION_TTL_HOURS', 168),
        max_sessions_per_user=_int('ANIVIDEOS_MAX_SESSIONS_PER_USER', 5),
        hsts_max_age=_int('ANIVIDEOS_HSTS_MAX_AGE', 31_536_000),
        tmdb_read_token=(os.getenv('TMDB_READ_TOKEN') or '').strip() or None,
        tmdb_region=(os.getenv('TMDB_REGION') or 'PE').strip().upper(),
    )


settings = load_settings()

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parents[1]


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f'{name} must be an integer') from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f'{name} must be between {minimum} and {maximum}')
    return value


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in os.getenv(name, default).split(',') if item.strip())
    if not values:
        raise RuntimeError(f'{name} must contain at least one value')
    return values


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, '1' if default else '0').strip().lower()
    if raw in {'1', 'true', 'yes', 'on'}:
        return True
    if raw in {'0', 'false', 'no', 'off'}:
        return False
    raise RuntimeError(f'{name} must be a boolean value')


def _environment() -> str:
    value = os.getenv('ANIVIDEOS_ENV', 'development').strip().lower()
    if value not in {'development', 'test', 'production'}:
        raise RuntimeError('ANIVIDEOS_ENV must be development, test, or production')
    return value


def _validated_origins(values: tuple[str, ...], *, production: bool) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if value == '*':
            raise RuntimeError('Wildcard CORS origins are not allowed')
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {'http', 'https'}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {'', '/'}
        ):
            raise RuntimeError(f'Invalid allowed origin: {value}')
        if production and parsed.scheme != 'https':
            raise RuntimeError('Production origins must use HTTPS')
        normalized.append(f'{parsed.scheme}://{parsed.netloc}')
    return tuple(dict.fromkeys(normalized))


def _validated_hosts(values: tuple[str, ...], *, production: bool) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        host = value.strip().lower()
        if not host or '://' in host or '/' in host or any(character.isspace() for character in host):
            raise RuntimeError(f'Invalid allowed host: {value}')
        if production and host == '*':
            raise RuntimeError('Wildcard trusted hosts are not allowed in production')
        normalized.append(host)
    return tuple(dict.fromkeys(normalized))


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    host: str
    port: int
    database_path: Path
    allowed_origins: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    rate_limit_requests: int
    rate_limit_window_seconds: int
    auth_rate_limit_requests: int
    comment_rate_limit_requests: int
    max_request_bytes: int
    enable_docs: bool
    session_cookie_name: str
    session_ttl_hours: int
    max_sessions_per_user: int
    cookie_secure: bool
    hsts_max_age: int

    @property
    def production(self) -> bool:
        return self.environment == 'production'


def load_settings() -> Settings:
    environment = _environment()
    production = environment == 'production'
    default_db = BASE_DIR / 'data' / 'anivideos.db'
    db_path = Path(os.getenv('ANIVIDEOS_DB_PATH', str(default_db))).expanduser().resolve()
    cookie_secure = _bool_env('ANIVIDEOS_COOKIE_SECURE', production)
    enable_docs = _bool_env('ANIVIDEOS_ENABLE_DOCS', False)

    if production and not cookie_secure:
        raise RuntimeError('ANIVIDEOS_COOKIE_SECURE must be enabled in production')
    if production and enable_docs:
        raise RuntimeError('API documentation must stay disabled in production')

    session_cookie_name = os.getenv('ANIVIDEOS_SESSION_COOKIE', 'anivideos_session').strip() or 'anivideos_session'
    if not session_cookie_name.replace('_', '').replace('-', '').isalnum():
        raise RuntimeError('ANIVIDEOS_SESSION_COOKIE contains invalid characters')

    return Settings(
        environment=environment,
        host=os.getenv('ANIVIDEOS_HOST', '127.0.0.1').strip() or '127.0.0.1',
        port=_bounded_int('ANIVIDEOS_PORT', 3001, minimum=1, maximum=65535),
        database_path=db_path,
        allowed_origins=_validated_origins(
            _csv_env('ANIVIDEOS_ALLOWED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173'),
            production=production,
        ),
        allowed_hosts=_validated_hosts(
            _csv_env('ANIVIDEOS_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver'),
            production=production,
        ),
        rate_limit_requests=_bounded_int('ANIVIDEOS_RATE_LIMIT_REQUESTS', 180, minimum=10, maximum=10000),
        rate_limit_window_seconds=_bounded_int('ANIVIDEOS_RATE_LIMIT_WINDOW_SECONDS', 60, minimum=1, maximum=3600),
        auth_rate_limit_requests=_bounded_int('ANIVIDEOS_AUTH_RATE_LIMIT_REQUESTS', 12, minimum=1, maximum=1000),
        comment_rate_limit_requests=_bounded_int('ANIVIDEOS_COMMENT_RATE_LIMIT_REQUESTS', 20, minimum=1, maximum=2000),
        max_request_bytes=_bounded_int('ANIVIDEOS_MAX_REQUEST_BYTES', 262144, minimum=1024, maximum=10_485_760),
        enable_docs=enable_docs,
        session_cookie_name=session_cookie_name,
        session_ttl_hours=_bounded_int('ANIVIDEOS_SESSION_TTL_HOURS', 168, minimum=1, maximum=720),
        max_sessions_per_user=_bounded_int('ANIVIDEOS_MAX_SESSIONS_PER_USER', 5, minimum=1, maximum=20),
        cookie_secure=cookie_secure,
        hsts_max_age=_bounded_int('ANIVIDEOS_HSTS_MAX_AGE', 31536000, minimum=300, maximum=63072000),
    )


settings = load_settings()

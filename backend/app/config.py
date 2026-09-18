from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in os.getenv(name, default).split(',') if item.strip())
    if not values:
        raise RuntimeError(f"{name} must contain at least one value")
    return values


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, '1' if default else '0').strip().lower()
    if raw in {'1', 'true', 'yes', 'on'}:
        return True
    if raw in {'0', 'false', 'no', 'off'}:
        return False
    raise RuntimeError(f"{name} must be a boolean value")


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    database_path: Path
    allowed_origins: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    rate_limit_requests: int
    rate_limit_window_seconds: int
    auth_rate_limit_requests: int
    max_request_bytes: int
    enable_docs: bool
    session_cookie_name: str
    session_ttl_hours: int
    cookie_secure: bool


def load_settings() -> Settings:
    default_db = BASE_DIR / 'data' / 'anivideos.db'
    db_path = Path(os.getenv('ANIVIDEOS_DB_PATH', str(default_db))).expanduser().resolve()
    return Settings(
        host=os.getenv('ANIVIDEOS_HOST', '127.0.0.1').strip() or '127.0.0.1',
        port=_positive_int('ANIVIDEOS_PORT', 3001),
        database_path=db_path,
        allowed_origins=_csv_env(
            'ANIVIDEOS_ALLOWED_ORIGINS',
            'http://127.0.0.1:5173,http://localhost:5173',
        ),
        allowed_hosts=_csv_env('ANIVIDEOS_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver'),
        rate_limit_requests=_positive_int('ANIVIDEOS_RATE_LIMIT_REQUESTS', 180),
        rate_limit_window_seconds=_positive_int('ANIVIDEOS_RATE_LIMIT_WINDOW_SECONDS', 60),
        auth_rate_limit_requests=_positive_int('ANIVIDEOS_AUTH_RATE_LIMIT_REQUESTS', 12),
        max_request_bytes=_positive_int('ANIVIDEOS_MAX_REQUEST_BYTES', 1048576),
        enable_docs=_bool_env('ANIVIDEOS_ENABLE_DOCS', False),
        session_cookie_name=os.getenv('ANIVIDEOS_SESSION_COOKIE', 'anivideos_session').strip() or 'anivideos_session',
        session_ttl_hours=_positive_int('ANIVIDEOS_SESSION_TTL_HOURS', 168),
        cookie_secure=_bool_env('ANIVIDEOS_COOKIE_SECURE', False),
    )


settings = load_settings()

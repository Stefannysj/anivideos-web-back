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


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    database_path: Path
    allowed_origins: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    rate_limit_requests: int
    rate_limit_window_seconds: int
    max_request_bytes: int
    enable_docs: bool


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
        max_request_bytes=_positive_int('ANIVIDEOS_MAX_REQUEST_BYTES', 1048576),
        enable_docs=os.getenv('ANIVIDEOS_ENABLE_DOCS', '0').strip() == '1',
    )


settings = load_settings()

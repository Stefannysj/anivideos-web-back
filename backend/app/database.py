from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from app.config import BASE_DIR, settings

SCHEMA_PATH = BASE_DIR / 'sql' / 'schema.sql'
SEED_PATH = BASE_DIR / 'sql' / 'seed.sql'


def _path(database_path: Path | None = None) -> Path:
    return (database_path or settings.database_path).resolve()


@contextmanager
def connection(database_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = _path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    try:
        yield conn
    finally:
        conn.close()


def initialize_database(database_path: Path | None = None) -> None:
    path = _path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding='utf-8')
    seed = SEED_PATH.read_text(encoding='utf-8')
    with connection(path) as conn:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
        conn.executescript(schema)
        conn.executescript(seed)
        conn.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (int(datetime.now(timezone.utc).timestamp()),))
        conn.commit()


def database_is_healthy(database_path: Path | None = None) -> bool:
    try:
        with connection(database_path) as conn:
            result = conn.execute('SELECT 1 AS ok').fetchone()
        return bool(result and result['ok'] == 1)
    except sqlite3.Error:
        return False


def list_content(category: str | None = None, database_path: Path | None = None) -> list[dict[str, object]]:
    query = '''
        SELECT id, title, category, category_label, release_year, score,
               maturity, format, genres_json, artwork
          FROM content_items
    '''
    params: tuple[object, ...] = ()
    if category is not None:
        query += ' WHERE category = ?'
        params = (category,)
    query += ' ORDER BY display_order ASC'

    with connection(database_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            'id': row['id'],
            'title': row['title'],
            'category': row['category'],
            'category_label': row['category_label'],
            'year': row['release_year'],
            'score': row['score'],
            'maturity': row['maturity'],
            'format': row['format'],
            'genres': json.loads(row['genres_json']),
            'artwork': row['artwork'],
        }
        for row in rows
    ]


def list_banners(database_path: Path | None = None) -> list[dict[str, object]]:
    query = '''
        SELECT id, category, eyebrow, title, synopsis, release_year, age_rating,
               format, genres_json, artwork, section_href
          FROM featured_banners
         ORDER BY display_order ASC
    '''
    with connection(database_path) as conn:
        rows = conn.execute(query).fetchall()

    return [
        {
            'id': row['id'],
            'category': 'Película' if row['category'] == 'Pelicula' else row['category'],
            'eyebrow': row['eyebrow'],
            'title': row['title'],
            'synopsis': row['synopsis'],
            'year': row['release_year'],
            'age_rating': row['age_rating'],
            'format': row['format'],
            'genres': json.loads(row['genres_json']),
            'artwork': row['artwork'],
            'section_href': row['section_href'],
        }
        for row in rows
    ]


def create_user(
    username: str,
    email: str,
    password_hash: str,
    database_path: Path | None = None,
) -> dict[str, object]:
    with connection(database_path) as conn:
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash),
        )
        conn.commit()
        user_id = int(cursor.lastrowid)
    user = get_user_by_id(user_id, database_path)
    if user is None:
        raise RuntimeError('User creation failed')
    return user


def get_user_by_id(user_id: int, database_path: Path | None = None) -> dict[str, object] | None:
    with connection(database_path) as conn:
        row = conn.execute(
            '''SELECT id, username, email, password_hash, avatar_url, is_active, created_at
                 FROM users
                WHERE id = ?''',
            (user_id,),
        ).fetchone()
    return _user_row(row)


def get_user_by_identifier(identifier: str, database_path: Path | None = None) -> dict[str, object] | None:
    with connection(database_path) as conn:
        row = conn.execute(
            '''SELECT id, username, email, password_hash, avatar_url, is_active, created_at
                 FROM users
                WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
                LIMIT 1''',
            (identifier, identifier),
        ).fetchone()
    return _user_row(row)


def update_user_password_hash(user_id: int, password_hash: str, database_path: Path | None = None) -> None:
    with connection(database_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()


def create_auth_session(
    user_id: int,
    token_hash: str,
    expires_at: int,
    database_path: Path | None = None,
) -> None:
    with connection(database_path) as conn:
        conn.execute(
            'INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)',
            (token_hash, user_id, expires_at),
        )
        conn.commit()


def get_user_by_session(
    token_hash: str,
    now_epoch: int,
    database_path: Path | None = None,
) -> dict[str, object] | None:
    with connection(database_path) as conn:
        row = conn.execute(
            '''SELECT u.id, u.username, u.email, u.password_hash, u.avatar_url, u.is_active, u.created_at
                 FROM auth_sessions s
                 JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                  AND s.expires_at > ?
                  AND u.is_active = 1
                LIMIT 1''',
            (token_hash, now_epoch),
        ).fetchone()
    return _user_row(row)


def delete_auth_session(token_hash: str, database_path: Path | None = None) -> None:
    with connection(database_path) as conn:
        conn.execute('DELETE FROM auth_sessions WHERE token_hash = ?', (token_hash,))
        conn.commit()


def count_auth_sessions(database_path: Path | None = None) -> int:
    with connection(database_path) as conn:
        row = conn.execute('SELECT COUNT(*) AS total FROM auth_sessions').fetchone()
    return int(row['total']) if row else 0


def _user_row(row: sqlite3.Row | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        'id': int(row['id']),
        'username': row['username'],
        'email': row['email'],
        'password_hash': row['password_hash'],
        'avatar_url': row['avatar_url'],
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'],
    }

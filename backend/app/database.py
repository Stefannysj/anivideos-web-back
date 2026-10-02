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
    conn.execute('PRAGMA trusted_schema = OFF')
    conn.execute('PRAGMA secure_delete = ON')
    conn.execute('PRAGMA recursive_triggers = OFF')
    conn.execute('PRAGMA busy_timeout = 5000')
    try:
        yield conn
    finally:
        conn.close()


def _ensure_user_profile_columns(conn: sqlite3.Connection) -> None:
    columns = {str(row['name']) for row in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'display_name' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT CHECK(display_name IS NULL OR length(trim(display_name)) BETWEEN 1 AND 60)")
    if 'bio' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT CHECK(bio IS NULL OR length(bio) <= 280)")



def _ensure_content_detail_columns(conn: sqlite3.Connection) -> None:
    columns = {str(row['name']) for row in conn.execute('PRAGMA table_info(content_items)').fetchall()}
    if 'synopsis' not in columns:
        conn.execute("ALTER TABLE content_items ADD COLUMN synopsis TEXT NOT NULL DEFAULT ''")
    if 'origin' not in columns:
        conn.execute("ALTER TABLE content_items ADD COLUMN origin TEXT NOT NULL DEFAULT ''")
    if 'status' not in columns:
        conn.execute("ALTER TABLE content_items ADD COLUMN status TEXT NOT NULL DEFAULT ''")


def initialize_database(database_path: Path | None = None) -> None:
    path = _path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding='utf-8')
    seed = SEED_PATH.read_text(encoding='utf-8')
    with connection(path) as conn:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
        conn.executescript(schema)
        _ensure_user_profile_columns(conn)
        _ensure_content_detail_columns(conn)
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


def _escape_like(value: str) -> str:
    """Escapes LIKE wildcards so user input is treated as literal text."""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def list_content(
    category: str | None = None,
    database_path: Path | None = None,
    *,
    search: str | None = None,
    genre: str | None = None,
    year: int | None = None,
    min_score: float | None = None,
    sort: str = 'featured',
) -> list[dict[str, object]]:
    query = """
        SELECT id, title, category, category_label, release_year, score,
               maturity, format, genres_json, artwork, display_order
          FROM content_items
    """
    conditions: list[str] = []
    params: list[object] = []

    if category is not None:
        conditions.append('category = ?')
        params.append(category)

    if search is not None and search.strip():
        pattern = f"%{_escape_like(search.strip())}%"
        conditions.append("(title LIKE ? ESCAPE '\\' COLLATE NOCASE OR genres_json LIKE ? ESCAPE '\\' COLLATE NOCASE)")
        params.extend((pattern, pattern))

    if genre is not None and genre.strip():
        genre_pattern = f'%"{_escape_like(genre.strip())}"%'
        conditions.append("genres_json LIKE ? ESCAPE '\\' COLLATE NOCASE")
        params.append(genre_pattern)

    if year is not None:
        conditions.append('release_year = ?')
        params.append(year)

    if min_score is not None:
        conditions.append('score >= ?')
        params.append(min_score)

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    order_by = {
        'featured': 'display_order ASC',
        'title-asc': 'title COLLATE NOCASE ASC, display_order ASC',
        'year-desc': 'release_year DESC, display_order ASC',
        'score-desc': 'score DESC, display_order ASC',
    }.get(sort, 'display_order ASC')
    query += f' ORDER BY {order_by}'

    with connection(database_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

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


def get_content_by_id(content_id: str, database_path: Path | None = None) -> dict[str, object] | None:
    query = """
        SELECT id, title, category, category_label, release_year, score,
               maturity, format, genres_json, artwork, synopsis, origin, status
          FROM content_items
         WHERE id = ?
         LIMIT 1
    """
    with connection(database_path) as conn:
        row = conn.execute(query, (content_id,)).fetchone()
    if row is None:
        return None
    return {
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
        'synopsis': row['synopsis'],
        'origin': row['origin'],
        'status': row['status'],
    }


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
            '''SELECT id, username, email, password_hash, avatar_url, display_name, bio, is_active, created_at, updated_at
                 FROM users
                WHERE id = ?''',
            (user_id,),
        ).fetchone()
    return _user_row(row)


def get_user_by_identifier(identifier: str, database_path: Path | None = None) -> dict[str, object] | None:
    with connection(database_path) as conn:
        row = conn.execute(
            '''SELECT id, username, email, password_hash, avatar_url, display_name, bio, is_active, created_at, updated_at
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
    *,
    max_sessions: int = 5,
) -> None:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    with connection(database_path) as conn:
        conn.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (now_epoch,))
        conn.execute(
            'INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)',
            (token_hash, user_id, expires_at),
        )
        conn.execute(
            '''DELETE FROM auth_sessions
                WHERE user_id = ?
                  AND token_hash NOT IN (
                      SELECT token_hash
                        FROM auth_sessions
                       WHERE user_id = ?
                       ORDER BY rowid DESC
                       LIMIT ?
                  )''',
            (user_id, user_id, max_sessions),
        )
        conn.commit()


def get_user_by_session(
    token_hash: str,
    now_epoch: int,
    database_path: Path | None = None,
) -> dict[str, object] | None:
    with connection(database_path) as conn:
        row = conn.execute(
            '''SELECT u.id, u.username, u.email, u.password_hash, u.avatar_url, u.display_name, u.bio, u.is_active, u.created_at, u.updated_at
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


def delete_other_auth_sessions(
    user_id: int,
    keep_token_hash: str,
    database_path: Path | None = None,
) -> None:
    with connection(database_path) as conn:
        conn.execute(
            'DELETE FROM auth_sessions WHERE user_id = ? AND token_hash <> ?',
            (user_id, keep_token_hash),
        )
        conn.commit()


def delete_expired_auth_sessions(now_epoch: int, database_path: Path | None = None) -> int:
    with connection(database_path) as conn:
        cursor = conn.execute('DELETE FROM auth_sessions WHERE expires_at <= ?', (now_epoch,))
        conn.commit()
        return cursor.rowcount


def update_user_profile(
    user_id: int,
    *,
    username: str,
    email: str,
    display_name: str | None,
    bio: str | None,
    database_path: Path | None = None,
) -> dict[str, object]:
    with connection(database_path) as conn:
        conn.execute(
            """UPDATE users
                  SET username = ?, email = ?, display_name = ?, bio = ?,
                      updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?""",
            (username, email, display_name, bio, user_id),
        )
        conn.commit()
    user = get_user_by_id(user_id, database_path)
    if user is None:
        raise RuntimeError('User profile update failed')
    return user



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
        'display_name': row['display_name'],
        'bio': row['bio'],
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def list_favorites(user_id: int, database_path: Path | None = None) -> list[dict[str, object]]:
    query = '''
        SELECT c.id, c.title, c.category, c.category_label, c.release_year, c.score,
               c.maturity, c.format, c.genres_json, c.artwork
          FROM favorites f
          JOIN content_items c ON c.id = f.content_id
         WHERE f.user_id = ?
         ORDER BY f.created_at DESC, c.display_order ASC
    '''
    with connection(database_path) as conn:
        rows = conn.execute(query, (user_id,)).fetchall()

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


def add_favorite(user_id: int, content_id: str, database_path: Path | None = None) -> bool:
    """Adds one catalog item idempotently. Returns False when the content id does not exist."""
    with connection(database_path) as conn:
        exists = conn.execute('SELECT 1 FROM content_items WHERE id = ?', (content_id,)).fetchone()
        if exists is None:
            return False
        conn.execute(
            'INSERT OR IGNORE INTO favorites (user_id, content_id) VALUES (?, ?)',
            (user_id, content_id),
        )
        conn.commit()
    return True


def remove_favorite(user_id: int, content_id: str, database_path: Path | None = None) -> None:
    """Removes one favorite idempotently without exposing whether another user saved the item."""
    with connection(database_path) as conn:
        conn.execute(
            'DELETE FROM favorites WHERE user_id = ? AND content_id = ?',
            (user_id, content_id),
        )
        conn.commit()


def banner_exists(banner_id: str, database_path: Path | None = None) -> bool:
    with connection(database_path) as conn:
        row = conn.execute('SELECT 1 FROM featured_banners WHERE id = ?', (banner_id,)).fetchone()
    return row is not None


def list_banner_comments(
    banner_id: str,
    viewer_user_id: int | None = None,
    database_path: Path | None = None,
) -> list[dict[str, object]]:
    viewer_id = viewer_user_id if viewer_user_id is not None else -1
    query = '''
        SELECT c.id, c.banner_id, c.body, c.created_at,
               u.username, u.display_name,
               CASE WHEN c.user_id = ? THEN 1 ELSE 0 END AS is_owner
          FROM banner_comments c
          JOIN users u ON u.id = c.user_id
         WHERE c.banner_id = ?
         ORDER BY c.created_at DESC, c.id DESC
    '''
    with connection(database_path) as conn:
        rows = conn.execute(query, (viewer_id, banner_id)).fetchall()
    return [_banner_comment_row(row) for row in rows]


def create_banner_comment(
    banner_id: str,
    user_id: int,
    body: str,
    database_path: Path | None = None,
) -> dict[str, object] | None:
    with connection(database_path) as conn:
        banner = conn.execute('SELECT 1 FROM featured_banners WHERE id = ?', (banner_id,)).fetchone()
        if banner is None:
            return None
        cursor = conn.execute(
            'INSERT INTO banner_comments (banner_id, user_id, body) VALUES (?, ?, ?)',
            (banner_id, user_id, body),
        )
        comment_id = int(cursor.lastrowid)
        conn.commit()
        row = conn.execute(
            '''SELECT c.id, c.banner_id, c.body, c.created_at,
                      u.username, u.display_name, 1 AS is_owner
                 FROM banner_comments c
                 JOIN users u ON u.id = c.user_id
                WHERE c.id = ? AND c.banner_id = ?''',
            (comment_id, banner_id),
        ).fetchone()
    return _banner_comment_row(row) if row is not None else None


def delete_banner_comment(
    banner_id: str,
    comment_id: int,
    user_id: int,
    database_path: Path | None = None,
) -> bool:
    """Deletes only a comment owned by the authenticated user."""
    with connection(database_path) as conn:
        cursor = conn.execute(
            'DELETE FROM banner_comments WHERE id = ? AND banner_id = ? AND user_id = ?',
            (comment_id, banner_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def _banner_comment_row(row: sqlite3.Row) -> dict[str, object]:
    return {
        'id': int(row['id']),
        'banner_id': str(row['banner_id']),
        'body': str(row['body']),
        'author': {
            'username': str(row['username']),
            'display_name': str(row['display_name']) if row['display_name'] else None,
        },
        'created_at': str(row['created_at']),
        'is_owner': bool(row['is_owner']),
    }

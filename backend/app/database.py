from __future__ import annotations

from contextlib import contextmanager
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

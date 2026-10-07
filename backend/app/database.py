from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import json
from typing import Iterator, Sequence

import psycopg
from psycopg.rows import dict_row

from app.config import settings

CATEGORY_LABELS = {
    'anime': 'Anime',
    'k-drama': 'K-Drama',
    'j-drama': 'J-Drama',
    'donghua': 'Donghua',
    'movie': 'Película',
    'ova': 'OVA',
}
SECTION_HREFS = {
    'anime': '#anime',
    'k-drama': '#k-dramas',
    'j-drama': '#j-dramas',
    'donghua': '#donghua',
    'movie': '#peliculas',
    'ova': '#ovas',
}


@contextmanager
def connection(database_url: str | None = None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url or settings.database_url, row_factory=dict_row) as conn:
        yield conn


def initialize_database() -> None:
    """Validate PostgreSQL availability and require Alembic migrations before startup."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.content_items') AS table_name")
            row = cur.fetchone()
            if not row or row['table_name'] is None:
                raise RuntimeError('Database schema is missing. Run: alembic upgrade head')


def database_is_healthy() -> bool:
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 AS ok')
                return bool(cur.fetchone()['ok'])
    except psycopg.Error:
        return False


def _escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _content_projection(prefix: str = 'c', *, include_detail: bool = True) -> str:
    # List endpoints intentionally select only ContentItemResponse fields.
    # Detail/banner endpoints opt into the larger projection. This keeps payloads
    # smaller and, importantly, avoids passing detail-only keys into Pydantic
    # models configured with extra="forbid".
    fields = [
        f'{prefix}.id',
        f'{prefix}.source',
        f'{prefix}.external_id',
        f'{prefix}.title',
        f'{prefix}.original_title',
        f'{prefix}.category',
        f'{prefix}.release_year AS year',
        f'{prefix}.score',
        f'{prefix}.maturity',
        f'{prefix}.format',
        f'{prefix}.genres',
        f'{prefix}.cover_url AS artwork',
        f'{prefix}.studio',
        f'{prefix}.episodes',
        f'{prefix}.status',
    ]
    if include_detail:
        fields.extend([
            f'{prefix}.backdrop_url',
            f'{prefix}.synopsis',
            f'{prefix}.origin',
            f'{prefix}.trailer_youtube_id',
            f'{prefix}.official_url',
            f'{prefix}.platform_links',
            f'{prefix}.source_url',
        ])
    return ',\n        '.join(fields)


def _normalize_content_row(row: dict[str, object]) -> dict[str, object]:
    result = dict(row)
    category = str(result['category'])
    result['category_label'] = CATEGORY_LABELS.get(category, category)
    result['source_attribution'] = 'AniList' if result['source'] == 'anilist' else 'TMDB'
    result['genres'] = list(result.get('genres') or [])
    if 'platform_links' in result:
        result['platform_links'] = list(result.get('platform_links') or [])
    result['score'] = float(result.get('score') or 0)
    return result


def list_content(
    category: str | None = None,
    *,
    search: str | None = None,
    genre: str | None = None,
    year: int | None = None,
    min_score: float | None = None,
    status: str | None = None,
    format: str | None = None,
    sort: str = 'featured',
    limit: int = 120,
) -> list[dict[str, object]]:
    filters: list[str] = []
    params: list[object] = []

    if category:
        filters.append('c.category = %s')
        params.append(category)
    if search:
        pattern = f"%{_escape_like(search)}%"
        filters.append("(c.title ILIKE %s ESCAPE '\\\\' OR COALESCE(c.original_title, '') ILIKE %s ESCAPE '\\\\')")
        params.extend([pattern, pattern])
    if genre:
        filters.append('c.genres @> %s::jsonb')
        params.append(json.dumps([genre]))
    if year is not None:
        filters.append('c.release_year = %s')
        params.append(year)
    if min_score is not None:
        filters.append('c.score >= %s')
        params.append(min_score)
    if status:
        filters.append('c.status = %s')
        params.append(status)
    if format:
        filters.append('c.format = %s')
        params.append(format)

    order_by = {
        'featured': 'c.score DESC, c.release_year DESC NULLS LAST, c.title ASC',
        'title-asc': 'c.title ASC',
        'year-desc': 'c.release_year DESC NULLS LAST, c.score DESC',
        'score-desc': 'c.score DESC, c.title ASC',
    }.get(sort, 'c.score DESC, c.release_year DESC NULLS LAST, c.title ASC')

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ''
    query = f"""
        SELECT {_content_projection('c', include_detail=False)}
        FROM content_items c
        {where_sql}
        ORDER BY {order_by}
        LIMIT %s
    """
    params.append(max(1, min(limit, 200)))
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return [_normalize_content_row(row) for row in cur.fetchall()]


@lru_cache(maxsize=512)
def get_content_by_id(content_id: str) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_content_projection('c')} FROM content_items c WHERE c.id = %s",
                (content_id,),
            )
            row = cur.fetchone()
            return _normalize_content_row(row) if row else None


def list_banners() -> list[dict[str, object]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT b.id AS banner_id, b.eyebrow, b.display_order, {_content_projection('c')}
                FROM featured_banners b
                JOIN content_items c ON c.id = b.content_id
                WHERE b.is_active = TRUE
                ORDER BY b.display_order ASC, c.score DESC
                """
            )
            result = []
            for raw in cur.fetchall():
                item = _normalize_content_row(raw)
                category = str(item['category'])
                result.append({
                    'id': str(raw['banner_id']),
                    'content_id': str(item['id']),
                    'category': CATEGORY_LABELS.get(category, category),
                    'eyebrow': str(raw['eyebrow']),
                    'title': str(item['title']),
                    'synopsis': str(item['synopsis']),
                    'year': int(item['year']) if item['year'] is not None else datetime.now(timezone.utc).year,
                    'age_rating': str(item['maturity']),
                    'format': str(item['format']),
                    'genres': item['genres'],
                    'artwork': str(item.get('backdrop_url') or item['artwork']),
                    'section_href': SECTION_HREFS.get(category, '#catalogo'),
                    'source': str(item['source']),
                    'source_attribution': str(item['source_attribution']),
                })
            return result


def clear_public_query_caches() -> None:
    get_content_by_id.cache_clear()


def create_user(username: str, email: str, password_hash: str) -> dict[str, object]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (username, email, password_hash),
            )
            return dict(cur.fetchone())


def get_user_by_id(user_id: int) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_by_identifier(identifier: str) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM users WHERE lower(username) = lower(%s) OR lower(email) = lower(%s) LIMIT 1',
                (identifier, identifier),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_user_password_hash(user_id: int, password_hash: str) -> None:
    with connection() as conn:
        conn.execute(
            'UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s',
            (password_hash, user_id),
        )


def create_auth_session(
    user_id: int,
    token_hash: str,
    expires_at: int,
    *,
    max_sessions: int,
) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM auth_sessions WHERE expires_at <= %s', (int(datetime.now(timezone.utc).timestamp()),))
            cur.execute(
                'INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)',
                (token_hash, user_id, expires_at),
            )
            cur.execute(
                """
                DELETE FROM auth_sessions
                WHERE token_hash IN (
                    SELECT token_hash FROM auth_sessions
                    WHERE user_id = %s
                    ORDER BY created_at DESC, token_hash DESC
                    OFFSET %s
                )
                """,
                (user_id, max_sessions),
            )


def get_user_by_session(token_hash: str, now_epoch: int) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.*
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > %s AND u.is_active = TRUE
                """,
                (token_hash, now_epoch),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def delete_auth_session(token_hash: str) -> None:
    with connection() as conn:
        conn.execute('DELETE FROM auth_sessions WHERE token_hash = %s', (token_hash,))


def delete_other_auth_sessions(user_id: int, keep_token_hash: str) -> None:
    with connection() as conn:
        conn.execute(
            'DELETE FROM auth_sessions WHERE user_id = %s AND token_hash <> %s',
            (user_id, keep_token_hash),
        )


def delete_expired_auth_sessions(now_epoch: int) -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM auth_sessions WHERE expires_at <= %s', (now_epoch,))
            return cur.rowcount


def count_auth_sessions(user_id: int) -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS count FROM auth_sessions WHERE user_id = %s', (user_id,))
            return int(cur.fetchone()['count'])


def update_user_profile(
    user_id: int,
    *,
    username: str,
    email: str,
    display_name: str | None,
    bio: str | None,
) -> dict[str, object]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET username = %s, email = %s, display_name = %s, bio = %s, updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (username, email, display_name, bio, user_id),
            )
            return dict(cur.fetchone())


def list_favorites(user_id: int) -> list[dict[str, object]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_content_projection('c', include_detail=False)}
                FROM favorites f
                JOIN content_items c ON c.id = f.content_id
                WHERE f.user_id = %s
                ORDER BY f.created_at DESC
                """,
                (user_id,),
            )
            return [_normalize_content_row(row) for row in cur.fetchall()]


def add_favorite(user_id: int, content_id: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM content_items WHERE id = %s', (content_id,))
            if cur.fetchone() is None:
                return False
            cur.execute(
                'INSERT INTO favorites (user_id, content_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (user_id, content_id),
            )
            return True


def remove_favorite(user_id: int, content_id: str) -> None:
    with connection() as conn:
        conn.execute('DELETE FROM favorites WHERE user_id = %s AND content_id = %s', (user_id, content_id))


def banner_exists(banner_id: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM featured_banners WHERE id = %s AND is_active = TRUE', (banner_id,))
            return cur.fetchone() is not None


def _banner_comment_row(row: dict[str, object], viewer_id: int | None) -> dict[str, object]:
    return {
        'id': int(row['id']),
        'banner_id': str(row['banner_id']),
        'body': str(row['body']),
        'author': {
            'username': str(row['username']),
            'display_name': str(row['display_name']) if row['display_name'] else None,
        },
        'created_at': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']),
        'is_owner': viewer_id is not None and int(row['user_id']) == viewer_id,
    }


def list_banner_comments(banner_id: str, viewer_id: int | None) -> list[dict[str, object]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bc.*, u.username, u.display_name
                FROM banner_comments bc
                JOIN users u ON u.id = bc.user_id
                WHERE bc.banner_id = %s
                ORDER BY bc.created_at DESC, bc.id DESC
                """,
                (banner_id,),
            )
            return [_banner_comment_row(row, viewer_id) for row in cur.fetchall()]


def create_banner_comment(banner_id: str, user_id: int, body: str) -> dict[str, object] | None:
    if not banner_exists(banner_id):
        return None
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO banner_comments (banner_id, user_id, body)
                VALUES (%s, %s, %s)
                RETURNING id, banner_id, user_id, body, created_at
                """,
                (banner_id, user_id, body),
            )
            created = dict(cur.fetchone())
            cur.execute('SELECT username, display_name FROM users WHERE id = %s', (user_id,))
            created.update(cur.fetchone())
            return _banner_comment_row(created, user_id)


def delete_banner_comment(banner_id: str, comment_id: int, user_id: int) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM banner_comments WHERE id = %s AND banner_id = %s AND user_id = %s',
                (comment_id, banner_id, user_id),
            )
            return cur.rowcount > 0


def upsert_catalog_items(items: Sequence[dict[str, object]]) -> int:
    if not items:
        return 0
    query = """
        INSERT INTO content_items (
            id, source, external_id, category, title, original_title, synopsis, genres,
            cover_url, backdrop_url, studio, episodes, score, release_year, maturity,
            format, status, origin, trailer_youtube_id, official_url, platform_links,
            source_url, provider_updated_at, updated_at
        ) VALUES (
            %(id)s, %(source)s, %(external_id)s, %(category)s, %(title)s, %(original_title)s,
            %(synopsis)s, %(genres)s::jsonb, %(cover_url)s, %(backdrop_url)s, %(studio)s,
            %(episodes)s, %(score)s, %(release_year)s, %(maturity)s, %(format)s, %(status)s,
            %(origin)s, %(trailer_youtube_id)s, %(official_url)s, %(platform_links)s::jsonb,
            %(source_url)s, %(provider_updated_at)s, now()
        )
        ON CONFLICT (source, external_id) DO UPDATE SET
            id = EXCLUDED.id,
            category = EXCLUDED.category,
            title = EXCLUDED.title,
            original_title = EXCLUDED.original_title,
            synopsis = EXCLUDED.synopsis,
            genres = EXCLUDED.genres,
            cover_url = EXCLUDED.cover_url,
            backdrop_url = EXCLUDED.backdrop_url,
            studio = EXCLUDED.studio,
            episodes = EXCLUDED.episodes,
            score = EXCLUDED.score,
            release_year = EXCLUDED.release_year,
            maturity = EXCLUDED.maturity,
            format = EXCLUDED.format,
            status = EXCLUDED.status,
            origin = EXCLUDED.origin,
            trailer_youtube_id = EXCLUDED.trailer_youtube_id,
            official_url = EXCLUDED.official_url,
            platform_links = EXCLUDED.platform_links,
            source_url = EXCLUDED.source_url,
            provider_updated_at = EXCLUDED.provider_updated_at,
            updated_at = now()
    """
    normalized = []
    for item in items:
        row = dict(item)
        row['genres'] = json.dumps(row.get('genres') or [])
        row['platform_links'] = json.dumps(row.get('platform_links') or [])
        normalized.append(row)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, normalized)
    clear_public_query_caches()
    return len(normalized)


def refresh_featured_banners(limit: int = 4) -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE featured_banners SET is_active = FALSE, updated_at = now()')
            cur.execute(
                """
                SELECT id, category, title
                FROM content_items
                WHERE backdrop_url IS NOT NULL OR cover_url IS NOT NULL
                ORDER BY score DESC, release_year DESC NULLS LAST, title ASC
                LIMIT %s
                """,
                (limit,),
            )
            selected = cur.fetchall()
            for index, item in enumerate(selected):
                banner_id = f"featured-{item['id']}"
                eyebrow = f"{CATEGORY_LABELS.get(str(item['category']), str(item['category']))} destacado"
                cur.execute(
                    """
                    INSERT INTO featured_banners (id, content_id, eyebrow, display_order, is_active, updated_at)
                    VALUES (%s, %s, %s, %s, TRUE, now())
                    ON CONFLICT (id) DO UPDATE SET
                        content_id = EXCLUDED.content_id,
                        eyebrow = EXCLUDED.eyebrow,
                        display_order = EXCLUDED.display_order,
                        is_active = TRUE,
                        updated_at = now()
                    """,
                    (banner_id, item['id'], eyebrow, index),
                )
    return len(selected)

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
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
            f'{prefix}.season',
            f'{prefix}.season_year',
            f'{prefix}.next_airing_at',
            f'{prefix}.next_episode_number',
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
    if 'next_airing_at' in result and result.get('next_airing_at') is not None and hasattr(result['next_airing_at'], 'isoformat'):
        result['next_airing_at'] = result['next_airing_at'].isoformat()
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
        filters.append(
            "(c.title ILIKE %s ESCAPE '\\' OR COALESCE(c.original_title, '') ILIKE %s ESCAPE '\\' "
            "OR similarity(c.title, %s) >= 0.22 OR similarity(COALESCE(c.original_title, ''), %s) >= 0.22)"
        )
        params.extend([pattern, pattern, search, search])
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
    order_params: list[object] = []
    if search and sort == 'featured':
        order_by = "GREATEST(similarity(c.title, %s), similarity(COALESCE(c.original_title, ''), %s)) DESC, c.score DESC, c.title ASC"
        order_params.extend([search, search])

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ''
    query = f"""
        SELECT {_content_projection('c', include_detail=False)}
        FROM content_items c
        {where_sql}
        ORDER BY {order_by}
        LIMIT %s
    """
    params.extend(order_params)
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


def list_library(user_id: int) -> list[dict[str, object]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_content_projection('c', include_detail=False)},
                       ul.is_favorite, ul.progress_status, ul.updated_at AS library_updated_at
                FROM user_library ul
                JOIN content_items c ON c.id = ul.content_id
                WHERE ul.user_id = %s
                ORDER BY ul.updated_at DESC, c.title ASC
                """,
                (user_id,),
            )
            result = []
            for row in cur.fetchall():
                item = _normalize_content_row(row)
                result.append({
                    'content': {key: value for key, value in item.items() if key not in {'is_favorite', 'progress_status', 'library_updated_at'}},
                    'is_favorite': bool(row['is_favorite']),
                    'progress_status': row['progress_status'],
                    'updated_at': row['library_updated_at'].isoformat() if hasattr(row['library_updated_at'], 'isoformat') else str(row['library_updated_at']),
                })
            return result


def set_library_state(
    user_id: int,
    content_id: str,
    *,
    is_favorite: bool | None = None,
    progress_status: str | None | object = ...,
) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM content_items WHERE id = %s', (content_id,))
            if cur.fetchone() is None:
                return None
            cur.execute(
                'SELECT is_favorite, progress_status FROM user_library WHERE user_id = %s AND content_id = %s',
                (user_id, content_id),
            )
            current = cur.fetchone()
            next_favorite = bool(current['is_favorite']) if current else False
            next_status = current['progress_status'] if current else None
            if is_favorite is not None:
                next_favorite = is_favorite
            if progress_status is not ...:
                next_status = progress_status
            if not next_favorite and next_status is None:
                cur.execute('DELETE FROM user_library WHERE user_id = %s AND content_id = %s', (user_id, content_id))
                return {'content_id': content_id, 'is_favorite': False, 'progress_status': None}
            cur.execute(
                """
                INSERT INTO user_library (user_id, content_id, is_favorite, progress_status, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (user_id, content_id) DO UPDATE SET
                    is_favorite = EXCLUDED.is_favorite,
                    progress_status = EXCLUDED.progress_status,
                    updated_at = now()
                RETURNING is_favorite, progress_status
                """,
                (user_id, content_id, next_favorite, next_status),
            )
            row = cur.fetchone()
            return {'content_id': content_id, 'is_favorite': bool(row['is_favorite']), 'progress_status': row['progress_status']}


def list_favorites(user_id: int) -> list[dict[str, object]]:
    return [entry['content'] for entry in list_library(user_id) if entry['is_favorite']]


def add_favorite(user_id: int, content_id: str) -> bool:
    return set_library_state(user_id, content_id, is_favorite=True) is not None


def remove_favorite(user_id: int, content_id: str) -> None:
    set_library_state(user_id, content_id, is_favorite=False)


def search_suggestions(query: str, limit: int = 8) -> list[dict[str, object]]:
    normalized = query.strip()
    if len(normalized) < 2:
        return []
    pattern = f"%{_escape_like(normalized)}%"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_content_projection('c', include_detail=False)},
                       GREATEST(similarity(c.title, %s), similarity(COALESCE(c.original_title, ''), %s)) AS relevance
                FROM content_items c
                WHERE c.title ILIKE %s ESCAPE '\\'
                   OR COALESCE(c.original_title, '') ILIKE %s ESCAPE '\\'
                   OR similarity(c.title, %s) >= 0.18
                   OR similarity(COALESCE(c.original_title, ''), %s) >= 0.18
                ORDER BY relevance DESC, c.score DESC, c.title ASC
                LIMIT %s
                """,
                (normalized, normalized, pattern, pattern, normalized, normalized, max(1, min(limit, 12))),
            )
            result = []
            for row in cur.fetchall():
                item = _normalize_content_row(row)
                item.pop('relevance', None)
                result.append(item)
            return result


def list_recommendations(user_id: int, limit: int = 12) -> list[dict[str, object]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH preferred_genres AS (
                    SELECT genre.value AS genre, COUNT(*)::integer AS weight
                    FROM user_library ul
                    JOIN content_items owned ON owned.id = ul.content_id
                    CROSS JOIN LATERAL jsonb_array_elements_text(owned.genres) AS genre(value)
                    WHERE ul.user_id = %s AND ul.is_favorite = TRUE
                    GROUP BY genre.value
                ), ranked AS (
                    SELECT c.id, COALESCE(SUM(pg.weight), 0)::integer AS affinity
                    FROM content_items c
                    LEFT JOIN LATERAL jsonb_array_elements_text(c.genres) AS candidate_genre(value) ON TRUE
                    LEFT JOIN preferred_genres pg ON pg.genre = candidate_genre.value
                    WHERE NOT EXISTS (SELECT 1 FROM user_library ul2 WHERE ul2.user_id = %s AND ul2.content_id = c.id)
                    GROUP BY c.id
                )
                SELECT {_content_projection('c', include_detail=False)}, ranked.affinity
                FROM ranked
                JOIN content_items c ON c.id = ranked.id
                ORDER BY ranked.affinity DESC, c.score DESC, c.release_year DESC NULLS LAST, c.title ASC
                LIMIT %s
                """,
                (user_id, user_id, max(1, min(limit, 24))),
            )
            result = []
            for row in cur.fetchall():
                item = _normalize_content_row(row)
                item.pop('affinity', None)
                result.append(item)
            return result


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


def _review_row(row: dict[str, object], viewer_id: int | None) -> dict[str, object]:
    return {
        'id': int(row['id']),
        'content_id': str(row['content_id']),
        'rating': int(row['rating']),
        'body': str(row['body'] or ''),
        'author': {
            'username': str(row['username']),
            'display_name': str(row['display_name']) if row.get('display_name') else None,
        },
        'created_at': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']),
        'updated_at': row['updated_at'].isoformat() if hasattr(row['updated_at'], 'isoformat') else str(row['updated_at']),
        'is_owner': viewer_id is not None and int(row['user_id']) == viewer_id,
    }


def list_reviews(content_id: str, viewer_id: int | None) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM content_items WHERE id = %s', (content_id,))
            if cur.fetchone() is None:
                return None
            cur.execute(
                """
                SELECT r.*, u.username, u.display_name
                FROM reviews r
                JOIN users u ON u.id = r.user_id
                WHERE r.content_id = %s
                ORDER BY r.updated_at DESC, r.id DESC
                """,
                (content_id,),
            )
            items = [_review_row(row, viewer_id) for row in cur.fetchall()]
            cur.execute('SELECT COUNT(*) AS count, AVG(rating)::float AS average FROM reviews WHERE content_id = %s', (content_id,))
            summary = cur.fetchone()
            return {'items': items, 'count': int(summary['count']), 'average_rating': round(float(summary['average'] or 0), 1)}


def upsert_review(user_id: int, content_id: str, rating: int, body: str) -> dict[str, object] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM content_items WHERE id = %s', (content_id,))
            if cur.fetchone() is None:
                return None
            cur.execute(
                """
                INSERT INTO reviews (user_id, content_id, rating, body, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (user_id, content_id) DO UPDATE SET
                    rating = EXCLUDED.rating, body = EXCLUDED.body, updated_at = now()
                RETURNING *
                """,
                (user_id, content_id, rating, body),
            )
            row = dict(cur.fetchone())
            cur.execute('SELECT username, display_name FROM users WHERE id = %s', (user_id,))
            row.update(cur.fetchone())
            return _review_row(row, user_id)


def delete_review(user_id: int, content_id: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM reviews WHERE user_id = %s AND content_id = %s', (user_id, content_id))
            return cur.rowcount > 0


def report_review(review_id: int, reporter_user_id: int, reason: str, detail: str | None) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT user_id FROM reviews WHERE id = %s', (review_id,))
            row = cur.fetchone()
            if row is None or int(row['user_id']) == reporter_user_id:
                return False
            cur.execute(
                """
                INSERT INTO review_reports (review_id, reporter_user_id, reason, detail)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (review_id, reporter_user_id) DO UPDATE SET
                    reason = EXCLUDED.reason, detail = EXCLUDED.detail, created_at = now()
                """,
                (review_id, reporter_user_id, reason, detail),
            )
            return True


def list_weekly_calendar(week_start: date) -> list[dict[str, object]]:
    start = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_content_projection('c', include_detail=False)}, c.next_airing_at, c.next_episode_number
                FROM content_items c
                WHERE c.next_airing_at >= %s AND c.next_airing_at < %s
                ORDER BY c.next_airing_at ASC, c.title ASC
                """,
                (start, end),
            )
            result = []
            for row in cur.fetchall():
                item = _normalize_content_row(row)
                result.append({
                    'content': {key: value for key, value in item.items() if key not in {'next_airing_at', 'next_episode_number'}},
                    'airing_at': row['next_airing_at'].isoformat(),
                    'episode_number': row['next_episode_number'],
                })
            return result


def list_season_calendar(season: str, year: int, limit: int = 100) -> list[dict[str, object]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_content_projection('c', include_detail=False)}
                FROM content_items c
                WHERE c.season = %s AND c.season_year = %s
                ORDER BY c.score DESC, c.title ASC
                LIMIT %s
                """,
                (season, year, max(1, min(limit, 200))),
            )
            return [_normalize_content_row(row) for row in cur.fetchall()]



def upsert_catalog_items(items: Sequence[dict[str, object]]) -> int:
    if not items:
        return 0
    query = """
        INSERT INTO content_items (
            id, source, external_id, category, title, original_title, synopsis, genres,
            cover_url, backdrop_url, studio, episodes, score, release_year, maturity,
            format, status, origin, trailer_youtube_id, official_url, platform_links,
            source_url, provider_updated_at, season, season_year, next_airing_at, next_episode_number, updated_at
        ) VALUES (
            %(id)s, %(source)s, %(external_id)s, %(category)s, %(title)s, %(original_title)s,
            %(synopsis)s, %(genres)s::jsonb, %(cover_url)s, %(backdrop_url)s, %(studio)s,
            %(episodes)s, %(score)s, %(release_year)s, %(maturity)s, %(format)s, %(status)s,
            %(origin)s, %(trailer_youtube_id)s, %(official_url)s, %(platform_links)s::jsonb,
            %(source_url)s, %(provider_updated_at)s, %(season)s, %(season_year)s, %(next_airing_at)s, %(next_episode_number)s, now()
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
            season = EXCLUDED.season,
            season_year = EXCLUDED.season_year,
            next_airing_at = EXCLUDED.next_airing_at,
            next_episode_number = EXCLUDED.next_episode_number,
            updated_at = now()
    """
    normalized = []
    for item in items:
        row = dict(item)
        row['genres'] = json.dumps(row.get('genres') or [])
        row['platform_links'] = json.dumps(row.get('platform_links') or [])
        row.setdefault('season', None)
        row.setdefault('season_year', row.get('release_year'))
        row.setdefault('next_airing_at', None)
        row.setdefault('next_episode_number', None)
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

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

TMDB_API = 'https://api.themoviedb.org/3'
TMDB_WEB = 'https://www.themoviedb.org'
IMAGE_BASE = 'https://image.tmdb.org/t/p'


def _youtube_trailer(videos: list[dict[str, Any]]) -> str | None:
    youtube = [v for v in videos if v.get('site') == 'YouTube' and v.get('key')]
    official = [v for v in youtube if v.get('official') and v.get('type') == 'Trailer']
    trailer = official[0] if official else next((v for v in youtube if v.get('type') == 'Trailer'), None)
    return str(trailer['key']) if trailer else None




def _season_for_date(value: str | None) -> str | None:
    if not isinstance(value, str) or len(value) < 7:
        return None
    try:
        month = int(value[5:7])
    except ValueError:
        return None
    if month in {12, 1, 2}:
        return 'winter'
    if month in {3, 4, 5}:
        return 'spring'
    if month in {6, 7, 8}:
        return 'summer'
    return 'fall'


def _date_at_noon_utc(value: str | None) -> datetime | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        parsed = datetime.strptime(value[:10], '%Y-%m-%d')
    except ValueError:
        return None
    return parsed.replace(hour=12, tzinfo=timezone.utc)

def _status(value: str | None) -> str:
    normalized = (value or '').strip().lower()
    if normalized in {'ended', 'released'}:
        return 'finished'
    if normalized in {'returning series', 'in production'}:
        return 'airing'
    if normalized in {'planned', 'post production'}:
        return 'upcoming'
    if normalized in {'canceled', 'cancelled'}:
        return 'cancelled'
    return normalized.replace(' ', '-') or 'unknown'


def _provider_links(details: dict[str, Any], region: str, media_type: str, media_id: int) -> list[dict[str, str]]:
    providers = (((details.get('watch/providers') or {}).get('results') or {}).get(region) or {})
    tmdb_link = providers.get('link')
    names: list[str] = []
    for bucket in ('flatrate', 'free', 'ads', 'rent', 'buy'):
        for provider in providers.get(bucket) or []:
            name = str(provider.get('provider_name') or '').strip()
            if name and name not in names:
                names.append(name)
    result = []
    for name in names[:8]:
        result.append({
            'name': name,
            'url': str(tmdb_link or f'{TMDB_WEB}/{media_type}/{media_id}/watch'),
            'attribution': 'JustWatch',
        })
    return result


def map_details(details: dict[str, Any], *, category: str, media_type: str, region: str) -> dict[str, object]:
    media_id = int(details['id'])
    is_tv = media_type == 'tv'
    title = details.get('name') if is_tv else details.get('title')
    original_title = details.get('original_name') if is_tv else details.get('original_title')
    first_date = details.get('first_air_date') if is_tv else details.get('release_date')
    year = int(first_date[:4]) if isinstance(first_date, str) and len(first_date) >= 4 and first_date[:4].isdigit() else None
    companies = details.get('production_companies') or []
    networks = details.get('networks') or []
    studio = (networks[0].get('name') if networks else None) or (companies[0].get('name') if companies else None)
    poster = details.get('poster_path')
    backdrop = details.get('backdrop_path')
    source_path = f'/{media_type}/{media_id}'
    next_episode = details.get('next_episode_to_air') or {}
    next_date = next_episode.get('air_date') if is_tv else first_date
    return {
        'id': f'tmdb-{media_type}-{media_id}',
        'source': 'tmdb',
        'external_id': f'{media_type}:{media_id}',
        'category': category,
        'title': str(title or original_title or f'TMDB {media_id}'),
        'original_title': str(original_title) if original_title else None,
        'synopsis': str(details.get('overview') or '').strip(),
        'genres': [str(g.get('name')) for g in details.get('genres') or [] if g.get('name')],
        'cover_url': f'{IMAGE_BASE}/w780{poster}' if poster else '',
        'backdrop_url': f'{IMAGE_BASE}/w1280{backdrop}' if backdrop else None,
        'studio': str(studio) if studio else None,
        'episodes': details.get('number_of_episodes') if is_tv else None,
        'score': round(float(details.get('vote_average') or 0), 1),
        'release_year': year,
        'maturity': '18+' if details.get('adult') else 'NR',
        'format': 'tv' if is_tv else 'movie',
        'status': _status(details.get('status')),
        'origin': str((details.get('origin_country') or [details.get('original_language') or ''])[0]),
        'trailer_youtube_id': _youtube_trailer(((details.get('videos') or {}).get('results') or [])),
        'official_url': str(details.get('homepage')) if str(details.get('homepage') or '').startswith('https://') else None,
        'platform_links': _provider_links(details, region, media_type, media_id),
        'source_url': f'{TMDB_WEB}{source_path}',
        'season': _season_for_date(first_date),
        'season_year': year,
        'next_airing_at': _date_at_noon_utc(next_date),
        'next_episode_number': next_episode.get('episode_number') if is_tv else None,
        'provider_updated_at': datetime.now(timezone.utc),
    }


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
    response = await client.get(f'{TMDB_API}{path}', params=params)
    if response.status_code == 429:
        retry_after = min(float(response.headers.get('Retry-After', '1')), 5.0)
        await asyncio.sleep(retry_after)
        response = await client.get(f'{TMDB_API}{path}', params=params)
    response.raise_for_status()
    return response.json()


async def fetch_catalog(token: str, *, region: str = 'PE', pages: int = 1) -> list[dict[str, object]]:
    if not token:
        raise RuntimeError('TMDB_READ_TOKEN is required for TMDB synchronization.')
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json', 'User-Agent': 'AniVideos/0.17'}
    results: list[dict[str, object]] = []
    discoveries = [
        ('k-drama', 'tv', {'with_original_language': 'ko'}),
        ('j-drama', 'tv', {'with_original_language': 'ja'}),
        ('donghua', 'tv', {'with_original_language': 'zh', 'with_genres': '16'}),
        ('movie', 'movie', {}),
    ]
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        for category, media_type, extra in discoveries:
            for page in range(1, max(1, pages) + 1):
                params = {
                    'language': 'es-ES',
                    'include_adult': 'false',
                    'sort_by': 'popularity.desc',
                    'page': page,
                    **extra,
                }
                discovered = await _get(client, f'/discover/{media_type}', params)
                for item in discovered.get('results') or []:
                    media_id = int(item['id'])
                    details = await _get(
                        client,
                        f'/{media_type}/{media_id}',
                        {
                            'language': 'es-ES',
                            'append_to_response': 'videos,watch/providers',
                        },
                    )
                    results.append(map_details(details, category=category, media_type=media_type, region=region))
                    await asyncio.sleep(0.03)
    return results

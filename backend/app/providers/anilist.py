from __future__ import annotations

from datetime import datetime, timezone
import html
import re
from typing import Any

import httpx

ANILIST_API = 'https://graphql.anilist.co'
_ALLOWED_LINK_TYPES = {'STREAMING'}
_ALLOWED_STREAMING_SITES = {
    'Crunchyroll', 'Netflix', 'Hulu', 'Bilibili TV', 'Bilibili', 'YouTube',
    'Amazon Prime Video', 'Disney Plus', 'HIDIVE', 'Tubi TV', 'Viki',
}

QUERY = '''
query($page: Int!, $perPage: Int!) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(type: ANIME, sort: POPULARITY_DESC, isAdult: false) {
      id
      title { romaji english native }
      description(asHtml: false)
      genres
      averageScore
      episodes
      status
      format
      season
      seasonYear
      nextAiringEpisode { airingAt episode }
      countryOfOrigin
      siteUrl
      coverImage { extraLarge large }
      bannerImage
      studios(isMain: true) { nodes { name } }
      trailer { id site }
      externalLinks { site url type }
    }
  }
}
'''


def _clean_description(value: str | None) -> str:
    if not value:
        return ''
    text = html.unescape(re.sub(r'<[^>]+>', ' ', value))
    return re.sub(r'\s+', ' ', text).strip()[:5000]


def _status(value: str | None) -> str:
    return {
        'FINISHED': 'finished',
        'RELEASING': 'airing',
        'NOT_YET_RELEASED': 'upcoming',
        'CANCELLED': 'cancelled',
        'HIATUS': 'hiatus',
    }.get(value or '', 'unknown')


def _format(value: str | None) -> str:
    return {
        'TV': 'tv', 'TV_SHORT': 'tv-short', 'MOVIE': 'movie', 'SPECIAL': 'special',
        'OVA': 'ova', 'ONA': 'ona', 'MUSIC': 'music',
    }.get(value or '', (value or 'unknown').lower())


def map_media(media: dict[str, Any]) -> dict[str, object]:
    media_id = str(media['id'])
    title_data = media.get('title') or {}
    title = title_data.get('english') or title_data.get('romaji') or title_data.get('native') or f'AniList {media_id}'
    original_title = title_data.get('native') or title_data.get('romaji')
    media_format = _format(media.get('format'))
    category = 'ova' if media_format == 'ova' else 'anime'
    cover = media.get('coverImage') or {}
    studio_nodes = ((media.get('studios') or {}).get('nodes') or [])
    trailer = media.get('trailer') or {}
    trailer_id = trailer.get('id') if trailer.get('site') == 'youtube' else None

    links = []
    for link in media.get('externalLinks') or []:
        url = str(link.get('url') or '')
        if not url.startswith('https://'):
            continue
        if link.get('type') in _ALLOWED_LINK_TYPES or link.get('site') in _ALLOWED_STREAMING_SITES:
            links.append({'name': str(link.get('site') or 'Plataforma oficial'), 'url': url})

    return {
        'id': f'anilist-{media_id}',
        'source': 'anilist',
        'external_id': media_id,
        'category': category,
        'title': str(title),
        'original_title': str(original_title) if original_title else None,
        'synopsis': _clean_description(media.get('description')),
        'genres': list(media.get('genres') or []),
        'cover_url': cover.get('extraLarge') or cover.get('large') or '',
        'backdrop_url': media.get('bannerImage'),
        'studio': str(studio_nodes[0].get('name')) if studio_nodes else None,
        'episodes': media.get('episodes'),
        'score': round(float(media.get('averageScore') or 0) / 10, 1),
        'release_year': media.get('seasonYear'),
        'maturity': 'NR',
        'format': media_format,
        'status': _status(media.get('status')),
        'origin': str(media.get('countryOfOrigin') or 'JP'),
        'trailer_youtube_id': str(trailer_id) if trailer_id else None,
        'official_url': str(media.get('siteUrl')) if media.get('siteUrl') else None,
        'platform_links': links[:10],
        'source_url': str(media.get('siteUrl')) if media.get('siteUrl') else None,
        'season': str(media.get('season') or '').lower() or None,
        'season_year': media.get('seasonYear'),
        'next_airing_at': datetime.fromtimestamp(int((media.get('nextAiringEpisode') or {}).get('airingAt')), tz=timezone.utc) if (media.get('nextAiringEpisode') or {}).get('airingAt') else None,
        'next_episode_number': (media.get('nextAiringEpisode') or {}).get('episode'),
        'provider_updated_at': datetime.now(timezone.utc),
    }


async def fetch_catalog(*, pages: int = 2, per_page: int = 25) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=20.0, headers={'User-Agent': 'AniVideos/0.17'}) as client:
        for page in range(1, max(1, pages) + 1):
            response = await client.post(ANILIST_API, json={'query': QUERY, 'variables': {'page': page, 'perPage': per_page}})
            response.raise_for_status()
            payload = response.json()
            if payload.get('errors'):
                raise RuntimeError(f"AniList error: {payload['errors'][0].get('message', 'unknown error')}")
            page_data = payload['data']['Page']
            results.extend(map_media(item) for item in page_data.get('media') or [])
            if not (page_data.get('pageInfo') or {}).get('hasNextPage'):
                break
    return results

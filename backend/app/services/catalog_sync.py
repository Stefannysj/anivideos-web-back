from __future__ import annotations

import asyncio

from app.config import settings
from app.database import refresh_featured_banners, upsert_catalog_items
from app.providers import anilist, tmdb


async def synchronize_catalog(*, source: str = 'all', pages: int = 1) -> dict[str, int]:
    counts = {'anilist': 0, 'tmdb': 0, 'banners': 0}
    if source in {'all', 'anilist'}:
        items = await anilist.fetch_catalog(pages=max(1, pages))
        counts['anilist'] = upsert_catalog_items(items)
    if source in {'all', 'tmdb'}:
        if not settings.tmdb_read_token:
            if source == 'tmdb':
                raise RuntimeError('TMDB_READ_TOKEN is required.')
        else:
            items = await tmdb.fetch_catalog(
                settings.tmdb_read_token,
                region=settings.tmdb_region,
                pages=max(1, pages),
            )
            counts['tmdb'] = upsert_catalog_items(items)
    counts['banners'] = refresh_featured_banners()
    return counts


def run_sync(*, source: str = 'all', pages: int = 1) -> dict[str, int]:
    return asyncio.run(synchronize_catalog(source=source, pages=pages))

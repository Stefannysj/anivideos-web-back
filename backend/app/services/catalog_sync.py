from __future__ import annotations

import asyncio

from app.database import refresh_featured_banners, upsert_catalog_items
from app.providers import anilist


async def synchronize_catalog(*, source: str = 'anilist', pages: int = 1) -> dict[str, int]:
    if source not in {'all', 'anilist'}:
        raise ValueError('AniList is the only active external catalog provider.')

    items = await anilist.fetch_catalog(pages=max(1, pages))
    return {
        'anilist': upsert_catalog_items(items),
        'banners': refresh_featured_banners(),
    }


def run_sync(*, source: str = 'anilist', pages: int = 1) -> dict[str, int]:
    return asyncio.run(synchronize_catalog(source=source, pages=pages))

from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status

from app.database import get_content_by_id, list_content
from app.http_cache import apply_public_cache
from app.schemas import CatalogResponse, ContentDetailResponse, ContentItemResponse

router = APIRouter()
Category = Literal['anime', 'k-drama', 'series', 'movie']
SortOption = Literal['featured', 'title-asc', 'year-desc', 'score-desc']


@router.get('/catalog', response_model=CatalogResponse)
def catalog(
    request: Request,
    response: Response,
    category: Category | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=80),
    genre: str | None = Query(default=None, min_length=1, max_length=40),
    year: int | None = Query(default=None, ge=1900, le=2100),
    min_score: float | None = Query(default=None, ge=0, le=10, alias='minScore'),
    sort: SortOption = Query(default='featured'),
):
    """Returns cacheable public catalog metadata with bounded, parameterized filters."""
    search = q.strip() if q is not None else None
    normalized_genre = genre.strip() if genre is not None else None

    payload = CatalogResponse(
        items=[
            ContentItemResponse(**item)
            for item in list_content(
                category=category,
                search=search or None,
                genre=normalized_genre or None,
                year=year,
                min_score=min_score,
                sort=sort,
            )
        ]
    )
    return apply_public_cache(request, response, payload, max_age=120, stale_while_revalidate=120)


@router.get('/catalog/{content_id}', response_model=ContentDetailResponse)
def catalog_detail(
    request: Request,
    response: Response,
    content_id: str = Path(min_length=1, max_length=80, pattern=r'^[a-z0-9-]+$'),
):
    """Returns one public catalog item by stable id with conditional caching."""
    item = get_content_by_id(content_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    payload = ContentDetailResponse(**item)
    return apply_public_cache(request, response, payload, max_age=600, stale_while_revalidate=300)

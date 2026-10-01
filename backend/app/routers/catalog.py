from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.database import get_content_by_id, list_content
from app.schemas import CatalogResponse, ContentDetailResponse, ContentItemResponse

router = APIRouter()
Category = Literal['anime', 'k-drama', 'series', 'movie']
SortOption = Literal['featured', 'title-asc', 'year-desc', 'score-desc']


@router.get('/catalog', response_model=CatalogResponse)
def catalog(
    category: Category | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=80),
    genre: str | None = Query(default=None, min_length=1, max_length=40),
    year: int | None = Query(default=None, ge=1900, le=2100),
    min_score: float | None = Query(default=None, ge=0, le=10, alias='minScore'),
    sort: SortOption = Query(default='featured'),
) -> CatalogResponse:
    """Returns the public catalog with bounded, parameterized search and filters."""
    search = q.strip() if q is not None else None
    normalized_genre = genre.strip() if genre is not None else None

    items = [
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
    return CatalogResponse(items=items)


@router.get('/catalog/{content_id}', response_model=ContentDetailResponse)
def catalog_detail(
    content_id: str = Path(min_length=1, max_length=80, pattern=r'^[a-z0-9-]+$'),
) -> ContentDetailResponse:
    """Returns one public catalog item by its stable id."""
    item = get_content_by_id(content_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return ContentDetailResponse(**item)

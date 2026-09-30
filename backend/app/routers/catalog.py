from typing import Literal

from fastapi import APIRouter, Query

from app.database import list_content
from app.schemas import CatalogResponse, ContentItemResponse

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

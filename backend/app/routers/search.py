from fastapi import APIRouter, Query

from app.database import search_suggestions
from app.schemas import CatalogResponse, ContentItemResponse

router = APIRouter()


@router.get('/search/suggestions', response_model=CatalogResponse)
def suggestions(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=8, ge=1, le=12),
) -> CatalogResponse:
    items = [ContentItemResponse(**item) for item in search_suggestions(q, limit)]
    return CatalogResponse(items=items)

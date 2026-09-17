from typing import Literal

from fastapi import APIRouter, Query

from app.database import list_content
from app.schemas import CatalogResponse, ContentItemResponse

router = APIRouter()
Category = Literal['anime', 'k-drama', 'series', 'movie']


@router.get('/catalog', response_model=CatalogResponse)
def catalog(category: Category | None = Query(default=None)) -> CatalogResponse:
    items = [ContentItemResponse(**item) for item in list_content(category)]
    return CatalogResponse(items=items)

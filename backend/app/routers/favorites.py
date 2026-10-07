from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Request, status

from app.auth_dependencies import require_current_user
from app.database import add_favorite, list_favorites, remove_favorite
from app.schemas import CatalogResponse, ContentItemResponse, FavoriteStateResponse

router = APIRouter()
_CONTENT_ID_PATTERN = r'^[a-z0-9-]{1,120}$'


@router.get('/favorites', response_model=CatalogResponse)
def favorites(request: Request) -> CatalogResponse:
    user = require_current_user(request)
    items = [ContentItemResponse(**item) for item in list_favorites(int(user['id']))]
    return CatalogResponse(items=items)


@router.put('/favorites/{content_id}', response_model=FavoriteStateResponse)
def save_favorite(
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> FavoriteStateResponse:
    user = require_current_user(request)
    if not add_favorite(int(user['id']), content_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return FavoriteStateResponse(content_id=content_id, is_favorite=True)


@router.delete('/favorites/{content_id}', response_model=FavoriteStateResponse)
def delete_favorite(
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> FavoriteStateResponse:
    user = require_current_user(request)
    remove_favorite(int(user['id']), content_id)
    return FavoriteStateResponse(content_id=content_id, is_favorite=False)

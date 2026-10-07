from fastapi import APIRouter, Query, Request

from app.auth_dependencies import require_current_user
from app.database import list_recommendations
from app.schemas import CatalogResponse, ContentItemResponse

router = APIRouter()


@router.get('/recommendations', response_model=CatalogResponse)
def recommendations(request: Request, limit: int = Query(default=12, ge=1, le=24)) -> CatalogResponse:
    user = require_current_user(request)
    items = [ContentItemResponse(**item) for item in list_recommendations(int(user['id']), limit)]
    return CatalogResponse(items=items)

from fastapi import APIRouter, Request, Response

from app.database import list_banners
from app.http_cache import apply_public_cache
from app.schemas import BannerListResponse, BannerResponse

router = APIRouter()


@router.get('/banners', response_model=BannerListResponse)
def banners(request: Request, response: Response):
    payload = BannerListResponse(items=[BannerResponse(**item) for item in list_banners()])
    return apply_public_cache(request, response, payload, max_age=300, stale_while_revalidate=300)

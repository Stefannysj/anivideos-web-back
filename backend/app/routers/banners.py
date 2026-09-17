from fastapi import APIRouter

from app.database import list_banners
from app.schemas import BannerListResponse, BannerResponse

router = APIRouter()


@router.get('/banners', response_model=BannerListResponse)
def banners() -> BannerListResponse:
    items = [BannerResponse(**item) for item in list_banners()]
    return BannerListResponse(items=items)

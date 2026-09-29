from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Request, status

from app.auth_dependencies import current_user_or_none, require_current_user
from app.database import banner_exists, create_banner_comment, delete_banner_comment, list_banner_comments
from app.schemas import (
    BannerCommentCreateRequest,
    BannerCommentListResponse,
    BannerCommentResponse,
    MessageResponse,
)

router = APIRouter()
_BANNER_ID_PATTERN = r'^[a-z0-9-]{1,80}$'


@router.get('/banners/{banner_id}/comments', response_model=BannerCommentListResponse)
def comments(
    request: Request,
    banner_id: str = Path(min_length=1, max_length=80, pattern=_BANNER_ID_PATTERN),
) -> BannerCommentListResponse:
    if not banner_exists(banner_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Banner not found')
    viewer = current_user_or_none(request)
    viewer_id = int(viewer['id']) if viewer is not None else None
    items = [BannerCommentResponse(**item) for item in list_banner_comments(banner_id, viewer_id)]
    return BannerCommentListResponse(items=items)


@router.post('/banners/{banner_id}/comments', response_model=BannerCommentResponse, status_code=status.HTTP_201_CREATED)
def publish_comment(
    payload: BannerCommentCreateRequest,
    request: Request,
    banner_id: str = Path(min_length=1, max_length=80, pattern=_BANNER_ID_PATTERN),
) -> BannerCommentResponse:
    user = require_current_user(request)
    created = create_banner_comment(banner_id, int(user['id']), payload.body)
    if created is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Banner not found')
    return BannerCommentResponse(**created)


@router.delete('/banners/{banner_id}/comments/{comment_id}', response_model=MessageResponse)
def remove_comment(
    request: Request,
    banner_id: str = Path(min_length=1, max_length=80, pattern=_BANNER_ID_PATTERN),
    comment_id: int = Path(ge=1),
) -> MessageResponse:
    user = require_current_user(request)
    removed = delete_banner_comment(banner_id, comment_id, int(user['id']))
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found')
    return MessageResponse(message='Comentario eliminado.')

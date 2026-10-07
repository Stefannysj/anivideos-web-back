from fastapi import APIRouter, HTTPException, Path, Request, status

from app.auth_dependencies import current_user_or_none, require_current_user
from app.database import delete_review, list_reviews, report_review, upsert_review
from app.schemas import (
    MessageResponse,
    ReviewCreateRequest,
    ReviewListResponse,
    ReviewReportRequest,
    ReviewResponse,
)

router = APIRouter()
_CONTENT_ID_PATTERN = r'^[a-z0-9-]{1,120}$'


@router.get('/content/{content_id}/reviews', response_model=ReviewListResponse)
def reviews(
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> ReviewListResponse:
    viewer = current_user_or_none(request)
    result = list_reviews(content_id, int(viewer['id']) if viewer else None)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return ReviewListResponse(**result)


@router.put('/content/{content_id}/review', response_model=ReviewResponse)
def save_review(
    payload: ReviewCreateRequest,
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> ReviewResponse:
    user = require_current_user(request)
    result = upsert_review(int(user['id']), content_id, payload.rating, payload.body)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return ReviewResponse(**result)


@router.delete('/content/{content_id}/review', response_model=MessageResponse)
def remove_review(
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> MessageResponse:
    user = require_current_user(request)
    if not delete_review(int(user['id']), content_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')
    return MessageResponse(message='Reseña eliminada.')


@router.post('/reviews/{review_id}/reports', response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def report(
    payload: ReviewReportRequest,
    request: Request,
    review_id: int = Path(ge=1),
) -> MessageResponse:
    user = require_current_user(request)
    if not report_review(review_id, int(user['id']), payload.reason, payload.detail):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')
    return MessageResponse(message='Reporte registrado.')

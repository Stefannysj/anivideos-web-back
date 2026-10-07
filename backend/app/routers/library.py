from fastapi import APIRouter, HTTPException, Path, Request, status

from app.auth_dependencies import require_current_user
from app.database import list_library, set_library_state
from app.schemas import (
    LibraryEntryResponse,
    LibraryResponse,
    LibraryStateResponse,
    LibraryStatusRequest,
)

router = APIRouter()
_CONTENT_ID_PATTERN = r'^[a-z0-9-]{1,120}$'


@router.get('/my-list', response_model=LibraryResponse)
def my_list(request: Request) -> LibraryResponse:
    user = require_current_user(request)
    return LibraryResponse(items=[LibraryEntryResponse(**entry) for entry in list_library(int(user['id']))])


@router.put('/my-list/{content_id}/favorite', response_model=LibraryStateResponse)
def add_favorite(
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> LibraryStateResponse:
    user = require_current_user(request)
    state = set_library_state(int(user['id']), content_id, is_favorite=True)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return LibraryStateResponse(**state)


@router.delete('/my-list/{content_id}/favorite', response_model=LibraryStateResponse)
def remove_favorite(
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> LibraryStateResponse:
    user = require_current_user(request)
    state = set_library_state(int(user['id']), content_id, is_favorite=False)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return LibraryStateResponse(**state)


@router.put('/my-list/{content_id}/status', response_model=LibraryStateResponse)
def set_progress_status(
    payload: LibraryStatusRequest,
    request: Request,
    content_id: str = Path(min_length=1, max_length=120, pattern=_CONTENT_ID_PATTERN),
) -> LibraryStateResponse:
    user = require_current_user(request)
    state = set_library_state(int(user['id']), content_id, progress_status=payload.status)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Content not found')
    return LibraryStateResponse(**state)

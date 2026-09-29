from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from app.auth_security import hash_session_token
from app import config
from app.database import get_user_by_session


def current_user_or_none(request: Request) -> dict[str, object] | None:
    """Resolves an optional session without turning public endpoints into authenticated-only routes."""
    token = request.cookies.get(config.settings.session_cookie_name)
    if not token:
        return None
    return get_user_by_session(
        hash_session_token(token),
        int(datetime.now(timezone.utc).timestamp()),
    )


def require_current_user(request: Request) -> dict[str, object]:
    """Resolves the authenticated user exclusively from the opaque HttpOnly session cookie."""
    user = current_user_or_none(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    return user

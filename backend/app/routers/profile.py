from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Request, status

from app.auth_dependencies import require_current_user
from app.auth_security import verify_password
from app.database import update_user_profile
from app.routers.auth import public_user
from app.schemas import AuthResponse, ProfileUpdateRequest

router = APIRouter()


@router.get('/profile', response_model=AuthResponse)
def profile(request: Request) -> AuthResponse:
    return AuthResponse(user=public_user(require_current_user(request)))


@router.patch('/profile', response_model=AuthResponse)
def update_profile(payload: ProfileUpdateRequest, request: Request) -> AuthResponse:
    current = require_current_user(request)
    fields = payload.model_fields_set - {'current_password'}
    if not fields:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='No profile changes supplied')
    if ('username' in fields and payload.username is None) or ('email' in fields and payload.email is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='Usuario y correo no pueden quedar vacíos.')

    username = payload.username if 'username' in fields else str(current['username'])
    email = payload.email if 'email' in fields else str(current['email'])
    display_name = payload.display_name if 'display_name' in fields else current.get('display_name')
    bio = payload.bio if 'bio' in fields else current.get('bio')

    identity_changed = (
        username.casefold() != str(current['username']).casefold()
        or email.casefold() != str(current['email']).casefold()
    )
    if identity_changed:
        password = payload.current_password.get_secret_value() if payload.current_password else ''
        if not password or not verify_password(str(current['password_hash']), password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='La contraseña actual es incorrecta.')

    try:
        updated = update_user_profile(
            int(current['id']),
            username=username,
            email=email,
            display_name=display_name,
            bio=bio,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='No fue posible guardar el perfil. Revisa usuario y correo.',
        ) from exc

    return AuthResponse(user=public_user(updated))

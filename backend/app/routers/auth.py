from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth_security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    password_needs_rehash,
    verify_password_or_dummy,
)
from app.config import settings
from app.database import (
    create_auth_session,
    create_user,
    delete_auth_session,
    get_user_by_identifier,
    get_user_by_session,
    update_user_password_hash,
)
from app.schemas import AuthResponse, LoginRequest, MessageResponse, RegisterRequest, UserResponse

router = APIRouter()


def _public_user(user: dict[str, object]) -> UserResponse:
    return UserResponse(
        id=int(user['id']),
        username=str(user['username']),
        email=str(user['email']),
        avatar_url=str(user['avatar_url']) if user['avatar_url'] else None,
        created_at=str(user['created_at']),
    )


def _issue_session(response: Response, user_id: int) -> None:
    token = generate_session_token()
    ttl_seconds = settings.session_ttl_hours * 60 * 60
    expires_at = int((datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).timestamp())
    create_auth_session(user_id, hash_session_token(token), expires_at)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite='lax',
        path='/api',
    )


def _current_user(request: Request) -> dict[str, object]:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    user = get_user_by_session(
        hash_session_token(token),
        int(datetime.now(timezone.utc).timestamp()),
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    return user


@router.post('/auth/register', response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response) -> AuthResponse:
    password = payload.password.get_secret_value()
    try:
        user = create_user(payload.username, payload.email, hash_password(password))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='No fue posible registrar esa cuenta. Revisa usuario y correo.',
        ) from exc
    _issue_session(response, int(user['id']))
    return AuthResponse(user=_public_user(user))


@router.post('/auth/login', response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    user = get_user_by_identifier(payload.identifier)
    password = payload.password.get_secret_value()
    stored_hash = str(user['password_hash']) if user is not None and bool(user['is_active']) else None
    password_valid = verify_password_or_dummy(stored_hash, password)
    if user is None or not bool(user['is_active']) or not password_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuario/correo o contraseña incorrectos.')

    if password_needs_rehash(str(user['password_hash'])):
        update_user_password_hash(int(user['id']), hash_password(password))

    _issue_session(response, int(user['id']))
    return AuthResponse(user=_public_user(user))


@router.get('/auth/me', response_model=AuthResponse)
def me(request: Request) -> AuthResponse:
    return AuthResponse(user=_public_user(_current_user(request)))


@router.post('/auth/logout', response_model=MessageResponse)
def logout(request: Request, response: Response) -> MessageResponse:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        delete_auth_session(hash_session_token(token))
    response.delete_cookie(
        key=settings.session_cookie_name,
        path='/api',
        secure=settings.cookie_secure,
        httponly=True,
        samesite='lax',
    )
    return MessageResponse(message='Sesión cerrada.')

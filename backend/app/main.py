from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import initialize_database
from app.middleware.security import (
    AuthRateLimitMiddleware,
    CommentRateLimitMiddleware,
    CsrfOriginMiddleware,
    JsonContentTypeMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.routers import auth, banners, catalog, comments, favorites, health, profile

logger = logging.getLogger('anivideos')


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title='AniVideos API',
    version='0.15.0',
    lifespan=lifespan,
    docs_url='/docs' if settings.enable_docs else None,
    redoc_url=None,
    openapi_url='/openapi.json' if settings.enable_docs else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
app.add_middleware(GZipMiddleware, minimum_size=512, compresslevel=6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Accept', 'Content-Type', 'X-CSRF-Token'],
    expose_headers=['X-CSRF-Token', 'X-Request-ID'],
    max_age=600,
)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
app.add_middleware(JsonContentTypeMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(
    AuthRateLimitMiddleware,
    requests=settings.auth_rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(
    CommentRateLimitMiddleware,
    requests=settings.comment_rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(
    CsrfOriginMiddleware,
    cookie_name=settings.session_cookie_name,
    allowed_origins=settings.allowed_origins,
)
app.add_middleware(SecurityHeadersMiddleware, hsts_max_age=settings.hsts_max_age)
# Added last so every downstream response, including middleware rejections, receives a trace id.
app.add_middleware(RequestIdMiddleware)

app.include_router(health.router, prefix='/api', tags=['health'])
app.include_router(catalog.router, prefix='/api', tags=['catalog'])
app.include_router(banners.router, prefix='/api', tags=['banners'])
app.include_router(comments.router, prefix='/api', tags=['comments'])
app.include_router(auth.router, prefix='/api', tags=['auth'])
app.include_router(profile.router, prefix='/api', tags=['profile'])
app.include_router(favorites.router, prefix='/api', tags=['favorites'])


def _request_id(request: Request) -> str:
    return str(getattr(request.state, 'request_id', 'unavailable'))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for error in exc.errors():
        location = [str(part) for part in error.get('loc', ()) if part not in {'body', 'query', 'path'}]
        fields.append({'field': '.'.join(location) or 'request', 'message': str(error.get('msg', 'Invalid value'))})
    return JSONResponse(
        status_code=422,
        content={
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Revisa los datos enviados.',
                'fields': fields,
                'requestId': _request_id(request),
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    safe_detail = str(exc.detail) if isinstance(exc.detail, str) and exc.status_code < 500 else 'Service unavailable'
    code = {
        400: 'BAD_REQUEST',
        401: 'UNAUTHORIZED',
        403: 'FORBIDDEN',
        404: 'NOT_FOUND',
        409: 'CONFLICT',
        413: 'PAYLOAD_TOO_LARGE',
        415: 'UNSUPPORTED_MEDIA_TYPE',
        422: 'VALIDATION_ERROR',
        429: 'RATE_LIMITED',
        503: 'SERVICE_UNAVAILABLE',
    }.get(exc.status_code, 'REQUEST_FAILED')
    return JSONResponse(
        status_code=exc.status_code,
        content={'error': {'code': code, 'message': safe_detail, 'requestId': _request_id(request)}},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.exception('Unhandled request error', extra={'path': request.url.path, 'request_id': request_id})
    return JSONResponse(
        status_code=500,
        content={
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Unexpected server error',
                'requestId': request_id,
            }
        },
    )

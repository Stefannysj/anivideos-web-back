from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import initialize_database
from app.middleware.security import RateLimitMiddleware, RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from app.routers import banners, catalog, health

logger = logging.getLogger('anivideos')


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title='AniVideos API',
    version='0.6.0',
    lifespan=lifespan,
    docs_url='/docs' if settings.enable_docs else None,
    redoc_url=None,
    openapi_url='/openapi.json' if settings.enable_docs else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
    allow_headers=['Accept', 'Authorization', 'Content-Type'],
)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
app.add_middleware(
    RateLimitMiddleware,
    requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router, prefix='/api', tags=['health'])
app.include_router(catalog.router, prefix='/api', tags=['catalog'])
app.include_router(banners.router, prefix='/api', tags=['banners'])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception('Unhandled request error', extra={'path': request.url.path})
    return JSONResponse(
        status_code=500,
        content={'error': {'code': 'INTERNAL_ERROR', 'message': 'Unexpected server error'}},
    )

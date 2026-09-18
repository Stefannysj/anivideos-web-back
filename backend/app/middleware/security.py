from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_length = request.headers.get('content-length')
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError:
                return JSONResponse(status_code=400, content={'error': {'code': 'BAD_REQUEST', 'message': 'Invalid request'}})
            if content_length > self.max_bytes:
                return JSONResponse(status_code=413, content={'error': {'code': 'PAYLOAD_TOO_LARGE', 'message': 'Request body too large'}})
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.requests = requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith('/api/'):
            return await call_next(request)
        response = self._check(request, request.url.path)
        return response or await call_next(request)

    def _check(self, request: Request, key_suffix: str) -> JSONResponse | None:
        client = request.client.host if request.client else 'unknown'
        key = f'{client}:{key_suffix}'
        now = monotonic()
        cutoff = now - self.window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.requests:
            return JSONResponse(
                status_code=429,
                content={'error': {'code': 'RATE_LIMITED', 'message': 'Too many requests'}},
                headers={'Retry-After': str(self.window_seconds)},
            )
        bucket.append(now)
        return None


class AuthRateLimitMiddleware(RateLimitMiddleware):
    _AUTH_PATHS = {'/api/auth/login', '/api/auth/register'}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != 'POST' or request.url.path not in self._AUTH_PATHS:
            return await call_next(request)
        response = self._check(request, request.url.path)
        return response or await call_next(request)


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cookie_name: str, allowed_origins: tuple[str, ...]) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.allowed_origins = frozenset(origin.rstrip('/') for origin in allowed_origins)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        unsafe = request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
        has_session_cookie = self.cookie_name in request.cookies
        if unsafe and has_session_cookie:
            origin = request.headers.get('origin', '').rstrip('/')
            if origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={'error': {'code': 'ORIGIN_REJECTED', 'message': 'Request origin rejected'}},
                )
        return await call_next(request)

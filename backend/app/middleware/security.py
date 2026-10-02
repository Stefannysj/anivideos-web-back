from __future__ import annotations

from collections import defaultdict, deque
import secrets
from time import monotonic

from fastapi import Request
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth_security import CSRF_HEADER_NAME, verify_csrf_token


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate server-owned ids rather than trusting attacker-controlled trace headers.
        request.state.request_id = secrets.token_hex(12)
        response = await call_next(request)
        response.headers['X-Request-ID'] = request.state.request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, hsts_max_age: int) -> None:
        super().__init__(app)
        self.hsts_max_age = hsts_max_age

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['X-DNS-Prefetch-Control'] = 'off'
        # Public endpoints may opt into bounded HTTP caching; private API responses remain no-store by default.
        if 'Cache-Control' not in response.headers:
            response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
        if request.url.scheme == 'https':
            response.headers['Strict-Transport-Security'] = f'max-age={self.hsts_max_age}; includeSubDomains'
        return response


class RequestSizeLimitMiddleware:
    """Rejects oversized bodies even when Content-Length is missing or inaccurate."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        raw_length = headers.get('content-length')
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError:
                await self._reject(scope, receive, send, 400, 'BAD_REQUEST', 'Invalid request')
                return
            if content_length < 0:
                await self._reject(scope, receive, send, 400, 'BAD_REQUEST', 'Invalid request')
                return
            if content_length > self.max_bytes:
                await self._reject(scope, receive, send, 413, 'PAYLOAD_TOO_LARGE', 'Request body too large')
                return

        consumed = 0
        rejected = False

        async def limited_receive() -> Message:
            nonlocal consumed, rejected
            message = await receive()
            if message['type'] == 'http.request':
                consumed += len(message.get('body', b''))
                if consumed > self.max_bytes:
                    rejected = True
                    raise _PayloadTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _PayloadTooLarge:
            if not rejected:
                raise
            await self._reject(scope, receive, send, 413, 'PAYLOAD_TOO_LARGE', 'Request body too large')

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        response = JSONResponse(status_code=status_code, content={'error': {'code': code, 'message': message}})
        await response(scope, receive, send)


class _PayloadTooLarge(Exception):
    pass


class JsonContentTypeMiddleware(BaseHTTPMiddleware):
    """Allows JSON bodies only on API endpoints that parse JSON models."""

    @staticmethod
    def _expects_json(request: Request) -> bool:
        path = request.url.path
        if request.method == 'PATCH' and path == '/api/profile':
            return True
        if request.method == 'POST' and path in {'/api/auth/login', '/api/auth/register'}:
            return True
        return request.method == 'POST' and path.startswith('/api/banners/') and path.endswith('/comments')

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._expects_json(request):
            media_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
            if media_type != 'application/json':
                return JSONResponse(
                    status_code=415,
                    content={'error': {'code': 'UNSUPPORTED_MEDIA_TYPE', 'message': 'Content-Type must be application/json'}},
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.requests = requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_seen: dict[str, float] = {}
        self._max_buckets = 10_000

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == 'OPTIONS' or not request.url.path.startswith('/api/'):
            return await call_next(request)
        response = self._check(request, 'api')
        return response or await call_next(request)

    def _check(self, request: Request, key_suffix: str) -> JSONResponse | None:
        client = request.client.host if request.client else 'unknown'
        key = f'{client}:{key_suffix}'
        now = monotonic()
        cutoff = now - self.window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        self._last_seen[key] = now
        self._prune_stale(cutoff)
        if len(bucket) >= self.requests:
            return JSONResponse(
                status_code=429,
                content={'error': {'code': 'RATE_LIMITED', 'message': 'Too many requests'}},
                headers={'Retry-After': str(self.window_seconds)},
            )
        bucket.append(now)
        return None

    def _prune_stale(self, cutoff: float) -> None:
        if len(self._hits) <= self._max_buckets:
            return
        stale = [key for key, seen in self._last_seen.items() if seen <= cutoff]
        for key in stale:
            self._hits.pop(key, None)
            self._last_seen.pop(key, None)
        if len(self._hits) <= self._max_buckets:
            return
        overflow = len(self._hits) - self._max_buckets
        oldest = sorted(self._last_seen, key=self._last_seen.get)[:overflow]
        for key in oldest:
            self._hits.pop(key, None)
            self._last_seen.pop(key, None)


class AuthRateLimitMiddleware(RateLimitMiddleware):
    _AUTH_PATHS = {'/api/auth/login', '/api/auth/register'}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != 'POST' or request.url.path not in self._AUTH_PATHS:
            return await call_next(request)
        response = self._check(request, request.url.path)
        return response or await call_next(request)


class CommentRateLimitMiddleware(RateLimitMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        is_comment_write = (
            request.method in {'POST', 'DELETE'}
            and path.startswith('/api/banners/')
            and '/comments' in path
        )
        if not is_comment_write:
            return await call_next(request)
        response = self._check(request, 'banner-comments-write')
        return response or await call_next(request)


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    _AUTH_ENTRY_PATHS = {'/api/auth/login', '/api/auth/register'}

    def __init__(self, app: ASGIApp, cookie_name: str, allowed_origins: tuple[str, ...]) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.allowed_origins = frozenset(origin.rstrip('/') for origin in allowed_origins)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return await call_next(request)

        fetch_site = request.headers.get('sec-fetch-site', '').strip().lower()
        if fetch_site == 'cross-site':
            return self._rejected('Cross-site request rejected')

        origin = request.headers.get('origin')
        if origin is not None and origin.rstrip('/') not in self.allowed_origins:
            return self._rejected('Request origin rejected')

        session_token = request.cookies.get(self.cookie_name)
        if session_token and request.url.path not in self._AUTH_ENTRY_PATHS:
            csrf_token = request.headers.get(CSRF_HEADER_NAME, '').strip()
            if not csrf_token or not verify_csrf_token(session_token, csrf_token):
                return self._rejected('CSRF validation failed')

        return await call_next(request)

    @staticmethod
    def _rejected(message: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={'error': {'code': 'REQUEST_REJECTED', 'message': message}},
        )

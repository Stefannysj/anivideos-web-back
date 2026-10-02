from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from fastapi import Request, Response
from pydantic import BaseModel
from starlette.responses import Response as StarletteResponse


def _json_bytes(payload: Any) -> bytes:
    if isinstance(payload, BaseModel):
        serializable = payload.model_dump(mode='json', by_alias=True)
    else:
        serializable = payload
    return json.dumps(
        serializable,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')


def apply_public_cache(
    request: Request,
    response: Response,
    payload: Any,
    *,
    max_age: int,
    stale_while_revalidate: int = 60,
):
    """Adds deterministic ETag/cache headers and short-circuits matching conditional GETs."""
    etag = f'"{sha256(_json_bytes(payload)).hexdigest()}"'
    headers = {
        'Cache-Control': f'public, max-age={max_age}, stale-while-revalidate={stale_while_revalidate}',
        'ETag': etag,
    }
    if request.headers.get('if-none-match', '').strip() == etag:
        return StarletteResponse(status_code=304, headers=headers)
    for name, value in headers.items():
        response.headers[name] = value
    return payload

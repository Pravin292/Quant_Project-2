"""Request guards and observability (F28): size limit, rate limit, structured logs.

The rate limit and cache live in process memory, so on serverless hosting each
instance counts on its own. It is a light guard, not a security boundary.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from dcf.config import load_config

log = logging.getLogger("dcf.api")
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

_MAX_CLIENTS = 2048
_hits: OrderedDict[str, deque[float]] = OrderedDict()


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limited(key: str, limit: int, window: float = 60.0) -> bool:
    now = time.monotonic()
    q = _hits.setdefault(key, deque())
    _hits.move_to_end(key)
    while len(_hits) > _MAX_CLIENTS:
        _hits.popitem(last=False)
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def reset_rate_limit() -> None:
    _hits.clear()


async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    cfg = load_config()["api"]
    started = time.perf_counter()
    request_id = uuid.uuid4().hex[:12]
    response: Response
    too_large = error_response(413, "REQUEST_TOO_LARGE", "The request body is too large.")
    limit = cfg["max_upload_bytes" if request.url.path == "/api/upload" else "max_request_bytes"]
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        response = too_large
    elif request.method != "OPTIONS" and rate_limited(
        client_key(request), cfg["rate_limit_per_minute"]
    ):
        response = error_response(
            429, "RATE_LIMITED", "Too many requests. Wait a minute and try again."
        )
        response.headers["Retry-After"] = "60"
    elif request.method == "POST" and len(await request.body()) > limit:
        response = too_large
    else:
        try:
            response = await call_next(request)
        except Exception:
            log.exception(json.dumps({"request_id": request_id, "event": "unhandled_error"}))
            response = error_response(500, "INTERNAL", "Something went wrong on the server.")
    ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    log.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round(ms, 1),
                "cache": response.headers.get("X-Cache"),
            }
        )
    )
    return response

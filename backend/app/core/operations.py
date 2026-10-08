from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from .cache import redis_client
from .config import settings

logger = logging.getLogger("openresearch.requests")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RATE_SCRIPT = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"


def request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "")
    return supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex


def _limit_for(request: Request) -> tuple[str, int] | None:
    path, method = request.url.path, request.method
    if method == "POST" and path in {"/api/auth/login", "/api/users/login"}:
        return "login", settings.login_rate_limit
    if method == "POST" and path in {"/api/auth/register", "/api/users/register"}:
        return "register", settings.register_rate_limit
    if method == "POST" and re.fullmatch(r"/api/resources/\d+/files", path):
        return "upload", settings.upload_rate_limit
    if method == "GET" and path == "/api/search":
        return "search", settings.search_rate_limit
    if method == "GET" and path == "/api/search/suggestions":
        return "suggestions", settings.search_suggestions_rate_limit
    if method == "POST" and any(segment in path for segment in ("/discussions", "/issues", "/comments")):
        if "/comments" in path:
            return "comment", settings.comment_rate_limit
        if "/issues" in path:
            return "issue", settings.issue_rate_limit
        return "discussion", settings.discussion_rate_limit
    return None


async def operations_middleware(request: Request, call_next):
    rid = request_id(request)
    request.state.request_id = rid
    limit = _limit_for(request)
    if limit:
        bucket, maximum = limit
        address = request.client.host if request.client else "unknown"
        digest = hashlib.sha256(address.encode("utf-8", "replace")).hexdigest()[:24]
        key = f"openresearch:rate:{bucket}:{digest}"
        try:
            count = int(redis_client().eval(_RATE_SCRIPT, 1, key, settings.api_rate_limit_window_seconds))
            if count > maximum:
                response = JSONResponse({"detail": "Too many requests. Try again shortly.", "request_id": rid}, status_code=429, headers={"Retry-After": str(settings.api_rate_limit_window_seconds), "X-Request-ID": rid})
                return response
        except RedisError:
            logger.exception("rate_limit_store_unavailable request_id=%s bucket=%s", rid, bucket)
            if settings.app_env == "production":
                return JSONResponse({"detail": "Request protection is temporarily unavailable.", "request_id": rid}, status_code=503, headers={"X-Request-ID": rid})

    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        logger.info("request_id=%s method=%s path=%s status=%d duration_ms=%.2f", rid, request.method, request.url.path, status_code, (time.perf_counter() - started) * 1000)

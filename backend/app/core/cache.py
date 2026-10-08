from __future__ import annotations

import json

from redis import Redis

from .config import settings


def redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.8)


def redis_status() -> dict[str, str]:
    try:
        client = redis_client()
        client.ping()
        return {"status": "ok", "url": settings.redis_url}
    except Exception as exc:  # Redis is optional for the local SQLite demo.
        return {"status": "unavailable"}


REPOSITORY_CACHE_TTL = 300
SHOWCASE_CACHE_TTL = 300


def repository_cache_key(owner: str, name: str) -> str:
    return f"openresearch:repository:{owner}:{name}"


def repository_cache_get(owner: str, name: str) -> dict | None:
    try:
        value = redis_client().get(repository_cache_key(owner, name))
        return json.loads(value) if value else None
    except Exception:
        return None


def repository_cache_set(owner: str, name: str, value: dict, ttl: int = REPOSITORY_CACHE_TTL) -> None:
    try:
        redis_client().setex(repository_cache_key(owner, name), ttl, json.dumps(value, default=str))
    except Exception:
        return


def repository_cache_delete(owner: str, name: str) -> None:
    try:
        redis_client().delete(repository_cache_key(owner, name))
    except Exception:
        return


def showcase_cache_key(resource_id: int) -> str:
    return f"openresearch:showcase:resource:{resource_id}"


def showcase_media_cache_key(showcase_id: int) -> str:
    return f"openresearch:showcase:media:{showcase_id}"


def showcase_cache_get(resource_id: int) -> dict | None:
    try:
        value = redis_client().get(showcase_cache_key(resource_id))
        return json.loads(value) if value else None
    except Exception:
        return None


def showcase_cache_set(resource_id: int, value: dict, ttl: int = SHOWCASE_CACHE_TTL) -> None:
    try:
        redis_client().setex(showcase_cache_key(resource_id), ttl, json.dumps(value, default=str))
    except Exception:
        return


def showcase_media_cache_get(showcase_id: int) -> list[dict] | None:
    try:
        value = redis_client().get(showcase_media_cache_key(showcase_id))
        return json.loads(value) if value else None
    except Exception:
        return None


def showcase_media_cache_set(showcase_id: int, value: list[dict], ttl: int = SHOWCASE_CACHE_TTL) -> None:
    try:
        redis_client().setex(showcase_media_cache_key(showcase_id), ttl, json.dumps(value, default=str))
    except Exception:
        return


def showcase_cache_delete(resource_id: int, showcase_id: int | None = None) -> None:
    try:
        keys = [showcase_cache_key(resource_id)]
        if showcase_id is not None:
            keys.append(showcase_media_cache_key(showcase_id))
        redis_client().delete(*keys)
    except Exception:
        return

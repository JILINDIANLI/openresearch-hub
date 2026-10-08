from __future__ import annotations

from functools import lru_cache

from minio import Minio

from ..core.config import settings


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    """One shared MinIO client for the application process."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@lru_cache(maxsize=1)
def get_public_minio_client() -> Minio:
    """Client used only when generating browser-facing presigned URLs."""
    return Minio(
        settings.minio_public_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_public_secure,
        # The local MinIO bucket uses its default region. Providing it avoids a
        # network lookup against the browser-facing address from inside Docker.
        region="us-east-1",
    )

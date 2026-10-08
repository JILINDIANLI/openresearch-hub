from __future__ import annotations

from datetime import timedelta
from io import BufferedIOBase
from urllib.parse import quote
import re
import time

from minio.error import S3Error

from ..core.config import settings
from ..storage.minio_client import get_minio_client, get_public_minio_client


class StorageService:
    """The only place that talks to MinIO."""

    @property
    def bucket(self) -> str:
        return settings.minio_bucket

    def ensure_bucket(self) -> None:
        client = get_minio_client()
        last_error: Exception | None = None
        for _ in range(10):
            try:
                if not client.bucket_exists(self.bucket):
                    client.make_bucket(self.bucket)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(1)
        raise RuntimeError("MinIO is unavailable") from last_error

    def upload(self, object_key: str, stream: BufferedIOBase, length: int, content_type: str) -> None:
        self.ensure_bucket()
        get_minio_client().put_object(self.bucket, object_key, stream, length, content_type=content_type)

    def remove(self, object_key: str) -> None:
        get_minio_client().remove_object(self.bucket, object_key)

    def exists(self, object_key: str) -> bool:
        try:
            get_minio_client().stat_object(self.bucket, object_key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise

    def presigned_get_url(self, object_key: str, download_filename: str | None = None) -> str:
        if download_filename:
            original = str(download_filename).replace("\r", "").replace("\n", "")
            fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", original).strip("._") or "download"
            response_headers = {"response-content-disposition": f"attachment; filename=\"{fallback[:200]}\"; filename*=UTF-8''{quote(original[:200])}"}
        else:
            response_headers = None
        return get_public_minio_client().presigned_get_object(
            self.bucket,
            object_key,
            expires=timedelta(minutes=15),
            response_headers=response_headers,
        )


storage_service = StorageService()

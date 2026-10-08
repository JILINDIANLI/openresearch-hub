from __future__ import annotations

import hashlib
import mimetypes
import re
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.config import settings
from ..database.models import Resource, ResourceFile, User
from ..files.schemas import FILE_KINDS
from .storage_service import storage_service


CHUNK_SIZE = 1024 * 1024
PREVIEW_MIME_PREFIXES = ("image/", "video/")
PREVIEW_MIME_TYPES = {"application/pdf"}
ALLOWED_MIME_TYPES = {
    ".pt": {"application/octet-stream", "application/x-pytorch"},
    ".pth": {"application/octet-stream", "application/x-pytorch"},
    ".ckpt": {"application/octet-stream"},
    ".onnx": {"application/octet-stream"},
    ".safetensors": {"application/octet-stream"},
    ".zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
    ".csv": {"text/csv", "application/csv", "application/octet-stream"},
    ".json": {"application/json", "text/json", "application/octet-stream"},
    ".jsonl": {"application/json", "text/plain", "application/octet-stream"},
    ".parquet": {"application/octet-stream", "application/vnd.apache.parquet"},
    ".npy": {"application/octet-stream"},
    ".npz": {"application/octet-stream", "application/zip"},
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".mp4": {"video/mp4"},
    ".webm": {"video/webm"},
    ".mov": {"video/quicktime", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".yaml": {"application/yaml", "text/yaml", "text/plain", "application/octet-stream"},
    ".yml": {"application/yaml", "text/yaml", "text/plain", "application/octet-stream"},
    ".toml": {"application/toml", "text/plain", "application/octet-stream"},
}


class FileTooLargeError(Exception):
    pass


def safe_filename(filename: str) -> tuple[str, str]:
    original = Path(filename or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", original).strip("._")
    if not cleaned:
        cleaned = "upload"
    extension = Path(cleaned).suffix.lower()
    return cleaned[:200], extension


def validate_upload(filename: str, content_type: str | None, file_kind: str) -> tuple[str, str, str]:
    cleaned, extension = safe_filename(filename)
    kind = file_kind.strip().upper()
    if kind not in FILE_KINDS:
        raise HTTPException(status_code=422, detail=f"file_kind 必须是: {', '.join(sorted(FILE_KINDS))}")
    if extension not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="不支持的文件类型")
    mime_type = (content_type or mimetypes.guess_type(cleaned)[0] or "application/octet-stream").lower()
    if mime_type not in ALLOWED_MIME_TYPES[extension]:
        raise HTTPException(status_code=415, detail="文件扩展名与 MIME 类型不匹配")
    return cleaned, extension, mime_type


def validate_file_signature(extension: str, stream) -> None:
    """Check signatures for formats browsers render or commonly spoof."""
    offset = stream.tell()
    try:
        stream.seek(0)
        header = stream.read(32)
    finally:
        stream.seek(offset)
    signatures = {
        ".pdf": lambda value: value.startswith(b"%PDF-"),
        ".png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": lambda value: value.startswith(b"\xff\xd8\xff"),
        ".jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        ".webp": lambda value: value.startswith(b"RIFF") and value[8:12] == b"WEBP",
        ".zip": lambda value: value.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")),
        ".mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        ".mov": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        ".webm": lambda value: value.startswith(b"\x1aE\xdf\xa3"),
    }
    validator = signatures.get(extension)
    if validator and not validator(header):
        raise HTTPException(status_code=415, detail="文件内容与扩展名不匹配")


def file_to_dict(file: ResourceFile) -> dict:
    mime_type = file.mime_type or "application/octet-stream"
    can_preview = mime_type.startswith(PREVIEW_MIME_PREFIXES) or mime_type in PREVIEW_MIME_TYPES
    original_filename = file.original_filename or file.filename
    return {
        "id": file.id,
        "resource_id": file.resource_id,
        "version_id": file.version_id,
        "original_filename": original_filename,
        "file_kind": file.file_kind or (file.file_type or "OTHER").upper(),
        "mime_type": mime_type,
        "file_extension": file.file_extension or Path(original_filename).suffix.lower(),
        "file_size": file.file_size or file.size,
        "sha256": file.sha256 or "",
        "description": file.description,
        "download_count": file.download_count or 0,
        "created_at": file.created_at or file.created_time,
        "updated_at": file.updated_at or file.created_at or file.created_time,
        "uploader": (
            {"id": file.uploader.id, "username": file.uploader.username, "display_name": file.uploader.display_name or file.uploader.username}
            if file.uploader
            else {}
        ),
        "can_preview": can_preview,
        "download_url": f"/api/files/{file.id}/download",
        "preview_url": f"/api/files/{file.id}/preview" if can_preview else None,
    }


class FileService:
    @staticmethod
    def resource_with_files(db: Session, resource_id: int) -> Resource | None:
        return db.scalar(select(Resource).options(selectinload(Resource.files).selectinload(ResourceFile.uploader)).where(Resource.id == resource_id))

    @staticmethod
    def get_file(db: Session, file_id: int) -> ResourceFile | None:
        return db.scalar(select(ResourceFile).options(selectinload(ResourceFile.uploader), selectinload(ResourceFile.resource)).where(ResourceFile.id == file_id))

    @staticmethod
    async def create(
        db: Session,
        resource: Resource,
        uploader: User,
        upload: UploadFile,
        file_kind: str,
        description: str | None,
        version_id: int | None = None,
        version_name: str | None = None,
    ) -> ResourceFile:
        cleaned, extension, mime_type = validate_upload(upload.filename or "", upload.content_type, file_kind)
        digest = hashlib.sha256()
        size = 0
        temporary = tempfile.SpooledTemporaryFile(max_size=CHUNK_SIZE * 4, mode="w+b")
        try:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_size:
                    raise FileTooLargeError()
                digest.update(chunk)
                temporary.write(chunk)
            if size == 0:
                raise HTTPException(status_code=400, detail="不允许上传空文件")
            validate_file_signature(extension, temporary)
            stored_filename = f"{uuid.uuid4().hex}_{cleaned}"
            object_key = (
                f"resources/{resource.id}/versions/{version_name}/{uuid.uuid4().hex}/{stored_filename}"
                if version_id and version_name
                else f"resources/{resource.id}/{uuid.uuid4().hex}/{stored_filename}"
            )
            temporary.seek(0)
            storage_service.upload(object_key, temporary, size, mime_type)
            file = ResourceFile(
                resource_id=resource.id,
                version_id=version_id,
                uploader_id=uploader.id,
                filename=cleaned,
                file_type=file_kind.upper(),
                url="",
                size=size,
                original_filename=Path(upload.filename or cleaned).name[:255],
                stored_filename=stored_filename,
                object_key=object_key,
                bucket_name=settings.minio_bucket,
                mime_type=mime_type,
                file_extension=extension,
                file_size=size,
                file_kind=file_kind.upper(),
                sha256=digest.hexdigest(),
                description=(description or "").strip() or None,
            )
            try:
                db.add(file)
                db.commit()
                db.refresh(file)
            except Exception:
                db.rollback()
                try:
                    storage_service.remove(object_key)
                except Exception:
                    pass
                raise
            return FileService.get_file(db, file.id) or file
        finally:
            temporary.close()
            await upload.close()

    @staticmethod
    def remove(db: Session, resource: Resource, file: ResourceFile) -> None:
        if file.resource_id != resource.id:
            raise HTTPException(status_code=404, detail="文件不存在")
        if file.object_key:
            try:
                storage_service.remove(file.object_key)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="文件存储删除失败，请稍后重试") from exc
        db.delete(file)
        db.commit()

    @staticmethod
    def remove_all_for_resource(db: Session, resource: Resource) -> None:
        files = db.scalars(select(ResourceFile).where(ResourceFile.resource_id == resource.id)).all()
        for file in files:
            if file.object_key:
                try:
                    storage_service.remove(file.object_key)
                except Exception as exc:
                    raise HTTPException(status_code=502, detail="资源文件清理失败，资源未删除") from exc
            db.delete(file)
        db.flush()

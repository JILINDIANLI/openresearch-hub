from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.security import get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Resource, User
from ..files.schemas import FILE_KINDS, FileRead
from ..services.file_service import FileService, FileTooLargeError, file_to_dict
from ..services.storage_service import storage_service
from ..services.visibility import require_viewable_resource
from ..engagement.service import EngagementService


resource_files_router = APIRouter(prefix="/api/resources", tags=["Resource Files"])
files_router = APIRouter(prefix="/api/files", tags=["Resource Files"])


def get_owned_resource(db: Session, resource_id: int, current_user: User) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以管理文件")
    return resource


@resource_files_router.post("/{resource_id}/files", response_model=FileRead, status_code=201)
async def upload_file(
    resource_id: int,
    file: UploadFile = File(...),
    file_kind: str = Form(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = get_owned_resource(db, resource_id, current_user)
    try:
        created = await FileService.create(db, resource, current_user, file, file_kind, description)
        EngagementService.record_activity(db, resource.id, "FILE_UPLOADED", current_user.id, created.original_filename or created.filename)
        return file_to_dict(created)
    except FileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large.") from exc


@resource_files_router.get("/{resource_id}/files", response_model=list[FileRead])
def list_files(resource_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    resource = FileService.resource_with_files(db, resource_id)
    require_viewable_resource(resource, current_user)
    return [file_to_dict(file) for file in sorted((item for item in resource.files if item.version_id is None), key=lambda item: item.created_at or item.created_time, reverse=True)]


@resource_files_router.delete("/{resource_id}/files/{file_id}", status_code=204)
def delete_file(resource_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = get_owned_resource(db, resource_id, current_user)
    file = FileService.get_file(db, file_id)
    if file is None or file.resource_id != resource.id:
        raise HTTPException(status_code=404, detail="文件不存在")
    if file.version_id is not None:
        raise HTTPException(status_code=409, detail="版本文件请在对应版本中管理")
    filename = file.original_filename or file.filename
    FileService.remove(db, resource, file)
    EngagementService.record_activity(db, resource.id, "FILE_DELETED", current_user.id, filename)


@files_router.get("/{file_id}/download")
def download_file(file_id: int, request: Request, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    file = FileService.get_file(db, file_id)
    if file is None or not file.object_key or not storage_service.exists(file.object_key):
        raise HTTPException(status_code=404, detail="文件不存在")
    resource = require_viewable_resource(file.resource, current_user)
    is_owner = current_user is not None and resource.author_id == current_user.id
    file.download_count = max(file.download_count or 0, 0) + 1
    if file.version_id:
        from ..database.models import ResourceVersion
        version = db.get(ResourceVersion, file.version_id)
        if version:
            if version.status == "DRAFT" and not is_owner:
                raise HTTPException(status_code=404, detail="文件不存在")
            version.downloads_count = max(version.downloads_count or 0, 0) + 1
    if file.resource:
        EngagementService.record_download(db, file.resource, file.id, current_user.id if current_user else None)
    db.commit()
    EngagementService.invalidate_trending_cache()
    if file.version_id:
        from ..core.cache import redis_client
        try:
            redis_client().delete(f"resource:versions:{file.resource_id}", f"resource:latest-version:{file.resource_id}")
        except Exception:
            pass
    return RedirectResponse(storage_service.presigned_get_url(file.object_key, file.original_filename or file.filename), status_code=307)


@files_router.get("/{file_id}/preview")
def preview_file(file_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    file = FileService.get_file(db, file_id)
    if file is None or not file.object_key or not storage_service.exists(file.object_key):
        raise HTTPException(status_code=404, detail="文件不存在")
    resource = require_viewable_resource(file.resource, current_user)
    is_owner = current_user is not None and resource.author_id == current_user.id
    if file.version_id:
        from ..database.models import ResourceVersion
        version = db.get(ResourceVersion, file.version_id)
        if version and version.status == "DRAFT" and not is_owner:
            raise HTTPException(status_code=404, detail="文件不存在")
    mime_type = file.mime_type or ""
    if not (mime_type.startswith(("image/", "video/")) or mime_type == "application/pdf"):
        raise HTTPException(status_code=415, detail="此文件类型不支持预览")
    return RedirectResponse(storage_service.presigned_get_url(file.object_key), status_code=307)

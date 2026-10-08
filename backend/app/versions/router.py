from __future__ import annotations

from datetime import datetime
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..core.cache import redis_client
from ..core.security import get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Resource, ResourceFile, ResourceVersion, User
from ..engagement.service import EngagementService
from ..community.service import CommunityService
from ..files.schemas import FileRead
from ..services.file_service import FileService, FileTooLargeError, file_to_dict
from ..services.gitea_service import GiteaError, gitea_service
from ..services.visibility import is_public_resource, require_viewable_resource
from .schemas import VersionCreate, VersionRead, VersionUpdate, normalize_version


router = APIRouter(prefix="/api/resources/{resource_id}/versions", tags=["Resource Versions"])
VALID_STATUSES = {"DRAFT", "PUBLISHED", "ARCHIVED"}
VERSION_CACHE_SECONDS = 300


def resource_or_404(db: Session, resource_id: int) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    return resource


def version_query(resource_id: int, version: str):
    return (
        select(ResourceVersion)
        .options(selectinload(ResourceVersion.creator), selectinload(ResourceVersion.files).selectinload(ResourceFile.uploader))
        .where(ResourceVersion.resource_id == resource_id, ResourceVersion.version == version)
    )


def version_or_404(db: Session, resource_id: int, version: str) -> ResourceVersion:
    try:
        normalized = normalize_version(version)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    item = db.scalar(version_query(resource_id, normalized))
    if item is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    return item


def require_owner(resource: Resource, user: User) -> None:
    if resource.author_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以管理版本")


def require_visible(resource: Resource, version: ResourceVersion, user: User | None) -> None:
    is_owner = user is not None and resource.author_id == user.id
    require_viewable_resource(resource, user)
    if version.status == "DRAFT" and not is_owner:
        raise HTTPException(status_code=404, detail="版本不存在")


def clear_cache(resource_id: int) -> None:
    try:
        client = redis_client()
        client.delete(f"resource:versions:{resource_id}", f"resource:latest-version:{resource_id}")
    except Exception:
        pass


def cached_public_list(resource_id: int) -> list[dict] | None:
    try:
        value = redis_client().get(f"resource:versions:{resource_id}")
        return json.loads(value) if value else None
    except Exception:
        return None


def cache_public_list(resource_id: int, payload: list[dict]) -> None:
    try:
        redis_client().setex(f"resource:versions:{resource_id}", VERSION_CACHE_SECONDS, json.dumps(payload, default=str, ensure_ascii=False))
    except Exception:
        pass


def serialize(version: ResourceVersion, include_files: bool = True) -> dict:
    return {
        "id": version.id,
        "resource_id": version.resource_id,
        "version": version.version,
        "title": version.title,
        "description": version.description,
        "release_notes": version.release_notes,
        "status": version.status,
        "created_by": version.created_by,
        "publisher": (
            {
                "id": version.creator.id,
                "username": version.creator.username,
                "display_name": version.creator.display_name or version.creator.username,
            }
            if version.creator
            else {}
        ),
        "git_commit_sha": version.git_commit_sha,
        "git_branch": version.git_branch,
        "is_latest": version.is_latest,
        "published_at": version.published_at,
        "downloads_count": version.downloads_count or 0,
        "created_at": version.created_at,
        "updated_at": version.updated_at,
        "files": [file_to_dict(file) for file in version.files] if include_files else [],
    }


def validate_git_reference(resource: Resource, branch: str | None, commit: str | None) -> None:
    """Git references are optional, but must be real when a Gitea repository is linked."""
    if resource.repository is None:
        return
    try:
        if branch:
            names = {item["name"] for item in gitea_service.branches(resource.repository.owner, resource.repository.name)}
            if branch not in names:
                raise HTTPException(status_code=422, detail="Git branch 不存在于关联仓库")
        if commit:
            gitea_service.commit(resource.repository.owner, resource.repository.name, commit)
    except GiteaError as exc:
        raise HTTPException(status_code=422, detail="Git commit 不存在或无法验证") from exc


@router.get("/compare", response_model=dict)
def compare_versions(
    resource_id: int,
    from_version: str = Query(alias="from"),
    to: str = Query(),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = resource_or_404(db, resource_id)
    source = version_or_404(db, resource_id, from_version)
    target = version_or_404(db, resource_id, to)
    require_visible(resource, source, current_user)
    require_visible(resource, target, current_user)
    source_names = {item.original_filename or item.filename for item in source.files}
    target_names = {item.original_filename or item.filename for item in target.files}
    return {
        "resource_id": resource_id,
        "from": serialize(source),
        "to": serialize(target),
        "version_changed": source.version != target.version,
        "published_at_changed": source.published_at != target.published_at,
        "commit_changed": source.git_commit_sha != target.git_commit_sha,
        "release_notes_changed": source.release_notes != target.release_notes,
        "files_added": sorted(target_names - source_names),
        "files_removed": sorted(source_names - target_names),
    }


@router.get("/latest", response_model=VersionRead)
def latest_version(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = resource_or_404(db, resource_id)
    if current_user is None and is_public_resource(resource):
        try:
            cached = redis_client().get(f"resource:latest-version:{resource_id}")
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    version = db.scalar(
        select(ResourceVersion)
        .options(selectinload(ResourceVersion.creator), selectinload(ResourceVersion.files).selectinload(ResourceFile.uploader))
        .where(ResourceVersion.resource_id == resource_id, ResourceVersion.is_latest.is_(True), ResourceVersion.status == "PUBLISHED")
    )
    if version is None:
        raise HTTPException(status_code=404, detail="尚未发布版本")
    require_visible(resource, version, current_user)
    payload = serialize(version)
    if current_user is None and is_public_resource(resource):
        try:
            redis_client().setex(f"resource:latest-version:{resource_id}", VERSION_CACHE_SECONDS, json.dumps(payload, default=str, ensure_ascii=False))
        except Exception:
            pass
    return payload


@router.post("", response_model=VersionRead, status_code=201)
def create_version(
    resource_id: int,
    payload: VersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = resource_or_404(db, resource_id)
    require_owner(resource, current_user)
    validate_git_reference(resource, payload.git_branch, payload.git_commit_sha)
    major, minor, patch = (int(value) for value in payload.version.split("."))
    item = ResourceVersion(
        resource_id=resource_id,
        version=payload.version,
        version_major=major,
        version_minor=minor,
        version_patch=patch,
        title=payload.title.strip(),
        description=payload.description.strip(),
        release_notes=payload.release_notes.strip(),
        status="DRAFT",
        created_by=current_user.id,
        git_commit_sha=payload.git_commit_sha.strip() if payload.git_commit_sha else None,
        git_branch=payload.git_branch.strip() if payload.git_branch else None,
    )
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="该版本号已存在") from exc
    EngagementService.record_activity(db, resource_id, "VERSION_CREATED", current_user.id, f"v{item.version}")
    clear_cache(resource_id)
    return serialize(item)


@router.get("", response_model=list[VersionRead])
def list_versions(
    resource_id: int,
    version_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = resource_or_404(db, resource_id)
    is_owner = current_user is not None and current_user.id == resource.author_id
    require_viewable_resource(resource, current_user)
    if version_status and version_status.upper() not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="status 必须是 DRAFT、PUBLISHED 或 ARCHIVED")
    if current_user is None and is_public_resource(resource) and version_status is None:
        cached = cached_public_list(resource_id)
        if cached is not None:
            return cached
    query = (
        select(ResourceVersion)
        .options(selectinload(ResourceVersion.creator), selectinload(ResourceVersion.files).selectinload(ResourceFile.uploader))
        .where(ResourceVersion.resource_id == resource_id)
        .order_by(ResourceVersion.version_major.desc(), ResourceVersion.version_minor.desc(), ResourceVersion.version_patch.desc())
    )
    if version_status:
        query = query.where(ResourceVersion.status == version_status.upper())
    items = db.scalars(query).unique().all()
    if not is_owner:
        items = [item for item in items if item.status != "DRAFT"]
    payload = [serialize(item) for item in items]
    if current_user is None and is_public_resource(resource) and version_status is None:
        cache_public_list(resource_id, payload)
    return payload


@router.get("/{version}", response_model=VersionRead)
def get_version(
    resource_id: int,
    version: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = resource_or_404(db, resource_id)
    item = version_or_404(db, resource_id, version)
    require_visible(resource, item, current_user)
    return serialize(item)


@router.patch("/{version}", response_model=VersionRead)
def update_version(
    resource_id: int,
    version: str,
    payload: VersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = resource_or_404(db, resource_id)
    require_owner(resource, current_user)
    item = version_or_404(db, resource_id, version)
    if item.status != "DRAFT":
        raise HTTPException(status_code=409, detail="已发布或归档版本不能直接修改")
    values = payload.model_dump(exclude_unset=True)
    validate_git_reference(resource, values.get("git_branch", item.git_branch), values.get("git_commit_sha", item.git_commit_sha))
    for field, value in values.items():
        setattr(item, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(item)
    clear_cache(resource_id)
    return serialize(item)


@router.post("/{version}/publish", response_model=VersionRead)
def publish_version(
    resource_id: int,
    version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = resource_or_404(db, resource_id)
    require_owner(resource, current_user)
    item = version_or_404(db, resource_id, version)
    if item.status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="归档版本不能发布")
    validate_git_reference(resource, item.git_branch, item.git_commit_sha)
    if item.status != "PUBLISHED":
        db.execute(
            update(ResourceVersion)
            .where(ResourceVersion.resource_id == resource_id, ResourceVersion.id != item.id, ResourceVersion.is_latest.is_(True))
            .values(is_latest=False)
        )
        item.status = "PUBLISHED"
        item.is_latest = True
        item.published_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        EngagementService.record_activity(db, resource_id, "VERSION_PUBLISHED", current_user.id, f"v{item.version}")
        CommunityService.notify_version_followers(db, resource, current_user, item.version)
        db.commit()
    clear_cache(resource_id)
    return serialize(item)


@router.post("/{version}/archive", response_model=VersionRead)
def archive_version(
    resource_id: int,
    version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = resource_or_404(db, resource_id)
    require_owner(resource, current_user)
    item = version_or_404(db, resource_id, version)
    was_latest = item.is_latest
    item.status = "ARCHIVED"
    item.is_latest = False
    if was_latest:
        replacement = db.scalar(
            select(ResourceVersion)
            .where(ResourceVersion.resource_id == resource_id, ResourceVersion.status == "PUBLISHED", ResourceVersion.id != item.id)
            .order_by(ResourceVersion.version_major.desc(), ResourceVersion.version_minor.desc(), ResourceVersion.version_patch.desc())
        )
        if replacement:
            replacement.is_latest = True
    db.commit()
    db.refresh(item)
    EngagementService.record_activity(db, resource_id, "VERSION_ARCHIVED", current_user.id, f"v{item.version}")
    clear_cache(resource_id)
    return serialize(item)


@router.delete("/{version}", status_code=204)
def delete_version(
    resource_id: int,
    version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = resource_or_404(db, resource_id)
    require_owner(resource, current_user)
    item = version_or_404(db, resource_id, version)
    if item.status != "DRAFT":
        raise HTTPException(status_code=409, detail="已发布或归档版本不能删除")
    for file in list(item.files):
        FileService.remove(db, resource, file)
    db.delete(item)
    db.commit()
    clear_cache(resource_id)


@router.post("/{version}/files", response_model=FileRead, status_code=201)
async def upload_version_file(
    resource_id: int,
    version: str,
    file: UploadFile = File(...),
    file_kind: str = Form(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = resource_or_404(db, resource_id)
    require_owner(resource, current_user)
    item = version_or_404(db, resource_id, version)
    if item.status != "DRAFT":
        raise HTTPException(status_code=409, detail="只能向 Draft 版本上传文件")
    try:
        created = await FileService.create(db, resource, current_user, file, file_kind, description, version_id=item.id, version_name=item.version)
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail="File is too large.") from exc
    EngagementService.record_activity(db, resource_id, "VERSION_FILE_UPLOADED", current_user.id, created.original_filename or created.filename)
    clear_cache(resource_id)
    return file_to_dict(created)


@router.get("/{version}/files", response_model=list[FileRead])
def list_version_files(
    resource_id: int,
    version: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = resource_or_404(db, resource_id)
    item = version_or_404(db, resource_id, version)
    require_visible(resource, item, current_user)
    return [file_to_dict(file) for file in item.files]

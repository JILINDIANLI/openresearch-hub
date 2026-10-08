from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.cache import (
    showcase_cache_delete,
    showcase_cache_get,
    showcase_cache_set,
    showcase_media_cache_get,
    showcase_media_cache_set,
)
from ..core.security import get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Resource, ResourceShowcase, ShowcaseMedia, ShowcaseResult, User
from ..engagement.service import EngagementService
from ..services.file_service import FileService, FileTooLargeError
from ..services.visibility import is_public_resource, require_viewable_resource
from .schemas import MEDIA_TYPES, MediaRead, ResultCreate, ResultRead, ShowcaseCreate, ShowcaseRead, ShowcaseUpdate


resource_router = APIRouter(prefix="/api/resources", tags=["Research Showcase"])
router = APIRouter(prefix="/api/showcases", tags=["Research Showcase"])
result_router = APIRouter(prefix="/api/showcase", tags=["Research Showcase"])


def _showcase_query():
    return select(ResourceShowcase).options(
        selectinload(ResourceShowcase.resource).selectinload(Resource.author),
        selectinload(ResourceShowcase.media).selectinload(ShowcaseMedia.file),
        selectinload(ResourceShowcase.results),
    )


def _require_resource(db: Session, resource_id: int) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    return resource


def _assert_can_view(resource: Resource, current_user: User | None) -> None:
    require_viewable_resource(resource, current_user)


def _assert_owner(resource: Resource, current_user: User) -> None:
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以管理科研展示")


def _media_type(mime_type: str | None) -> str:
    normalized = (mime_type or "").lower()
    if normalized.startswith("image/"):
        return "IMAGE"
    if normalized.startswith("video/"):
        return "VIDEO"
    if normalized == "application/pdf":
        return "PDF"
    return "OTHER"


def _serialize_media(media: ShowcaseMedia) -> dict:
    file = media.file
    original_name = file.original_filename or file.filename
    return MediaRead(
        id=media.id,
        showcase_id=media.showcase_id,
        file_id=media.file_id,
        media_type=media.media_type,
        title=media.title,
        description=media.description,
        order_index=media.order_index,
        created_at=media.created_at,
        filename=original_name,
        mime_type=file.mime_type or "application/octet-stream",
        file_size=file.file_size or file.size,
        preview_url=f"/api/files/{file.id}/preview",
        download_url=f"/api/files/{file.id}/download",
    ).model_dump(mode="json")


def serialize_showcase(showcase: ResourceShowcase) -> dict:
    return ShowcaseRead(
        id=showcase.id,
        resource_id=showcase.resource_id,
        title=showcase.title,
        short_description=showcase.short_description,
        abstract=showcase.abstract,
        research_background=showcase.research_background,
        methodology=showcase.methodology,
        contributions=showcase.contributions,
        experiments=showcase.experiments,
        results_summary=showcase.results_summary,
        citation_text=showcase.citation_text,
        bibtex=showcase.bibtex,
        created_by=showcase.created_by,
        is_featured=showcase.is_featured,
        is_hidden=showcase.is_hidden,
        created_at=showcase.created_at,
        updated_at=showcase.updated_at,
        resource=(
            {
                "id": showcase.resource.id,
                "title": showcase.resource.title,
                "resource_type": showcase.resource.resource_type,
                "description": showcase.resource.description,
                "thumbnail_url": showcase.resource.thumbnail_url,
                "research_field": showcase.resource.research_field,
                "stars": showcase.resource.stars,
                "downloads": showcase.resource.downloads,
                "views": showcase.resource.views,
                "author_name": (
                    showcase.resource.author.display_name or showcase.resource.author.username
                    if showcase.resource.author
                    else "OpenResearch"
                ),
                "author": (
                    {
                        "id": showcase.resource.author.id,
                        "username": showcase.resource.author.username,
                        "display_name": showcase.resource.author.display_name or showcase.resource.author.username,
                        "avatar_url": showcase.resource.author.avatar_url or showcase.resource.author.avatar,
                    }
                    if showcase.resource.author
                    else {}
                ),
            }
            if showcase.resource
            else {}
        ),
        media=[_serialize_media(media) for media in showcase.media],
        results=[ResultRead.model_validate(result).model_dump(mode="json") for result in showcase.results],
    ).model_dump(mode="json")


def _load_showcase(db: Session, resource_id: int, current_user: User | None = None) -> ResourceShowcase:
    showcase = db.execute(_showcase_query().where(ResourceShowcase.resource_id == resource_id)).unique().scalar_one_or_none()
    if showcase is None:
        raise HTTPException(status_code=404, detail="该资源尚未创建科研展示")
    return showcase


def _assert_showcase_visible(showcase: ResourceShowcase, current_user: User | None) -> None:
    _assert_can_view(showcase.resource, current_user)
    if showcase.is_hidden and (current_user is None or showcase.resource.author_id != current_user.id):
        raise HTTPException(status_code=404, detail="科研展示不存在")


def _invalidate(showcase: ResourceShowcase) -> None:
    showcase_cache_delete(showcase.resource_id, showcase.id)


@resource_router.post("/{resource_id}/showcase", response_model=ShowcaseRead, status_code=status.HTTP_201_CREATED)
def create_showcase(
    resource_id: int,
    payload: ShowcaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = _require_resource(db, resource_id)
    _assert_owner(resource, current_user)
    if db.scalar(select(ResourceShowcase.id).where(ResourceShowcase.resource_id == resource_id)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该资源已有科研展示")
    showcase = ResourceShowcase(resource_id=resource_id, created_by=current_user.id, **payload.model_dump())
    db.add(showcase)
    db.commit()
    showcase = _load_showcase(db, resource_id)
    _invalidate(showcase)
    EngagementService.record_activity(db, resource.id, "SHOWCASE_CREATED", current_user.id, showcase.title)
    return serialize_showcase(showcase)


@resource_router.get("/{resource_id}/showcase", response_model=ShowcaseRead)
def get_showcase(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = _require_resource(db, resource_id)
    _assert_can_view(resource, current_user)
    showcase = _load_showcase(db, resource_id)
    _assert_showcase_visible(showcase, current_user)
    cached = showcase_cache_get(resource_id)
    if cached is not None:
        return cached
    result = serialize_showcase(showcase)
    if is_public_resource(resource) and not showcase.is_hidden:
        showcase_cache_set(resource_id, result)
    return result


@resource_router.patch("/{resource_id}/showcase", response_model=ShowcaseRead)
def update_showcase(
    resource_id: int,
    payload: ShowcaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = _require_resource(db, resource_id)
    _assert_owner(resource, current_user)
    showcase = _load_showcase(db, resource_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(showcase, field, value)
    db.commit()
    showcase = _load_showcase(db, resource_id)
    _invalidate(showcase)
    EngagementService.record_activity(db, resource.id, "SHOWCASE_UPDATED", current_user.id, showcase.title)
    return serialize_showcase(showcase)


@resource_router.delete("/{resource_id}/showcase", status_code=status.HTTP_204_NO_CONTENT)
def delete_showcase(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = _require_resource(db, resource_id)
    _assert_owner(resource, current_user)
    showcase = _load_showcase(db, resource_id)
    title = showcase.title
    # Showcase media owns its ResourceFile record. Deleting the object first prevents
    # a database record from outliving the underlying MinIO object.
    for media in list(showcase.media):
        FileService.remove(db, resource, media.file)
    showcase = _load_showcase(db, resource_id)
    db.delete(showcase)
    db.commit()
    showcase_cache_delete(resource_id, showcase.id)
    EngagementService.record_activity(db, resource.id, "SHOWCASE_DELETED", current_user.id, title)


@router.post("/{showcase_id}/media", response_model=MediaRead, status_code=status.HTTP_201_CREATED)
async def upload_showcase_media(
    showcase_id: int,
    file: UploadFile = File(...),
    title: str = Form(default=""),
    description: str = Form(default=""),
    order_index: int = Form(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    showcase = db.execute(_showcase_query().where(ResourceShowcase.id == showcase_id)).unique().scalar_one_or_none()
    if showcase is None:
        raise HTTPException(status_code=404, detail="科研展示不存在")
    resource = showcase.resource
    _assert_owner(resource, current_user)
    guessed_type = _media_type(file.content_type)
    if guessed_type not in {"IMAGE", "VIDEO", "PDF"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="科研展示只支持图片、视频或 PDF 文件")
    file_kind = {"IMAGE": "IMAGE", "VIDEO": "VIDEO", "PDF": "PAPER"}[guessed_type]
    try:
        uploaded = await FileService.create(db, resource, current_user, file, file_kind, description or None)
    except FileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件超过允许的上传大小") from exc
    media = ShowcaseMedia(
        showcase_id=showcase.id,
        file_id=uploaded.id,
        media_type=guessed_type,
        title=(title or Path(uploaded.original_filename or uploaded.filename).stem).strip()[:255],
        description=(description or "").strip(),
        order_index=order_index,
    )
    try:
        db.add(media)
        db.commit()
        db.refresh(media)
    except Exception:
        db.rollback()
        FileService.remove(db, resource, uploaded)
        raise
    media = db.execute(
        select(ShowcaseMedia).options(selectinload(ShowcaseMedia.file)).where(ShowcaseMedia.id == media.id)
    ).scalar_one()
    _invalidate(showcase)
    EngagementService.record_activity(db, resource.id, "SHOWCASE_MEDIA_UPLOADED", current_user.id, media.title)
    return _serialize_media(media)


@router.get("/{showcase_id}/media", response_model=list[MediaRead])
def list_showcase_media(
    showcase_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    showcase = db.execute(_showcase_query().where(ResourceShowcase.id == showcase_id)).unique().scalar_one_or_none()
    if showcase is None:
        raise HTTPException(status_code=404, detail="科研展示不存在")
    _assert_showcase_visible(showcase, current_user)
    cached = showcase_media_cache_get(showcase_id)
    if cached is not None:
        return cached
    media = [_serialize_media(item) for item in showcase.media]
    if is_public_resource(showcase.resource) and not showcase.is_hidden:
        showcase_media_cache_set(showcase_id, media)
    return media


@router.get("/featured", response_model=list[ShowcaseRead], summary="Featured public research showcases")
def list_featured_showcases(
    limit: int = 6,
    db: Session = Depends(get_db),
):
    """Curated public research stories for the homepage."""
    limit = min(max(limit, 1), 24)
    items = db.execute(
        _showcase_query()
        .join(ResourceShowcase.resource)
        .where(
            ResourceShowcase.is_featured.is_(True),
            ResourceShowcase.is_hidden.is_(False),
            Resource.visibility == "public",
            Resource.review_status == "PUBLISHED",
            Resource.is_hidden.is_(False),
        )
        .order_by(ResourceShowcase.updated_at.desc(), ResourceShowcase.id.desc())
        .limit(limit)
    ).unique().scalars().all()
    return [serialize_showcase(item) for item in items]


@router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_showcase_media(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = db.execute(
        select(ShowcaseMedia)
        .options(selectinload(ShowcaseMedia.file), selectinload(ShowcaseMedia.showcase).selectinload(ResourceShowcase.resource))
        .where(ShowcaseMedia.id == media_id)
    ).scalar_one_or_none()
    if media is None:
        raise HTTPException(status_code=404, detail="展示媒体不存在")
    showcase = media.showcase
    resource = showcase.resource
    _assert_owner(resource, current_user)
    title = media.title
    FileService.remove(db, resource, media.file)
    _invalidate(showcase)
    EngagementService.record_activity(db, resource.id, "SHOWCASE_MEDIA_DELETED", current_user.id, title)


@router.post("/{showcase_id}/results", response_model=ResultRead, status_code=status.HTTP_201_CREATED)
def create_showcase_result(
    showcase_id: int,
    payload: ResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    showcase = db.execute(_showcase_query().where(ResourceShowcase.id == showcase_id)).unique().scalar_one_or_none()
    if showcase is None:
        raise HTTPException(status_code=404, detail="科研展示不存在")
    _assert_owner(showcase.resource, current_user)
    result = ShowcaseResult(showcase_id=showcase.id, **payload.model_dump())
    db.add(result)
    db.commit()
    db.refresh(result)
    _invalidate(showcase)
    EngagementService.record_activity(db, showcase.resource_id, "SHOWCASE_RESULT_CREATED", current_user.id, result.title)
    return ResultRead.model_validate(result).model_dump(mode="json")


@router.get("/{showcase_id}/results", response_model=list[ResultRead])
def list_showcase_results(
    showcase_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    showcase = db.execute(_showcase_query().where(ResourceShowcase.id == showcase_id)).unique().scalar_one_or_none()
    if showcase is None:
        raise HTTPException(status_code=404, detail="科研展示不存在")
    _assert_can_view(showcase.resource, current_user)
    if showcase.is_hidden and (current_user is None or showcase.resource.author_id != current_user.id):
        raise HTTPException(status_code=404, detail="科研展示不存在")
    return [ResultRead.model_validate(result).model_dump(mode="json") for result in showcase.results]


@result_router.delete("/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_showcase_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.execute(
        select(ShowcaseResult)
        .options(selectinload(ShowcaseResult.showcase).selectinload(ResourceShowcase.resource))
        .where(ShowcaseResult.id == result_id)
    ).scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="展示结果不存在")
    showcase = result.showcase
    _assert_owner(showcase.resource, current_user)
    title = result.title
    db.delete(result)
    db.commit()
    _invalidate(showcase)
    EngagementService.record_activity(db, showcase.resource_id, "SHOWCASE_RESULT_DELETED", current_user.id, title)

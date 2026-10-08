from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database.database import get_db
from ..database.models import Resource, ResourceVersion, User
from ..core.security import get_current_user, get_optional_user
from ..engagement.service import EngagementService
from ..services.resource_service import ResourceService
from ..services.file_service import FileService
from ..services.visibility import public_resource_conditions, require_viewable_resource
from .schemas import ResourceCreate, ResourceRead, ResourceUpdate

router = APIRouter(prefix="/api/resources", tags=["Resources"])


def serialize_resource(resource: Resource, starred_ids: set[int] | None = None, favorited_ids: set[int] | None = None) -> dict:
    details: dict = {}
    if resource.details_json:
        try:
            details = json.loads(resource.details_json)
        except json.JSONDecodeError:
            details = {}
    for key, detail in (
        ("project", resource.project),
        ("paper", resource.paper),
        ("dataset", resource.dataset),
        ("model", resource.model),
        ("algorithm", resource.algorithm),
        ("demo", resource.demo),
        ("tutorial", resource.tutorial),
    ):
        if detail is not None:
            details[key] = {column.name: getattr(detail, column.name) for column in detail.__table__.columns if column.name not in {"id", "resource_id"}}
            if key == "dataset":
                details[key]["download_url"] = details[key].get("download_url") or details[key].get("dataset_url")
    latest_version = next((item for item in resource.versions if item.status == "PUBLISHED" and item.is_latest), None)
    return ResourceRead(
        id=resource.id,
        title=resource.title,
        resource_type=resource.resource_type,
        type=resource.resource_type.upper(),
        description=resource.description,
        author_id=resource.author_id,
        author_name=resource.author.username if resource.author else "",
        author=(
            {
                "id": resource.author.id,
                "username": resource.author.username,
                "display_name": resource.author.display_name or resource.author.username,
                "avatar_url": resource.author.avatar_url or resource.author.avatar,
                "organization": resource.author.organization,
            }
            if resource.author
            else {}
        ),
        created_time=resource.created_time,
        updated_time=resource.updated_time,
        created_at=resource.created_time,
        updated_at=resource.updated_time,
        views=resource.views,
        stars=resource.stars,
        downloads=resource.downloads,
        stars_count=max(resource.stars or 0, 0),
        favorites_count=max(resource.favorites_count or 0, 0),
        views_count=max(resource.views or 0, 0),
        downloads_count=max(resource.downloads or 0, 0),
        is_starred=resource.id in (starred_ids or set()),
        is_favorited=resource.id in (favorited_ids or set()),
        license=resource.license,
        visibility=resource.visibility,
        research_field=resource.research_field,
        thumbnail_url=resource.thumbnail_url,
        repository_url=resource.repository_url,
        homepage_url=resource.homepage_url,
        latest_version=latest_version.version if latest_version else None,
        latest_version_published_at=latest_version.published_at if latest_version else None,
        has_showcase=resource.showcase is not None,
        tags=resource.tags,
        details=details,
    ).model_dump()


def resource_query():
    return select(Resource).options(
        selectinload(Resource.author),
        selectinload(Resource.tags),
        selectinload(Resource.project),
        selectinload(Resource.paper),
        selectinload(Resource.dataset),
        selectinload(Resource.model),
        selectinload(Resource.algorithm),
        selectinload(Resource.demo),
        selectinload(Resource.tutorial),
        selectinload(Resource.repository),
        selectinload(Resource.showcase),
        selectinload(Resource.versions),
    )


@router.get("", response_model=list[ResourceRead])
def list_resources(
    resource_type: str | None = Query(default=None, alias="type"),
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    query = resource_query().where(*public_resource_conditions())
    if resource_type:
        query = query.where(Resource.resource_type == resource_type.lower())
    if q:
        needle = f"%{q.strip()}%"
        query = query.join(Resource.author).where(or_(Resource.title.ilike(needle), Resource.description.ilike(needle), User.username.ilike(needle)))
    resources = db.scalars(query.order_by(Resource.updated_time.desc()).limit(limit)).unique().all()
    starred, favorited = EngagementService.interaction_ids(db, current_user.id if current_user else None, [item.id for item in resources])
    return [serialize_resource(item, starred, favorited) for item in resources]


@router.get("/stats", tags=["Resources"])
def resource_stats(db: Session = Depends(get_db)) -> dict:
    public_filter = public_resource_conditions()
    total = db.scalar(select(func.count(Resource.id)).where(*public_filter)) or 0
    counts = {
        item: db.scalar(select(func.count(Resource.id)).where(Resource.resource_type == item, *public_filter)) or 0
        for item in ("model", "dataset", "algorithm", "project", "paper", "demo", "tutorial")
    }
    authors = db.scalar(
        select(func.count(func.distinct(Resource.author_id))).where(*public_filter, Resource.author_id.is_not(None))
    ) or 0
    return {"total": total, "by_type": counts, "authors": authors}


@router.get("/popular", response_model=list[ResourceRead])
def popular_resources(
    sort: str = Query(default="stars", pattern="^(stars|downloads|views)$"),
    resource_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    normalized_type = resource_type.lower() if resource_type else None
    if normalized_type and normalized_type not in {"model", "dataset", "algorithm", "project", "paper", "demo", "tutorial"}:
        raise HTTPException(status_code=422, detail="不支持的资源类型")
    column = {"stars": Resource.stars, "downloads": Resource.downloads, "views": Resource.views}[sort]
    query = resource_query().where(*public_resource_conditions())
    if normalized_type:
        query = query.where(Resource.resource_type == normalized_type)
    resources = db.scalars(query.order_by(column.desc(), Resource.updated_time.desc()).limit(limit)).unique().all()
    starred, favorited = EngagementService.interaction_ids(db, current_user.id if current_user else None, [item.id for item in resources])
    return [serialize_resource(item, starred, favorited) for item in resources]


@router.get("/featured", response_model=list[ResourceRead], summary="Featured public resources")
def featured_resources(
    limit: int = Query(default=8, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resources = db.scalars(
        resource_query().where(
            Resource.is_featured.is_(True), *public_resource_conditions()
        ).order_by(Resource.updated_time.desc(), Resource.id.desc()).limit(limit)
    ).unique().all()
    starred, favorited = EngagementService.interaction_ids(db, current_user.id if current_user else None, [item.id for item in resources])
    return [serialize_resource(item, starred, favorited) for item in resources]


@router.get("/{resource_id}/related", response_model=list[ResourceRead], summary="Related public resources")
def related_resources(
    resource_id: int,
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    source = db.execute(resource_query().where(Resource.id == resource_id)).unique().scalar_one_or_none()
    require_viewable_resource(source, current_user)
    source_tag_ids = {tag.id for tag in source.tags}
    candidates = db.scalars(
        resource_query().where(Resource.id != source.id, *public_resource_conditions()).limit(250)
    ).unique().all()

    def relevance(item: Resource) -> tuple[int, int, int, int]:
        shared_tags = len(source_tag_ids.intersection({tag.id for tag in item.tags}))
        same_field = bool(source.research_field and item.research_field and source.research_field.lower() == item.research_field.lower())
        same_type = item.resource_type == source.resource_type
        return (shared_tags * 4 + int(same_field) * 3 + int(same_type), item.stars or 0, item.downloads or 0, item.views or 0)

    candidates.sort(key=relevance, reverse=True)
    candidates = candidates[:limit]
    ids = [item.id for item in candidates]
    starred, favorited = EngagementService.interaction_ids(db, current_user.id if current_user else None, ids)
    return [serialize_resource(item, starred, favorited) for item in candidates]


@router.get("/{resource_id}", response_model=ResourceRead)
def get_resource(
    resource_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    resource = db.execute(resource_query().where(Resource.id == resource_id)).unique().scalar_one_or_none()
    require_viewable_resource(resource, current_user)
    session_id = request.cookies.get("openresearch_view_session") or secrets.token_urlsafe(24)
    if not request.cookies.get("openresearch_view_session"):
        response.set_cookie("openresearch_view_session", session_id, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    EngagementService.record_view(db, resource, current_user.id if current_user else None, session_id)
    starred, favorited = EngagementService.interaction_ids(db, current_user.id if current_user else None, [resource.id])
    return serialize_resource(resource, starred, favorited)


@router.post("", response_model=ResourceRead, status_code=201)
def create_resource(payload: ResourceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        resource = ResourceService.create(db, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    EngagementService.record_activity(db, resource.id, "RESOURCE_CREATED", current_user.id)
    resource = db.execute(resource_query().where(Resource.id == resource.id)).unique().scalar_one()
    return serialize_resource(resource)


@router.put("/{resource_id}", response_model=ResourceRead)
def update_resource(resource_id: int, payload: ResourceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = db.execute(resource_query().where(Resource.id == resource_id)).unique().scalar_one_or_none()
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以修改资源")
    values = payload.model_dump(exclude_unset=True)
    tags = values.pop("tags", None)
    details = values.pop("details", None)
    if details is not None:
        resource.details_json = json.dumps(details, ensure_ascii=False)
        ResourceService.update_extension(resource, details)
    for field, value in values.items():
        setattr(resource, field, value)
    if tags is not None:
        resource.tags = ResourceService.tags(db, tags)
    db.commit()
    return serialize_resource(resource)


@router.delete("/{resource_id}", status_code=204)
def delete_resource(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    if resource.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以删除资源")
    FileService.remove_all_for_resource(db, resource)
    db.delete(resource)
    db.commit()

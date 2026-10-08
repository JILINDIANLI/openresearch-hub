from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.security import get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Resource, ResourceActivity, ResourceFavorite, ResourceStar, User
from ..resources.router import resource_query, serialize_resource
from ..resources.schemas import ResourceRead
from ..community.service import CommunityService
from ..services.visibility import public_resource_conditions, require_viewable_resource
from .schemas import ActivityRead, EngagementState, StarSummary, TrendingResourceRead
from .service import EngagementService


router = APIRouter(prefix="/api", tags=["Engagement"])


def require_resource(db: Session, resource_id: int, current_user: User | None = None) -> Resource:
    return require_viewable_resource(db.get(Resource, resource_id), current_user)


def state_response(db: Session, resource: Resource, user_id: int | None) -> EngagementState:
    return EngagementState(**EngagementService.state(db, resource, user_id))


@router.post("/resources/{resource_id}/star", response_model=EngagementState)
def star_resource(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_resource(db, resource_id, current_user)
    resource, created = EngagementService.star(db, resource_id, current_user.id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    if created:
        EngagementService.record_activity(db, resource.id, "STARRED", current_user.id)
        CommunityService.notify_resource_owner(
            db,
            resource,
            current_user,
            "RESOURCE_STARRED",
            "Your resource was starred",
            f"{current_user.display_name or current_user.username} starred {resource.title}.",
            "RESOURCE",
            resource.id,
        )
        db.commit()
    return state_response(db, resource, current_user.id)


@router.delete("/resources/{resource_id}/star", response_model=EngagementState)
def unstar_resource(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_resource(db, resource_id, current_user)
    resource, _ = EngagementService.unstar(db, resource_id, current_user.id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    return state_response(db, resource, current_user.id)


@router.get("/resources/{resource_id}/stars", response_model=StarSummary)
def resource_stars(resource_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    resource = require_resource(db, resource_id, current_user)
    starred, _ = EngagementService.interaction_ids(db, current_user.id if current_user else None, [resource.id])
    return StarSummary(resource_id=resource.id, stars_count=max(resource.stars or 0, 0), is_starred=resource.id in starred)


@router.post("/resources/{resource_id}/favorite", response_model=EngagementState)
def favorite_resource(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_resource(db, resource_id, current_user)
    resource, _ = EngagementService.favorite(db, resource_id, current_user.id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    return state_response(db, resource, current_user.id)


@router.delete("/resources/{resource_id}/favorite", response_model=EngagementState)
def unfavorite_resource(resource_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_resource(db, resource_id, current_user)
    resource, _ = EngagementService.unfavorite(db, resource_id, current_user.id)
    if resource is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    return state_response(db, resource, current_user.id)


def saved_resources(db: Session, user_id: int, model, limit: int) -> list[dict]:
    rows = db.scalars(
        resource_query()
        .join(model, model.resource_id == Resource.id)
        .where(
            model.user_id == user_id,
            *public_resource_conditions(),
        )
        .order_by(model.created_at.desc())
        .limit(limit)
    ).unique().all()
    ids = [item.id for item in rows]
    starred, favorited = EngagementService.interaction_ids(db, user_id, ids)
    return [serialize_resource(item, starred, favorited) for item in rows]


@router.get("/me/stars", response_model=list[ResourceRead])
def my_stars(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return saved_resources(db, current_user.id, ResourceStar, limit)


@router.get("/me/favorites", response_model=list[ResourceRead])
def my_favorites(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return saved_resources(db, current_user.id, ResourceFavorite, limit)


@router.get("/trending", response_model=list[TrendingResourceRead])
def trending(
    period: str = Query(default="week", pattern="^(day|week|month)$"),
    resource_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    normalized_type = resource_type.lower() if resource_type else None
    if normalized_type and normalized_type not in {"model", "dataset", "algorithm", "project", "paper", "demo", "tutorial"}:
        raise HTTPException(status_code=422, detail="不支持的资源类型")
    cache_key = f"trending:{period}:{normalized_type or 'all'}:{limit}"
    if current_user is None:
        cached = EngagementService.cached_trending(cache_key)
        if cached is not None:
            return cached
    days = {"day": 1, "week": 7, "month": 30}[period]
    query = resource_query().where(
        Resource.visibility == "public",
        Resource.review_status == "PUBLISHED",
        Resource.is_hidden.is_(False),
    )
    if normalized_type:
        query = query.where(Resource.resource_type == normalized_type)
    resources = db.scalars(query).unique().all()
    cutoff = datetime.utcnow() - timedelta(days=days)
    ids = [item.id for item in resources]
    recent_stars, recent_downloads, recent_views = EngagementService.recent_counts(db, cutoff, ids)
    starred, favorited = EngagementService.interaction_ids(db, current_user.id if current_user else None, ids)
    payload = []
    for resource in resources:
        resource_id = resource.id
        score = recent_stars.get(resource_id, 0) * 5 + recent_downloads.get(resource_id, 0) * 3 + recent_views.get(resource_id, 0) * 0.2
        item = serialize_resource(resource, starred, favorited)
        item.update({"score": score, "recent_stars": recent_stars.get(resource_id, 0), "recent_downloads": recent_downloads.get(resource_id, 0), "recent_views": recent_views.get(resource_id, 0)})
        payload.append(item)
    payload.sort(key=lambda item: (item["score"], item["stars_count"], item["downloads_count"], item["updated_time"]), reverse=True)
    payload = payload[:limit]
    if current_user is None:
        EngagementService.cache_trending(cache_key, payload)
    return payload


@router.get("/resources/{resource_id}/activity", response_model=list[ActivityRead])
def resource_activity(
    resource_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    require_resource(db, resource_id, current_user)
    records = db.scalars(
        select(ResourceActivity).options(selectinload(ResourceActivity.actor)).where(ResourceActivity.resource_id == resource_id).order_by(ResourceActivity.created_at.desc()).limit(limit)
    ).all()
    return [
        ActivityRead(
            id=item.id,
            resource_id=item.resource_id,
            activity_type=item.activity_type,
            detail=item.detail,
            created_at=item.created_at,
            actor=(
                {"id": item.actor.id, "username": item.actor.username, "display_name": item.actor.display_name or item.actor.username}
                if item.actor
                else {}
            ),
        )
        for item in records
    ]

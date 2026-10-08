from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.cache import redis_client
from ..database.models import (
    Resource,
    ResourceActivity,
    ResourceDownload,
    ResourceFavorite,
    ResourceStar,
    ResourceView,
)


VIEW_DEDUPE_SECONDS = 30 * 60
TRENDING_CACHE_SECONDS = 120


class EngagementService:
    @staticmethod
    def interaction_ids(db: Session, user_id: int | None, resource_ids: list[int]) -> tuple[set[int], set[int]]:
        if not user_id or not resource_ids:
            return set(), set()
        starred = set(db.scalars(select(ResourceStar.resource_id).where(ResourceStar.user_id == user_id, ResourceStar.resource_id.in_(resource_ids))).all())
        favorited = set(db.scalars(select(ResourceFavorite.resource_id).where(ResourceFavorite.user_id == user_id, ResourceFavorite.resource_id.in_(resource_ids))).all())
        return starred, favorited

    @staticmethod
    def state(db: Session, resource: Resource, user_id: int | None) -> dict:
        starred, favorited = EngagementService.interaction_ids(db, user_id, [resource.id])
        return {
            "resource_id": resource.id,
            "stars_count": max(resource.stars or 0, 0),
            "favorites_count": max(resource.favorites_count or 0, 0),
            "is_starred": resource.id in starred,
            "is_favorited": resource.id in favorited,
        }

    @staticmethod
    def _locked_resource(db: Session, resource_id: int) -> Resource | None:
        return db.scalar(select(Resource).where(Resource.id == resource_id).with_for_update())

    @staticmethod
    def star(db: Session, resource_id: int, user_id: int) -> tuple[Resource | None, bool]:
        resource = EngagementService._locked_resource(db, resource_id)
        if resource is None:
            return None, False
        existing = db.scalar(select(ResourceStar.id).where(ResourceStar.resource_id == resource_id, ResourceStar.user_id == user_id))
        if existing is not None:
            return resource, False
        try:
            db.add(ResourceStar(resource_id=resource_id, user_id=user_id))
            resource.stars = max(resource.stars or 0, 0) + 1
            db.commit()
        except IntegrityError:
            db.rollback()
            resource = db.get(Resource, resource_id)
            return resource, False
        EngagementService.invalidate_trending_cache()
        return resource, True

    @staticmethod
    def unstar(db: Session, resource_id: int, user_id: int) -> tuple[Resource | None, bool]:
        resource = EngagementService._locked_resource(db, resource_id)
        if resource is None:
            return None, False
        record = db.scalar(select(ResourceStar).where(ResourceStar.resource_id == resource_id, ResourceStar.user_id == user_id))
        if record is None:
            return resource, False
        db.delete(record)
        resource.stars = max(resource.stars or 0, 0)
        resource.stars = max(resource.stars - 1, 0)
        db.commit()
        EngagementService.invalidate_trending_cache()
        return resource, True

    @staticmethod
    def favorite(db: Session, resource_id: int, user_id: int) -> tuple[Resource | None, bool]:
        resource = EngagementService._locked_resource(db, resource_id)
        if resource is None:
            return None, False
        existing = db.scalar(select(ResourceFavorite.id).where(ResourceFavorite.resource_id == resource_id, ResourceFavorite.user_id == user_id))
        if existing is not None:
            return resource, False
        try:
            db.add(ResourceFavorite(resource_id=resource_id, user_id=user_id))
            resource.favorites_count = max(resource.favorites_count or 0, 0) + 1
            db.commit()
        except IntegrityError:
            db.rollback()
            resource = db.get(Resource, resource_id)
            return resource, False
        return resource, True

    @staticmethod
    def unfavorite(db: Session, resource_id: int, user_id: int) -> tuple[Resource | None, bool]:
        resource = EngagementService._locked_resource(db, resource_id)
        if resource is None:
            return None, False
        record = db.scalar(select(ResourceFavorite).where(ResourceFavorite.resource_id == resource_id, ResourceFavorite.user_id == user_id))
        if record is None:
            return resource, False
        db.delete(record)
        resource.favorites_count = max((resource.favorites_count or 0) - 1, 0)
        db.commit()
        return resource, True

    @staticmethod
    def record_view(db: Session, resource: Resource, user_id: int | None, session_id: str) -> bool:
        identity = f"user:{user_id}" if user_id else f"session:{session_id}"
        key = f"resource:view:{resource.id}:{identity}"
        accepted: bool | None = None
        try:
            accepted = bool(redis_client().set(key, "1", nx=True, ex=VIEW_DEDUPE_SECONDS))
        except Exception:
            accepted = None
        if accepted is None:
            since = datetime.utcnow() - timedelta(seconds=VIEW_DEDUPE_SECONDS)
            query = select(ResourceView.id).where(ResourceView.resource_id == resource.id, ResourceView.created_at >= since)
            query = query.where(ResourceView.user_id == user_id) if user_id else query.where(ResourceView.session_id == session_id)
            if db.scalar(query) is not None:
                return False
        elif not accepted:
            return False
        db.add(ResourceView(resource_id=resource.id, user_id=user_id, session_id=None if user_id else session_id))
        db.execute(update(Resource).where(Resource.id == resource.id).values(views=Resource.views + 1))
        db.commit()
        db.refresh(resource)
        EngagementService.invalidate_trending_cache()
        return True

    @staticmethod
    def record_download(db: Session, resource: Resource, file_id: int, user_id: int | None) -> None:
        db.add(ResourceDownload(resource_id=resource.id, file_id=file_id, user_id=user_id))
        resource.downloads = max(resource.downloads or 0, 0) + 1

    @staticmethod
    def record_activity(db: Session, resource_id: int, activity_type: str, actor_id: int | None = None, detail: str | None = None) -> None:
        db.add(ResourceActivity(resource_id=resource_id, actor_id=actor_id, activity_type=activity_type, detail=detail))
        db.commit()

    @staticmethod
    def recent_counts(db: Session, since: datetime, resource_ids: list[int]) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
        if not resource_ids:
            return {}, {}, {}

        def grouped(model):
            rows = db.execute(select(model.resource_id, func.count(model.id)).where(model.resource_id.in_(resource_ids), model.created_at >= since).group_by(model.resource_id)).all()
            return {resource_id: int(count) for resource_id, count in rows}

        return grouped(ResourceStar), grouped(ResourceDownload), grouped(ResourceView)

    @staticmethod
    def cached_trending(key: str) -> list[dict] | None:
        try:
            value = redis_client().get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    @staticmethod
    def cache_trending(key: str, payload: list[dict]) -> None:
        try:
            redis_client().setex(key, TRENDING_CACHE_SECONDS, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            pass

    @staticmethod
    def invalidate_trending_cache() -> None:
        try:
            client = redis_client()
            keys = list(client.scan_iter(match="trending:*"))
            if keys:
                client.delete(*keys)
        except Exception:
            pass

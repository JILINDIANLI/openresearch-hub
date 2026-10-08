from __future__ import annotations

import json
import logging
from time import perf_counter
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core.cache import redis_client
from ..core.config import settings
from ..database.models import (
    AdminLog,
    Discussion,
    DiscussionComment,
    Issue,
    IssueComment,
    Notification,
    Resource,
    ResourceDownload,
    ResourceFile,
    ResourceShowcase,
    ResourceStar,
    ResourceView,
    User,
)
from ..services.file_service import FileService, file_to_dict
from ..services.storage_service import storage_service

logger = logging.getLogger(__name__)


def log_action(db: Session, admin: User, action: str, target_type: str, target_id: int | None = None, detail: str = "") -> AdminLog:
    item = AdminLog(admin_id=admin.id, action=action, target_type=target_type, target_id=target_id, detail=detail)
    db.add(item)
    db.flush()
    return item


def count(db: Session, model, *conditions) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def sum_value(db: Session, model, column) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(column), 0)).select_from(model)) or 0)


def service_status(db: Session) -> dict:
    result = {}
    def probe(name, callback):
        started = perf_counter()
        try:
            callback()
            result[name] = {"status": "Running", "response_ms": round((perf_counter() - started) * 1000, 2)}
        except Exception:
            result[name] = {"status": "Error", "response_ms": round((perf_counter() - started) * 1000, 2)}
    probe("PostgreSQL", lambda: db.execute(select(1)))
    probe("Redis", lambda: redis_client().ping())
    from ..storage.minio_client import get_minio_client
    probe("MinIO", lambda: get_minio_client().bucket_exists(settings.minio_bucket))
    request = Request(settings.gitea_internal_url + "/api/healthz", method="GET")
    def check_gitea():
        with urlopen(request, timeout=settings.gitea_timeout) as response:
            if response.status >= 400:
                raise RuntimeError("unhealthy")
    probe("Gitea", check_gitea)
    result["Backend"] = {"status": "Running", "response_ms": 0}
    result["Nginx"] = {"status": "External probe required", "response_ms": None}
    return result


def dashboard(db: Session) -> dict:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    resources = {str(item[0]).upper(): int(item[1]) for item in db.execute(select(Resource.resource_type, func.count(Resource.id)).group_by(Resource.resource_type)).all()}
    total_files = count(db, ResourceFile)
    return {
        "users": {"total": count(db, User), "active": count(db, User, User.is_active.is_(True)), "new_today": count(db, User, User.created_time >= today)},
        "resources": {"total": count(db, Resource), "by_type": resources, "published": count(db, Resource, Resource.review_status == "PUBLISHED"), "pending": count(db, Resource, Resource.review_status == "PENDING")},
        "files": {"total": total_files, "storage_usage": sum_value(db, ResourceFile, ResourceFile.file_size), "downloads": sum_value(db, ResourceFile, ResourceFile.download_count)},
        "community": {"discussions": count(db, Discussion), "issues": count(db, Issue), "comments": count(db, DiscussionComment) + count(db, IssueComment), "stars": sum_value(db, Resource, Resource.stars)},
        "system": service_status(db),
    }


def serialize_user(db: Session, user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name or user.username, "email": user.email, "role": (user.role or "USER").upper(), "is_active": user.is_active, "organization": user.organization, "created_at": user.created_at or user.created_time, "resource_count": count(db, Resource, Resource.author_id == user.id)}


def serialize_resource(resource: Resource) -> dict:
    return {"id": resource.id, "title": resource.title, "resource_type": resource.resource_type, "author": (resource.author.display_name or resource.author.username) if resource.author else "Unknown", "author_id": resource.author_id, "created_time": resource.created_time, "updated_time": resource.updated_time, "views": resource.views, "stars": resource.stars, "downloads": resource.downloads, "review_status": resource.review_status, "review_note": resource.review_note, "visibility": resource.visibility, "is_featured": resource.is_featured, "is_hidden": resource.is_hidden}


def serialize_showcase(item: ResourceShowcase) -> dict:
    return {"id": item.id, "resource_id": item.resource_id, "title": item.title, "author": (item.resource.author.display_name or item.resource.author.username) if item.resource and item.resource.author else "Unknown", "resource_type": item.resource.resource_type if item.resource else "", "updated_at": item.updated_at, "is_featured": item.is_featured, "is_hidden": item.is_hidden}


def serialize_log(item: AdminLog) -> dict:
    return {"id": item.id, "admin_id": item.admin_id, "admin_name": item.admin.display_name or item.admin.username if item.admin else "Unknown", "action": item.action, "target_type": item.target_type, "target_id": item.target_id, "detail": item.detail, "created_time": item.created_time}


def daily_series(db: Session, model, column, days: int = 14) -> list[dict]:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    items = db.scalars(select(column).where(column >= start)).all()
    buckets = defaultdict(int)
    for value in items:
        if value:
            buckets[value.date().isoformat()] += 1
    return [{"date": (start + timedelta(days=index)).date().isoformat(), "value": buckets[(start + timedelta(days=index)).date().isoformat()]} for index in range(days)]


def statistics(db: Session) -> dict:
    top = db.execute(select(Resource.id, Resource.title, Resource.views, Resource.downloads, Resource.stars).order_by(Resource.views.desc(), Resource.downloads.desc()).limit(10)).all()
    return {"period_days": 14, "users": daily_series(db, User, User.created_time), "resources": daily_series(db, Resource, Resource.created_time), "downloads": daily_series(db, ResourceDownload, ResourceDownload.created_at), "views": daily_series(db, ResourceView, ResourceView.created_at), "popular_resources": [{"id": row[0], "title": row[1], "views": row[2], "downloads": row[3], "stars": row[4]} for row in top]}


def remove_file(db: Session, file: ResourceFile) -> None:
    resource = db.get(Resource, file.resource_id)
    if resource is not None:
        FileService.remove(db, resource, file)
    else:
        if file.object_key:
            storage_service.remove(file.object_key)
        db.delete(file)

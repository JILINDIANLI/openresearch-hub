from __future__ import annotations

import hmac
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Request
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ..core.cache import showcase_cache_delete
from ..core.security import require_admin
from ..database.database import get_db
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
    SearchQuery,
    User,
    UserFollow,
)
from ..community.service import CommunityService
from ..engagement.service import EngagementService
from ..services.file_service import FileService, file_to_dict
from .schemas import ActiveUpdate, FeaturedUpdate, ResourceStatusUpdate, RoleUpdate, VisibilityUpdate
from .service import (
    dashboard,
    daily_series,
    log_action,
    serialize_log,
    serialize_resource,
    serialize_showcase,
    serialize_user,
    statistics,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Center"])


def invalidate_resource_caches(db: Session, resource: Resource) -> None:
    """Clear every public cache affected by a moderation decision."""
    showcase = db.scalar(select(ResourceShowcase).where(ResourceShowcase.resource_id == resource.id))
    if showcase is not None:
        showcase_cache_delete(resource.id, showcase.id)
    EngagementService.invalidate_trending_cache()
    try:
        from ..core.cache import redis_client
        redis_client().delete("openresearch:statistics:public:v1")
    except Exception:
        pass



def require_delete_confirmation(request: Request, target_type: str, target_id: int) -> None:
    expected = f"DELETE:{target_type}:{target_id}"
    supplied = request.headers.get("x-delete-confirmation", "")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=428, detail=f"Confirm deletion with X-Delete-Confirmation: {expected}")


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return dashboard(db)


@router.get("/users")
def list_users(search: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = select(User)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.username.ilike(pattern), User.email.ilike(pattern), User.display_name.ilike(pattern)))
    total = int(db.scalar(select(func.count(User.id)).where(*query._where_criteria)) or 0)
    items = db.scalars(query.order_by(User.created_time.desc(), User.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_user(db, user) for user in items], "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    return serialize_user(db, user)


@router.patch("/users/{user_id}/role")
def update_role(user_id: int, payload: RoleUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id and payload.role != "ADMIN":
        raise HTTPException(409, "不能取消当前管理员自己的管理员权限")
    user.role = payload.role
    log_action(db, admin, "USER_ROLE_CHANGED", "USER", user.id, f"{user.username} -> {payload.role}")
    db.commit()
    return serialize_user(db, user)


@router.patch("/users/{user_id}/status")
def update_user_status(user_id: int, payload: ActiveUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(409, "不能停用当前管理员账号")
    user.is_active = payload.is_active
    log_action(db, admin, "USER_STATUS_CHANGED", "USER", user.id, f"is_active={payload.is_active}")
    db.commit()
    return serialize_user(db, user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_delete_confirmation(request, "USER", user_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(409, "不能删除当前登录管理员")
    if (user.role or "USER").upper() == "ADMIN":
        raise HTTPException(409, "请先取消该用户的管理员角色，再执行删除")
    # Preserve public content by transferring ownership to the acting admin.
    db.execute(update(Resource).where(Resource.author_id == user.id).values(author_id=admin.id))
    db.execute(update(ResourceShowcase).where(ResourceShowcase.created_by == user.id).values(created_by=admin.id))
    from ..database.models import ResourceVersion
    db.execute(update(ResourceVersion).where(ResourceVersion.created_by == user.id).values(created_by=admin.id))
    db.execute(update(Discussion).where(Discussion.author_id == user.id).values(author_id=admin.id))
    db.execute(update(DiscussionComment).where(DiscussionComment.author_id == user.id).values(author_id=admin.id))
    db.execute(update(Issue).where(Issue.author_id == user.id).values(author_id=admin.id))
    db.execute(update(IssueComment).where(IssueComment.author_id == user.id).values(author_id=admin.id))
    db.execute(update(ResourceFile).where(ResourceFile.uploader_id == user.id).values(uploader_id=None))
    db.execute(update(ResourceView).where(ResourceView.user_id == user.id).values(user_id=None))
    db.execute(update(ResourceDownload).where(ResourceDownload.user_id == user.id).values(user_id=None))
    db.execute(update(SearchQuery).where(SearchQuery.user_id == user.id).values(user_id=None))
    db.execute(update(Notification).where(Notification.actor_id == user.id).values(actor_id=None))
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(ResourceStar).where(ResourceStar.user_id == user.id))
    db.execute(delete(UserFollow).where(or_(UserFollow.follower_id == user.id, UserFollow.following_id == user.id)))
    log_action(db, admin, "USER_DELETED", "USER", user.id, user.username)
    db.delete(user)
    db.commit()


@router.get("/resources")
def list_resources(search: str | None = None, resource_type: str | None = Query(None, alias="type"), review_status: str | None = Query(None, alias="status"), page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = select(Resource).options(selectinload(Resource.author))
    filters = []
    if search:
        filters.append(Resource.title.ilike(f"%{search.strip()}%"))
    if resource_type:
        filters.append(Resource.resource_type == resource_type.lower())
    if review_status:
        filters.append(Resource.review_status == review_status.upper())
    query = query.where(*filters)
    total = int(db.scalar(select(func.count(Resource.id)).where(*filters)) or 0)
    items = db.scalars(query.order_by(Resource.updated_time.desc(), Resource.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_resource(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.patch("/resources/{resource_id}/status")
def update_resource_status(resource_id: int, payload: ResourceStatusUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(404, "资源不存在")
    resource.review_status = payload.status
    resource.review_note = (payload.reason or "").strip()
    if payload.status == "PUBLISHED":
        resource.visibility = "public"
        resource.is_hidden = False
    elif payload.status in {"REJECTED", "DRAFT"}:
        resource.is_hidden = True
    invalidate_resource_caches(db, resource)
    log_action(db, admin, f"RESOURCE_{payload.status}", "RESOURCE", resource.id, resource.review_note)
    db.commit()
    return serialize_resource(resource)


@router.patch("/resources/{resource_id}/featured")
def feature_resource(resource_id: int, payload: FeaturedUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(404, "资源不存在")
    resource.is_featured = payload.featured
    showcase = db.scalar(select(ResourceShowcase).where(ResourceShowcase.resource_id == resource.id))
    if showcase is not None:
        showcase.is_featured = payload.featured
    invalidate_resource_caches(db, resource)
    log_action(db, admin, "RESOURCE_FEATURED" if payload.featured else "RESOURCE_UNFEATURED", "RESOURCE", resource.id)
    db.commit()
    return serialize_resource(resource)


@router.patch("/resources/{resource_id}/visibility")
def hide_resource(resource_id: int, payload: VisibilityUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(404, "资源不存在")
    resource.is_hidden = payload.hidden
    invalidate_resource_caches(db, resource)
    log_action(db, admin, "RESOURCE_HIDDEN" if payload.hidden else "RESOURCE_SHOWN", "RESOURCE", resource.id)
    db.commit()
    return serialize_resource(resource)


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_delete_confirmation(request, "RESOURCE", resource_id)
    resource = db.scalar(select(Resource).options(selectinload(Resource.files)).where(Resource.id == resource_id))
    if resource is None:
        raise HTTPException(404, "资源不存在")
    invalidate_resource_caches(db, resource)
    FileService.remove_all_for_resource(db, resource)
    log_action(db, admin, "RESOURCE_DELETED", "RESOURCE", resource.id, resource.title)
    db.delete(resource)
    db.commit()


@router.get("/showcases")
def list_showcases(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = select(ResourceShowcase).options(selectinload(ResourceShowcase.resource).selectinload(Resource.author))
    total = count = int(db.scalar(select(func.count(ResourceShowcase.id))) or 0)
    items = db.scalars(query.order_by(ResourceShowcase.updated_at.desc(), ResourceShowcase.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_showcase(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.patch("/showcases/{showcase_id}/featured")
def feature_showcase(showcase_id: int, payload: FeaturedUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    item = db.get(ResourceShowcase, showcase_id)
    if item is None:
        raise HTTPException(404, "Showcase 不存在")
    item.is_featured = payload.featured
    log_action(db, admin, "SHOWCASE_FEATURED" if payload.featured else "SHOWCASE_UNFEATURED", "SHOWCASE", item.id)
    db.commit()
    return serialize_showcase(item)


@router.patch("/showcases/{showcase_id}/visibility")
def hide_showcase(showcase_id: int, payload: VisibilityUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    item = db.get(ResourceShowcase, showcase_id)
    if item is None:
        raise HTTPException(404, "Showcase 不存在")
    item.is_hidden = payload.hidden
    showcase_cache_delete(item.resource_id, item.id)
    log_action(db, admin, "SHOWCASE_HIDDEN" if payload.hidden else "SHOWCASE_SHOWN", "SHOWCASE", item.id)
    db.commit()
    return serialize_showcase(item)


@router.delete("/showcases/{showcase_id}", status_code=204)
def delete_showcase(showcase_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_delete_confirmation(request, "SHOWCASE", showcase_id)
    item = db.scalar(select(ResourceShowcase).options(selectinload(ResourceShowcase.media)).where(ResourceShowcase.id == showcase_id))
    if item is None:
        raise HTTPException(404, "Showcase 不存在")
    for media in list(item.media):
        if media.file and media.file.object_key:
            from ..services.storage_service import storage_service
            storage_service.remove(media.file.object_key)
        if media.file:
            db.delete(media.file)
    showcase_cache_delete(item.resource_id, item.id)
    log_action(db, admin, "SHOWCASE_DELETED", "SHOWCASE", item.id, item.title)
    db.delete(item)
    db.commit()


@router.get("/files")
def list_files(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), search: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = select(ResourceFile).options(selectinload(ResourceFile.uploader), selectinload(ResourceFile.resource))
    if search:
        query = query.where(ResourceFile.original_filename.ilike(f"%{search.strip()}%"))
    total = int(db.scalar(select(func.count(ResourceFile.id)).where(*query._where_criteria)) or 0)
    items = db.scalars(query.order_by(ResourceFile.created_at.desc(), ResourceFile.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    payload = []
    for item in items:
        row = file_to_dict(item)
        row["resource_title"] = item.resource.title if item.resource else ""
        payload.append(row)
    return {"items": payload, "total": total, "storage_usage": int(db.scalar(select(func.coalesce(func.sum(ResourceFile.file_size), 0))) or 0), "page": page, "page_size": page_size}


@router.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_delete_confirmation(request, "FILE", file_id)
    item = db.scalar(select(ResourceFile).options(selectinload(ResourceFile.resource)).where(ResourceFile.id == file_id))
    if item is None:
        raise HTTPException(404, "文件不存在")
    filename = item.original_filename or item.filename
    resource = item.resource
    if item.object_key:
        from ..services.storage_service import storage_service
        storage_service.remove(item.object_key)
    db.delete(item)
    log_action(db, admin, "FILE_DELETED", "FILE", item.id, filename)
    db.commit()


@router.get("/community")
def list_community(kind: str = Query("all", pattern="^(all|discussions|issues|comments)$"), page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    payload = {}
    if kind in {"all", "discussions"}:
        items = db.scalars(select(Discussion).options(selectinload(Discussion.author), selectinload(Discussion.resource)).order_by(Discussion.created_at.desc()).limit(page_size)).all()
        payload["discussions"] = [{"id": x.id, "title": x.title, "content": x.content, "author": x.author.display_name if x.author else "", "resource": x.resource.title if x.resource else "", "is_hidden": x.is_hidden, "created_at": x.created_at} for x in items]
    if kind in {"all", "issues"}:
        items = db.scalars(select(Issue).options(selectinload(Issue.author), selectinload(Issue.resource)).order_by(Issue.created_at.desc()).limit(page_size)).all()
        payload["issues"] = [{"id": x.id, "title": x.title, "description": x.description, "status": x.status, "author": x.author.display_name if x.author else "", "resource": x.resource.title if x.resource else "", "is_hidden": x.is_hidden, "created_at": x.created_at} for x in items]
    if kind in {"all", "comments"}:
        discussions = db.scalars(select(DiscussionComment).options(selectinload(DiscussionComment.author)).order_by(DiscussionComment.created_at.desc()).limit(page_size)).all()
        issues = db.scalars(select(IssueComment).options(selectinload(IssueComment.author)).order_by(IssueComment.created_at.desc()).limit(page_size)).all()
        payload["comments"] = [{"id": x.id, "kind": "discussion_comment", "content": x.content, "author": x.author.display_name if x.author else "", "is_deleted": x.is_deleted, "is_hidden": x.is_hidden, "created_at": x.created_at} for x in discussions] + [{"id": x.id, "kind": "issue_comment", "content": x.content, "author": x.author.display_name if x.author else "", "is_deleted": x.is_deleted, "is_hidden": x.is_hidden, "created_at": x.created_at} for x in issues]
    return payload


@router.patch("/community/{kind}/{item_id}/visibility")
def hide_community(kind: str, item_id: int, payload: VisibilityUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    model = {"discussion": Discussion, "issue": Issue}.get(kind)
    if model is not None:
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(404, "内容不存在")
        item.is_hidden = payload.hidden
    elif kind in {"discussion_comment", "issue_comment"}:
        model = DiscussionComment if kind == "discussion_comment" else IssueComment
        item = db.get(model, item_id)
        if item is None:
            raise HTTPException(404, "评论不存在")
        item.is_hidden = payload.hidden
    else:
        raise HTTPException(422, "不支持的社区内容类型")
    if kind == "discussion":
        CommunityService.invalidate_community_list("discussions", item.resource_id)
    elif kind == "issue":
        CommunityService.invalidate_community_list("issues", item.resource_id)
    elif kind == "discussion_comment":
        discussion = db.get(Discussion, item.discussion_id)
        if discussion is not None:
            CommunityService.invalidate_community_list("discussions", discussion.resource_id)
    elif kind == "issue_comment":
        issue = db.get(Issue, item.issue_id)
        if issue is not None:
            CommunityService.invalidate_community_list("issues", issue.resource_id)
    log_action(db, admin, "COMMUNITY_HIDDEN" if payload.hidden else "COMMUNITY_SHOWN", kind.upper(), item_id)
    db.commit()
    return {"ok": True, "hidden": payload.hidden}


@router.delete("/community/{kind}/{item_id}", status_code=204)
def delete_community(kind: str, item_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    require_delete_confirmation(request, kind.upper(), item_id)
    model = {"discussion": Discussion, "issue": Issue}.get(kind)
    if model is not None:
        item = db.get(model, item_id)
    elif kind == "discussion_comment":
        item = db.get(DiscussionComment, item_id)
    elif kind == "issue_comment":
        item = db.get(IssueComment, item_id)
    else:
        raise HTTPException(422, "不支持的社区内容类型")
    if item is None:
        raise HTTPException(404, "内容不存在")
    if hasattr(item, "is_deleted"):
        if not item.is_deleted:
            item.is_deleted = True
            item.content = ""
            if kind == "discussion_comment":
                parent = db.get(Discussion, item.discussion_id)
                if parent is not None:
                    parent.comments_count = max((parent.comments_count or 0) - 1, 0)
                    CommunityService.invalidate_community_list("discussions", parent.resource_id)
            else:
                parent = db.get(Issue, item.issue_id)
                if parent is not None:
                    parent.comments_count = max((parent.comments_count or 0) - 1, 0)
                    CommunityService.invalidate_community_list("issues", parent.resource_id)
    else:
        db.delete(item)
    log_action(db, admin, "COMMUNITY_DELETED", kind.upper(), item_id)
    db.commit()


@router.get("/logs")
def list_logs(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = select(AdminLog).options(selectinload(AdminLog.admin)).order_by(AdminLog.created_time.desc(), AdminLog.id.desc())
    total = int(db.scalar(select(func.count(AdminLog.id))) or 0)
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_log(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.get("/statistics")
def get_statistics(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return statistics(db)

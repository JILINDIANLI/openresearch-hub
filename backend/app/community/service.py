from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.cache import redis_client
from ..core.config import settings
from ..services.visibility import require_viewable_resource
from ..database.models import (
    Discussion,
    DiscussionComment,
    Issue,
    IssueComment,
    Notification,
    Resource,
    ResourceActivity,
    User,
    UserFollow,
)


class CommunityService:
    @staticmethod
    def require_visible_resource(db: Session, resource_id: int, user: User | None = None) -> Resource:
        return require_viewable_resource(db.get(Resource, resource_id), user)

    @staticmethod
    def require_resource_owner(resource: Resource, user: User) -> None:
        if resource.author_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有资源作者可以执行此操作")

    @staticmethod
    def user_summary(user: User | None) -> dict | None:
        if user is None:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "avatar_url": user.avatar_url or user.avatar,
            "organization": user.organization,
        }

    @staticmethod
    def resource_summary(resource: Resource) -> dict:
        return {"id": resource.id, "title": resource.title, "resource_type": resource.resource_type, "author_id": resource.author_id}

    @staticmethod
    def discussion_summary(item: Discussion) -> dict:
        return {
            "id": item.id,
            "resource_id": item.resource_id,
            "title": item.title,
            "status": item.status,
            "is_pinned": item.is_pinned,
            "is_locked": item.is_locked,
            "comments_count": item.comments_count or 0,
            "author": CommunityService.user_summary(item.author),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    @staticmethod
    def discussion_comment_tree(items: list[DiscussionComment]) -> list[dict]:
        serialized = {
            item.id: {
                "id": item.id,
                "discussion_id": item.discussion_id,
                "parent_id": item.parent_id,
                "content": "[unavailable]" if item.is_deleted or item.is_hidden else item.content,
                "is_deleted": item.is_deleted,
                "is_hidden": item.is_hidden,
                "author": CommunityService.user_summary(item.author),
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "replies": [],
            }
            for item in items
        }
        roots: list[dict] = []
        for item in items:
            value = serialized[item.id]
            if item.parent_id and item.parent_id in serialized:
                serialized[item.parent_id]["replies"].append(value)
            else:
                roots.append(value)
        return roots

    @staticmethod
    def discussion_detail(item: Discussion) -> dict:
        payload = CommunityService.discussion_summary(item)
        payload.update(
            {
                "content": item.content,
                "resource": CommunityService.resource_summary(item.resource),
                "comments": CommunityService.discussion_comment_tree(item.comments),
            }
        )
        return payload

    @staticmethod
    def issue_summary(item: Issue) -> dict:
        return {
            "id": item.id,
            "resource_id": item.resource_id,
            "title": item.title,
            "issue_type": item.issue_type,
            "status": item.status,
            "priority": item.priority,
            "comments_count": item.comments_count or 0,
            "author": CommunityService.user_summary(item.author),
            "assignee": CommunityService.user_summary(item.assignee),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "closed_at": item.closed_at,
        }

    @staticmethod
    def issue_comment_tree(items: list[IssueComment]) -> list[dict]:
        serialized = {
            item.id: {
                "id": item.id,
                "issue_id": item.issue_id,
                "parent_id": item.parent_id,
                "content": "[unavailable]" if item.is_deleted or item.is_hidden else item.content,
                "is_deleted": item.is_deleted,
                "is_hidden": item.is_hidden,
                "author": CommunityService.user_summary(item.author),
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "replies": [],
            }
            for item in items
        }
        roots: list[dict] = []
        for item in items:
            value = serialized[item.id]
            if item.parent_id and item.parent_id in serialized:
                serialized[item.parent_id]["replies"].append(value)
            else:
                roots.append(value)
        return roots

    @staticmethod
    def issue_detail(item: Issue) -> dict:
        payload = CommunityService.issue_summary(item)
        payload.update(
            {
                "description": item.description,
                "resource": CommunityService.resource_summary(item.resource),
                "comments": CommunityService.issue_comment_tree(item.comments),
            }
        )
        return payload

    @staticmethod
    def activity(db: Session, resource_id: int, activity_type: str, actor_id: int | None = None, detail: str | None = None) -> None:
        db.add(ResourceActivity(resource_id=resource_id, activity_type=activity_type, actor_id=actor_id, detail=detail))

    @staticmethod
    def _notification_cache_key(user_id: int) -> str:
        return f"community:notifications:unread:{user_id}"

    @staticmethod
    def invalidate_unread_count(user_id: int) -> None:
        try:
            redis_client().delete(CommunityService._notification_cache_key(user_id))
        except Exception:
            pass

    @staticmethod
    def unread_count(db: Session, user_id: int) -> int:
        key = CommunityService._notification_cache_key(user_id)
        try:
            cached = redis_client().get(key)
            if cached is not None:
                return int(cached)
        except Exception:
            pass
        value = int(db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read.is_(False))) or 0)
        try:
            redis_client().setex(key, settings.community_cache_ttl, str(value))
        except Exception:
            pass
        return value

    @staticmethod
    def create_notification(
        db: Session,
        recipient_id: int,
        actor_id: int | None,
        notification_type: str,
        title: str,
        message: str,
        target_type: str,
        target_id: int | None,
    ) -> None:
        if actor_id is not None and recipient_id == actor_id:
            return
        db.add(
            Notification(
                user_id=recipient_id,
                actor_id=actor_id,
                type=notification_type,
                title=title[:255],
                message=message,
                target_type=target_type,
                target_id=target_id,
            )
        )
        CommunityService.invalidate_unread_count(recipient_id)

    @staticmethod
    def notify_resource_owner(db: Session, resource: Resource, actor: User, notification_type: str, title: str, message: str, target_type: str, target_id: int) -> None:
        if resource.author_id:
            CommunityService.create_notification(db, resource.author_id, actor.id, notification_type, title, message, target_type, target_id)

    @staticmethod
    def notify_version_followers(db: Session, resource: Resource, actor: User, version: str) -> None:
        if resource.visibility != "public":
            return
        followers = db.scalars(select(UserFollow.follower_id).where(UserFollow.following_id == actor.id)).all()
        for follower_id in followers:
            CommunityService.create_notification(
                db,
                follower_id,
                actor.id,
                "VERSION_PUBLISHED",
                f"New version published: {resource.title}",
                f"{actor.display_name or actor.username} published v{version}.",
                "RESOURCE_VERSION",
                resource.id,
            )

    @staticmethod
    def notification_dict(item: Notification) -> dict:
        actor = CommunityService.user_summary(item.actor)
        target_url = None
        if item.target_type == "DISCUSSION" and item.target_id:
            target_url = f"/discussions/{item.target_id}"
        elif item.target_type == "ISSUE" and item.target_id:
            target_url = f"/issues/{item.target_id}"
        elif item.target_type == "RESOURCE_VERSION" and item.target_id:
            target_url = f"/resources/{item.target_id}"
        elif item.target_type == "RESOURCE" and item.target_id:
            target_url = f"/resources/{item.target_id}"
        elif item.target_type == "USER" and actor:
            target_url = f"/users/{actor['username']}"
        return {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "message": item.message,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "target_url": target_url,
            "is_read": item.is_read,
            "actor": actor,
            "created_at": item.created_at,
        }

    @staticmethod
    def enforce_rate_limit(action: str, user_id: int, maximum: int) -> None:
        window = settings.community_rate_limit_window_seconds
        key = f"community:rate:{action}:{user_id}:{int(datetime.utcnow().timestamp() // window)}"
        try:
            client = redis_client()
            count = client.incr(key)
            if count == 1:
                client.expire(key, window)
            if count > maximum:
                raise HTTPException(status_code=429, detail=f"操作过于频繁，请在 {window} 秒后重试")
        except HTTPException:
            raise
        except Exception:
            # Redis is an enhancement, not a single point of failure for community work.
            return

    @staticmethod
    def _community_revision_key(kind: str, resource_id: int) -> str:
        return f"community:revision:{kind}:{resource_id}"

    @staticmethod
    def community_cache_key(kind: str, resource_id: int, suffix: str) -> str | None:
        try:
            client = redis_client()
            revision = client.get(CommunityService._community_revision_key(kind, resource_id)) or "0"
            return f"community:{kind}:{resource_id}:{revision}:{suffix}"
        except Exception:
            return None

    @staticmethod
    def get_cached_list(kind: str, resource_id: int, suffix: str) -> dict | None:
        key = CommunityService.community_cache_key(kind, resource_id, suffix)
        if not key:
            return None
        try:
            value = redis_client().get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    @staticmethod
    def set_cached_list(kind: str, resource_id: int, suffix: str, payload: dict) -> None:
        key = CommunityService.community_cache_key(kind, resource_id, suffix)
        if not key:
            return
        try:
            redis_client().setex(key, settings.community_cache_ttl, json.dumps(payload, default=str, ensure_ascii=False))
        except Exception:
            pass

    @staticmethod
    def invalidate_community_list(kind: str, resource_id: int) -> None:
        try:
            redis_client().incr(CommunityService._community_revision_key(kind, resource_id))
        except Exception:
            pass

    @staticmethod
    def follow_counts(db: Session, user_id: int) -> tuple[int, int]:
        key = f"community:follows:counts:{user_id}"
        try:
            cached = redis_client().get(key)
            if cached:
                payload = json.loads(cached)
                return int(payload["followers"]), int(payload["following"])
        except Exception:
            pass
        followers = int(db.scalar(select(func.count(UserFollow.id)).where(UserFollow.following_id == user_id)) or 0)
        following = int(db.scalar(select(func.count(UserFollow.id)).where(UserFollow.follower_id == user_id)) or 0)
        try:
            redis_client().setex(key, settings.community_cache_ttl, json.dumps({"followers": followers, "following": following}))
        except Exception:
            pass
        return followers, following

    @staticmethod
    def invalidate_follow_counts(*user_ids: int) -> None:
        if not user_ids:
            return
        try:
            redis_client().delete(*(f"community:follows:counts:{user_id}" for user_id in user_ids))
        except Exception:
            pass

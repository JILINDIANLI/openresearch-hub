from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.service import authenticate_user, get_by_identifier, public_user_to_dict, register_user, user_to_dict
from ..auth.schemas import PublicUserRead, RegisterRequest, UserRead
from ..core.security import create_access_token, get_current_user, get_optional_user
from ..database.database import get_db
from ..database.models import Resource, ResourceStar, User, UserFollow
from ..community.schemas import FollowListResponse, FollowState
from ..community.service import CommunityService
from ..engagement.service import EngagementService
from ..resources.router import resource_query, serialize_resource
from ..resources.schemas import ResourceRead
from ..services.visibility import public_resource_conditions
from .schemas import LegacyLogin, LegacyUserCreate

router = APIRouter(prefix="/api/users", tags=["Users"])


def follow_state(db: Session, target: User, viewer_id: int | None) -> dict:
    followers, following = CommunityService.follow_counts(db, target.id)
    is_following = bool(viewer_id and db.scalar(select(UserFollow.id).where(UserFollow.follower_id == viewer_id, UserFollow.following_id == target.id)))
    return {"username": target.username, "is_following": is_following, "followers_count": followers, "following_count": following}


@router.post("/register", response_model=UserRead, status_code=201)
def legacy_register(payload: LegacyUserCreate, db: Session = Depends(get_db)):
    from ..core.config import settings
    import os
    if settings.app_env == "production" and os.getenv("ALLOW_PUBLIC_REGISTRATION", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Registration is currently disabled")
    if settings.app_env == "production":
        from sqlalchemy import func
        if int(db.scalar(select(func.count(User.id)).where(User.role == "ADMIN", User.is_active.is_(True))) or 0) == 0:
            raise HTTPException(status_code=403, detail="Administrator setup is required before public registration")
    try:
        normalized = RegisterRequest(
            username=payload.username,
            display_name=payload.display_name or payload.username,
            email=payload.email,
            password=payload.password,
            confirm_password=payload.password,
            organization=payload.organization,
            research_interests=payload.research_interest or payload.research_fields,
        )
        user = register_user(db, normalized)
        db.commit()
        db.refresh(user)
        return user_to_dict(user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/login")
def legacy_login(payload: LegacyLogin, db: Session = Depends(get_db)):
    identifier = payload.identifier or payload.email
    if not identifier:
        raise HTTPException(status_code=422, detail="需要提供 username 或 email")
    user = authenticate_user(db, identifier, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名/邮箱或密码错误")
    from ..core.config import settings
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "expires_in": settings.access_token_expire_minutes * 60, "user": user_to_dict(user)}


@router.get("/{username}/resources", response_model=list[ResourceRead])
def user_resources(username: str, resource_type: str | None = Query(default=None, alias="type"), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    query = resource_query().where(Resource.author_id == user.id, *public_resource_conditions())
    if resource_type:
        query = query.where(Resource.resource_type == resource_type.lower())
    resources = db.scalars(query.order_by(Resource.created_time.desc())).unique().all()
    return [serialize_resource(resource) for resource in resources]


@router.get("/{username}/stars", response_model=list[ResourceRead])
def user_stars(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    resources = db.scalars(
        resource_query().join(ResourceStar, ResourceStar.resource_id == Resource.id).where(ResourceStar.user_id == user.id, *public_resource_conditions()).order_by(ResourceStar.created_at.desc())
    ).unique().all()
    starred, favorited = EngagementService.interaction_ids(db, user.id, [item.id for item in resources])
    return [serialize_resource(resource, starred, favorited) for resource in resources]


def get_user(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username))
    if user is None and username.isdigit():
        user = db.get(User, int(username))
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user_to_dict(user)


@router.post("/{username}/follow", response_model=FollowState)
def follow_user(username: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = db.scalar(select(User).where(User.username == username))
    if target is None: raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == current_user.id: raise HTTPException(status_code=400, detail="不能关注自己")
    existing = db.scalar(select(UserFollow).where(UserFollow.follower_id == current_user.id, UserFollow.following_id == target.id))
    if existing is None:
        db.add(UserFollow(follower_id=current_user.id, following_id=target.id))
        CommunityService.create_notification(db, target.id, current_user.id, "USER_FOLLOWED", "New follower", f"{current_user.display_name or current_user.username} started following you.", "USER", current_user.id)
        db.commit()
        CommunityService.invalidate_follow_counts(current_user.id, target.id)
    return follow_state(db, target, current_user.id)


@router.delete("/{username}/follow", response_model=FollowState)
def unfollow_user(username: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = db.scalar(select(User).where(User.username == username))
    if target is None: raise HTTPException(status_code=404, detail="用户不存在")
    record = db.scalar(select(UserFollow).where(UserFollow.follower_id == current_user.id, UserFollow.following_id == target.id))
    if record:
        db.delete(record); db.commit(); CommunityService.invalidate_follow_counts(current_user.id, target.id)
    return follow_state(db, target, current_user.id)


@router.get("/{username}/followers", response_model=FollowListResponse)
def followers(username: str, db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.username == username))
    if target is None: raise HTTPException(status_code=404, detail="用户不存在")
    users = db.scalars(select(User).join(UserFollow, UserFollow.follower_id == User.id).where(UserFollow.following_id == target.id).order_by(UserFollow.created_at.desc())).all()
    return {"items": [CommunityService.user_summary(item) for item in users], "total": len(users)}


@router.get("/{username}/following", response_model=FollowListResponse)
def following(username: str, db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.username == username))
    if target is None: raise HTTPException(status_code=404, detail="用户不存在")
    users = db.scalars(select(User).join(UserFollow, UserFollow.following_id == User.id).where(UserFollow.follower_id == target.id).order_by(UserFollow.created_at.desc())).all()
    return {"items": [CommunityService.user_summary(item) for item in users], "total": len(users)}


@router.get("/{username}/follow-state", response_model=FollowState)
def get_follow_state(username: str, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    target = db.scalar(select(User).where(User.username == username))
    if target is None: raise HTTPException(status_code=404, detail="用户不存在")
    return follow_state(db, target, current_user.id if current_user else None)


# Keep the broad profile route last so /follow and related community routes win first.
router.add_api_route("/{username}", get_user, methods=["GET"], response_model=PublicUserRead)

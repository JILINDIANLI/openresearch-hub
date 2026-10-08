from __future__ import annotations

import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.security import hash_password, verify_password
from ..database.models import User
from .schemas import RegisterRequest


def interests_for(user: User) -> list[str]:
    raw = user.research_interests or user.research_fields or ""
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]


def public_user_to_dict(user: User) -> dict:
    created_at = user.created_at or user.created_time
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar_url": user.avatar_url or user.avatar,
        "organization": user.organization,
        "bio": user.bio,
        "research_interests": interests_for(user),
        "website_url": user.website_url,
        "github_url": user.github_url,
        "created_at": created_at,
        "updated_at": user.updated_at or created_at,
        "avatar": user.avatar_url or user.avatar,
        "research_fields": interests_for(user),
        "research_interest": interests_for(user),
        "created_time": user.created_time,
    }


def user_to_dict(user: User) -> dict:
    """Private account representation for login and /api/auth/me only."""
    payload = public_user_to_dict(user)
    payload.update({"email": user.email, "is_active": user.is_active, "role": (user.role or "USER").upper()})
    return payload


def get_by_identifier(db: Session, identifier: str) -> User | None:
    identifier = identifier.strip()
    return db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier.lower())))


def register_user(db: Session, payload: RegisterRequest) -> User:
    username = payload.username.strip()
    email = str(payload.email).strip().lower()
    exists = db.scalar(select(User).where(or_(User.username == username, User.email == email)))
    if exists:
        raise ValueError("用户名或邮箱已存在")
    interests = [item.strip() for item in payload.research_interests if item.strip()]
    user = User(
        username=username,
        display_name=payload.display_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        organization=payload.organization,
        research_fields=", ".join(interests),
        research_interests=json.dumps(interests, ensure_ascii=False),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    user = get_by_identifier(db, identifier)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user

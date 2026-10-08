from __future__ import annotations

from fastapi import HTTPException

from ..database.models import Resource, User


def public_resource_conditions():
    """SQLAlchemy predicates for a resource that may be shown anonymously."""
    return (
        Resource.visibility == "public",
        Resource.review_status == "PUBLISHED",
        Resource.is_hidden.is_(False),
    )


def is_public_resource(resource: Resource | None) -> bool:
    return bool(
        resource
        and resource.visibility == "public"
        and resource.review_status == "PUBLISHED"
        and not resource.is_hidden
    )


def can_view_resource(resource: Resource | None, user: User | None) -> bool:
    return is_public_resource(resource) or bool(resource and user and resource.author_id == user.id)


def require_viewable_resource(resource: Resource | None, user: User | None) -> Resource:
    if not can_view_resource(resource, user):
        # Keep private, pending, rejected, and hidden resources indistinguishable
        # from resources that do not exist.
        raise HTTPException(status_code=404, detail="资源不存在")
    return resource

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..resources.schemas import ResourceRead


class EngagementState(BaseModel):
    resource_id: int
    stars_count: int
    favorites_count: int
    is_starred: bool
    is_favorited: bool


class StarSummary(BaseModel):
    resource_id: int
    stars_count: int
    is_starred: bool = False


class TrendingResourceRead(ResourceRead):
    score: float = 0
    recent_stars: int = 0
    recent_downloads: int = 0
    recent_views: int = 0


class ActivityRead(BaseModel):
    id: int
    resource_id: int
    activity_type: str
    detail: str | None = None
    created_at: datetime
    actor: dict = Field(default_factory=dict)

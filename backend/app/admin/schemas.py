from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["USER", "ADMIN"]
ReviewStatus = Literal["DRAFT", "PENDING", "PUBLISHED", "REJECTED"]


class RoleUpdate(BaseModel):
    role: Role


class ActiveUpdate(BaseModel):
    is_active: bool


class ResourceStatusUpdate(BaseModel):
    status: ReviewStatus
    reason: str | None = Field(default=None, max_length=5000)


class FeaturedUpdate(BaseModel):
    featured: bool


class VisibilityUpdate(BaseModel):
    hidden: bool


class AdminLogRead(BaseModel):
    id: int
    admin_id: int
    admin_name: str
    action: str
    target_type: str
    target_id: int | None
    detail: str
    created_time: datetime

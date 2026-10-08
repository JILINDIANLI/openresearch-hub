from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


DISCUSSION_STATUSES = {"OPEN", "CLOSED"}
ISSUE_TYPES = {"BUG", "DOCUMENTATION", "DATASET", "MODEL", "REPRODUCTION", "FEATURE_REQUEST", "QUESTION", "OTHER"}
ISSUE_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}
ISSUE_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _clean(value: str) -> str:
    return str(value).strip()


class UserSummary(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_url: str | None = None
    organization: str | None = None


class ResourceSummary(BaseModel):
    id: int
    title: str
    resource_type: str
    author_id: int | None = None


class DiscussionCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)

    _strip = field_validator("title", "content", mode="before")(_clean)


class DiscussionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=20_000)

    _strip = field_validator("title", "content", mode="before")(_clean)


class DiscussionCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    parent_id: int | None = Field(default=None, gt=0)

    _strip = field_validator("content", mode="before")(_clean)


class DiscussionCommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)

    _strip = field_validator("content", mode="before")(_clean)


class DiscussionCommentRead(BaseModel):
    id: int
    discussion_id: int
    parent_id: int | None = None
    content: str
    is_deleted: bool
    is_hidden: bool = False
    author: UserSummary | None = None
    created_at: datetime
    updated_at: datetime
    replies: list["DiscussionCommentRead"] = Field(default_factory=list)


class DiscussionListItem(BaseModel):
    id: int
    resource_id: int
    title: str
    status: Literal["OPEN", "CLOSED"]
    is_pinned: bool
    is_locked: bool
    comments_count: int
    author: UserSummary
    created_at: datetime
    updated_at: datetime


class DiscussionRead(DiscussionListItem):
    content: str
    resource: ResourceSummary
    comments: list[DiscussionCommentRead] = Field(default_factory=list)


class DiscussionListResponse(BaseModel):
    items: list[DiscussionListItem]
    page: int
    page_size: int
    total: int


class IssueCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=1, max_length=20_000)
    issue_type: str = Field(default="OTHER", max_length=30)

    _strip = field_validator("title", "description", mode="before")(_clean)

    @field_validator("issue_type", mode="before")
    @classmethod
    def valid_type(cls, value: str) -> str:
        normalized = _clean(value).upper()
        if normalized not in ISSUE_TYPES:
            raise ValueError("issue_type 不支持")
        return normalized


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=20_000)
    status: str | None = Field(default=None, max_length=20)
    priority: str | None = Field(default=None, max_length=20)
    assignee_id: int | None = Field(default=None, gt=0)

    _strip = field_validator("title", "description", mode="before")(_clean)

    @field_validator("status", mode="before")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = _clean(value).upper()
        if normalized not in ISSUE_STATUSES:
            raise ValueError("status 不支持")
        return normalized

    @field_validator("priority", mode="before")
    @classmethod
    def valid_priority(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = _clean(value).upper()
        if normalized not in ISSUE_PRIORITIES:
            raise ValueError("priority 不支持")
        return normalized


class IssueCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    parent_id: int | None = Field(default=None, gt=0)

    _strip = field_validator("content", mode="before")(_clean)


class IssueCommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)

    _strip = field_validator("content", mode="before")(_clean)


class IssueCommentRead(BaseModel):
    id: int
    issue_id: int
    parent_id: int | None = None
    content: str
    is_deleted: bool
    is_hidden: bool = False
    author: UserSummary | None = None
    created_at: datetime
    updated_at: datetime
    replies: list["IssueCommentRead"] = Field(default_factory=list)


class IssueListItem(BaseModel):
    id: int
    resource_id: int
    title: str
    issue_type: str
    status: str
    priority: str
    comments_count: int
    author: UserSummary
    assignee: UserSummary | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class IssueRead(IssueListItem):
    description: str
    resource: ResourceSummary
    comments: list[IssueCommentRead] = Field(default_factory=list)


class IssueListResponse(BaseModel):
    items: list[IssueListItem]
    page: int
    page_size: int
    total: int


class FollowState(BaseModel):
    username: str
    is_following: bool
    followers_count: int
    following_count: int


class FollowListResponse(BaseModel):
    items: list[UserSummary]
    total: int


class NotificationRead(BaseModel):
    id: int
    type: str
    title: str
    message: str
    target_type: str
    target_id: int | None = None
    target_url: str | None = None
    is_read: bool
    actor: UserSummary | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    unread_count: int


class UnreadCount(BaseModel):
    unread_count: int


DiscussionCommentRead.model_rebuild()
IssueCommentRead.model_rebuild()

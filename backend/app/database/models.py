from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


resource_tags = Table(
    "resource_tags",
    Base.metadata,
    Column("resource_id", ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    avatar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_interests: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="USER", server_default="USER", nullable=False, index=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    resources: Mapped[list["Resource"]] = relationship(back_populates="author")
    uploaded_files: Mapped[list["ResourceFile"]] = relationship(back_populates="uploader", foreign_keys="ResourceFile.uploader_id")
    star_records: Mapped[list["ResourceStar"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    favorite_records: Mapped[list["ResourceFavorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    view_records: Mapped[list["ResourceView"]] = relationship(back_populates="user", foreign_keys="ResourceView.user_id")
    download_records: Mapped[list["ResourceDownload"]] = relationship(back_populates="user", foreign_keys="ResourceDownload.user_id")
    activity_records: Mapped[list["ResourceActivity"]] = relationship(back_populates="actor", foreign_keys="ResourceActivity.actor_id")
    search_queries: Mapped[list["SearchQuery"]] = relationship(back_populates="user", foreign_keys="SearchQuery.user_id")
    discussions: Mapped[list["Discussion"]] = relationship(back_populates="author", foreign_keys="Discussion.author_id")
    discussion_comments: Mapped[list["DiscussionComment"]] = relationship(back_populates="author", foreign_keys="DiscussionComment.author_id")
    issues: Mapped[list["Issue"]] = relationship(back_populates="author", foreign_keys="Issue.author_id")
    assigned_issues: Mapped[list["Issue"]] = relationship(back_populates="assignee", foreign_keys="Issue.assignee_id")
    issue_comments: Mapped[list["IssueComment"]] = relationship(back_populates="author", foreign_keys="IssueComment.author_id")
    following_records: Mapped[list["UserFollow"]] = relationship(back_populates="follower", foreign_keys="UserFollow.follower_id", cascade="all, delete-orphan")
    follower_records: Mapped[list["UserFollow"]] = relationship(back_populates="following", foreign_keys="UserFollow.following_id", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", foreign_keys="Notification.user_id", cascade="all, delete-orphan")
    notification_actions: Mapped[list["Notification"]] = relationship(back_populates="actor", foreign_keys="Notification.actor_id")
    admin_logs: Mapped[list["AdminLog"]] = relationship(back_populates="admin", foreign_keys="AdminLog.admin_id")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resources: Mapped[list["Resource"]] = relationship(secondary=resource_tags, back_populates="tags")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    views: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    favorites_count: Mapped[int] = mapped_column(Integer, default=0)
    review_status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING", nullable=False, index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    license: Mapped[str] = mapped_column(String(80), default="MIT")
    visibility: Mapped[str] = mapped_column(String(30), default="public", index=True)
    research_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    homepage_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    author: Mapped[User | None] = relationship(back_populates="resources")
    tags: Mapped[list[Tag]] = relationship(secondary=resource_tags, back_populates="resources")
    project: Mapped["Project | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    paper: Mapped["Paper | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    dataset: Mapped["Dataset | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    model: Mapped["Model | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    algorithm: Mapped["Algorithm | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    demo: Mapped["Demo | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    tutorial: Mapped["Tutorial | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    files: Mapped[list["ResourceFile"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    versions: Mapped[list["ResourceVersion"]] = relationship(back_populates="resource", cascade="all, delete-orphan", order_by="ResourceVersion.version_major.desc(), ResourceVersion.version_minor.desc(), ResourceVersion.version_patch.desc()")
    star_records: Mapped[list["ResourceStar"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    favorite_records: Mapped[list["ResourceFavorite"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    view_records: Mapped[list["ResourceView"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    download_records: Mapped[list["ResourceDownload"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    activities: Mapped[list["ResourceActivity"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    repository: Mapped["Repository | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    showcase: Mapped["ResourceShowcase | None"] = relationship(back_populates="resource", uselist=False, cascade="all, delete-orphan")
    discussions: Mapped[list["Discussion"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    issues: Mapped[list["Issue"]] = relationship(back_populates="resource", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    leader: Mapped[str] = mapped_column(String(120), default="")
    members: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="published")
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paper_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource: Mapped[Resource] = relationship(back_populates="project")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    authors: Mapped[str] = mapped_column(Text, default="")
    journal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    abstract: Mapped[str] = mapped_column(Text, default="")
    resource: Mapped[Resource] = relationship(back_populates="paper")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    size: Mapped[str] = mapped_column(String(80), default="")
    format: Mapped[str] = mapped_column(String(80), default="")
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    dataset_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    download_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    task: Mapped[str] = mapped_column(String(255), default="")
    resource: Mapped[Resource] = relationship(back_populates="dataset")


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    framework: Mapped[str] = mapped_column(String(80), default="")
    parameters: Mapped[str] = mapped_column(String(80), default="")
    task: Mapped[str] = mapped_column(String(255), default="")
    model_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource: Mapped[Resource] = relationship(back_populates="model")


class Algorithm(Base):
    __tablename__ = "algorithms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    category: Mapped[str] = mapped_column(String(120), default="")
    difficulty: Mapped[str] = mapped_column(String(30), default="")
    paper_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    code_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource: Mapped[Resource] = relationship(back_populates="algorithm")


class Demo(Base):
    __tablename__ = "demos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[str] = mapped_column(String(40), default="")
    resource: Mapped[Resource] = relationship(back_populates="demo")


class Tutorial(Base):
    __tablename__ = "tutorials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True)
    difficulty: Mapped[str] = mapped_column(String(30), default="")
    duration: Mapped[str] = mapped_column(String(40), default="")
    content_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource: Mapped[Resource] = relationship(back_populates="tutorial")


class ResourceFile(Base):
    __tablename__ = "resource_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("resource_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # Legacy fields stay populated for the V1 schema and backwards compatibility.
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(80), default="other")
    url: Mapped[str] = mapped_column(String(500), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(700), unique=True, nullable=True)
    bucket_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_kind: Mapped[str] = mapped_column(String(40), default="OTHER", index=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    resource: Mapped[Resource] = relationship(back_populates="files")
    version: Mapped["ResourceVersion | None"] = relationship(back_populates="files")
    uploader: Mapped[User | None] = relationship(back_populates="uploaded_files", foreign_keys=[uploader_id])
    showcase_media: Mapped[list["ShowcaseMedia"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class ResourceStar(Base):
    __tablename__ = "resource_stars"
    __table_args__ = (UniqueConstraint("user_id", "resource_id", name="uq_resource_stars_user_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user: Mapped[User] = relationship(back_populates="star_records")
    resource: Mapped[Resource] = relationship(back_populates="star_records")


class ResourceFavorite(Base):
    __tablename__ = "resource_favorites"
    __table_args__ = (UniqueConstraint("user_id", "resource_id", name="uq_resource_favorites_user_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user: Mapped[User] = relationship(back_populates="favorite_records")
    resource: Mapped[Resource] = relationship(back_populates="favorite_records")


class ResourceView(Base):
    __tablename__ = "resource_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    resource: Mapped[Resource] = relationship(back_populates="view_records")
    user: Mapped[User | None] = relationship(back_populates="view_records", foreign_keys=[user_id])


class ResourceDownload(Base):
    __tablename__ = "resource_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("resource_files.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    resource: Mapped[Resource] = relationship(back_populates="download_records")
    user: Mapped[User | None] = relationship(back_populates="download_records", foreign_keys=[user_id])


class ResourceActivity(Base):
    __tablename__ = "resource_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String(40), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    resource: Mapped[Resource] = relationship(back_populates="activities")
    actor: Mapped[User | None] = relationship(back_populates="activity_records", foreign_keys=[actor_id])


class Discussion(Base):
    __tablename__ = "discussions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    resource: Mapped[Resource] = relationship(back_populates="discussions")
    author: Mapped[User] = relationship(back_populates="discussions", foreign_keys=[author_id])
    comments: Mapped[list["DiscussionComment"]] = relationship(back_populates="discussion", cascade="all, delete-orphan", order_by="DiscussionComment.created_at.asc()")


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discussion_id: Mapped[int] = mapped_column(ForeignKey("discussions.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("discussion_comments.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    discussion: Mapped[Discussion] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="discussion_comments", foreign_keys=[author_id])
    parent: Mapped["DiscussionComment | None"] = relationship(remote_side="DiscussionComment.id", back_populates="replies")
    replies: Mapped[list["DiscussionComment"]] = relationship(back_populates="parent")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    issue_type: Mapped[str] = mapped_column(String(30), default="OTHER", index=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    resource: Mapped[Resource] = relationship(back_populates="issues")
    author: Mapped[User] = relationship(back_populates="issues", foreign_keys=[author_id])
    assignee: Mapped[User | None] = relationship(back_populates="assigned_issues", foreign_keys=[assignee_id])
    comments: Mapped[list["IssueComment"]] = relationship(back_populates="issue", cascade="all, delete-orphan", order_by="IssueComment.created_at.asc()")


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("issue_comments.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    issue: Mapped[Issue] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="issue_comments", foreign_keys=[author_id])
    parent: Mapped["IssueComment | None"] = relationship(remote_side="IssueComment.id", back_populates="replies")
    replies: Mapped[list["IssueComment"]] = relationship(back_populates="parent")


class UserFollow(Base):
    __tablename__ = "user_follows"
    __table_args__ = (UniqueConstraint("follower_id", "following_id", name="uq_user_follows_follower_following"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    following_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    follower: Mapped[User] = relationship(back_populates="following_records", foreign_keys=[follower_id])
    following: Mapped[User] = relationship(back_populates="follower_records", foreign_keys=[following_id])


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, default="")
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user: Mapped[User] = relationship(back_populates="notifications", foreign_keys=[user_id])
    actor: Mapped[User | None] = relationship(back_populates="notification_actions", foreign_keys=[actor_id])


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(60), index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    admin: Mapped[User] = relationship(back_populates="admin_logs", foreign_keys=[admin_id])


class ResourceShowcase(Base):
    """The editorial research story attached to one resource."""

    __tablename__ = "resource_showcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    short_description: Mapped[str] = mapped_column(Text, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    research_background: Mapped[str] = mapped_column(Text, default="")
    methodology: Mapped[str] = mapped_column(Text, default="")
    contributions: Mapped[str] = mapped_column(Text, default="")
    experiments: Mapped[str] = mapped_column(Text, default="")
    results_summary: Mapped[str] = mapped_column(Text, default="")
    citation_text: Mapped[str] = mapped_column(Text, default="")
    bibtex: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resource: Mapped[Resource] = relationship(back_populates="showcase")
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    media: Mapped[list["ShowcaseMedia"]] = relationship(back_populates="showcase", cascade="all, delete-orphan", order_by="ShowcaseMedia.order_index.asc(), ShowcaseMedia.created_at.asc()")
    results: Mapped[list["ShowcaseResult"]] = relationship(back_populates="showcase", cascade="all, delete-orphan", order_by="ShowcaseResult.created_at.asc()")


class ShowcaseMedia(Base):
    __tablename__ = "showcase_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showcase_id: Mapped[int] = mapped_column(ForeignKey("resource_showcases.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("resource_files.id", ondelete="CASCADE"), unique=True, index=True)
    media_type: Mapped[str] = mapped_column(String(20), default="OTHER", index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    showcase: Mapped[ResourceShowcase] = relationship(back_populates="media")
    file: Mapped[ResourceFile] = relationship(back_populates="showcase_media")


class ShowcaseResult(Base):
    __tablename__ = "showcase_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showcase_id: Mapped[int] = mapped_column(ForeignKey("resource_showcases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    table_data: Mapped[dict | list] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    showcase: Mapped[ResourceShowcase] = relationship(back_populates="results")


class SearchQuery(Base):
    """Anonymous-safe search analytics; no IP address or token is stored."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(200), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user: Mapped[User | None] = relationship(back_populates="search_queries", foreign_keys=[user_id])


class ResourceVersion(Base):
    __tablename__ = "resource_versions"
    __table_args__ = (UniqueConstraint("resource_id", "version", name="uq_resource_versions_resource_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(40), index=True)
    version_major: Mapped[int] = mapped_column(Integer, default=0, index=True)
    version_minor: Mapped[int] = mapped_column(Integer, default=0, index=True)
    version_patch: Mapped[int] = mapped_column(Integer, default=0, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    release_notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    git_commit_sha: Mapped[str | None] = mapped_column(String(120), nullable=True)
    git_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downloads_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resource: Mapped[Resource] = relationship(back_populates="versions")
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    files: Mapped[list[ResourceFile]] = relationship(back_populates="version")




class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("resource_id", name="uq_repositories_resource"), UniqueConstraint("provider", "owner", "name", name="uq_repositories_provider_owner_name"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="GITEA", index=True)
    owner: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160))
    full_name: Mapped[str] = mapped_column(String(300), index=True)
    clone_url: Mapped[str] = mapped_column(String(700), default="")
    ssh_url: Mapped[str] = mapped_column(String(700), default="")
    web_url: Mapped[str] = mapped_column(String(700), default="")
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stars_count: Mapped[int] = mapped_column(Integer, default=0)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="PUBLIC", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resource: Mapped[Resource] = relationship(back_populates="repository")

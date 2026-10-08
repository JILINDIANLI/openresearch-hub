from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


RESOURCE_TYPES = {"model", "dataset", "algorithm", "project", "paper", "demo", "tutorial"}
DIFFICULTIES = {"Beginner", "Intermediate", "Advanced"}


def _clean_url(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    value = str(value).strip()
    if not value.startswith(("http://", "https://")):
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    return value


class ModelDetails(BaseModel):
    framework: str = ""
    task: str = ""
    parameters: str = ""
    model_url: str | None = None
    _url = field_validator("model_url", mode="before")(_clean_url)


class DatasetDetails(BaseModel):
    size: str = ""
    format: str = ""
    task: str = ""
    download_url: str | None = None
    _url = field_validator("download_url", mode="before")(_clean_url)


class AlgorithmDetails(BaseModel):
    category: str = ""
    difficulty: str = ""
    paper_url: str | None = None
    code_url: str | None = None
    _urls = field_validator("paper_url", "code_url", mode="before")(_clean_url)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        if value and value not in DIFFICULTIES:
            raise ValueError("difficulty 只能是 Beginner、Intermediate 或 Advanced")
        return value


class ProjectDetails(BaseModel):
    github_url: str | None = None
    paper_url: str | None = None
    demo_url: str | None = None
    members: list[str] = Field(default_factory=list)
    _urls = field_validator("github_url", "paper_url", "demo_url", mode="before")(_clean_url)


class PaperDetails(BaseModel):
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2027)
    doi: str | None = None
    pdf_url: str | None = None
    _url = field_validator("pdf_url", mode="before")(_clean_url)


class DemoDetails(BaseModel):
    video_url: str | None = None
    project_url: str | None = None
    duration: str = ""
    _urls = field_validator("video_url", "project_url", mode="before")(_clean_url)


class TutorialDetails(BaseModel):
    difficulty: str = ""
    duration: str = ""
    content_url: str | None = None
    _url = field_validator("content_url", mode="before")(_clean_url)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        if value and value not in DIFFICULTIES:
            raise ValueError("difficulty 只能是 Beginner、Intermediate 或 Advanced")
        return value


class ResourceCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str = Field(min_length=3, max_length=150)
    resource_type: str = Field(validation_alias=AliasChoices("type", "resource_type"))
    description: str = Field(min_length=10, max_length=10000)
    license: str = Field(default="MIT", max_length=80)
    research_field: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list, max_length=20)
    thumbnail_url: str | None = None
    repository_url: str | None = None
    homepage_url: str | None = None
    visibility: str = Field(default="public", pattern="^(public|private|internal)$")
    details: dict[str, Any] = Field(default_factory=dict)
    model: ModelDetails | None = None
    dataset: DatasetDetails | None = None
    algorithm: AlgorithmDetails | None = None
    project: ProjectDetails | None = None
    paper: PaperDetails | None = None
    demo: DemoDetails | None = None
    tutorial: TutorialDetails | None = None

    @field_validator("resource_type")
    @classmethod
    def normalize_resource_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in RESOURCE_TYPES:
            raise ValueError(f"resource_type 必须是: {', '.join(sorted(RESOURCE_TYPES))}")
        return normalized

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    _urls = field_validator("thumbnail_url", "repository_url", "homepage_url", mode="before")(_clean_url)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if any(len(value) > 120 for value in cleaned):
            raise ValueError("单个标签不能超过 120 个字符")
        return cleaned


class ResourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    license: str | None = None
    visibility: str | None = Field(default=None, pattern="^(public|private|internal)$")
    research_field: str | None = None
    thumbnail_url: str | None = None
    repository_url: str | None = None
    homepage_url: str | None = None
    tags: list[str] | None = None
    details: dict[str, Any] | None = None

    _urls = field_validator("thumbnail_url", "repository_url", "homepage_url", mode="before")(_clean_url)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if len(cleaned) > 20 or any(len(value) > 120 for value in cleaned):
            raise ValueError("标签数量或长度不合法")
        return cleaned


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None


class ResourceRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int
    title: str
    resource_type: str
    type: str
    description: str
    author_id: int | None = None
    author_name: str
    author: dict = Field(default_factory=dict)
    created_time: datetime
    updated_time: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
    views: int
    stars: int
    downloads: int
    stars_count: int = 0
    favorites_count: int = 0
    views_count: int = 0
    downloads_count: int = 0
    is_starred: bool = False
    is_favorited: bool = False
    stars_count: int = 0
    favorites_count: int = 0
    views_count: int = 0
    downloads_count: int = 0
    is_starred: bool = False
    is_favorited: bool = False
    license: str
    visibility: str
    research_field: str | None = None
    thumbnail_url: str | None = None
    repository_url: str | None = None
    homepage_url: str | None = None
    latest_version: str | None = None
    latest_version_published_at: datetime | None = None
    has_showcase: bool = False
    tags: list[TagRead] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    repository: dict | None = None

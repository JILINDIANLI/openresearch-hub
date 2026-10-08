from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def normalize_version(value: str) -> str:
    normalized = str(value).strip().removeprefix("v")
    if not SEMVER.fullmatch(normalized):
        raise ValueError("版本号必须为 MAJOR.MINOR.PATCH，例如 1.2.0")
    return normalized


class VersionCreate(BaseModel):
    version: str = Field(min_length=5, max_length=40)
    title: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=10000)
    release_notes: str = Field(default="", max_length=30000)
    git_commit_sha: str | None = Field(default=None, max_length=120)
    git_branch: str | None = Field(default=None, max_length=255)

    _version = field_validator("version", mode="before")(normalize_version)


class VersionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    release_notes: str | None = Field(default=None, max_length=30000)
    git_commit_sha: str | None = Field(default=None, max_length=120)
    git_branch: str | None = Field(default=None, max_length=255)


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    version: str
    title: str
    description: str
    release_notes: str
    status: str
    created_by: int
    publisher: dict = Field(default_factory=dict)
    git_commit_sha: str | None = None
    git_branch: str | None = None
    is_latest: bool
    published_at: datetime | None = None
    downloads_count: int = 0
    created_at: datetime
    updated_at: datetime
    files: list[dict] = Field(default_factory=list)

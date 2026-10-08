from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    description: str = Field(default="", max_length=10000)
    private: bool = False
    initialize_readme: bool = True


class RepositoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resource_id: int
    provider: str
    owner: str
    name: str
    full_name: str
    clone_url: str
    ssh_url: str
    web_url: str
    default_branch: str
    description: str
    language: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    last_commit_at: datetime | None = None
    visibility: str
    created_at: datetime
    updated_at: datetime


class RepositoryFile(BaseModel):
    path: str
    name: str
    type: str
    size: int | None = None
    sha: str | None = None
    url: str | None = None
    html_url: str | None = None


class RepositoryCommit(BaseModel):
    sha: str
    message: str
    author: str | None = None
    created_at: datetime | None = None
    url: str | None = None


class RepositoryBranch(BaseModel):
    name: str
    protected: bool = False
    commit_sha: str | None = None


class RepositoryFileContent(BaseModel):
    path: str
    name: str
    size: int
    language: str | None = None
    content: str
    raw_url: str
    download_url: str

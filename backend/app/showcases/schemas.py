from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


MEDIA_TYPES = {"IMAGE", "VIDEO", "PDF", "OTHER"}


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).strip()


class ShowcaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    short_description: str = Field(default="", max_length=2000, validation_alias=AliasChoices("short_description", "description"))
    abstract: str = Field(default="", max_length=30000)
    research_background: str = Field(default="", max_length=30000)
    methodology: str = Field(default="", max_length=30000)
    contributions: str = Field(default="", max_length=30000)
    experiments: str = Field(default="", max_length=30000)
    results_summary: str = Field(default="", max_length=30000, validation_alias=AliasChoices("results_summary", "results"))
    citation_text: str = Field(default="", max_length=10000, validation_alias=AliasChoices("citation_text", "citation"))
    bibtex: str = Field(default="", max_length=20000)

    _clean = field_validator(
        "title", "short_description", "abstract", "research_background", "methodology",
        "contributions", "experiments", "results_summary", "citation_text", "bibtex",
        mode="before",
    )(_strip)


class ShowcaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    abstract: str | None = Field(default=None, max_length=30000)
    short_description: str | None = Field(default=None, max_length=2000, validation_alias=AliasChoices("short_description", "description"))
    research_background: str | None = Field(default=None, max_length=30000, validation_alias=AliasChoices("research_background", "background"))
    methodology: str | None = Field(default=None, max_length=30000)
    contributions: str | None = Field(default=None, max_length=30000)
    experiments: str | None = Field(default=None, max_length=30000)
    results_summary: str | None = Field(default=None, max_length=30000, validation_alias=AliasChoices("results_summary", "results"))
    citation_text: str | None = Field(default=None, max_length=10000, validation_alias=AliasChoices("citation_text", "citation"))
    bibtex: str | None = Field(default=None, max_length=20000)

    _clean = field_validator(
        "title", "short_description", "abstract", "research_background", "methodology",
        "contributions", "experiments", "results_summary", "citation_text", "bibtex",
        mode="before",
    )(_strip)


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    showcase_id: int
    file_id: int
    media_type: str
    title: str
    description: str
    order_index: int
    created_at: datetime
    filename: str
    mime_type: str
    file_size: int
    preview_url: str | None = None
    download_url: str


class ResultCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    table_data: dict[str, Any] | list[Any] = Field(default_factory=dict)

    _clean = field_validator("title", "description", mode="before")(_strip)


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    showcase_id: int
    title: str
    description: str
    table_data: dict[str, Any] | list[Any]
    created_at: datetime


class ShowcaseRead(BaseModel):
    id: int
    resource_id: int
    title: str
    short_description: str
    abstract: str
    research_background: str
    methodology: str
    contributions: str
    experiments: str
    results_summary: str
    citation_text: str
    bibtex: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    media: list[MediaRead] = Field(default_factory=list)
    results: list[ResultRead] = Field(default_factory=list)

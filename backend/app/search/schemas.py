from typing import Literal

from pydantic import BaseModel, Field


class SearchFacets(BaseModel):
    research_fields: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    licenses: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)


class SearchResponse(BaseModel):
    items: list[dict] = Field(default_factory=list)
    page: int
    page_size: int
    total: int
    total_pages: int
    counts: dict[str, int] = Field(default_factory=dict)
    facets: SearchFacets = Field(default_factory=SearchFacets)


class SearchSuggestion(BaseModel):
    kind: Literal["resource", "tag", "research_field"]
    label: str
    resource_id: int | None = None
    resource_type: str | None = None


class TrendingSearch(BaseModel):
    query: str
    count: int

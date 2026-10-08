from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class DailyResourcePoint(BaseModel):
    date: date
    resources: int = 0
    researchers: int = 0


class DailyUsagePoint(BaseModel):
    date: date
    downloads: int = 0


class DailyCommunityPoint(BaseModel):
    date: date
    discussions: int = 0
    issues: int = 0
    comments: int = 0


class DistributionPoint(BaseModel):
    type: str
    count: int


class ResearchAreaPoint(BaseModel):
    name: str
    count: int


class ActiveResearcher(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    avatar_url: str | None = None
    organization: str | None = None
    resource_count: int = 0
    stars: int = 0
    downloads: int = 0


class PublicStatistics(BaseModel):
    generated_at: str
    overview: dict[str, int]
    resource_growth: list[DailyResourcePoint]
    resource_distribution: list[DistributionPoint]
    download_trend: list[DailyUsagePoint]
    community_activity: list[DailyCommunityPoint]
    research_areas: list[ResearchAreaPoint]
    active_researchers: list[ActiveResearcher]


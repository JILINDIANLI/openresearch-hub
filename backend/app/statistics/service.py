from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.cache import redis_client
from ..services.visibility import public_resource_conditions
from ..database.models import (
    Discussion,
    DiscussionComment,
    Issue,
    IssueComment,
    Resource,
    ResourceDownload,
)


STATISTICS_CACHE_KEY = "openresearch:statistics:public:v1"
STATISTICS_CACHE_TTL = 600
PUBLIC_RESOURCE_TYPES = ("model", "dataset", "algorithm", "project", "paper", "demo", "tutorial")


def _public_filter():
    return public_resource_conditions()


def _empty_days(days: int = 30) -> list[date]:
    today = datetime.utcnow().date()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _count_by_day(records: list[datetime], days: list[date]) -> dict[date, int]:
    counts = Counter(item.date() for item in records if item)
    return {day: int(counts.get(day, 0)) for day in days}


def _split_fields(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("；", ";").replace("，", ",").replace("/", ",")
    return [part.strip() for group in normalized.split(";") for part in group.split(",") if part.strip()]


def _cached() -> dict | None:
    try:
        value = redis_client().get(STATISTICS_CACHE_KEY)
        return json.loads(value) if value else None
    except Exception:
        return None


def _cache(payload: dict) -> None:
    try:
        redis_client().setex(STATISTICS_CACHE_KEY, STATISTICS_CACHE_TTL, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        return


def public_statistics(db: Session, *, use_cache: bool = True) -> dict:
    if use_cache:
        cached = _cached()
        if cached is not None:
            return cached

    days = _empty_days()
    start = datetime.combine(days[0], datetime.min.time())
    resources = db.scalars(
        select(Resource)
        .options(selectinload(Resource.author), selectinload(Resource.tags))
        .where(*_public_filter())
    ).unique().all()
    resource_ids = [item.id for item in resources]
    by_type = Counter(item.resource_type for item in resources)
    contributor_ids = {item.author_id for item in resources if item.author_id is not None}
    resource_day_counts = _count_by_day([item.created_time for item in resources if item.created_time and item.created_time >= start], days)
    resource_day_researchers: dict[date, set[int]] = defaultdict(set)
    for item in resources:
        if item.created_time and item.created_time >= start and item.author_id is not None:
            resource_day_researchers[item.created_time.date()].add(item.author_id)

    download_dates = []
    if resource_ids:
        download_dates = db.scalars(
            select(ResourceDownload.created_at).where(
                ResourceDownload.resource_id.in_(resource_ids),
                ResourceDownload.created_at >= start,
            )
        ).all()
    download_day_counts = _count_by_day(download_dates, days)

    discussion_dates = db.scalars(select(Discussion.created_at).join(Discussion.resource).where(Discussion.is_hidden.is_(False), Discussion.created_at >= start, *_public_filter())).all()
    issue_dates = db.scalars(select(Issue.created_at).join(Issue.resource).where(Issue.is_hidden.is_(False), Issue.created_at >= start, *_public_filter())).all()
    discussion_comment_dates = db.scalars(select(DiscussionComment.created_at).join(DiscussionComment.discussion).join(Discussion.resource).where(DiscussionComment.is_deleted.is_(False), DiscussionComment.is_hidden.is_(False), Discussion.is_hidden.is_(False), DiscussionComment.created_at >= start, *_public_filter())).all()
    issue_comment_dates = db.scalars(select(IssueComment.created_at).join(IssueComment.issue).join(Issue.resource).where(IssueComment.is_deleted.is_(False), IssueComment.is_hidden.is_(False), Issue.is_hidden.is_(False), IssueComment.created_at >= start, *_public_filter())).all()
    discussion_counts = _count_by_day(discussion_dates, days)
    issue_counts = _count_by_day(issue_dates, days)
    comment_counts = _count_by_day(list(discussion_comment_dates) + list(issue_comment_dates), days)

    areas = Counter()
    for item in resources:
        fields = _split_fields(item.research_field) or [tag.name for tag in item.tags]
        for field in fields:
            areas[field] += 1

    author_stats: dict[int, dict] = {}
    for item in resources:
        if item.author is None:
            continue
        stat = author_stats.setdefault(item.author.id, {"user": item.author, "resource_count": 0, "stars": 0, "downloads": 0})
        stat["resource_count"] += 1
        stat["stars"] += max(item.stars or 0, 0)
        stat["downloads"] += max(item.downloads or 0, 0)
    active_researchers = []
    for stat in sorted(author_stats.values(), key=lambda value: (value["resource_count"], value["stars"], value["downloads"]), reverse=True)[:12]:
        user = stat["user"]
        active_researchers.append({
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "avatar_url": user.avatar_url or user.avatar,
            "organization": user.organization,
            "resource_count": stat["resource_count"],
            "stars": stat["stars"],
            "downloads": stat["downloads"],
        })

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "overview": {
            "researchers": len(contributor_ids),
            "resources": len(resources),
            "projects": int(by_type.get("project", 0)),
            "downloads": sum(max(item.downloads or 0, 0) for item in resources),
        },
        "resource_growth": [
            {"date": day, "resources": resource_day_counts[day], "researchers": len(resource_day_researchers.get(day, set()))}
            for day in days
        ],
        "resource_distribution": [
            {"type": resource_type.upper(), "count": int(by_type.get(resource_type, 0))}
            for resource_type in PUBLIC_RESOURCE_TYPES
            if by_type.get(resource_type, 0) or resource_type in {"model", "dataset", "algorithm", "paper"}
        ],
        "download_trend": [{"date": day, "downloads": download_day_counts[day]} for day in days],
        "community_activity": [
            {"date": day, "discussions": discussion_counts[day], "issues": issue_counts[day], "comments": comment_counts[day]}
            for day in days
        ],
        "research_areas": [{"name": name, "count": count} for name, count in areas.most_common(12)],
        "active_researchers": active_researchers,
    }
    _cache(payload)
    return payload


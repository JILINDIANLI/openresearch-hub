from __future__ import annotations

"""Search and discovery queries for public OpenResearch resources."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from math import ceil
import re

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..database.models import (
    Algorithm,
    Dataset,
    Model,
    Paper,
    Project,
    Resource,
    ResourceDownload,
    ResourceActivity,
    ResourceStar,
    ResourceView,
    SearchQuery,
    Tag,
    User,
)
from ..engagement.service import EngagementService
from ..resources.router import resource_query, serialize_resource


RESOURCE_TYPES = {"model", "dataset", "algorithm", "project", "paper", "demo", "tutorial"}
SORT_OPTIONS = {"relevance", "newest", "oldest", "stars", "downloads", "views", "trending"}


def _values(values: Iterable[str] | None) -> list[str]:
    """Normalize repeated and comma-separated query parameters."""
    result: list[str] = []
    for value in values or []:
        result.extend(part.strip() for part in str(value).split(",") if part.strip())
    return result


_SENSITIVE_SEARCH = re.compile(r"(?:@|https?://|www\.|(?:token|secret|password|api[_-]?key|bearer)\s*[:=])", re.IGNORECASE)
_SAFE_TRENDING = re.compile(r"^[\w\s.,+/#()&-]{3,80}$", re.UNICODE)


class SearchService:
    @staticmethod
    def normalize_types(values: Iterable[str] | None) -> list[str]:
        normalized = [value.lower() for value in _values(values)]
        invalid = sorted(set(normalized) - RESOURCE_TYPES)
        if invalid:
            raise ValueError(f"Unsupported resource type: {', '.join(invalid)}")
        return normalized

    @staticmethod
    def filters(
        *,
        resource_types: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        research_fields: Iterable[str] | None = None,
        frameworks: Iterable[str] | None = None,
        licenses: Iterable[str] | None = None,
        author: str | None = None,
        year: int | None = None,
    ) -> list:
        predicates = [
            Resource.visibility == "public",
            Resource.review_status == "PUBLISHED",
            Resource.is_hidden.is_(False),
        ]
        normalized_types = SearchService.normalize_types(resource_types)
        if normalized_types:
            predicates.append(Resource.resource_type.in_(normalized_types))
        for tag in _values(tags):
            predicates.append(Resource.tags.any(func.lower(Tag.name) == tag.lower()))
        fields = [value.lower() for value in _values(research_fields)]
        if fields:
            predicates.append(func.lower(func.coalesce(Resource.research_field, "")).in_(fields))
        frameworks = [value.lower() for value in _values(frameworks)]
        if frameworks:
            predicates.append(Resource.model.has(func.lower(func.coalesce(Model.framework, "")).in_(frameworks)))
        licenses = [value.lower() for value in _values(licenses)]
        if licenses:
            predicates.append(func.lower(Resource.license).in_(licenses))
        if author and author.strip():
            predicates.append(Resource.author.has(User.username.ilike(f"%{author.strip()}%")))
        if year is not None:
            predicates.append(Resource.paper.has(Paper.year == year))
        return predicates

    @staticmethod
    def text_predicate(query: str | None):
        if not query or not query.strip():
            return None
        needle = f"%{query.strip()}%"
        return or_(
            Resource.title.ilike(needle),
            func.coalesce(Resource.description, "").ilike(needle),
            Resource.tags.any(Tag.name.ilike(needle)),
            Resource.author.has(or_(User.username.ilike(needle), func.coalesce(User.display_name, "").ilike(needle))),
            Resource.model.has(or_(func.coalesce(Model.framework, "").ilike(needle), func.coalesce(Model.task, "").ilike(needle))),
            Resource.dataset.has(or_(func.coalesce(Dataset.name, "").ilike(needle), func.coalesce(Dataset.task, "").ilike(needle), func.coalesce(Dataset.format, "").ilike(needle))),
            Resource.paper.has(or_(Paper.title.ilike(needle), func.coalesce(Paper.authors, "").ilike(needle), func.coalesce(Paper.journal, "").ilike(needle), func.coalesce(Paper.abstract, "").ilike(needle))),
            Resource.project.has(or_(func.coalesce(Project.leader, "").ilike(needle), func.coalesce(Project.members, "").ilike(needle), func.coalesce(Project.status, "").ilike(needle))),
            Resource.algorithm.has(or_(func.coalesce(Algorithm.category, "").ilike(needle), func.coalesce(Algorithm.difficulty, "").ilike(needle))),
        )

    @staticmethod
    def relevance_expression(query: str):
        normalized = query.strip().lower()
        if not normalized:
            return Resource.updated_time
        exact = normalized
        prefix = f"{normalized}%"
        contains = f"%{normalized}%"
        return case(
            (func.lower(Resource.title) == exact, 100),
            (func.lower(Resource.title).like(prefix), 80),
            (func.lower(Resource.title).like(contains), 65),
            (Resource.tags.any(func.lower(Tag.name).like(contains)), 55),
            (Resource.author.has(or_(func.lower(User.username).like(contains), func.lower(func.coalesce(User.display_name, "")).like(contains))), 50),
            (Resource.model.has(or_(func.lower(func.coalesce(Model.framework, "")).like(contains), func.lower(func.coalesce(Model.task, "")).like(contains))), 40),
            (Resource.paper.has(or_(func.lower(Paper.title).like(contains), func.lower(func.coalesce(Paper.authors, "")).like(contains), func.lower(func.coalesce(Paper.journal, "")).like(contains))), 38),
            (func.lower(func.coalesce(Resource.description, "")).like(contains), 30),
            else_=0,
        )

    @staticmethod
    def trending_expression():
        cutoff = datetime.utcnow() - timedelta(days=30)
        star_count = select(func.count(ResourceStar.id)).where(ResourceStar.resource_id == Resource.id, ResourceStar.created_at >= cutoff).correlate(Resource).scalar_subquery()
        download_count = select(func.count(ResourceDownload.id)).where(ResourceDownload.resource_id == Resource.id, ResourceDownload.created_at >= cutoff).correlate(Resource).scalar_subquery()
        view_count = select(func.count(ResourceView.id)).where(ResourceView.resource_id == Resource.id, ResourceView.created_at >= cutoff).correlate(Resource).scalar_subquery()
        return (func.coalesce(star_count, 0) * 5) + (func.coalesce(download_count, 0) * 3) + (func.coalesce(view_count, 0) * 0.2)

    @staticmethod
    def portal_trending_expression(cutoff: datetime):
        star_count = select(func.count(ResourceStar.id)).where(ResourceStar.resource_id == Resource.id, ResourceStar.created_at >= cutoff).correlate(Resource).scalar_subquery()
        download_count = select(func.count(ResourceDownload.id)).where(ResourceDownload.resource_id == Resource.id, ResourceDownload.created_at >= cutoff).correlate(Resource).scalar_subquery()
        view_count = select(func.count(ResourceView.id)).where(ResourceView.resource_id == Resource.id, ResourceView.created_at >= cutoff).correlate(Resource).scalar_subquery()
        activity_count = select(func.count(ResourceActivity.id)).where(ResourceActivity.resource_id == Resource.id, ResourceActivity.created_at >= cutoff).correlate(Resource).scalar_subquery()
        return (func.coalesce(star_count, 0) * 5) + (func.coalesce(download_count, 0) * 3) + (func.coalesce(view_count, 0) * 0.2) + (func.coalesce(activity_count, 0) * 2)

    @staticmethod
    def portal_trending(db: Session, *, period: str, resource_type: str | None, limit: int, user_id: int | None) -> list[dict]:
        days = {"day": 1, "week": 7, "month": 30}[period]
        score = SearchService.portal_trending_expression(datetime.utcnow() - timedelta(days=days))
        query = resource_query().where(Resource.visibility == "public", Resource.review_status == "PUBLISHED", Resource.is_hidden.is_(False))
        if resource_type:
            query = query.where(Resource.resource_type == resource_type)
        resources = db.scalars(query.order_by(score.desc(), Resource.updated_time.desc()).limit(limit)).unique().all()
        starred, favorited = EngagementService.interaction_ids(db, user_id, [item.id for item in resources])
        return [{**serialize_resource(item, starred, favorited), "score": float(db.scalar(select(score).where(Resource.id == item.id)) or 0)} for item in resources]

    @staticmethod
    def order(query: str | None, sort: str):
        if sort not in SORT_OPTIONS:
            raise ValueError("Unsupported sort option")
        if sort == "relevance":
            if query and query.strip():
                score = SearchService.relevance_expression(query)
                return (score.desc(), Resource.updated_time.desc())
            return (Resource.updated_time.desc(),)
        if sort == "oldest":
            return (Resource.created_time.asc(),)
        if sort == "stars":
            return (Resource.stars.desc(), Resource.updated_time.desc())
        if sort == "downloads":
            return (Resource.downloads.desc(), Resource.updated_time.desc())
        if sort == "views":
            return (Resource.views.desc(), Resource.updated_time.desc())
        if sort == "trending":
            return (SearchService.trending_expression().desc(), Resource.updated_time.desc())
        return (Resource.updated_time.desc(),)

    @staticmethod
    def result(db: Session, *, query: str | None, resource_types: list[str] | None, tags: list[str] | None, research_fields: list[str] | None, frameworks: list[str] | None, licenses: list[str] | None, author: str | None, year: int | None, sort: str, page: int, page_size: int, user_id: int | None) -> dict:
        predicates = SearchService.filters(resource_types=resource_types, tags=tags, research_fields=research_fields, frameworks=frameworks, licenses=licenses, author=author, year=year)
        text_predicate = SearchService.text_predicate(query)
        if text_predicate is not None:
            predicates.append(text_predicate)
        id_query = select(Resource.id).where(*predicates).distinct()
        total = int(db.scalar(select(func.count()).select_from(id_query.subquery())) or 0)
        order = SearchService.order(query, sort)
        resources = db.scalars(resource_query().where(Resource.id.in_(id_query)).order_by(*order).offset((page - 1) * page_size).limit(page_size)).unique().all()
        starred, favorited = EngagementService.interaction_ids(db, user_id, [resource.id for resource in resources])
        counts = {
            resource_type.upper(): int(count)
            for resource_type, count in db.execute(select(Resource.resource_type, func.count(Resource.id)).where(Resource.id.in_(id_query)).group_by(Resource.resource_type)).all()
        }
        facets = SearchService.facets(db, id_query)
        return {
            "items": [serialize_resource(resource, starred, favorited) for resource in resources],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
            "counts": counts,
            "facets": facets,
        }

    @staticmethod
    def facets(db: Session, id_query) -> dict:
        resource_ids = id_query.subquery()
        def values(statement):
            return [str(value) for value in db.scalars(statement).all() if value]
        return {
            "research_fields": values(select(Resource.research_field).where(Resource.id.in_(select(resource_ids.c.id)), Resource.research_field.is_not(None)).distinct().order_by(Resource.research_field)),
            "tags": values(select(Tag.name).join(Tag.resources).where(Resource.id.in_(select(resource_ids.c.id))).distinct().order_by(Tag.name)),
            "frameworks": values(select(Model.framework).join(Model.resource).where(Resource.id.in_(select(resource_ids.c.id)), Model.framework != "").distinct().order_by(Model.framework)),
            "licenses": values(select(Resource.license).where(Resource.id.in_(select(resource_ids.c.id))).distinct().order_by(Resource.license)),
            "years": [int(value) for value in db.scalars(select(Paper.year).join(Paper.resource).where(Resource.id.in_(select(resource_ids.c.id)), Paper.year.is_not(None)).distinct().order_by(Paper.year.desc())).all()],
        }

    @staticmethod
    def log_query(db: Session, query: str | None, user_id: int | None, result_count: int) -> None:
        normalized = (query or "").strip()
        if len(normalized) < 3 or len(normalized) > 80 or _SENSITIVE_SEARCH.search(normalized):
            return
        db.add(SearchQuery(query=normalized[:80], user_id=user_id, result_count=result_count))
        db.commit()

    @staticmethod
    def suggestions(db: Session, query: str, limit: int = 10) -> list[dict]:
        normalized = query.strip()
        if not normalized:
            return []
        needle = f"%{normalized}%"
        suggestions: list[dict] = []
        resources = db.scalars(
            select(Resource).where(
                Resource.visibility == "public",
                Resource.review_status == "PUBLISHED",
                Resource.is_hidden.is_(False),
                Resource.title.ilike(needle),
            ).order_by(Resource.stars.desc(), Resource.updated_time.desc()).limit(limit)
        ).all()
        for resource in resources:
            suggestions.append({"kind": "resource", "label": resource.title, "resource_id": resource.id, "resource_type": resource.resource_type})
        remaining = max(0, limit - len(suggestions))
        if remaining:
            for tag in db.scalars(select(Tag).where(Tag.name.ilike(needle)).order_by(Tag.name).limit(remaining)).all():
                suggestions.append({"kind": "tag", "label": tag.name})
        remaining = max(0, limit - len(suggestions))
        if remaining:
            fields = db.scalars(select(Resource.research_field).where(
                Resource.visibility == "public",
                Resource.review_status == "PUBLISHED",
                Resource.is_hidden.is_(False),
                Resource.research_field.is_not(None),
                Resource.research_field.ilike(needle),
            ).distinct().order_by(Resource.research_field).limit(remaining)).all()
            suggestions.extend({"kind": "research_field", "label": field} for field in fields if field)
        return suggestions[:limit]

    @staticmethod
    def trending_queries(db: Session, limit: int = 10) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=30)
        normalized_query = func.lower(SearchQuery.query)
        rows = db.execute(
            select(normalized_query.label("query"), func.count(SearchQuery.id).label("count"))
            .where(SearchQuery.created_at >= cutoff, SearchQuery.result_count > 0)
            .group_by(normalized_query)
            .having(func.count(SearchQuery.id) >= 3)
            .order_by(func.count(SearchQuery.id).desc(), func.max(SearchQuery.created_at).desc())
            .limit(limit * 4)
        ).all()
        return [{"query": query, "count": int(count)} for query, count in rows if _SAFE_TRENDING.fullmatch(query or "")][:limit]

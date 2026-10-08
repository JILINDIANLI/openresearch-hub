from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.security import get_optional_user
from ..database.database import get_db
from ..database.models import User
from .schemas import SearchResponse, SearchSuggestion, TrendingSearch
from .service import SORT_OPTIONS, SearchService

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("", response_model=SearchResponse, summary="Search public research resources")
def search(
    q: str | None = Query(default=None, max_length=200, description="Keyword, case-insensitive and partial-match supported."),
    resource_type: list[str] | None = Query(default=None, alias="type"),
    tag: list[str] | None = Query(default=None, description="Repeat tag to require multiple tags."),
    research_field: list[str] | None = Query(default=None),
    framework: list[str] | None = Query(default=None),
    license: list[str] | None = Query(default=None),
    author: str | None = Query(default=None, max_length=120),
    year: int | None = Query(default=None, ge=1900, le=2100),
    sort: str | None = Query(default=None, description="relevance, newest, oldest, stars, downloads, views, trending"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, description="Maximum effective page size is 100."),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    normalized_query = (q or "").strip() or None
    selected_sort = (sort or ("relevance" if normalized_query else "newest")).lower()
    if selected_sort not in SORT_OPTIONS:
        raise HTTPException(status_code=422, detail="sort must be relevance, newest, oldest, stars, downloads, views, or trending")
    try:
        SearchService.normalize_types(resource_type)
        result = SearchService.result(
            db,
            query=normalized_query,
            resource_types=resource_type,
            tags=tag,
            research_fields=research_field,
            frameworks=framework,
            licenses=license,
            author=author,
            year=year,
            sort=selected_sort,
            page=page,
            page_size=min(page_size, 100),
            user_id=current_user.id if current_user else None,
        )
        SearchService.log_query(db, normalized_query, current_user.id if current_user else None, result["total"])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/suggestions", response_model=list[SearchSuggestion], summary="Autocomplete titles, tags, and research fields")
def suggestions(q: str = Query(min_length=1, max_length=200), limit: int = Query(default=10, ge=1, le=10), db: Session = Depends(get_db)):
    return SearchService.suggestions(db, q, limit)


@router.get("/trending", response_model=list[TrendingSearch], summary="Popular real search queries from the recent 30 days")
def trending_searches(limit: int = Query(default=10, ge=1, le=20), db: Session = Depends(get_db)):
    return SearchService.trending_queries(db, limit)

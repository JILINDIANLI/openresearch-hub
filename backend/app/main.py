from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .core.config import settings
from sqlalchemy import text

from .core.cache import redis_client
from .core.operations import operations_middleware
from .files.router import files_router, resource_files_router
from .engagement.router import router as engagement_router
from .services.storage_service import storage_service
from .auth.router import router as auth_router
from .database.database import Base, engine, ensure_database_directory, ensure_schema_compatibility, ensure_sqlite_compatibility
from .database import models as _models
from .projects.router import router as projects_router
from .resources.router import router as resources_router
from .search.router import router as search_router
from .repositories.router import router as repositories_router
from .versions.router import router as versions_router
from .community.router import resource_router as community_resource_router, router as community_router, notifications_router
from .showcases.router import resource_router as showcase_resource_router, router as showcase_router, result_router as showcase_result_router
from .tags.router import router as tags_router
from .users.router import router as users_router
from .seed import seed_database
from .admin.router import router as admin_router
from .statistics.router import router as statistics_router
from .admin.service import service_status
from .core.security import require_admin
from .database.models import User

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "uploads"


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database_directory()
    if settings.app_env != "production":
        ensure_sqlite_compatibility()
        Base.metadata.create_all(bind=engine)
        ensure_schema_compatibility()
        seed_database()
    storage_service.ensure_bucket()
    yield


logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)
app.middleware("http")(operations_middleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(tags_router)
app.include_router(resources_router)
app.include_router(projects_router)
app.include_router(search_router)
app.include_router(repositories_router)
app.include_router(versions_router)
app.include_router(community_resource_router)
app.include_router(community_router)
app.include_router(notifications_router)
app.include_router(showcase_resource_router)
app.include_router(showcase_router)
app.include_router(showcase_result_router)
app.include_router(resource_files_router)
app.include_router(files_router)
app.include_router(engagement_router)
app.include_router(admin_router)
app.include_router(statistics_router)


@app.get("/api/health", tags=["System"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["System"])
def readiness() -> JSONResponse:
    checks: dict[str, dict[str, str | float]] = {}
    started = perf_counter()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok", "response_ms": round((perf_counter() - started) * 1000, 2)}
    except Exception:
        checks["postgres"] = {"status": "unavailable"}
    started = perf_counter()
    try:
        redis_client().ping()
        checks["redis"] = {"status": "ok", "response_ms": round((perf_counter() - started) * 1000, 2)}
    except Exception:
        checks["redis"] = {"status": "unavailable"}
    started = perf_counter()
    try:
        from .storage.minio_client import get_minio_client
        get_minio_client().bucket_exists(settings.minio_bucket)
        checks["minio"] = {"status": "ok", "response_ms": round((perf_counter() - started) * 1000, 2)}
    except Exception:
        checks["minio"] = {"status": "unavailable"}
    started = perf_counter()
    try:
        from urllib.request import Request, urlopen
        with urlopen(Request(settings.gitea_internal_url + "/api/healthz"), timeout=settings.gitea_timeout) as response:
            checks["gitea"] = {"status": "ok" if response.status < 400 else "unavailable", "response_ms": round((perf_counter() - started) * 1000, 2)}
    except Exception:
        checks["gitea"] = {"status": "unavailable"}
    ready = all(item["status"] == "ok" for item in checks.values())
    return JSONResponse({"status": "ok" if ready else "unavailable", "checks": checks, "updated_at": datetime.now(timezone.utc).isoformat()}, status_code=200 if ready else 503)


@app.get("/api/version", tags=["System"])
def version() -> dict:
    return {"name": "OpenResearch Hub", "version": settings.app_version}


@app.get("/api/admin/system", tags=["Admin Center"])
def system_status(_: User = Depends(require_admin)) -> dict:
    from .database.database import SessionLocal
    started = perf_counter()
    with SessionLocal() as db:
        statuses = service_status(db)
    statuses["Backend"] = {"status": "Running", "response_ms": round((perf_counter() - started) * 1000, 2)}
    statuses["Nginx"] = {"status": "Behind reverse proxy", "response_ms": None}
    return {"services": statuses, "updated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


@app.get("/publish", include_in_schema=False)
def publish_page() -> FileResponse:
    return FileResponse(ROOT / "publish.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})

@app.get("/register", include_in_schema=False)
def register_page() -> FileResponse:
    return FileResponse(ROOT / "register.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(ROOT / "login.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/users/{username}", include_in_schema=False)
def user_profile_page(username: str) -> FileResponse:
    return FileResponse(ROOT / "user-profile.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/resources/{resource_id}", include_in_schema=False)
def resource_detail_page(resource_id: int) -> FileResponse:
    return FileResponse(ROOT / "resource-detail.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


@app.get("/resources/{resource_id}/showcase", include_in_schema=False)
def showcase_page(resource_id: int) -> FileResponse:
    return FileResponse(ROOT / "showcase.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


@app.get("/resources/{resource_id}/versions/{version}", include_in_schema=False)
def version_detail_page(resource_id: int, version: str) -> FileResponse:
    return FileResponse(ROOT / "version-detail.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


@app.get("/discussions/{discussion_id}", include_in_schema=False)
def discussion_detail_page(discussion_id: int) -> FileResponse:
    return FileResponse(ROOT / "discussion-detail.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/issues/{issue_id}", include_in_schema=False)
def issue_detail_page(issue_id: int) -> FileResponse:
    return FileResponse(ROOT / "issue-detail.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/search", include_in_schema=False)
def search_page() -> FileResponse:
    return FileResponse(ROOT / "search.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


@app.get("/statistics", include_in_schema=False)
def statistics_page() -> FileResponse:
    return FileResponse(ROOT / "statistics.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


@app.get("/admin", include_in_schema=False)
@app.get("/admin/{admin_path:path}", include_in_schema=False)
def admin_page(admin_path: str = "") -> FileResponse:
    return FileResponse(ROOT / "admin.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})


app.mount("/", StaticFiles(directory=ROOT, html=True), name="frontend_assets")

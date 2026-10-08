from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


class Settings:
    app_env: str = os.getenv("APP_ENV", "development").lower()
    app_name: str = os.getenv("APP_NAME", "OpenResearch Hub API")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    enable_api_docs: bool = os.getenv("ENABLE_API_DOCS", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    trusted_hosts: list[str] = [item.strip() for item in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if item.strip()]
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'data' / 'openresearch.db').as_posix()}")
    redis_url: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    secret_key: str = os.getenv("SECRET_KEY", "")
    jwt_secret: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", ""))
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "")
    # Containers use the internal endpoint; browsers must receive a host-reachable URL.
    minio_public_endpoint: str = os.getenv("MINIO_PUBLIC_ENDPOINT", os.getenv("MINIO_ENDPOINT", ""))
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "openresearch-resources")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    minio_public_secure: bool = os.getenv("MINIO_PUBLIC_SECURE", os.getenv("MINIO_SECURE", "false")).lower() == "true"
    gitea_url: str = os.getenv("GITEA_URL", "http://127.0.0.1:3000").rstrip("/")
    gitea_internal_url: str = os.getenv("GITEA_INTERNAL_URL", os.getenv("GITEA_URL", "http://127.0.0.1:3000")).rstrip("/")
    gitea_api_url: str = os.getenv("GITEA_API_URL", "http://127.0.0.1:3000/api/v1").rstrip("/")
    gitea_token: str = os.getenv("GITEA_TOKEN", "")
    gitea_default_owner: str = os.getenv("GITEA_DEFAULT_OWNER", "openresearch")
    gitea_http_port: int = int(os.getenv("GITEA_HTTP_PORT", "3000"))
    gitea_ssh_port: int = int(os.getenv("GITEA_SSH_PORT", "2222"))
    gitea_timeout: float = float(os.getenv("GITEA_TIMEOUT", "8"))
    max_upload_size: int = int(os.getenv("MAX_UPLOAD_SIZE", str(200 * 1024 * 1024)))
    community_cache_ttl: int = int(os.getenv("COMMUNITY_CACHE_TTL", "120"))
    discussion_rate_limit: int = int(os.getenv("DISCUSSION_RATE_LIMIT", "5"))
    issue_rate_limit: int = int(os.getenv("ISSUE_RATE_LIMIT", "5"))
    comment_rate_limit: int = int(os.getenv("COMMENT_RATE_LIMIT", "10"))
    community_rate_limit_window_seconds: int = int(os.getenv("COMMUNITY_RATE_LIMIT_WINDOW_SECONDS", "60"))
    cors_origins: list[str] = [
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
        if item.strip()
    ]
    login_rate_limit: int = int(os.getenv("LOGIN_RATE_LIMIT", "8"))
    register_rate_limit: int = int(os.getenv("REGISTER_RATE_LIMIT", "5"))
    upload_rate_limit: int = int(os.getenv("UPLOAD_RATE_LIMIT", "12"))
    search_suggestions_rate_limit: int = int(os.getenv("SEARCH_SUGGESTIONS_RATE_LIMIT", "60"))
    search_rate_limit: int = int(os.getenv("SEARCH_RATE_LIMIT", "90"))
    api_rate_limit_window_seconds: int = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))


settings = Settings()

if not settings.secret_key:
    raise RuntimeError("SECRET_KEY must be configured in .env before starting OpenResearch Hub")
if not all((settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key)):
    raise RuntimeError("MINIO_ENDPOINT, MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be configured in .env")

if settings.app_env == "production":
    weak_values = {"change-this-secret-key", "change-me", "change-me-in-production", "openresearch", "secret", "password"}
    if len(settings.secret_key) < 32 or settings.secret_key.lower() in weak_values:
        raise RuntimeError("Production SECRET_KEY must be unique and at least 32 characters")
    if len(settings.jwt_secret) < 32 or settings.jwt_secret.lower() in weak_values:
        raise RuntimeError("Production JWT_SECRET must be unique and at least 32 characters")
    if settings.minio_access_key.lower() in weak_values or len(settings.minio_secret_key) < 24 or settings.minio_secret_key.lower() in weak_values:
        raise RuntimeError("Production MinIO credentials are weak or use a placeholder")
    if len(os.getenv("POSTGRES_PASSWORD", "")) < 24 or os.getenv("POSTGRES_PASSWORD", "").lower() in weak_values:
        raise RuntimeError("Production POSTGRES_PASSWORD must be unique and at least 24 characters")
    redis_password = os.getenv("REDIS_PASSWORD", "")
    if len(redis_password) < 24 or redis_password.lower() in weak_values:
        raise RuntimeError("Production REDIS_PASSWORD must be unique and at least 24 characters")
    if "*" in settings.cors_origins:
        raise RuntimeError("CORS_ORIGINS cannot contain '*' in production")
    if not settings.trusted_hosts or "*" in settings.trusted_hosts:
        raise RuntimeError("Production TRUSTED_HOSTS must explicitly list allowed hostnames")

if settings.database_url.startswith("sqlite:///./"):
    relative_path = settings.database_url.removeprefix("sqlite:///./")
    settings.database_url = f"sqlite:///{(ROOT / relative_path).as_posix()}"

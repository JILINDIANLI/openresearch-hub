from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..core.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
pool_options = {} if settings.database_url.startswith("sqlite") else {
    "pool_size": int(__import__("os").getenv("DB_POOL_SIZE", "10")),
    "max_overflow": int(__import__("os").getenv("DB_MAX_OVERFLOW", "20")),
}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True, **pool_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ensure_database_directory() -> None:
    if settings.database_url.startswith("sqlite"):
        database_path = Path(settings.database_url.removeprefix("sqlite:///"))
        database_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_sqlite_compatibility() -> None:
    """Allow nullable resource authors in an existing V1 SQLite database."""
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "resources" not in inspector.get_table_names():
        return
    author_column = next((column for column in inspector.get_columns("resources") if column["name"] == "author_id"), None)
    if author_column is None or author_column.get("nullable", True):
        return
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("ALTER TABLE resources RENAME TO resources_v1"))
        connection.execute(text("""
            CREATE TABLE resources (
                id INTEGER NOT NULL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                resource_type VARCHAR(40) NOT NULL,
                description TEXT NOT NULL,
                author_id INTEGER,
                created_time DATETIME NOT NULL,
                updated_time DATETIME NOT NULL,
                views INTEGER NOT NULL,
                stars INTEGER NOT NULL,
                downloads INTEGER NOT NULL,
                license VARCHAR(80) NOT NULL,
                visibility VARCHAR(30) NOT NULL,
                details_json TEXT NOT NULL,
                FOREIGN KEY(author_id) REFERENCES users (id)
            )
        """))
        connection.execute(text("""
            INSERT INTO resources
            (id, title, resource_type, description, author_id, created_time,
             updated_time, views, stars, downloads, license, visibility, details_json)
            SELECT id, title, resource_type, description, author_id, created_time,
                   updated_time, views, stars, downloads, license, visibility, details_json
            FROM resources_v1
        """))
        connection.execute(text("DROP TABLE resources_v1"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_resources_title ON resources (title)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_resources_resource_type ON resources (resource_type)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_resources_visibility ON resources (visibility)"))
        connection.execute(text("PRAGMA foreign_keys=ON"))


def ensure_schema_compatibility() -> None:
    """Apply additive changes for both the bundled demo DB and an existing Postgres volume.

    The project historically initialized tables with ``create_all``. These small,
    idempotent upgrades keep that existing database usable while the formal
    migration history is introduced later.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "users" in tables:
            columns = {column["name"] for column in inspect(connection).get_columns("users")}
            user_columns = {
                "display_name": "VARCHAR(120)",
                "avatar_url": "VARCHAR(500)",
                "research_interests": "TEXT",
                "website_url": "VARCHAR(500)",
                "github_url": "VARCHAR(500)",
                "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
                "created_at": "TIMESTAMP",
                "updated_at": "TIMESTAMP",
                "token_version": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, definition in user_columns.items():
                if name in columns:
                    continue
                if settings.database_url.startswith("sqlite"):
                    sqlite_definition = definition.replace("VARCHAR", "TEXT").replace("BOOLEAN", "INTEGER").replace("TIMESTAMP", "DATETIME")
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sqlite_definition}"))
                else:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {definition}"))
            if "created_at" in {column["name"] for column in inspect(connection).get_columns("users")}:
                connection.execute(text("UPDATE users SET created_at = created_time WHERE created_at IS NULL"))
            if "updated_at" in {column["name"] for column in inspect(connection).get_columns("users")}:
                connection.execute(text("UPDATE users SET updated_at = created_time WHERE updated_at IS NULL"))
        if "resources" in tables:
            columns = {column["name"] for column in inspect(connection).get_columns("resources")}
            resource_columns = {
                "research_field": "VARCHAR(255)",
                "thumbnail_url": "VARCHAR(500)",
                "repository_url": "VARCHAR(500)",
                "homepage_url": "VARCHAR(500)",
                "favorites_count": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, definition in resource_columns.items():
                if name in columns:
                    continue
                if settings.database_url.startswith("sqlite"):
                    connection.execute(text(f"ALTER TABLE resources ADD COLUMN {name} {definition}"))
                else:
                    connection.execute(text(f"ALTER TABLE resources ADD COLUMN IF NOT EXISTS {name} {definition}"))
            existing_columns = {column["name"] for column in inspect(connection).get_columns("resources")}
            for name, definition in {
                "review_status": "VARCHAR(20) NOT NULL DEFAULT 'PUBLISHED'",
                "review_note": "TEXT NOT NULL DEFAULT ''",
                "is_featured": "BOOLEAN NOT NULL DEFAULT FALSE",
                "is_hidden": "BOOLEAN NOT NULL DEFAULT FALSE",
            }.items():
                if name in existing_columns:
                    continue
                if settings.database_url.startswith("sqlite"):
                    connection.execute(text(f"ALTER TABLE resources ADD COLUMN {name} {definition.replace('BOOLEAN', 'INTEGER')}"))
                else:
                    connection.execute(text(f"ALTER TABLE resources ADD COLUMN IF NOT EXISTS {name} {definition}"))
        if "users" in tables:
            existing_columns = {column["name"] for column in inspect(connection).get_columns("users")}
            if "role" not in existing_columns:
                if settings.database_url.startswith("sqlite"):
                    connection.execute(text("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'USER'"))
                else:
                    connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'USER'"))
        for table_name in ("discussions", "issues", "discussion_comments", "issue_comments"):
            if table_name not in tables:
                continue
            columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
            if "is_hidden" not in columns:
                definition = "INTEGER NOT NULL DEFAULT 0" if settings.database_url.startswith("sqlite") else "BOOLEAN NOT NULL DEFAULT FALSE"
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN is_hidden {definition}"))
        if "resource_showcases" in tables:
            columns = {column["name"] for column in inspect(connection).get_columns("resource_showcases")}
            for name in ("is_featured", "is_hidden"):
                if name not in columns:
                    definition = "INTEGER NOT NULL DEFAULT 0" if settings.database_url.startswith("sqlite") else "BOOLEAN NOT NULL DEFAULT FALSE"
                    connection.execute(text(f"ALTER TABLE resource_showcases ADD COLUMN {name} {definition}"))
        if "admin_logs" not in tables:
            id_definition = "INTEGER PRIMARY KEY AUTOINCREMENT" if settings.database_url.startswith("sqlite") else "BIGSERIAL PRIMARY KEY"
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id {id_definition},
                    admin_id INTEGER NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    target_type VARCHAR(60) NOT NULL,
                    target_id INTEGER,
                    detail TEXT NOT NULL DEFAULT '',
                    created_time TIMESTAMP NOT NULL
                )
            """.format(id_definition=id_definition)))
        if "datasets" in tables:
            columns = {column["name"] for column in inspect(connection).get_columns("datasets")}
            dataset_columns = {"task": "VARCHAR(255) NOT NULL DEFAULT ''", "download_url": "VARCHAR(500)"}
            for name, definition in dataset_columns.items():
                if name in columns:
                    continue
                if settings.database_url.startswith("sqlite"):
                    connection.execute(text(f"ALTER TABLE datasets ADD COLUMN {name} {definition}"))
                else:
                    connection.execute(text(f"ALTER TABLE datasets ADD COLUMN IF NOT EXISTS {name} {definition}"))
        if "resource_files" in tables:
            columns = {column["name"] for column in inspect(connection).get_columns("resource_files")}
            file_columns = {
                "uploader_id": "INTEGER",
                "original_filename": "VARCHAR(255)",
                "stored_filename": "VARCHAR(255)",
                "object_key": "VARCHAR(700)",
                "bucket_name": "VARCHAR(120)",
                "mime_type": "VARCHAR(160)",
                "file_extension": "VARCHAR(32)",
                "file_size": "INTEGER NOT NULL DEFAULT 0",
                "file_kind": "VARCHAR(40) NOT NULL DEFAULT 'OTHER'",
                "sha256": "VARCHAR(64)",
                "description": "TEXT",
                "download_count": "INTEGER NOT NULL DEFAULT 0",
                "created_at": "TIMESTAMP",
                "updated_at": "TIMESTAMP",
            }
            for name, definition in file_columns.items():
                if name in columns:
                    continue
                if settings.database_url.startswith("sqlite"):
                    sqlite_definition = definition.replace("VARCHAR", "TEXT").replace("TIMESTAMP", "DATETIME")
                    connection.execute(text(f"ALTER TABLE resource_files ADD COLUMN {name} {sqlite_definition}"))
                else:
                    connection.execute(text(f"ALTER TABLE resource_files ADD COLUMN IF NOT EXISTS {name} {definition}"))
            existing_columns = {column["name"] for column in inspect(connection).get_columns("resource_files")}
            if "created_at" in existing_columns:
                connection.execute(text("UPDATE resource_files SET created_at = created_time WHERE created_at IS NULL"))
            if "updated_at" in existing_columns:
                connection.execute(text("UPDATE resource_files SET updated_at = created_time WHERE updated_at IS NULL"))

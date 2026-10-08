"""Add search query analytics and PostgreSQL partial-search indexes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_search_discovery_v1"
down_revision = "0005_engagement_trending_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "search_queries" not in inspector.get_table_names():
        op.create_table(
            "search_queries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("query", sa.String(length=200), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes("search_queries")}
    for name, columns in (("ix_search_queries_query", ["query"]), ("ix_search_queries_user_id", ["user_id"]), ("ix_search_queries_created_at", ["created_at"])):
        if name not in indexes:
            op.create_index(name, "search_queries", columns)
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute("CREATE INDEX IF NOT EXISTS ix_resources_title_trgm ON resources USING gin (title gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_resources_description_trgm ON resources USING gin (description gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_users_username_trgm ON users USING gin (username gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_users_display_name_trgm ON users USING gin (display_name gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_tags_name_trgm ON tags USING gin (name gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_models_framework_trgm ON models USING gin (framework gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_models_task_trgm ON models USING gin (task gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_papers_title_trgm ON papers USING gin (title gin_trgm_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_papers_authors_trgm ON papers USING gin (authors gin_trgm_ops)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for index in ("ix_papers_authors_trgm", "ix_papers_title_trgm", "ix_models_task_trgm", "ix_models_framework_trgm", "ix_tags_name_trgm", "ix_users_display_name_trgm", "ix_users_username_trgm", "ix_resources_description_trgm", "ix_resources_title_trgm"):
            op.execute(f"DROP INDEX IF EXISTS {index}")
    op.drop_index("ix_search_queries_created_at", table_name="search_queries")
    op.drop_index("ix_search_queries_user_id", table_name="search_queries")
    op.drop_index("ix_search_queries_query", table_name="search_queries")
    op.drop_table("search_queries")

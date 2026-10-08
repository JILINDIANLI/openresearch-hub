"""Add stars, favorites, views, downloads, and activity tracking."""

from alembic import op
import sqlalchemy as sa


revision = "0005_engagement_trending_v1"
down_revision = "0004_file_storage_assets_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resources", sa.Column("favorites_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("resource_stars", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id", "resource_id", name="uq_resource_stars_user_resource"))
    op.create_index("ix_resource_stars_user_id", "resource_stars", ["user_id"])
    op.create_index("ix_resource_stars_resource_id", "resource_stars", ["resource_id"])
    op.create_index("ix_resource_stars_created_at", "resource_stars", ["created_at"])
    op.create_table("resource_favorites", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id", "resource_id", name="uq_resource_favorites_user_resource"))
    op.create_index("ix_resource_favorites_user_id", "resource_favorites", ["user_id"])
    op.create_index("ix_resource_favorites_resource_id", "resource_favorites", ["resource_id"])
    op.create_index("ix_resource_favorites_created_at", "resource_favorites", ["created_at"])
    op.create_table("resource_views", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("session_id", sa.String(64), nullable=True), sa.Column("ip_hash", sa.String(64), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_resource_views_resource_id", "resource_views", ["resource_id"])
    op.create_index("ix_resource_views_user_id", "resource_views", ["user_id"])
    op.create_index("ix_resource_views_session_id", "resource_views", ["session_id"])
    op.create_index("ix_resource_views_created_at", "resource_views", ["created_at"])
    op.create_table("resource_downloads", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False), sa.Column("file_id", sa.Integer(), sa.ForeignKey("resource_files.id", ondelete="SET NULL"), nullable=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_resource_downloads_resource_id", "resource_downloads", ["resource_id"])
    op.create_index("ix_resource_downloads_file_id", "resource_downloads", ["file_id"])
    op.create_index("ix_resource_downloads_user_id", "resource_downloads", ["user_id"])
    op.create_index("ix_resource_downloads_created_at", "resource_downloads", ["created_at"])
    op.create_table("resource_activities", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("activity_type", sa.String(40), nullable=False), sa.Column("detail", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_resource_activities_resource_id", "resource_activities", ["resource_id"])
    op.create_index("ix_resource_activities_actor_id", "resource_activities", ["actor_id"])
    op.create_index("ix_resource_activities_activity_type", "resource_activities", ["activity_type"])
    op.create_index("ix_resource_activities_created_at", "resource_activities", ["created_at"])


def downgrade() -> None:
    for table, indexes in (("resource_activities", ["ix_resource_activities_created_at", "ix_resource_activities_activity_type", "ix_resource_activities_actor_id", "ix_resource_activities_resource_id"]), ("resource_downloads", ["ix_resource_downloads_created_at", "ix_resource_downloads_user_id", "ix_resource_downloads_file_id", "ix_resource_downloads_resource_id"]), ("resource_views", ["ix_resource_views_created_at", "ix_resource_views_session_id", "ix_resource_views_user_id", "ix_resource_views_resource_id"]), ("resource_favorites", ["ix_resource_favorites_created_at", "ix_resource_favorites_resource_id", "ix_resource_favorites_user_id"]), ("resource_stars", ["ix_resource_stars_created_at", "ix_resource_stars_resource_id", "ix_resource_stars_user_id"])):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
    op.drop_column("resources", "favorites_count")

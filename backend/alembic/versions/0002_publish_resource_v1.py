"""Add publish-resource fields and extension tables."""

from alembic import op
import sqlalchemy as sa


revision = "0002_publish_resource_v1"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resources", sa.Column("research_field", sa.String(255), nullable=True))
    op.add_column("resources", sa.Column("thumbnail_url", sa.String(500), nullable=True))
    op.add_column("resources", sa.Column("repository_url", sa.String(500), nullable=True))
    op.add_column("resources", sa.Column("homepage_url", sa.String(500), nullable=True))
    op.add_column("datasets", sa.Column("download_url", sa.String(500), nullable=True))
    op.create_table(
        "algorithms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("difficulty", sa.String(30), nullable=False, server_default=""),
        sa.Column("paper_url", sa.String(500)),
        sa.Column("code_url", sa.String(500)),
    )
    op.create_table(
        "demos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("video_url", sa.String(500)),
        sa.Column("project_url", sa.String(500)),
        sa.Column("duration", sa.String(40), nullable=False, server_default=""),
    )
    op.create_table(
        "tutorials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("difficulty", sa.String(30), nullable=False, server_default=""),
        sa.Column("duration", sa.String(40), nullable=False, server_default=""),
        sa.Column("content_url", sa.String(500)),
    )


def downgrade() -> None:
    op.drop_table("tutorials")
    op.drop_table("demos")
    op.drop_table("algorithms")
    op.drop_column("datasets", "download_url")
    op.drop_column("resources", "homepage_url")
    op.drop_column("resources", "repository_url")
    op.drop_column("resources", "thumbnail_url")
    op.drop_column("resources", "research_field")

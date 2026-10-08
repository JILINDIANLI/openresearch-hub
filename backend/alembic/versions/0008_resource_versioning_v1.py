"""Add resource versions and version-owned files."""

from alembic import op
import sqlalchemy as sa


revision = "0008_resource_versioning_v1"
down_revision = "0007_gitea_repositories_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("version_major", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_patch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("release_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("git_commit_sha", sa.String(120), nullable=True),
        sa.Column("git_branch", sa.String(255), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("downloads_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("resource_id", "version", name="uq_resource_versions_resource_version"),
    )
    for name, columns in (
        ("resource_id", ["resource_id"]),
        ("status", ["status"]),
        ("created_by", ["created_by"]),
        ("is_latest", ["is_latest"]),
        ("version_sort", ["version_major", "version_minor", "version_patch"]),
    ):
        op.create_index(f"ix_resource_versions_{name}", "resource_versions", columns)
    op.add_column("resource_files", sa.Column("version_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_resource_files_version_id", "resource_files", "resource_versions", ["version_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_resource_files_version_id", "resource_files", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_resource_files_version_id", table_name="resource_files")
    op.drop_constraint("fk_resource_files_version_id", "resource_files", type_="foreignkey")
    op.drop_column("resource_files", "version_id")
    for name in ("version_sort", "is_latest", "created_by", "status", "resource_id"):
        op.drop_index(f"ix_resource_versions_{name}", table_name="resource_versions")
    op.drop_table("resource_versions")

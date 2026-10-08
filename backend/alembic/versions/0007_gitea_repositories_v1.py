"""Add one-to-one Gitea repository associations for resources."""

from alembic import op
import sqlalchemy as sa


revision = "0007_gitea_repositories_v1"
down_revision = "0006_search_discovery_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="GITEA"),
        sa.Column("owner", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("full_name", sa.String(length=300), nullable=False),
        sa.Column("clone_url", sa.String(length=700), nullable=False, server_default=""),
        sa.Column("ssh_url", sa.String(length=700), nullable=False, server_default=""),
        sa.Column("web_url", sa.String(length=700), nullable=False, server_default=""),
        sa.Column("default_branch", sa.String(length=120), nullable=False, server_default="main"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(length=120), nullable=True),
        sa.Column("stars_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_issues_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_commit_at", sa.DateTime(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="PUBLIC"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("resource_id", name="uq_repositories_resource"),
        sa.UniqueConstraint("provider", "owner", "name", name="uq_repositories_provider_owner_name"),
    )
    op.create_index("ix_repositories_resource_id", "repositories", ["resource_id"])
    op.create_index("ix_repositories_provider", "repositories", ["provider"])
    op.create_index("ix_repositories_owner", "repositories", ["owner"])
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
    op.create_index("ix_repositories_visibility", "repositories", ["visibility"])


def downgrade() -> None:
    for name in ("ix_repositories_visibility", "ix_repositories_full_name", "ix_repositories_owner", "ix_repositories_provider", "ix_repositories_resource_id"):
        op.drop_index(name, table_name="repositories")
    op.drop_table("repositories")

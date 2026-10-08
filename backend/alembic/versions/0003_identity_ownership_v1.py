"""Add Identity and Ownership V1 user fields without removing legacy data."""

from alembic import op
import sqlalchemy as sa


revision = "0003_identity_ownership_v1"
down_revision = "0002_publish_resource_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("research_interests", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("website_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("github_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")
    op.execute("UPDATE users SET avatar_url = avatar WHERE avatar_url IS NULL")
    op.execute("UPDATE users SET research_interests = research_fields WHERE research_interests IS NULL")
    op.execute("UPDATE users SET created_at = created_time WHERE created_at IS NULL")
    op.execute("UPDATE users SET updated_at = created_time WHERE updated_at IS NULL")
    op.execute("UPDATE resources SET author_id = (SELECT id FROM users WHERE email = 'kai.shen@openresearch.local' LIMIT 1) WHERE author_id IS NULL")


def downgrade() -> None:
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "github_url")
    op.drop_column("users", "website_url")
    op.drop_column("users", "research_interests")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "display_name")

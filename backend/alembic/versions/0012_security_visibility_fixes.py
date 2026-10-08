"""Add session revocation and non-destructive comment moderation fields.

Revision ID: 0012_security_visibility_fixes
Revises: 0011_admin_center_v13
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_security_visibility_fixes"
down_revision = "0011_admin_center_v13"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    if "token_version" not in _columns("users"):
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))

    if "is_hidden" not in _columns("discussion_comments"):
        op.add_column("discussion_comments", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"))
    if "ix_discussion_comments_is_hidden" not in _indexes("discussion_comments"):
        op.create_index("ix_discussion_comments_is_hidden", "discussion_comments", ["is_hidden"])

    if "is_hidden" not in _columns("issue_comments"):
        op.add_column("issue_comments", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"))
    if "ix_issue_comments_is_hidden" not in _indexes("issue_comments"):
        op.create_index("ix_issue_comments_is_hidden", "issue_comments", ["is_hidden"])

    op.alter_column("resources", "review_status", existing_type=sa.String(20), existing_nullable=False, server_default="PENDING")


def downgrade() -> None:
    op.alter_column("resources", "review_status", existing_type=sa.String(20), existing_nullable=False, server_default="PUBLISHED")
    if "ix_issue_comments_is_hidden" in _indexes("issue_comments"):
        op.drop_index("ix_issue_comments_is_hidden", table_name="issue_comments")
    if "is_hidden" in _columns("issue_comments"):
        op.drop_column("issue_comments", "is_hidden")
    if "ix_discussion_comments_is_hidden" in _indexes("discussion_comments"):
        op.drop_index("ix_discussion_comments_is_hidden", table_name="discussion_comments")
    if "is_hidden" in _columns("discussion_comments"):
        op.drop_column("discussion_comments", "is_hidden")
    if "token_version" in _columns("users"):
        op.drop_column("users", "token_version")

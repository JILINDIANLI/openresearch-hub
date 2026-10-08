"""Add V13 administrator center fields and audit logs.

Revision ID: 0011_admin_center_v13
Revises: 0010_research_showcase_v1
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_admin_center_v13"
down_revision = "0010_research_showcase_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(20), nullable=False, server_default="USER"))
    op.create_index("ix_users_role", "users", ["role"])
    for name, type_, default in (
        ("review_status", sa.String(20), "PUBLISHED"),
        ("review_note", sa.Text(), ""),
        ("is_featured", sa.Boolean(), "false"),
        ("is_hidden", sa.Boolean(), "false"),
    ):
        op.add_column("resources", sa.Column(name, type_, nullable=False if name != "review_note" else True, server_default=default))
    op.create_index("ix_resources_review_status", "resources", ["review_status"])
    op.create_index("ix_resources_is_featured", "resources", ["is_featured"])
    op.create_index("ix_resources_is_hidden", "resources", ["is_hidden"])
    op.add_column("discussions", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_discussions_is_hidden", "discussions", ["is_hidden"])
    op.add_column("issues", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_issues_is_hidden", "issues", ["is_hidden"])
    op.add_column("resource_showcases", sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("resource_showcases", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_resource_showcases_is_featured", "resource_showcases", ["is_featured"])
    op.create_index("ix_resource_showcases_is_hidden", "resource_showcases", ["is_hidden"])
    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(60), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_time", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_logs_admin_id", "admin_logs", ["admin_id"])
    op.create_index("ix_admin_logs_action", "admin_logs", ["action"])
    op.create_index("ix_admin_logs_target_type", "admin_logs", ["target_type"])
    op.create_index("ix_admin_logs_target_id", "admin_logs", ["target_id"])
    op.create_index("ix_admin_logs_created_time", "admin_logs", ["created_time"])


def downgrade() -> None:
    for name in ("created_time", "target_id", "target_type", "action", "admin_id"):
        op.drop_index(f"ix_admin_logs_{name}", table_name="admin_logs")
    op.drop_table("admin_logs")
    for name in ("is_hidden", "is_featured"):
        op.drop_index(f"ix_resource_showcases_{name}", table_name="resource_showcases")
        op.drop_column("resource_showcases", name)
    op.drop_index("ix_issues_is_hidden", table_name="issues")
    op.drop_column("issues", "is_hidden")
    op.drop_index("ix_discussions_is_hidden", table_name="discussions")
    op.drop_column("discussions", "is_hidden")
    for name in ("is_hidden", "is_featured", "review_status"):
        op.drop_index(f"ix_resources_{name}", table_name="resources") if name != "review_status" else op.drop_index("ix_resources_review_status", table_name="resources")
        op.drop_column("resources", name)
    op.drop_column("resources", "review_note")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")

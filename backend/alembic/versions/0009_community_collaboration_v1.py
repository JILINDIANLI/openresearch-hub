"""Add V9 community and collaboration tables."""

from alembic import op
import sqlalchemy as sa


revision = "0009_community_collaboration_v1"
down_revision = "0008_resource_versioning_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discussions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("comments_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_discussions_resource_id", "discussions", ["resource_id"])
    op.create_index("ix_discussions_author_id", "discussions", ["author_id"])
    op.create_index("ix_discussions_status", "discussions", ["status"])
    op.create_index("ix_discussions_is_pinned", "discussions", ["is_pinned"])
    op.create_index("ix_discussions_created_at", "discussions", ["created_at"])
    op.create_index("ix_discussions_updated_at", "discussions", ["updated_at"])

    op.create_table(
        "discussion_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("discussion_id", sa.Integer(), sa.ForeignKey("discussions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("discussion_comments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_discussion_comments_discussion_id", "discussion_comments", ["discussion_id"])
    op.create_index("ix_discussion_comments_author_id", "discussion_comments", ["author_id"])
    op.create_index("ix_discussion_comments_parent_id", "discussion_comments", ["parent_id"])
    op.create_index("ix_discussion_comments_created_at", "discussion_comments", ["created_at"])
    op.create_index("ix_discussion_comments_is_deleted", "discussion_comments", ["is_deleted"])

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("issue_type", sa.String(30), nullable=False, server_default="OTHER"),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_issues_resource_id", "issues", ["resource_id"])
    op.create_index("ix_issues_author_id", "issues", ["author_id"])
    op.create_index("ix_issues_assignee_id", "issues", ["assignee_id"])
    op.create_index("ix_issues_status", "issues", ["status"])
    op.create_index("ix_issues_issue_type", "issues", ["issue_type"])
    op.create_index("ix_issues_priority", "issues", ["priority"])
    op.create_index("ix_issues_created_at", "issues", ["created_at"])
    op.create_index("ix_issues_updated_at", "issues", ["updated_at"])

    op.create_table(
        "issue_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("issue_comments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_issue_comments_issue_id", "issue_comments", ["issue_id"])
    op.create_index("ix_issue_comments_author_id", "issue_comments", ["author_id"])
    op.create_index("ix_issue_comments_parent_id", "issue_comments", ["parent_id"])
    op.create_index("ix_issue_comments_created_at", "issue_comments", ["created_at"])
    op.create_index("ix_issue_comments_is_deleted", "issue_comments", ["is_deleted"])

    op.create_table(
        "user_follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("follower_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("following_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("follower_id", "following_id", name="uq_user_follows_follower_following"),
    )
    op.create_index("ix_user_follows_follower_id", "user_follows", ["follower_id"])
    op.create_index("ix_user_follows_following_id", "user_follows", ["following_id"])
    op.create_index("ix_user_follows_created_at", "user_follows", ["created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(40), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_actor_id", "notifications", ["actor_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_target_id", "notifications", ["target_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    for name in ("user_read", "created_at", "is_read", "target_id", "type", "actor_id", "user_id"):
        op.drop_index(f"ix_notifications_{name}", table_name="notifications")
    op.drop_table("notifications")
    for name in ("created_at", "following_id", "follower_id"):
        op.drop_index(f"ix_user_follows_{name}", table_name="user_follows")
    op.drop_table("user_follows")
    for name in ("is_deleted", "created_at", "parent_id", "author_id", "issue_id"):
        op.drop_index(f"ix_issue_comments_{name}", table_name="issue_comments")
    op.drop_table("issue_comments")
    for name in ("updated_at", "created_at", "priority", "issue_type", "status", "assignee_id", "author_id", "resource_id"):
        op.drop_index(f"ix_issues_{name}", table_name="issues")
    op.drop_table("issues")
    for name in ("is_deleted", "created_at", "parent_id", "author_id", "discussion_id"):
        op.drop_index(f"ix_discussion_comments_{name}", table_name="discussion_comments")
    op.drop_table("discussion_comments")
    for name in ("updated_at", "created_at", "is_pinned", "status", "author_id", "resource_id"):
        op.drop_index(f"ix_discussions_{name}", table_name="discussions")
    op.drop_table("discussions")

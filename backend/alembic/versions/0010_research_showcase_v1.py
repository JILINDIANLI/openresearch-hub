"""Add V10 research showcase tables.

Revision ID: 0010_research_showcase_v1
Revises: 0009_community_collaboration_v1
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_research_showcase_v1"
down_revision = "0009_community_collaboration_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_showcases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("short_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("abstract", sa.Text(), nullable=False, server_default=""),
        sa.Column("research_background", sa.Text(), nullable=False, server_default=""),
        sa.Column("methodology", sa.Text(), nullable=False, server_default=""),
        sa.Column("contributions", sa.Text(), nullable=False, server_default=""),
        sa.Column("experiments", sa.Text(), nullable=False, server_default=""),
        sa.Column("results_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("citation_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("bibtex", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("resource_id", name="uq_resource_showcases_resource_id"),
    )
    op.create_index("ix_resource_showcases_resource_id", "resource_showcases", ["resource_id"])
    op.create_index("ix_resource_showcases_created_by", "resource_showcases", ["created_by"])
    op.create_index("ix_resource_showcases_created_at", "resource_showcases", ["created_at"])

    op.create_table(
        "showcase_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("showcase_id", sa.Integer(), sa.ForeignKey("resource_showcases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("resource_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False, server_default="OTHER"),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("file_id", name="uq_showcase_media_file_id"),
    )
    op.create_index("ix_showcase_media_showcase_id", "showcase_media", ["showcase_id"])
    op.create_index("ix_showcase_media_file_id", "showcase_media", ["file_id"])
    op.create_index("ix_showcase_media_media_type", "showcase_media", ["media_type"])
    op.create_index("ix_showcase_media_order_index", "showcase_media", ["order_index"])
    op.create_index("ix_showcase_media_created_at", "showcase_media", ["created_at"])

    op.create_table(
        "showcase_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("showcase_id", sa.Integer(), sa.ForeignKey("resource_showcases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("table_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_showcase_results_showcase_id", "showcase_results", ["showcase_id"])
    op.create_index("ix_showcase_results_created_at", "showcase_results", ["created_at"])


def downgrade() -> None:
    for name in ("created_at", "showcase_id"):
        op.drop_index(f"ix_showcase_results_{name}", table_name="showcase_results")
    op.drop_table("showcase_results")

    for name in ("created_at", "order_index", "media_type", "file_id", "showcase_id"):
        op.drop_index(f"ix_showcase_media_{name}", table_name="showcase_media")
    op.drop_table("showcase_media")

    for name in ("created_at", "created_by", "resource_id"):
        op.drop_index(f"ix_resource_showcases_{name}", table_name="resource_showcases")
    op.drop_table("resource_showcases")

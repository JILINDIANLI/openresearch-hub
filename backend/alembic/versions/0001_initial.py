"""Create OpenResearch Hub V2 resource center tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("avatar", sa.String(500)), sa.Column("organization", sa.String(255)),
        sa.Column("bio", sa.Text()), sa.Column("research_fields", sa.Text()),
        sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username"), sa.UniqueConstraint("email"))
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_table("tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()), sa.UniqueConstraint("name"))
    op.create_index("ix_tags_name", "tags", ["name"], unique=False)
    op.create_table("resources",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("created_time", sa.DateTime(), nullable=False),
        sa.Column("updated_time", sa.DateTime(), nullable=False), sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"), sa.Column("downloads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("license", sa.String(80), nullable=False, server_default="MIT"), sa.Column("visibility", sa.String(30), nullable=False, server_default="public"),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"))
    for name in ("title", "resource_type", "visibility"):
        op.create_index(f"ix_resources_{name}", "resources", [name], unique=False)
    op.create_table("resource_tags",
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("models",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("framework", sa.String(80), nullable=False, server_default=""), sa.Column("parameters", sa.String(80), nullable=False, server_default=""),
        sa.Column("task", sa.String(255), nullable=False, server_default=""), sa.Column("model_url", sa.String(500)))
    op.create_table("datasets",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""), sa.Column("size", sa.String(80), nullable=False, server_default=""),
        sa.Column("format", sa.String(80), nullable=False, server_default=""), sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dataset_url", sa.String(500)), sa.Column("task", sa.String(255), nullable=False, server_default=""))
    op.create_table("research_projects",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("leader", sa.String(120), nullable=False, server_default=""), sa.Column("members", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="published"), sa.Column("github_url", sa.String(500)),
        sa.Column("paper_url", sa.String(500)), sa.Column("demo_url", sa.String(500)))
    op.create_table("papers",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False, server_default=""), sa.Column("authors", sa.Text(), nullable=False, server_default=""),
        sa.Column("journal", sa.String(255)), sa.Column("year", sa.Integer()), sa.Column("doi", sa.String(255)), sa.Column("pdf_url", sa.String(500)),
        sa.Column("abstract", sa.Text(), nullable=False, server_default=""))
    op.create_table("resource_files",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False), sa.Column("file_type", sa.String(80), nullable=False, server_default="other"),
        sa.Column("url", sa.String(500), nullable=False), sa.Column("size", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_time", sa.DateTime(), nullable=False))


def downgrade() -> None:
    for table in ("resource_files", "papers", "research_projects", "datasets", "models", "resource_tags", "resources", "tags", "users"):
        op.drop_table(table)

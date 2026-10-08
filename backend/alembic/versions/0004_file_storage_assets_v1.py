"""Add MinIO-backed resource file metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0004_file_storage_assets_v1"
down_revision = "0003_identity_ownership_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resource_files", sa.Column("uploader_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_resource_files_uploader_id_users", "resource_files", "users", ["uploader_id"], ["id"], ondelete="SET NULL")
    op.add_column("resource_files", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("resource_files", sa.Column("stored_filename", sa.String(255), nullable=True))
    op.add_column("resource_files", sa.Column("object_key", sa.String(700), nullable=True))
    op.create_unique_constraint("uq_resource_files_object_key", "resource_files", ["object_key"])
    op.add_column("resource_files", sa.Column("bucket_name", sa.String(120), nullable=True))
    op.add_column("resource_files", sa.Column("mime_type", sa.String(160), nullable=True))
    op.add_column("resource_files", sa.Column("file_extension", sa.String(32), nullable=True))
    op.add_column("resource_files", sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("resource_files", sa.Column("file_kind", sa.String(40), nullable=False, server_default="OTHER"))
    op.add_column("resource_files", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("resource_files", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("resource_files", sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("resource_files", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("resource_files", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_resource_files_resource_id", "resource_files", ["resource_id"])
    op.create_index("ix_resource_files_uploader_id", "resource_files", ["uploader_id"])
    op.create_index("ix_resource_files_file_kind", "resource_files", ["file_kind"])
    op.create_index("ix_resource_files_sha256", "resource_files", ["sha256"])
    op.execute("UPDATE resource_files SET original_filename = filename WHERE original_filename IS NULL")
    op.execute("UPDATE resource_files SET file_size = size WHERE file_size = 0")
    op.execute("UPDATE resource_files SET file_kind = UPPER(file_type) WHERE file_kind = 'OTHER' AND file_type IS NOT NULL")
    op.execute("UPDATE resource_files SET created_at = created_time WHERE created_at IS NULL")
    op.execute("UPDATE resource_files SET updated_at = created_time WHERE updated_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_resource_files_sha256", table_name="resource_files")
    op.drop_index("ix_resource_files_file_kind", table_name="resource_files")
    op.drop_index("ix_resource_files_uploader_id", table_name="resource_files")
    op.drop_index("ix_resource_files_resource_id", table_name="resource_files")
    op.drop_constraint("uq_resource_files_object_key", "resource_files", type_="unique")
    op.drop_constraint("fk_resource_files_uploader_id_users", "resource_files", type_="foreignkey")
    for name in ("updated_at", "created_at", "download_count", "description", "sha256", "file_kind", "file_size", "file_extension", "mime_type", "bucket_name", "object_key", "stored_filename", "original_filename", "uploader_id"):
        op.drop_column("resource_files", name)

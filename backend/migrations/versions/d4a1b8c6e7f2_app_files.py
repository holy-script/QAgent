"""app_files: test files an app's tests can upload

Revision ID: d4a1b8c6e7f2
Revises: c3d9e5f1a2b4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a1b8c6e7f2"
down_revision: Union[str, None] = "c3d9e5f1a2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_files",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("app_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False, server_default="application/octet-stream"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_app_files_app_id", "app_files", ["app_id"])


def downgrade() -> None:
    op.drop_index("ix_app_files_app_id", table_name="app_files")
    op.drop_table("app_files")

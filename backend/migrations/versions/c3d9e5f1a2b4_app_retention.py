"""apps: per-app retention policy

Revision ID: c3d9e5f1a2b4
Revises: b7e2c4a91d30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d9e5f1a2b4"
down_revision: Union[str, None] = "b7e2c4a91d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("apps", sa.Column("retention_days", sa.Integer(), nullable=True))
    op.add_column("apps", sa.Column("retention_keep_last", sa.Integer(), nullable=False, server_default="10"))


def downgrade() -> None:
    op.drop_column("apps", "retention_keep_last")
    op.drop_column("apps", "retention_days")

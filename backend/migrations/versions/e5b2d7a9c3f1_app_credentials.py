"""app_credentials: saved sign-in details (encrypted)

Revision ID: e5b2d7a9c3f1
Revises: d4a1b8c6e7f2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b2d7a9c3f1"
down_revision: Union[str, None] = "d4a1b8c6e7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_credentials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("app_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("ciphertext", sa.String(), nullable=False),
        sa.Column("secret", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_app_credentials_app_id", "app_credentials", ["app_id"])


def downgrade() -> None:
    op.drop_index("ix_app_credentials_app_id", table_name="app_credentials")
    op.drop_table("app_credentials")

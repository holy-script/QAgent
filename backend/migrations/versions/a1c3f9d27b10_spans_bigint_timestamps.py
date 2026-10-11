"""spans: widen start_ns/end_ns to BIGINT (epoch nanoseconds overflow INTEGER)

Revision ID: a1c3f9d27b10
Revises: 540bff330f77
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3f9d27b10"
down_revision: Union[str, None] = "540bff330f77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spans") as batch:
        batch.alter_column("start_ns", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)
        batch.alter_column("end_ns", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("spans") as batch:
        batch.alter_column("start_ns", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)
        batch.alter_column("end_ns", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)

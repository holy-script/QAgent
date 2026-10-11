"""model_calls: judge and report calls recorded on the run's tape, with cost

Revision ID: b7e2c4a91d30
Revises: 7d4e05d14316
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2c4a91d30"
down_revision: Union[str, None] = "7d4e05d14316"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("flow_run_id", sa.String(), nullable=True),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("decider", sa.String(), nullable=False, server_default=""),
        sa.Column("model_version", sa.String(), nullable=False, server_default=""),
        sa.Column("label", sa.String(), nullable=False, server_default=""),
        sa.Column("input_hash", sa.String(), nullable=False, server_default=""),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("replayed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("run_id", "flow_run_id", "purpose", "input_hash"):
        op.create_index(f"ix_model_calls_{col}", "model_calls", [col])


def downgrade() -> None:
    for col in ("run_id", "flow_run_id", "purpose", "input_hash"):
        op.drop_index(f"ix_model_calls_{col}", table_name="model_calls")
    op.drop_table("model_calls")

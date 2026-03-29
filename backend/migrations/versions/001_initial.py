"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("normalized_response_json", sa.Text(), nullable=True),
        sa.Column("raw_response_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(36), nullable=True),
        sa.Column("parent_run_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_runs_trace_id", "runs", ["trace_id"])
    op.create_index("ix_runs_parent_run_id", "runs", ["parent_run_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_parent_run_id", "runs")
    op.drop_index("ix_runs_trace_id", "runs")
    op.drop_table("runs")

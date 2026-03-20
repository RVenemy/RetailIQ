"""market intelligence tables

Revision ID: 0a1b2c3d4e5f
Revises: d6e87a2b9c45
Create Date: 2026-03-10 12:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, None] = "d6e87a2b9c45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Data Sources ──────────────────────────────────────────────────────────
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Market Signals ────────────────────────────────────────────────────────
    op.create_table(
        "market_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("region_code", sa.String(length=10), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Price Indices ─────────────────────────────────────────────────────────
    op.create_table(
        "price_indices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(length=10), nullable=True),
        sa.Column("index_value", sa.Float(), nullable=True),
        sa.Column("computation_method", sa.String(length=100), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("base_period", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Market Alerts ─────────────────────────────────────────────────────────
    op.create_table(
        "market_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Intelligence Reports ──────────────────────────────────────────────────
    op.create_table(
        "intelligence_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("intelligence_reports")
    op.drop_table("market_alerts")
    op.drop_table("price_indices")
    op.drop_table("market_signals")
    op.drop_table("data_sources")

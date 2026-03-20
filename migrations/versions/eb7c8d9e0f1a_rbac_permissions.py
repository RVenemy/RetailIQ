"""rbac permissions tables

Revision ID: eb7c8d9e0f1a
Revises: 0a1b2c3d4e5f
Create Date: 2026-03-10 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "eb7c8d9e0f1a"
down_revision: Union[str, None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── RBAC Permissions ──────────────────────────────────────────────────────
    op.create_table(
        "rbac_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("is_allowed", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", "resource", "action", name="uq_rbac_role_resource_action"),
    )
    op.create_index("idx_rbac_permissions_role", "rbac_permissions", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_rbac_permissions_role", table_name="rbac_permissions")
    op.drop_table("rbac_permissions")

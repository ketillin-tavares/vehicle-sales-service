"""create initial tables

Revision ID: 001
Revises:
Create Date: 2026-08-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Aplica a migração criando as tabelas vehicle_replicas e sales com seus índices."""
    op.create_table(
        "vehicle_replicas",
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="AVAILABLE"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("vehicle_id"),
    )
    op.create_index("idx_vehicle_replicas_status_price", "vehicle_replicas", ["status", "price"])

    op.create_table(
        "sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_cpf", sa.String(length=11), nullable=False),
        sa.Column("sale_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING_PAYMENT"),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicle_replicas.vehicle_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_code"),
    )
    op.create_index(
        "uq_sales_active_vehicle",
        "sales",
        ["vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING_PAYMENT', 'CONFIRMED')"),
    )
    op.create_index("idx_sales_status_sale_price", "sales", ["status", "sale_price"])


def downgrade() -> None:
    """Reverte a migração removendo as tabelas sales e vehicle_replicas."""
    op.drop_index("idx_sales_status_sale_price", table_name="sales")
    op.drop_index("uq_sales_active_vehicle", table_name="sales")
    op.drop_table("sales")
    op.drop_index("idx_vehicle_replicas_status_price", table_name="vehicle_replicas")
    op.drop_table("vehicle_replicas")

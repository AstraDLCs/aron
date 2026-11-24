"""Estado del worker de IA visible en la app: última señal y qué está haciendo.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("worker_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_settings", sa.Column("worker_status", sa.String(300), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("app_settings", "worker_status")
    op.drop_column("app_settings", "worker_seen_at")

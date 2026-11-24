"""Organigrama, fuentes, requerimientos y configuración.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("folder_name", sa.String(80), nullable=False),
        sa.Column("area", sa.String(200), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("positions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("required_skills", sa.Text, nullable=False, server_default=""),
        sa.Column("technical_specifications", sa.Text, nullable=False, server_default=""),
        sa.Column("min_years_experience", sa.Integer, nullable=False, server_default="0"),
        sa.Column("education_profile", sa.Text, nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_positions_name"),
        sa.UniqueConstraint("folder_name", name="uq_positions_folder_name"),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("folder_name", sa.String(80), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("proposals_sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_response_hours", sa.Float, nullable=False, server_default="0"),
        sa.Column("last_proposal_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_sources_name"),
        sa.UniqueConstraint("folder_name", name="uq_sources_folder_name"),
    )
    op.create_table(
        "requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("positions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("target_days_to_fill", sa.Integer, nullable=False, server_default="30"),
        sa.Column("context", sa.Text, nullable=False, server_default=""),
        sa.Column("extra_skills", sa.Text, nullable=False, server_default=""),
        sa.Column("published_source_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Abierto"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_name", sa.String(200), nullable=False, server_default=""),
        sa.CheckConstraint("quantity >= 1", name="ck_requirements_quantity"),
    )
    op.create_index("ix_requirements_position_id", "requirements", ["position_id"])
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("ai_model", sa.String(200), nullable=False, server_default=""),
        sa.Column("ai_fallback_models", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("ai_preapprove_threshold", sa.Integer, nullable=False, server_default="70"),
        sa.Column("ai_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("ai_paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_app_settings_single_row"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("ix_requirements_position_id", table_name="requirements")
    op.drop_table("requirements")
    op.drop_table("sources")
    op.drop_table("positions")

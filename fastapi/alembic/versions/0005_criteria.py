"""Criterios de reclutamiento.

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CLOCK = sa.text("clock_timestamp()")


def upgrade() -> None:
    op.create_table(
        "recruitment_criteria",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("applies_to_department", sa.String(200), nullable=False),
        sa.Column("weight_label", sa.String(20), nullable=False),
        sa.Column("rule_text", sa.Text, nullable=False),
        sa.Column("is_correction", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("wrong_ai_assumption", sa.Text, nullable=True),
        sa.Column("learned_from_candidate", sa.String(300), nullable=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.CheckConstraint("weight_label in ('Prioritario','Importante','Deseable')", name="ck_criteria_weight"),
    )


def downgrade() -> None:
    op.drop_table("recruitment_criteria")

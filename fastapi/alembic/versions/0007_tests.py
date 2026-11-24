"""Catálogo de pruebas y resultados Excel.

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

CLOCK = sa.text("clock_timestamp()")


def upgrade() -> None:
    op.create_table(
        "test_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("target_area", sa.String(200), nullable=False, server_default=""),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("passing_score", sa.Integer, nullable=False, server_default="70"),
        sa.Column("source_file_name", sa.String(500), nullable=True),
        sa.Column("created_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.CheckConstraint(
            "category in ('Psicolaboral','Técnica Minera','Seguridad HSEC','Operación / Maquinaria')",
            name="ck_test_definitions_category",
        ),
    )
    op.create_table(
        "excel_test_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_id", sa.String(36), sa.ForeignKey("test_definitions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("test_name", sa.String(300), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.Column("uploaded_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("total_questions", sa.Integer, nullable=False),
        sa.Column("answered_count", sa.Integer, nullable=False),
        sa.Column("auto_computed_score", sa.Integer, nullable=False),
        sa.Column("is_concrete_result", sa.Boolean, nullable=False),
        sa.Column("concrete_verdict", sa.String(40), nullable=False),
        sa.Column("ai_analysis", sa.Text, nullable=False, server_default=""),
        sa.Column("parsed_rows", JSONB, nullable=False, server_default="[]"),
        sa.Column("passing_score", sa.Integer, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
    )
    op.create_index("ix_excel_test_results_person_id", "excel_test_results", ["person_id"])


def downgrade() -> None:
    op.drop_table("excel_test_results")
    op.drop_table("test_definitions")

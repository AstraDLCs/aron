"""Personas, archivos de CV, hashes bloqueados y postulaciones.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CLOCK = sa.text("clock_timestamp()")
PSYCH_DEFAULT = (
    '{"testBatteryName": "Pendiente de prueba", "accessCode": "", "status": "Sin enviar", "scores": null, '
    '"averageScore": null, "aptitudeLevel": "Pendiente", "aiPsychObservation": ""}'
)


def _jsonb(name: str, default: str = "[]") -> sa.Column:
    return sa.Column(name, postgresql.JSONB, nullable=False, server_default=default)


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("first_names", sa.String(200), nullable=False, server_default=""),
        sa.Column("last_names", sa.String(200), nullable=False, server_default=""),
        sa.Column("full_name", sa.String(300), nullable=False),
        sa.Column("document_id", sa.String(30), nullable=False, server_default=""),
        sa.Column("email", sa.String(320), nullable=False, server_default=""),
        sa.Column("phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("origin_location", sa.String(200), nullable=False, server_default=""),
        sa.Column("university", sa.String(300), nullable=False, server_default=""),
        sa.Column("career", sa.String(300), nullable=False, server_default=""),
        sa.Column("years_worked", sa.Integer, nullable=True),
        sa.Column("work_history_summary", sa.Text, nullable=False, server_default=""),
        _jsonb("specifications"),
        _jsonb("languages"),
        _jsonb("licenses"),
        _jsonb("field_sources", "{}"),
        _jsonb("psych_evaluation", PSYCH_DEFAULT),
        _jsonb("possible_same_person_ids"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
    )
    op.create_index("ix_persons_document_id", "persons", ["document_id"])
    op.create_index("ix_persons_email_lower", "persons", [sa.text("lower(email)")])

    op.create_table(
        "cv_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("positions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("stored_path", sa.String(1000), nullable=False),
        sa.Column("mime", sa.String(200), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("origin", sa.String(30), nullable=False),
        sa.Column("text", sa.Text, nullable=False, server_default=""),
        sa.Column("text_status", sa.String(10), nullable=False),
        sa.Column("missing", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.UniqueConstraint("sha256", "position_id", name="uq_cv_files_sha256_position"),
        sa.UniqueConstraint("stored_path", name="uq_cv_files_stored_path"),
    )
    op.create_index("ix_cv_files_position_id", "cv_files", ["position_id"])

    op.create_table(
        "deleted_cv_hashes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("positions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("deleted_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.UniqueConstraint("sha256", "position_id", name="uq_deleted_cv_hashes_sha256_position"),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cv_file_id", sa.String(36), sa.ForeignKey("cv_files.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("positions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "requirement_id", sa.String(36), sa.ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("interview_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=CLOCK),
        sa.Column("rule_technical", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rule_experience", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rule_education", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rule_bonus", sa.Integer, nullable=False, server_default="0"),
        _jsonb("rule_applied_criteria"),
        sa.Column("rule_report", sa.Text, nullable=False, server_default=""),
        sa.Column("ai_status", sa.String(20), nullable=False),
        sa.Column("ai_verdict", sa.String(20), nullable=True),
        sa.Column("ai_aptitude_score", sa.Integer, nullable=True),
        sa.Column("ai_technical", sa.Integer, nullable=True),
        sa.Column("ai_experience", sa.Integer, nullable=True),
        sa.Column("ai_education", sa.Integer, nullable=True),
        _jsonb("ai_strengths"),
        _jsonb("ai_observations"),
        sa.Column("ai_reason", sa.Text, nullable=False, server_default=""),
        _jsonb("ai_applied_criteria"),
        sa.Column("ai_summary", sa.Text, nullable=False, server_default=""),
        sa.Column("ai_detailed_report", sa.Text, nullable=False, server_default=""),
        sa.Column("ai_model", sa.String(200), nullable=True),
        sa.Column("ai_classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_error", sa.Text, nullable=True),
        sa.Column("decision", sa.String(30), nullable=False, server_default="Pendiente de revisión"),
        sa.Column("manager_score", sa.Integer, nullable=True),
        sa.Column("manager_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("decided_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by_name", sa.String(200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("cv_file_id", name="uq_candidates_cv_file_id"),
    )
    for col in ("person_id", "position_id", "requirement_id", "source_id", "ai_status"):
        op.create_index(f"ix_candidates_{col}", "candidates", [col])


def downgrade() -> None:
    for col in ("person_id", "position_id", "requirement_id", "source_id", "ai_status"):
        op.drop_index(f"ix_candidates_{col}", table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("deleted_cv_hashes")
    op.drop_index("ix_cv_files_position_id", table_name="cv_files")
    op.drop_table("cv_files")
    op.drop_index("ix_persons_email_lower", table_name="persons")
    op.drop_index("ix_persons_document_id", table_name="persons")
    op.drop_table("persons")

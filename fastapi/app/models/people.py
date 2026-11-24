"""Personas, archivos de CV, hashes bloqueados y postulaciones.

Las fechas de alta usan `clock_timestamp()` (y no `now()`, que es el inicio de la transacción) para que
varias filas creadas en una misma transacción —por ejemplo, una revisión de la carpeta del servidor— queden
ordenadas como se crearon: el worker toma la cola por `created_at`.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

DEFAULT_PSYCH_EVALUATION = {
    "testBatteryName": "Pendiente de prueba",
    "accessCode": "",
    "status": "Sin enviar",
    "scores": None,
    "averageScore": None,
    "aptitudeLevel": "Pendiente",
    "aiPsychObservation": "",
}
_PSYCH_SERVER_DEFAULT = (
    '{"testBatteryName": "Pendiente de prueba", "accessCode": "", "status": "Sin enviar", "scores": null, '
    '"averageScore": null, "aptitudeLevel": "Pendiente", "aiPsychObservation": ""}'
)
_CLOCK = text("clock_timestamp()")


def _uuid() -> str:
    return str(uuid.uuid4())


def default_psych_evaluation() -> dict:
    return dict(DEFAULT_PSYCH_EVALUATION)


class Person(Base):
    """Datos personales: uno por persona, compartidos por todas sus postulaciones."""

    __tablename__ = "persons"
    __table_args__ = (Index("ix_persons_document_id", "document_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    first_names: Mapped[str] = mapped_column(String(200), default="", server_default="")
    last_names: Mapped[str] = mapped_column(String(200), default="", server_default="")
    full_name: Mapped[str] = mapped_column(String(300))
    document_id: Mapped[str] = mapped_column(String(30), default="", server_default="")
    email: Mapped[str] = mapped_column(String(320), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), default="", server_default="")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin_location: Mapped[str] = mapped_column(String(200), default="", server_default="")
    university: Mapped[str] = mapped_column(String(300), default="", server_default="")
    career: Mapped[str] = mapped_column(String(300), default="", server_default="")
    years_worked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_history_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    specifications: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    languages: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    licenses: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # campo -> 'user' | 'ia' | 'reglas': quién fijó el valor actual (prioridad user > ia > reglas)
    field_sources: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    psych_evaluation: Mapped[dict] = mapped_column(
        JSONB, default=default_psych_evaluation, server_default=_PSYCH_SERVER_DEFAULT
    )
    possible_same_person_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)


# El email se busca sin distinguir mayúsculas.
Index("ix_persons_email_lower", func.lower(Person.email))


class CvFile(Base):
    """Archivo de la carpeta `rrhh/<puesto>/<fuente>/`. Sin repetidos dentro de un puesto: (sha256, puesto)."""

    __tablename__ = "cv_files"
    __table_args__ = (
        UniqueConstraint("sha256", "position_id", name="uq_cv_files_sha256_position"),
        UniqueConstraint("stored_path", name="uq_cv_files_stored_path"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sha256: Mapped[str] = mapped_column(String(64))
    position_id: Mapped[str] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))
    original_name: Mapped[str] = mapped_column(String(500))
    stored_path: Mapped[str] = mapped_column(String(1000))  # relativa a RRHH_ROOT
    mime: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(30))
    # El texto puede ser largo: no se carga salvo que se pida (la foto no lo usa).
    text: Mapped[str] = mapped_column(Text, default="", server_default="", deferred=True)
    text_status: Mapped[str] = mapped_column(String(10))
    missing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)


class DeletedCvHash(Base):
    """CV eliminado a propósito: no se vuelve a importar a ese puesto hasta que se desbloquee."""

    __tablename__ = "deleted_cv_hashes"
    __table_args__ = (UniqueConstraint("sha256", "position_id", name="uq_deleted_cv_hashes_sha256_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sha256: Mapped[str] = mapped_column(String(64))
    position_id: Mapped[str] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"))
    original_name: Mapped[str] = mapped_column(String(500))
    deleted_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)


class Candidate(Base):
    """Postulación: una persona en un puesto (equivale al `Candidate` de la app)."""

    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("cv_file_id", name="uq_candidates_cv_file_id"),)

    # relaciones y datos
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="RESTRICT"), index=True)
    cv_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("cv_files.id", ondelete="RESTRICT"), nullable=True
    )
    position_id: Mapped[str] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"), index=True)
    requirement_id: Mapped[str | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), index=True)
    interview_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)

    # resultado de las reglas
    rule_technical: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rule_experience: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rule_education: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rule_bonus: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rule_applied_criteria: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    rule_report: Mapped[str] = mapped_column(Text, default="", server_default="")

    # resultado de la IA
    ai_status: Mapped[str] = mapped_column(String(20), index=True)
    ai_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_aptitude_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_technical: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_education: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_strengths: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    ai_observations: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    ai_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    ai_applied_criteria: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    ai_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    ai_detailed_report: Mapped[str] = mapped_column(Text, default="", server_default="")
    ai_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # decisión humana
    decision: Mapped[str] = mapped_column(
        String(30), default="Pendiente de revisión", server_default="Pendiente de revisión"
    )
    manager_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

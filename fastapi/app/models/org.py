import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Position(Base):
    """Puesto del organigrama. `parent_id` arma el árbol (el puesto del que depende)."""

    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    folder_name: Mapped[str] = mapped_column(String(80), unique=True)
    area: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    required_skills: Mapped[str] = mapped_column(Text, default="", server_default="")
    technical_specifications: Mapped[str] = mapped_column(Text, default="", server_default="")
    min_years_experience: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    education_profile: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Source(Base):
    """Fuente de reclutamiento (portal, red, bolsa, referidos)."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    folder_name: Mapped[str] = mapped_column(String(80), unique=True)
    category: Mapped[str] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    proposals_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    avg_response_hours: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    last_proposal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Requirement(Base):
    """Requerimiento de personal: cuántas vacantes de un puesto y con qué urgencia."""

    __tablename__ = "requirements"
    __table_args__ = (CheckConstraint("quantity >= 1", name="ck_requirements_quantity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    position_id: Mapped[str] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    urgency: Mapped[str] = mapped_column(String(20))
    target_days_to_fill: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    context: Mapped[str] = mapped_column(Text, default="", server_default="")
    extra_skills: Mapped[str] = mapped_column(Text, default="", server_default="")
    published_source_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), default="Abierto", server_default="Abierto")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")

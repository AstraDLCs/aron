"""Criterios de reclutamiento: reglas por área que suben el puntaje y que la IA debe tener en cuenta."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

_CLOCK = text("clock_timestamp()")


class RecruitmentCriterion(Base):
    __tablename__ = "recruitment_criteria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    applies_to_department: Mapped[str] = mapped_column(String(200), default="Todas las áreas")
    weight_label: Mapped[str] = mapped_column(String(20), default="Importante")  # Prioritario | Importante | Deseable
    rule_text: Mapped[str] = mapped_column(Text)
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    wrong_ai_assumption: Mapped[str | None] = mapped_column(Text, nullable=True)
    learned_from_candidate: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK, onupdate=_CLOCK)

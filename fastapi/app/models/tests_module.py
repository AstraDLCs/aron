"""Catálogo de pruebas y resultados de pruebas Excel por persona."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

_CLOCK = text("clock_timestamp()")


def _uuid() -> str:
    return str(uuid.uuid4())


class TestDefinition(Base):
    __test__ = False  # no es una clase de pruebas de pytest
    __tablename__ = "test_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(40))
    target_area: Mapped[str] = mapped_column(String(200), default="", server_default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    questions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    passing_score: Mapped[int] = mapped_column(Integer, default=70, server_default="70")
    source_file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)


class ExcelTestResult(Base):
    __tablename__ = "excel_test_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    test_id: Mapped[str | None] = mapped_column(ForeignKey("test_definitions.id", ondelete="SET NULL"), nullable=True)
    test_name: Mapped[str] = mapped_column(String(300))
    file_name: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)
    uploaded_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    auto_computed_score: Mapped[int] = mapped_column(Integer, default=0)
    is_concrete_result: Mapped[bool] = mapped_column(Boolean, default=False)
    concrete_verdict: Mapped[str] = mapped_column(String(40))
    ai_analysis: Mapped[str] = mapped_column(Text, default="", server_default="")
    parsed_rows: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    passing_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

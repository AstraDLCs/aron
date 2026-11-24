"""Conversaciones con la IA sobre una postulación (informe, chat) y los votos de cada respuesta."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

_CLOCK = text("clock_timestamp()")


def _uuid() -> str:
    return str(uuid.uuid4())


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    created_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)
    structured_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AiMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        CheckConstraint("role in ('assistant','user')", name="ck_ai_messages_role"),
        CheckConstraint("vote is null or vote in ('up','down')", name="ck_ai_messages_vote"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_CLOCK)
    vote: Mapped[str | None] = mapped_column(String(4), nullable=True)
    feedback_note: Mapped[str] = mapped_column(Text, default="", server_default="")

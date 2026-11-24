from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditLog(Base):
    """Bitácora de solo inserción (un trigger bloquea UPDATE, DELETE y TRUNCATE).

    `user_id` no es FK a propósito: la bitácora debe sobrevivir a cualquier cambio en `users`.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

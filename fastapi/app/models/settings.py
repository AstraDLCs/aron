from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AppSettings(Base):
    """Configuración global de la instalación: una sola fila con id = 1."""

    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    company_name: Mapped[str] = mapped_column(String(200))
    ai_model: Mapped[str] = mapped_column(String(200), default="", server_default="")
    ai_fallback_models: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    ai_preapprove_threshold: Mapped[int] = mapped_column(Integer, default=70, server_default="70")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ai_paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

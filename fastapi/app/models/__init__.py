"""Modelos ORM. Cada módulo se importa aquí para que Alembic vea todo el metadata."""
from app.models import audit, org, settings, user  # noqa: F401

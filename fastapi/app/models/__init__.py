"""Modelos ORM. Cada módulo se importa aquí para que Alembic vea todo el metadata."""
from app.models import audit, criteria, org, people, settings, user  # noqa: F401

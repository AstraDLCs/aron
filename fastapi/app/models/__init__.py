"""Modelos ORM. Cada módulo se importa aquí para que Alembic vea todo el metadata."""
from app.models import ai, audit, criteria, org, people, settings, tests_module, user  # noqa: F401

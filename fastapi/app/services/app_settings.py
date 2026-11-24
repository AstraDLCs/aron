from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import DEFAULT_AI_FALLBACK_MODELS, DEFAULT_AI_MODEL, get_settings
from app.models.settings import AppSettings


def get_app_settings(db: Session) -> AppSettings:
    """Devuelve la fila única de configuración (id = 1); la crea si todavía no existe."""
    row = db.get(AppSettings, 1)
    if row is None:
        # ON CONFLICT: dos primeras peticiones simultáneas no deben chocar en la clave primaria.
        db.execute(
            insert(AppSettings)
            .values(
                id=1, company_name=get_settings().company_name_default, ai_model="", ai_fallback_models=[],
                ai_preapprove_threshold=70, ai_enabled=True,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        row = db.get(AppSettings, 1)
    return row


def effective_ai_model(row: AppSettings) -> str:
    """El modelo configurado o, si está vacío, el predeterminado."""
    return (row.ai_model or "").strip() or DEFAULT_AI_MODEL


def effective_fallback_models(row: AppSettings) -> list[str]:
    """Los modelos de respaldo configurados; con el modelo predeterminado en uso, sus respaldos."""
    if (row.ai_model or "").strip():
        return list(row.ai_fallback_models or [])
    return list(row.ai_fallback_models or DEFAULT_AI_FALLBACK_MODELS)

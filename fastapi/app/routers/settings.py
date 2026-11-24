import time

from fastapi import APIRouter, HTTPException, Request

from app.audit import log_action
from app.config import get_settings
from app.deps import CurrentUser, client_ip
from app.routers._util import DbDep, apply_changes
from app.schemas.org import SettingsOut, SettingsUpdate
from app.services.app_settings import effective_ai_model, effective_fallback_models, get_app_settings
from app.services.openrouter import OpenRouterError, make_client
from app.services.snapshot import state_response

router = APIRouter(prefix="/settings", tags=["settings"])

MODELS_TTL_S = 3600
_models_cache: dict = {"at": None, "data": []}  # modelos gratuitos de OpenRouter, en memoria durante 1 h


def _is_free_model(model_id: str) -> bool:
    """Gratuito: el id termina en ':free' o figura en la lista de gratuitos que se consultó."""
    return model_id.endswith(":free") or any(m["id"] == model_id for m in _models_cache["data"])


@router.get("", response_model=SettingsOut, response_model_by_alias=True)
def read_settings(_: CurrentUser, db: DbDep):
    row = get_app_settings(db)
    db.commit()  # persiste la fila si se acaba de crear
    return SettingsOut(
        company_name=row.company_name, ai_model=effective_ai_model(row),
        ai_fallback_models=effective_fallback_models(row),
        ai_preapprove_threshold=row.ai_preapprove_threshold, ai_enabled=row.ai_enabled,
        ai_configured=bool(get_settings().openrouter_api_key),
    )


@router.patch("")
def update_settings(body: SettingsUpdate, request: Request, user: CurrentUser, db: DbDep):
    values = body.model_dump(exclude_unset=True)
    requested = [m for m in [values.get("ai_model"), *(values.get("ai_fallback_models") or [])] if m]
    if not all(_is_free_model(m) for m in requested):
        raise HTTPException(status_code=422, detail="Solo se permiten modelos gratuitos")
    row = get_app_settings(db)
    before, after = apply_changes(row, values)
    if before:
        log_action(
            db, actor=user, action="settings.update", entity_type="settings", entity_id="1",
            summary="Actualizó la configuración: " + ", ".join(after), details={"before": before, "after": after},
            ip=client_ip(request),
        )
    db.commit()
    return state_response(db, user)



def reset_models_cache() -> None:
    _models_cache.update(at=None, data=[])


@router.get("/ai-models")
def ai_models(_: CurrentUser):
    """Modelos gratuitos de OpenRouter (id, nombre y contexto) para elegir el modelo; se guardan 1 h."""
    client = make_client()
    if client is None:
        raise HTTPException(status_code=503, detail="La IA no está configurada (falta OPENROUTER_API_KEY)")
    cached_at = _models_cache["at"]
    if cached_at is None or time.monotonic() - cached_at >= MODELS_TTL_S:
        try:
            models = client.list_free_models()
        except OpenRouterError:
            raise HTTPException(status_code=502, detail="No se pudo consultar la lista de modelos de OpenRouter") from None
        _models_cache.update(at=time.monotonic(), data=sorted(models, key=lambda m: m["name"].lower()))
    return {"models": _models_cache["data"]}

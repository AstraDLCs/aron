from fastapi import APIRouter, Request

from app.audit import log_action
from app.config import get_settings
from app.deps import CurrentUser, client_ip
from app.routers._util import DbDep, apply_changes
from app.schemas.org import SettingsOut, SettingsUpdate
from app.services.app_settings import get_app_settings
from app.services.snapshot import state_response

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut, response_model_by_alias=True)
def read_settings(_: CurrentUser, db: DbDep):
    row = get_app_settings(db)
    db.commit()  # persiste la fila si se acaba de crear
    return SettingsOut(
        company_name=row.company_name, ai_model=row.ai_model, ai_fallback_models=list(row.ai_fallback_models),
        ai_preapprove_threshold=row.ai_preapprove_threshold, ai_enabled=row.ai_enabled,
        ai_configured=bool(get_settings().openrouter_api_key),
    )


@router.patch("")
def update_settings(body: SettingsUpdate, request: Request, user: CurrentUser, db: DbDep):
    row = get_app_settings(db)
    before, after = apply_changes(row, body.model_dump(exclude_unset=True))
    if before:
        log_action(
            db, actor=user, action="settings.update", entity_type="settings", entity_id="1",
            summary="Actualizó la configuración: " + ", ".join(after), details={"before": before, "after": after},
            ip=client_ip(request),
        )
    db.commit()
    return state_response(db, user)

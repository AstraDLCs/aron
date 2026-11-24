import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.audit import log_action
from app.config import get_settings
from app.deps import CurrentUser, client_ip
from app.routers._util import DbDep
from app.routers.reports import download_response
from app.services import datacenter
from app.services.reports import today_str
from app.services.snapshot import build_state
from app.services.storage import get_storage

router = APIRouter(prefix="/datacenter", tags=["datacenter"])


class RestoreBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    confirm: str
    backup: dict


@router.get("/status")
def get_status(user: CurrentUser, db: DbDep):
    return datacenter.status(db, str(get_settings().rrhh_root))


@router.get("/backup")
def backup(request: Request, user: CurrentUser, db: DbDep):
    payload = datacenter.export_business_data(db)
    counts = {k: len(v) for k, v in payload["data"].items()}
    log_action(
        db, actor=user, action="datacenter.backup", entity_type="datacenter",
        summary="Descargó un respaldo de los datos", details={"counts": counts}, ip=client_ip(request),
    )
    db.commit()
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return download_response(body, "application/json", f"Respaldo_Pulso_Laboral_{today_str()}.json")


@router.post("/restore")
def restore(body: RestoreBody, request: Request, user: CurrentUser, db: DbDep):
    if body.confirm != "RESTAURAR":
        raise HTTPException(status_code=422, detail="Escribe RESTAURAR para confirmar")
    try:
        result = datacenter.restore_business_data(db, body.backup, user, get_storage(), ip=client_ip(request))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=422, detail="El respaldo está dañado o no es compatible") from None
    db.commit()
    return {**result, "state": build_state(db, user)}

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, select

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.audit import AuditLog
from app.routers._util import DbDep
from app.routers.reports import download_response
from app.services.reports import build_audit_csv, today_str

router = APIRouter(prefix="/audit", tags=["audit"])


def _parse(value: str | None, end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        if "T" in value or " " in value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.astimezone()
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: {value}") from None
    return datetime.combine(d + timedelta(days=1) if end else d, time.min).astimezone()


def _like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filters(user_id, action, entity_type, entity_id, date_from, date_to, q) -> list:
    conds = []
    if user_id:
        conds.append(AuditLog.user_id == user_id)
    if action:
        conds.append(AuditLog.action.like(_like(action) + "%", escape="\\"))
    if entity_type:
        conds.append(AuditLog.entity_type == entity_type)
    if entity_id:
        conds.append(AuditLog.entity_id == entity_id)
    start, end = _parse(date_from), _parse(date_to, end=True)
    if start:
        conds.append(AuditLog.at >= start)
    if end:
        conds.append(AuditLog.at < end)
    if q:
        conds.append(AuditLog.summary.ilike(f"%{_like(q)}%", escape="\\"))
    return conds


def _item(r: AuditLog) -> dict:
    return {
        "id": r.id, "at": r.at.isoformat(), "userId": r.user_id, "userName": r.user_name, "action": r.action,
        "entityType": r.entity_type, "entityId": r.entity_id, "summary": r.summary, "details": r.details,
        "ip": r.ip,
    }


@router.get("")
def list_audit(
    user: CurrentUser, db: DbDep,
    userId: str | None = None, action: str | None = None, entityType: str | None = None,
    entityId: str | None = None, dateFrom: str | None = None, dateTo: str | None = None, q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100, offset: Annotated[int, Query(ge=0)] = 0,
):
    conds = _filters(userId, action, entityType, entityId, dateFrom, dateTo, q)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conds)) or 0
    rows = db.scalars(
        select(AuditLog).where(*conds).order_by(AuditLog.at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    )
    return {"items": [_item(r) for r in rows], "total": total}


@router.get("/export.csv")
def export_csv(
    request: Request, user: CurrentUser, db: DbDep,
    userId: str | None = None, action: str | None = None, entityType: str | None = None,
    entityId: str | None = None, dateFrom: str | None = None, dateTo: str | None = None, q: str | None = None,
) -> Response:
    conds = _filters(userId, action, entityType, entityId, dateFrom, dateTo, q)
    rows = db.scalars(select(AuditLog).where(*conds).order_by(AuditLog.at.desc(), AuditLog.id.desc()))
    body = build_audit_csv([_item(r) for r in rows])
    filters = dict(userId=userId, action=action, entityType=entityType, entityId=entityId, dateFrom=dateFrom,
                   dateTo=dateTo, q=q)
    log_action(
        db, actor=user, action="audit.export", entity_type="audit", summary="Exportó la bitácora a CSV",
        details={"filters": {k: v for k, v in filters.items() if v}}, ip=client_ip(request),
    )
    db.commit()
    return download_response(body, "text/csv; charset=utf-8", f"Bitacora_{today_str()}.csv")

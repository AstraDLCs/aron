from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.org import Position, Requirement, Source
from app.routers._util import DbDep, apply_changes
from app.schemas.org import RequirementCreate, RequirementUpdate
from app.services.snapshot import build_state, hired_counts, pick

router = APIRouter(prefix="/requirements", tags=["requirements"])


def _unique(ids: list[str]) -> list[str]:
    return list(dict.fromkeys(ids))


def _check_sources(db, source_ids: list[str]) -> None:
    if not source_ids:
        return
    found = set(db.scalars(select(Source.id).where(Source.id.in_(source_ids))))
    if missing := [sid for sid in source_ids if sid not in found]:
        raise HTTPException(status_code=422, detail=f"La fuente {missing[0]} no existe")


@router.post("", status_code=201)
def create_requirement(body: RequirementCreate, request: Request, user: CurrentUser, db: DbDep):
    pos = db.get(Position, body.position_id)
    if pos is None:
        raise HTTPException(status_code=422, detail="El puesto no existe")
    source_ids = _unique(body.published_source_ids)
    _check_sources(db, source_ids)
    req = Requirement(
        **body.model_dump(exclude={"published_source_ids"}), published_source_ids=source_ids,
        created_by_id=user.id, created_by_name=user.full_name,
    )
    db.add(req)
    db.flush()
    log_action(
        db, actor=user, action="requirement.create", entity_type="requirement", entity_id=req.id,
        summary=f"Creó un requerimiento de {req.quantity} vacante(s) para {pos.name}", ip=client_ip(request),
    )
    db.commit()
    state = build_state(db, user)
    return {"requirement": pick(state, "jobNeeds", req.id), "state": state}


@router.patch("/{requirement_id}")
def update_requirement(
    requirement_id: str, body: RequirementUpdate, request: Request, user: CurrentUser, db: DbDep
):
    req = db.get(Requirement, requirement_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requerimiento no encontrado")
    pos = db.get(Position, req.position_id)
    values = body.model_dump(exclude_unset=True)

    if (quantity := values.get("quantity")) is not None:
        hired = hired_counts(db).get(req.id, 0)
        if quantity < hired:
            raise HTTPException(
                status_code=422, detail=f"La cantidad no puede ser menor que los {hired} contratado(s)"
            )
    if "published_source_ids" in values:
        values["published_source_ids"] = _unique(values["published_source_ids"])
        _check_sources(db, values["published_source_ids"])

    new_status = values.pop("status", None)
    cancelled = False
    if new_status is not None and new_status != req.status:
        if req.status not in ("Abierto", "Cancelado"):
            raise HTTPException(status_code=422, detail="Solo se puede cambiar entre Abierto y Cancelado")
        values["status"] = new_status
        values["closed_at"] = datetime.now(UTC) if new_status == "Cancelado" else None
        cancelled = new_status == "Cancelado"

    before, after = apply_changes(req, values)
    if before:
        if cancelled:
            action, summary = "requirement.cancel", f"Canceló el requerimiento de {pos.name}"
        elif "status" in after:
            action, summary = "requirement.update", f"Reabrió el requerimiento de {pos.name}"
        else:
            action, summary = "requirement.update", f"Actualizó el requerimiento de {pos.name}"
        log_action(
            db, actor=user, action=action, entity_type="requirement", entity_id=req.id, summary=summary,
            details={"before": before, "after": after}, ip=client_ip(request),
        )
    db.commit()
    state = build_state(db, user)
    return {"requirement": pick(state, "jobNeeds", req.id), "state": state}

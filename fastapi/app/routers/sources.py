from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.org import Position, Requirement, Source
from app.routers._util import DbDep, apply_changes
from app.schemas.org import ProposalIn, SourceCreate, SourceUpdate
from app.services.slugs import folder_name_for
from app.services.snapshot import build_state, pick, state_response

router = APIRouter(prefix="/sources", tags=["sources"])

DUP_NAME = "Ya existe una fuente con ese nombre"
DUP_FOLDER = "Ya existe una fuente con esa carpeta"


def _get(db, source_id: str) -> Source:
    src = db.get(Source, source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    return src


@router.post("", status_code=201)
def create_source(body: SourceCreate, request: Request, user: CurrentUser, db: DbDep):
    folder = folder_name_for(body.folder_name or body.name)
    if not folder:
        raise HTTPException(status_code=422, detail="El nombre de carpeta no es válido")
    if db.scalar(select(Source.id).where(Source.name == body.name)) is not None:
        raise HTTPException(status_code=409, detail=DUP_NAME)
    if db.scalar(select(Source.id).where(Source.folder_name == folder)) is not None:
        raise HTTPException(status_code=409, detail=DUP_FOLDER)
    src = Source(name=body.name, folder_name=folder, category=body.category,
                 avg_response_hours=body.avg_response_hours)
    db.add(src)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=DUP_NAME) from None
    log_action(
        db, actor=user, action="source.create", entity_type="source", entity_id=src.id,
        summary=f"Creó la fuente {src.name}", ip=client_ip(request),
    )
    db.commit()
    state = build_state(db, user)
    return {"source": pick(state, "jobBoards", src.id), "state": state}


@router.patch("/{source_id}")
def update_source(source_id: str, body: SourceUpdate, request: Request, user: CurrentUser, db: DbDep):
    src = _get(db, source_id)
    values = body.model_dump(exclude_unset=True)
    if "name" in values:
        other = db.scalar(select(Source.id).where(Source.name == values["name"]))
        if other is not None and other != src.id:
            raise HTTPException(status_code=409, detail=DUP_NAME)
    before, after = apply_changes(src, values)
    if before:
        log_action(
            db, actor=user, action="source.update", entity_type="source", entity_id=src.id,
            summary=f"Actualizó la fuente {src.name}", details={"before": before, "after": after},
            ip=client_ip(request),
        )
    db.commit()
    state = build_state(db, user)
    return {"source": pick(state, "jobBoards", src.id), "state": state}


@router.post("/{source_id}/proposals")
def register_proposal(source_id: str, body: ProposalIn, request: Request, user: CurrentUser, db: DbDep):
    src = _get(db, source_id)
    req = db.get(Requirement, body.requirement_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requerimiento no encontrado")
    src.proposals_sent = Source.proposals_sent + 1  # en SQL: sin pisar propuestas simultáneas
    src.last_proposal_at = datetime.now(UTC)
    position = db.get(Position, req.position_id)
    if src.id not in req.published_source_ids:
        req.published_source_ids = [*req.published_source_ids, src.id]  # reasignar: JSONB no detecta mutaciones
    log_action(
        db, actor=user, action="source.proposal", entity_type="source", entity_id=src.id,
        summary=f"Registró una propuesta enviada a {src.name} para el puesto {position.name}",
        details={"requirementId": req.id}, ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)

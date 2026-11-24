"""Cola de la IA: estado, reintento de errores y reclasificación de una postulación o de todo un puesto."""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.org import Position
from app.models.people import Candidate, Person
from app.routers._util import DbDep
from app.services.classifier import requeue_candidate
from app.services.ingest import ai_available
from app.services.snapshot import ai_queue_payload, state_response

router = APIRouter(tags=["ai"])

MSG_UNAVAILABLE = "La IA no está disponible: configura OPENROUTER_API_KEY y activa la IA en la configuración"


@router.get("/ai/queue")
def read_queue(_: CurrentUser, db: DbDep):
    payload = ai_queue_payload(db)
    db.commit()  # persiste la configuración si se acaba de crear
    return payload


@router.post("/ai/queue/retry-errors")
def retry_errors(request: Request, user: CurrentUser, db: DbDep):
    """Vuelve a poner en cola las postulaciones con 'Error IA' y, si hay IA disponible, también las 'Sin IA'."""
    available = ai_available(db)
    statuses = ("Error IA", "Sin IA") if available else ("Error IA",)
    rows = list(db.scalars(select(Candidate).where(Candidate.ai_status.in_(statuses)).with_for_update()))
    counts = {"errors": 0, "sinIa": 0}
    for cand in rows:
        counts["errors" if cand.ai_status == "Error IA" else "sinIa"] += 1
        cand.ai_status = "En cola"
        cand.ai_attempts = 0
        cand.ai_next_attempt_at = None
        cand.ai_error = None
    if rows:
        log_action(
            db, actor=user, action="ai.requeue", entity_type="ai_queue",
            summary=f"Volvió a encolar {len(rows)} postulaciones para la IA ({counts['errors']} con error, {counts['sinIa']} sin IA)",
            details={"count": len(rows), **counts}, ip=client_ip(request),
        )
    db.commit()
    return state_response(db, user, requeued=len(rows))


@router.post("/candidates/{candidate_id}/reclassify")
def reclassify_candidate(candidate_id: str, request: Request, user: CurrentUser, db: DbDep):
    candidate = db.scalar(select(Candidate).where(Candidate.id == candidate_id).with_for_update())
    if candidate is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")
    if not ai_available(db):
        raise HTTPException(status_code=409, detail=MSG_UNAVAILABLE)
    if candidate.ai_status == "Procesando":
        raise HTTPException(status_code=409, detail="La IA está procesando esta postulación; espera a que termine")
    status = requeue_candidate(db, candidate)
    person = db.get(Person, candidate.person_id)
    log_action(
        db, actor=user, action="candidate.reclassify", entity_type="candidate", entity_id=candidate.id,
        summary=f"Pidió reclasificar con la IA a {person.full_name}", details={"aiStatus": status},
        ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)


@router.post("/positions/{position_id}/reclassify")
def reclassify_position(position_id: str, request: Request, user: CurrentUser, db: DbDep):
    position = db.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail="Puesto no encontrado")
    if not ai_available(db):
        raise HTTPException(status_code=409, detail=MSG_UNAVAILABLE)
    rows = list(db.scalars(
        select(Candidate)
        .where(Candidate.position_id == position.id, Candidate.ai_status != "Procesando")
        .order_by(Candidate.created_at, Candidate.id)
        .with_for_update()
    ))
    for cand in rows:
        requeue_candidate(db, cand)
    log_action(
        db, actor=user, action="position.reclassify", entity_type="position", entity_id=position.id,
        summary=f"Pidió reclasificar con la IA {len(rows)} postulaciones de {position.name}",
        details={"count": len(rows)}, ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user, requeued=len(rows))

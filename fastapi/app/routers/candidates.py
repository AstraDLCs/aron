from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.deps import CurrentUser, client_ip
from app.models.org import Position
from app.models.people import Candidate, Person
from app.routers._util import DbDep
from app.schemas.people import DecisionIn, ManualCandidateIn
from app.services.criteria import create_criterion
from app.services.decisions import DecisionError, apply_decision
from app.services.ingest import create_manual_candidate
from app.services.snapshot import build_state, state_response

router = APIRouter(prefix="/candidates", tags=["candidates"])

PERSON_KEYS = (
    "full_name", "career", "age", "origin_location", "university", "years_worked", "work_history_summary",
    "specifications", "email", "phone", "document_id",
)


@router.post("", status_code=201)
def create_candidate(body: ManualCandidateIn, request: Request, user: CurrentUser, db: DbDep):
    """Alta manual sin CV: crea (o enlaza) la persona y la postulación."""
    values = body.model_dump(include=set(PERSON_KEYS))
    try:
        candidate = create_manual_candidate(
            db, values=values, position_id=body.position_id, source_id=body.source_id,
            requirement_id=body.requirement_id or None, interview_notes=body.interview_notes, actor=user,
            ip=client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    db.commit()
    return {"candidateId": candidate.id, "state": build_state(db, user)}


@router.post("/{candidate_id}/decision")
def decide(candidate_id: str, body: DecisionIn, request: Request, user: CurrentUser, db: DbDep):
    """Decisión humana (Aprobar / Rechazar / Contratar). Con `teachAi` crea además un criterio del área."""
    title, rule = (body.criterion_title or "").strip(), (body.criterion_rule or "").strip()
    if body.teach_ai and not (title and rule):
        raise HTTPException(status_code=422, detail="Para enseñar a la IA indica el título y la regla del criterio")
    candidate = db.scalar(select(Candidate).where(Candidate.id == candidate_id).with_for_update())
    if candidate is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")
    ip = client_ip(request)
    try:
        apply_decision(
            db, candidate, decision=body.decision, manager_score=body.manager_score,
            manager_notes=candidate.manager_notes if body.manager_notes is None else body.manager_notes,
            requirement_id=body.requirement_id or None, actor=user, ip=ip,
        )
    except DecisionError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from None
    if body.teach_ai:
        create_criterion(
            db, actor=user, title=title, rule_text=rule, department=db.get(Position, candidate.position_id).area,
            weight=body.criterion_weight, is_correction=body.is_correction,
            wrong_ai_assumption=(body.wrong_ai_assumption or "").strip() or None,
            learned_from_candidate=db.get(Person, candidate.person_id).full_name, ip=ip,
        )
    db.commit()
    return state_response(db, user)

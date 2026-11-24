from fastapi import APIRouter, HTTPException, Request

from app.deps import CurrentUser, client_ip
from app.routers._util import DbDep
from app.schemas.people import ManualCandidateIn
from app.services.ingest import create_manual_candidate
from app.services.snapshot import build_state

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

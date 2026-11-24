"""Informe de IA, chat con la IA y votos de sus respuestas."""
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.people import Candidate, Person
from app.routers._util import DbDep
from app.schemas.common import CamelModel
from app.services import ai_chat
from app.services.ingest import ai_available
from app.services.openrouter import DailyLimitReached, OpenRouterError, make_client
from app.services.snapshot import pick, state_response

router = APIRouter(prefix="/ai", tags=["ai"])

MSG_UNAVAILABLE = "La IA no está configurada (falta OPENROUTER_API_KEY o está desactivada)"
LIMA = ZoneInfo("America/Lima")


class EvaluateIn(CamelModel):
    candidate_id: str


class ChatIn(CamelModel):
    conversation_id: str | None = None
    candidate_id: str
    message: str = Field(min_length=1, max_length=4000)


class VoteIn(CamelModel):
    conversation_id: str
    message_id: str
    vote: Literal["up", "down"] | None
    feedback_note: str | None = Field(default=None, max_length=2000)


def _candidate(db, candidate_id: str) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")
    return candidate


def _client(db):
    client = make_client() if ai_available(db) else None
    if client is None:
        raise HTTPException(status_code=503, detail=MSG_UNAVAILABLE)
    return client


def _ai_error(db, exc: OpenRouterError) -> HTTPException:
    db.rollback()
    if isinstance(exc, DailyLimitReached):
        hour = exc.reset_at.astimezone(LIMA).strftime("%H:%M")
        return HTTPException(429, f"Límite diario de IA alcanzado; se reanuda a las {hour} (hora de Perú)")
    return HTTPException(502, f"No se pudo consultar la IA: {exc.message}")


@router.post("/evaluate-candidate")
def evaluate_candidate(body: EvaluateIn, request: Request, user: CurrentUser, db: DbDep):
    candidate = _candidate(db, body.candidate_id)
    client = _client(db)
    try:
        conv = ai_chat.evaluate_candidate(db, candidate, client, user)
    except OpenRouterError as exc:
        raise _ai_error(db, exc) from None
    person = db.get(Person, candidate.person_id)
    log_action(
        db, actor=user, action="ai.evaluate", entity_type="candidate", entity_id=candidate.id,
        summary=f"Pidió un informe de IA sobre {person.full_name}", details={"conversationId": conv.id},
        ip=client_ip(request),
    )
    db.commit()
    state = state_response(db, user)
    return {"conversation": pick(state["state"], "aiConversations", conv.id), **state}


@router.post("/assistant-chat")
def assistant_chat(body: ChatIn, request: Request, user: CurrentUser, db: DbDep):
    candidate = _candidate(db, body.candidate_id)
    client = _client(db)
    try:
        conv = ai_chat.assistant_reply(db, body.conversation_id, candidate, body.message, client, user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except OpenRouterError as exc:
        raise _ai_error(db, exc) from None
    person = db.get(Person, candidate.person_id)
    log_action(
        db, actor=user, action="ai.chat", entity_type="candidate", entity_id=candidate.id,
        summary=f"Consultó a la IA sobre {person.full_name}", details={"conversationId": conv.id},
        ip=client_ip(request),
    )
    db.commit()
    state = state_response(db, user)
    return {"conversation": pick(state["state"], "aiConversations", conv.id), **state}


@router.post("/vote-response")
def vote_response(body: VoteIn, request: Request, user: CurrentUser, db: DbDep):
    try:
        criterion = ai_chat.apply_vote(
            db, body.conversation_id, body.message_id, body.vote, body.feedback_note, user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    verdict = {"up": "a favor", "down": "en contra"}.get(body.vote or "", "sin voto")
    log_action(
        db, actor=user, action="ai.vote", entity_type="ai_message", entity_id=body.message_id,
        summary=f"Votó {verdict} una respuesta de la IA" + (" y creó un criterio de corrección" if criterion else ""),
        details={"conversationId": body.conversation_id, "vote": body.vote,
                 "criterionId": criterion.id if criterion else None},
        ip=client_ip(request),
    )
    db.commit()
    state = state_response(db, user)
    extra = {}
    if criterion is not None:
        extra["criterion"] = pick(state["state"], "recruitmentCriteria", criterion.id)
    return {**extra, **state}

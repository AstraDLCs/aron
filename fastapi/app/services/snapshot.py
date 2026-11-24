"""Foto del estado (`GET /api/state`): todo lo que la app necesita, con las claves exactas del contrato.

Cada colección tiene su función `_xxx`. Las postulaciones y los CVs bloqueados se arman en
`snapshot_candidates`. Las tareas posteriores reemplazan las que hoy devuelven `[]` (catálogo de pruebas,
conversaciones).
"""
from collections import Counter

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.criteria import RecruitmentCriterion
from app.models.org import Position, Requirement, Source
from app.models.people import Candidate
from app.models.settings import AppSettings
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.criteria import CriterionOut
from app.schemas.org import AiQueueOut, JobBoardOut, JobNeedOut, PositionOut, SettingsOut
from app.services.ai_chat import conversations_payload
from app.services.app_settings import effective_ai_model, effective_fallback_models, get_app_settings
from app.services.scoring import compute_kpis
from app.services.tests_module import catalog_payload
from app.services.snapshot_candidates import blocked_payload, candidates_payload

CATALOG_VERSION = 4


def _dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True)


# --- contadores calculados a partir de las postulaciones --------------------


def hired_counts(db: Session) -> dict[str, int]:
    """requirement_id -> postulaciones 'Contratado' (plazas cubiertas)."""
    rows = db.execute(
        select(Candidate.requirement_id, func.count())
        .where(Candidate.decision == "Contratado", Candidate.requirement_id.is_not(None))
        .group_by(Candidate.requirement_id)
    )
    return {rid: n for rid, n in rows}


def _candidate_counts(db: Session) -> dict[str, int]:
    """position_id -> nº de postulaciones."""
    rows = db.execute(select(Candidate.position_id, func.count()).group_by(Candidate.position_id))
    return {pid: n for pid, n in rows}


def _source_counts(db: Session) -> dict[str, dict[str, int]]:
    """source_id -> {received, shortlisted (Aprobado + Contratado), hired (Contratado)}."""
    shortlisted = func.count(case((Candidate.decision.in_(("Aprobado", "Contratado")), 1)))
    hired = func.count(case((Candidate.decision == "Contratado", 1)))
    rows = db.execute(
        select(Candidate.source_id, func.count(), shortlisted, hired).group_by(Candidate.source_id)
    )
    return {sid: {"received": r, "shortlisted": s, "hired": h} for sid, r, s, h in rows}


def _ai_status_counts(db: Session) -> Counter:
    return Counter({st: n for st, n in db.execute(
        select(Candidate.ai_status, func.count()).group_by(Candidate.ai_status)
    )})


# --- colecciones -----------------------------------------------------------


def _positions(db: Session, open_counts: Counter) -> list[dict]:
    candidates = _candidate_counts(db)
    rows = db.scalars(select(Position).order_by(Position.sort_order, Position.name))
    return [
        _dump(PositionOut(
            **{c: getattr(p, c) for c in (
                "id", "name", "folder_name", "area", "parent_id", "description", "required_skills",
                "technical_specifications", "min_years_experience", "education_profile", "sort_order",
            )},
            open_requirements_count=open_counts[p.id],
            candidates_count=candidates.get(p.id, 0),
        ))
        for p in rows
    ]


def _job_needs(db: Session) -> list[dict]:
    positions = {p.id: p for p in db.scalars(select(Position))}
    sources = {s.id: s.name for s in db.scalars(select(Source))}
    hired = hired_counts(db)
    out = []
    for r in db.scalars(select(Requirement).order_by(Requirement.opened_at, Requirement.id)):
        pos = positions[r.position_id]
        skills = ", ".join(x for x in (pos.required_skills.strip(), r.extra_skills.strip()) if x)
        out.append(_dump(JobNeedOut(
            id=r.id, position_id=r.position_id, title=pos.name, department=pos.area, urgency=r.urgency,
            vacancies=r.quantity, filled_count=hired.get(r.id, 0), required_skills=skills,
            technical_specifications=pos.technical_specifications, company_context=r.context,
            published_boards=[sources[sid] for sid in r.published_source_ids if sid in sources],
            published_source_ids=list(r.published_source_ids), opened_at=r.opened_at,
            target_days_to_fill=r.target_days_to_fill, created_by=r.created_by_name, status=r.status,
            extra_skills=r.extra_skills,
        )))
    return out


def _job_boards(db: Session) -> list[dict]:
    counts = _source_counts(db)
    out = []
    for s in db.scalars(select(Source).order_by(Source.name)):
        c = counts.get(s.id, {})
        out.append(_dump(JobBoardOut(
            id=s.id, name=s.name, folder_name=s.folder_name, category=s.category, proposals_sent=s.proposals_sent,
            candidates_received=c.get("received", 0), shortlisted_count=c.get("shortlisted", 0),
            hired_count=c.get("hired", 0), avg_response_hours=s.avg_response_hours,
            last_proposal_at=s.last_proposal_at, active=s.active,
        )))
    return out


def criteria_payload(db: Session) -> list[dict]:
    rows = db.scalars(select(RecruitmentCriterion).order_by(RecruitmentCriterion.created_at, RecruitmentCriterion.id))
    return [
        _dump(CriterionOut(
            id=c.id, title=c.title, applies_to_department=c.applies_to_department, weight_label=c.weight_label,
            rule_text=c.rule_text, is_correction=c.is_correction, wrong_ai_assumption=c.wrong_ai_assumption,
            learned_from_candidate=c.learned_from_candidate, created_by=c.created_by_name,
            created_at=c.created_at, updated_at=c.updated_at,
        ))
        for c in rows
    ]


def _settings_block(row: AppSettings) -> dict:
    return _dump(SettingsOut(
        company_name=row.company_name, ai_model=effective_ai_model(row),
        ai_fallback_models=effective_fallback_models(row),
        ai_preapprove_threshold=row.ai_preapprove_threshold, ai_enabled=row.ai_enabled,
        ai_configured=bool(get_settings().openrouter_api_key),
    ))


def _ai_queue(db: Session, row: AppSettings) -> dict:
    counts = _ai_status_counts(db)
    return _dump(AiQueueOut(
        queued=counts["En cola"], processing=counts["Procesando"], errors=counts["Error IA"],
        sin_ia=counts["Sin IA"], paused_until=row.ai_paused_until,
        ai_enabled=row.ai_enabled and bool(get_settings().openrouter_api_key), model=effective_ai_model(row),
    ))


# --- API pública -----------------------------------------------------------


def ai_queue_payload(db: Session) -> dict:
    """Contadores de la cola de la IA (`aiQueue` de la foto), también para `GET /api/ai/queue`."""
    return _ai_queue(db, get_app_settings(db))


def build_state(db: Session, user: User) -> dict:
    settings_row = get_app_settings(db)
    open_counts = Counter(
        pid for pid in db.scalars(select(Requirement.position_id).where(Requirement.status == "Abierto"))
    )
    job_needs = _job_needs(db)
    job_boards = _job_boards(db)
    candidates = candidates_payload(db)
    return {
        "catalogVersion": CATALOG_VERSION,
        "companyName": settings_row.company_name,
        "hrChiefName": user.full_name,
        "hrChiefTitle": user.job_title,
        "currentUser": _dump(UserOut.model_validate(user)),
        "settings": _settings_block(settings_row),
        "aiQueue": _ai_queue(db, settings_row),
        "positions": _positions(db, open_counts),
        "jobNeeds": job_needs,
        "jobBoards": job_boards,
        "candidates": candidates,
        "blockedCvFiles": blocked_payload(db),
        "recruitmentCriteria": criteria_payload(db),
        "testCatalog": catalog_payload(db),
        "aiConversations": conversations_payload(db),
        "kpis": compute_kpis(job_needs, job_boards, candidates),
    }


def state_response(db: Session, user: User, **extra) -> dict:
    """Respuesta estándar de toda ruta que modifica datos: `{"state": ...}` más los campos propios."""
    return {**extra, "state": build_state(db, user)}


def pick(state: dict, collection: str, item_id: str) -> dict:
    """Entrada de una colección de la foto por id (para devolverla junto al estado)."""
    return next(item for item in state[collection] if item["id"] == item_id)

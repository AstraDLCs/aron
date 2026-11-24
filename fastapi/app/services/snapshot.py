"""Foto del estado (`GET /api/state`): todo lo que la app necesita, con las claves exactas del contrato.

Cada colección tiene su función `_xxx`. Las tareas posteriores reemplazan las que hoy devuelven `[]`
(candidatos, bloqueados, criterios, catálogo de pruebas, conversaciones) y los contadores de `_hired_counts`,
`_source_counts` y `_candidate_counts`.
"""
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.org import Position, Requirement, Source
from app.models.settings import AppSettings
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.org import AiQueueOut, JobBoardOut, JobNeedOut, PositionOut, SettingsOut
from app.services.app_settings import get_app_settings
from app.services.scoring import compute_kpis

CATALOG_VERSION = 4


def _dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True)


# --- contadores que completan las tareas siguientes ------------------------


def hired_counts(db: Session) -> dict[str, int]:
    """requirement_id -> candidatos 'Contratado'. Sin candidatos todavía: vacío."""
    return {}


def _candidate_counts(db: Session) -> dict[str, int]:
    """position_id -> nº de postulaciones. Sin candidatos todavía: vacío."""
    return {}


def _source_counts(db: Session) -> dict[str, dict[str, int]]:
    """source_id -> {received, shortlisted, hired}. Sin candidatos todavía: vacío."""
    return {}


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


def _settings_block(row: AppSettings) -> dict:
    return _dump(SettingsOut(
        company_name=row.company_name, ai_model=row.ai_model, ai_fallback_models=list(row.ai_fallback_models),
        ai_preapprove_threshold=row.ai_preapprove_threshold, ai_enabled=row.ai_enabled,
        ai_configured=bool(get_settings().openrouter_api_key),
    ))


def _ai_queue(row: AppSettings) -> dict:
    """Los contadores de la cola los completa la Tarea 7; hoy no hay candidatos."""
    return _dump(AiQueueOut(
        queued=0, processing=0, errors=0, sin_ia=0, paused_until=row.ai_paused_until,
        ai_enabled=row.ai_enabled and bool(get_settings().openrouter_api_key), model=row.ai_model,
    ))


# --- API pública -----------------------------------------------------------


def build_state(db: Session, user: User) -> dict:
    settings_row = get_app_settings(db)
    open_counts = Counter(
        pid for pid in db.scalars(select(Requirement.position_id).where(Requirement.status == "Abierto"))
    )
    job_needs = _job_needs(db)
    job_boards = _job_boards(db)
    candidates: list[dict] = []
    return {
        "catalogVersion": CATALOG_VERSION,
        "companyName": settings_row.company_name,
        "hrChiefName": user.full_name,
        "hrChiefTitle": user.job_title,
        "currentUser": _dump(UserOut.model_validate(user)),
        "settings": _settings_block(settings_row),
        "aiQueue": _ai_queue(settings_row),
        "positions": _positions(db, open_counts),
        "jobNeeds": job_needs,
        "jobBoards": job_boards,
        "candidates": candidates,
        "blockedCvFiles": [],
        "recruitmentCriteria": [],
        "testCatalog": [],
        "aiConversations": [],
        "kpis": compute_kpis(job_needs, job_boards, candidates),
    }


def state_response(db: Session, user: User, **extra) -> dict:
    """Respuesta estándar de toda ruta que modifica datos: `{"state": ...}` más los campos propios."""
    return {**extra, "state": build_state(db, user)}


def pick(state: dict, collection: str, item_id: str) -> dict:
    """Entrada de una colección de la foto por id (para devolverla junto al estado)."""
    return next(item for item in state[collection] if item["id"] == item_id)

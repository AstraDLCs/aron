"""Decisiones humanas sobre una postulación y su efecto en la cobertura del requerimiento.

`apply_decision` valida la transición, bloquea la fila del requerimiento (para que dos contrataciones a la vez
no superen las vacantes), actualiza la postulación y anota la bitácora. No hace commit. Lanza `DecisionError`
sin haber modificado nada si la decisión no procede.
"""
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.constants import DECISION_TRANSITIONS, SYSTEM_ACTOR
from app.models.org import Position, Requirement
from app.models.people import Candidate, Person
from app.models.user import User

HIRED = "Contratado"

MSG_NO_REQUIREMENT = "La postulación no tiene un requerimiento abierto asignado"
MSG_COVERED = "El requerimiento ya está cubierto"
MSG_REQUIREMENT_MISSING = "El requerimiento no existe"
MSG_REQUIREMENT_OTHER_POSITION = "El requerimiento no corresponde al puesto de la postulación"


class DecisionError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _hired_count(db: Session, requirement_id: str, *, excluding: str | None = None) -> int:
    query = select(func.count()).select_from(Candidate).where(
        Candidate.requirement_id == requirement_id, Candidate.decision == HIRED
    )
    if excluding:
        query = query.where(Candidate.id != excluding)
    return db.scalar(query) or 0


def _lock_requirement(db: Session, requirement_id: str) -> Requirement | None:
    return db.scalar(select(Requirement).where(Requirement.id == requirement_id).with_for_update())


def _requirement_for_hire(db: Session, candidate: Candidate, requirement_id: str | None) -> Requirement:
    """El requerimiento (bloqueado) en el que se contrata: el indicado o, si no, el que ya tiene la postulación."""
    target_id = requirement_id or candidate.requirement_id
    if not target_id:
        raise DecisionError(409, MSG_NO_REQUIREMENT)
    requirement = _lock_requirement(db, target_id)
    if requirement is None:
        raise DecisionError(422, MSG_REQUIREMENT_MISSING)
    if requirement.position_id != candidate.position_id:
        raise DecisionError(422, MSG_REQUIREMENT_OTHER_POSITION)
    if requirement.status == "Cubierto":
        raise DecisionError(409, MSG_COVERED)
    if requirement.status != "Abierto":
        raise DecisionError(409, MSG_NO_REQUIREMENT)
    if _hired_count(db, requirement.id, excluding=candidate.id) >= requirement.quantity:
        raise DecisionError(409, MSG_COVERED)
    return requirement


def apply_decision(
    db: Session,
    candidate: Candidate,
    *,
    decision: str,
    manager_score: int | None,
    manager_notes: str,
    requirement_id: str | None,
    actor: User,
    ip: str | None = None,
) -> None:
    """Aplica la decisión. `manager_score=None` conserva el puntaje anterior; `manager_notes` es el texto final."""
    previous = candidate.decision
    if decision not in DECISION_TRANSITIONS.get(previous, set()):
        raise DecisionError(409, f"Transición no permitida: {previous} → {decision}")

    requirement: Requirement | None = None
    if decision == HIRED:
        requirement = _requirement_for_hire(db, candidate, requirement_id)
    elif previous == HIRED and candidate.requirement_id:
        requirement = _lock_requirement(db, candidate.requirement_id)

    now = datetime.now(UTC)
    candidate.decision = decision
    if manager_score is not None:
        candidate.manager_score = manager_score
    candidate.manager_notes = manager_notes
    candidate.decided_by_id, candidate.decided_by_name, candidate.decided_at = actor.id, actor.full_name, now
    if decision == HIRED:
        candidate.requirement_id = requirement.id
    db.flush()

    name = db.get(Person, candidate.person_id).full_name
    position = db.get(Position, candidate.position_id).name
    if previous == HIRED:
        summary = f"Deshizo la contratación de {name} ({position})"
    else:
        verb = {"Aprobado": "Aprobó a", "Rechazado": "Rechazó a", HIRED: "Contrató a"}[decision]
        summary = f"{verb} {name} para {position}"
    log_action(
        db, actor=actor, action="candidate.decision", entity_type="candidate", entity_id=candidate.id,
        summary=summary, details={"from": previous, "to": decision, "managerScore": candidate.manager_score}, ip=ip,
    )

    if requirement is None:
        return
    hired = _hired_count(db, requirement.id)
    if decision == HIRED and hired >= requirement.quantity and requirement.status == "Abierto":
        requirement.status, requirement.closed_at = "Cubierto", now
        db.flush()
        log_action(
            db, actor=SYSTEM_ACTOR, action="requirement.covered", entity_type="requirement",
            entity_id=requirement.id, summary=f"Se cubrieron las {requirement.quantity} vacante(s) de {position}",
            details={"candidateId": candidate.id}, ip=ip,
        )
    elif previous == HIRED and requirement.status == "Cubierto" and hired < requirement.quantity:
        requirement.status, requirement.closed_at = "Abierto", None
        db.flush()
        log_action(
            db, actor=SYSTEM_ACTOR, action="requirement.reopened", entity_type="requirement",
            entity_id=requirement.id, summary=f"Se reabrió el requerimiento de {position}: quedó una plaza libre",
            details={"candidateId": candidate.id}, ip=ip,
        )

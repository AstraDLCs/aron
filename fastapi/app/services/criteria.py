"""Criterios de reclutamiento: alta y recálculo del puntaje por reglas (ruling R11).

Al crear o editar un criterio se recalcula el puntaje por reglas de las postulaciones del área afectada, en la
misma transacción. La clasificación por IA no se vuelve a encolar.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.constants import ALL_AREAS
from app.models.criteria import RecruitmentCriterion
from app.models.org import Position
from app.models.people import Candidate, Person
from app.models.user import User
from app.services.candidate_rules import apply_rule_scores, criteria_views


def create_criterion(
    db: Session, *, actor: User, title: str, rule_text: str, department: str, weight: str, is_correction: bool,
    wrong_ai_assumption: str | None, learned_from_candidate: str | None = None, ip: str | None = None,
) -> RecruitmentCriterion:
    """Crea el criterio, lo anota en la bitácora y recalcula las reglas de su área. No hace commit."""
    criterion = RecruitmentCriterion(
        title=title, rule_text=rule_text, applies_to_department=department, weight_label=weight,
        is_correction=is_correction, wrong_ai_assumption=wrong_ai_assumption or None,
        learned_from_candidate=learned_from_candidate, created_by_id=actor.id, created_by_name=actor.full_name,
    )
    db.add(criterion)
    db.flush()
    log_action(
        db, actor=actor, action="criterion.create", entity_type="criterion", entity_id=criterion.id,
        summary=f"Creó el criterio «{title}» para {department}",
        details={"appliesToDepartment": department, "weightLabel": weight, "isCorrection": is_correction,
                 "learnedFromCandidate": learned_from_candidate},
        ip=ip,
    )
    rescore_departments(db, {department})
    return criterion


def rescore_departments(db: Session, departments: set[str]) -> int:
    """Recalcula las reglas de las postulaciones cuyo puesto es de esas áreas (todas si incluye 'Todas las áreas')."""
    query = select(Candidate, Person, Position).join(Person, Candidate.person_id == Person.id).join(
        Position, Candidate.position_id == Position.id
    )
    if ALL_AREAS not in departments:
        query = query.where(Position.area.in_(departments))
    criteria = criteria_views(db)
    count = 0
    for candidate, person, position in db.execute(query):
        apply_rule_scores(candidate, person, position, criteria)
        count += 1
    db.flush()
    return count

"""Puntaje por reglas de una postulación (pilares, bono y dictamen) a partir de la persona y el puesto.

Se recalcula cuando cambia algo que lo alimenta: al ingresar el CV, al mover la postulación de puesto, al
editar o unir a la persona y (Tarea 10) al cambiar su evaluación psicológica.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org import Position
from app.models.people import Candidate, Person
from app.services.scoring import compute_rule_scores, global_index, rule_report_text


def person_psych_score(person: Person) -> float | None:
    """Promedio psicológico de la persona si su evaluación está Completada; si no, None (→ 64)."""
    ev = person.psych_evaluation or {}
    return ev.get("averageScore") if ev.get("status") == "Completada" else None


def position_view(position: Position) -> dict:
    """El puesto con las claves que usan `scoring` y `cv_parser`."""
    return {
        "id": position.id,
        "name": position.name,
        "area": position.area,
        "requiredSkills": position.required_skills,
        "technicalSpecifications": position.technical_specifications,
    }


def candidate_view(person: Person, candidate: Candidate, position: Position) -> dict:
    """La postulación con las claves al estilo TS que lee `compute_rule_scores` / `rule_report_text`."""
    return {
        "specifications": [*(person.specifications or []), *(person.licenses or [])],
        "workHistorySummary": person.work_history_summary,
        "interviewNotes": candidate.interview_notes,
        "yearsWorked": person.years_worked,
        "career": person.career,
        "university": person.university,
        "targetRoleTitle": position.name,
        "psychEvaluation": person.psych_evaluation,
    }


def apply_rule_scores(
    candidate: Candidate, person: Person, position: Position, criteria: list[dict] | None = None
) -> None:
    """Guarda en la postulación los pilares, el bono, los criterios aplicados y el dictamen de reglas.

    `criteria` queda vacío hasta que exista la tabla de criterios (Tarea 6).
    """
    pos = position_view(position)
    view = candidate_view(person, candidate, position)
    scores = compute_rule_scores(view, pos, criteria or [])
    overall = global_index(
        scores["technical"], scores["experience"], scores["education"], person_psych_score(person),
        scores["criteriaBonus"],
    )
    candidate.rule_technical = scores["technical"]
    candidate.rule_experience = scores["experience"]
    candidate.rule_education = scores["education"]
    candidate.rule_bonus = scores["criteriaBonus"]
    candidate.rule_applied_criteria = list(scores["appliedCriteria"])
    candidate.rule_report = rule_report_text(view, pos, scores, overall)


def rescore_person(db: Session, person: Person) -> None:
    """Recalcula el puntaje por reglas de todas las postulaciones de la persona."""
    for cand in db.scalars(select(Candidate).where(Candidate.person_id == person.id)):
        apply_rule_scores(cand, person, db.get(Position, cand.position_id))

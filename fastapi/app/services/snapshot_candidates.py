"""Postulaciones y CVs bloqueados de la foto (`candidates`, `blockedCvFiles`), con las claves del contrato.

`metricReport` se calcula en el momento: pilares de la IA si la postulación está `Clasificado` (sin bono) o, si
no, los de las reglas (con su bono); el psicológico es el de la persona; luego `global_index` y `fit_verdict`.
"""
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org import Position, Source
from app.models.people import Candidate, CvFile, DeletedCvHash, Person
from app.schemas.people import BlockedCvFileOut, CandidateOut, MetricReportOut, OtherApplicationOut
from app.services.candidate_rules import person_psych_score
from app.services.scoring import PSYCH_BASELINE, fit_verdict, global_index
from app.services.tests_module import results_by_person


def _dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True)


def metric_report(candidate: Candidate, person: Person) -> MetricReportOut:
    psych = person_psych_score(person)
    ai_pillars = (candidate.ai_technical, candidate.ai_experience, candidate.ai_education)
    use_ai = candidate.ai_status == "Clasificado" and None not in ai_pillars
    if use_ai:
        (technical, experience, education), bonus = ai_pillars, 0  # el bono solo existe sin IA
    else:
        technical, experience, education = candidate.rule_technical, candidate.rule_experience, candidate.rule_education
        bonus = candidate.rule_bonus
    overall = global_index(technical, experience, education, psych, bonus)
    return MetricReportOut(
        technical_specs_score=technical,
        experience_score=experience,
        education_career_score=education,
        psych_score=PSYCH_BASELINE if psych is None else psych,
        overall_score=overall,
        fit_verdict=fit_verdict(overall),
        ai_detailed_report=candidate.ai_detailed_report or candidate.rule_report,
        generated_at=(candidate.ai_classified_at if use_ai and candidate.ai_classified_at else candidate.created_at),
    )


def _candidate_out(
    c: Candidate, person: Person, cv: CvFile | None, position: Position, source_name: str,
    others: list[OtherApplicationOut], now: datetime,
) -> CandidateOut:
    report = metric_report(c, person)
    return CandidateOut(
        id=c.id, person_id=c.person_id, cv_file_id=c.cv_file_id, position_id=c.position_id,
        requirement_id=c.requirement_id, target_need_id=c.requirement_id or "", target_role_title=position.name,
        source_board_id=c.source_id, source_board_name=source_name,
        full_name=person.full_name, first_names=person.first_names, last_names=person.last_names,
        document_id=person.document_id, email=person.email, phone=person.phone,
        phone_or_email=" · ".join(x for x in (person.email, person.phone) if x),
        age=person.age, origin_location=person.origin_location, university=person.university, career=person.career,
        years_worked=person.years_worked, work_history_summary=person.work_history_summary,
        specifications=list(person.specifications or []), languages=list(person.languages or []),
        licenses=list(person.licenses or []), interview_notes=c.interview_notes,
        cv_file_name=cv.original_name if cv else None, cv_mime_type=cv.mime if cv else None,
        cv_uploaded_at=cv.uploaded_at if cv else None, cv_uploaded_by=cv.uploaded_by_name if cv else None,
        cv_origin=cv.origin if cv else None, cv_path=cv.stored_path if cv else None,
        cv_missing=bool(cv and cv.missing),
        psych_evaluation=dict(person.psych_evaluation or {}),
        excel_test_results=[],  # Tarea 10
        metric_report=report,
        ai_status=c.ai_status, ai_verdict=c.ai_verdict, ai_aptitude_score=c.ai_aptitude_score,
        ai_strengths=list(c.ai_strengths or []), ai_observations=list(c.ai_observations or []),
        ai_reason=c.ai_reason,
        ai_applied_criteria=list(c.ai_applied_criteria if c.ai_status == "Clasificado" else c.rule_applied_criteria),
        ai_applied_correction_title=None,  # Tarea 6/7: no se guarda todavía
        ai_model=c.ai_model, ai_classified_at=c.ai_classified_at, ai_error=c.ai_error, ai_summary=c.ai_summary,
        ai_observed_score=report.overall_score,
        decision=c.decision, manager_score=c.manager_score, manager_notes=c.manager_notes,
        evaluated_by=c.decided_by_name, evaluated_at=c.decided_at,
        possible_same_person_ids=list(person.possible_same_person_ids or []),
        other_applications=others,
        process_days_elapsed=max(0, (now - c.created_at).days),
        created_at=c.created_at,
    )


def candidates_payload(db: Session, now: datetime | None = None) -> list[dict]:
    """Una entrada por postulación, sin el texto del CV (la columna `text` es diferida y no se carga)."""
    now = now or datetime.now(UTC)
    candidates = list(db.scalars(select(Candidate).order_by(Candidate.created_at, Candidate.id)))
    if not candidates:
        return []
    persons = {p.id: p for p in db.scalars(select(Person))}
    cvs = {cv.id: cv for cv in db.scalars(select(CvFile))}
    positions = {p.id: p for p in db.scalars(select(Position))}
    sources = {s.id: s.name for s in db.scalars(select(Source))}
    by_person: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        by_person[c.person_id].append(c)

    excel_results = results_by_person(db)
    out = []
    for c in candidates:
        others = [
            OtherApplicationOut(candidate_id=o.id, position_name=positions[o.position_id].name, decision=o.decision)
            for o in by_person[c.person_id] if o.id != c.id
        ]
        cv = cvs.get(c.cv_file_id) if c.cv_file_id else None
        item = _dump(_candidate_out(
            c, persons[c.person_id], cv, positions[c.position_id], sources.get(c.source_id, ""), others, now,
        ))
        item["excelTestResults"] = excel_results.get(c.person_id, [])
        out.append(item)
    return out


def blocked_payload(db: Session) -> list[dict]:
    rows = db.scalars(select(DeletedCvHash).order_by(DeletedCvHash.deleted_at.desc(), DeletedCvHash.id))
    return [
        _dump(BlockedCvFileOut(
            id=b.id, sha256=b.sha256, position_id=b.position_id, original_name=b.original_name,
            deleted_by=b.deleted_by_name, deleted_at=b.deleted_at,
        ))
        for b in rows
    ]

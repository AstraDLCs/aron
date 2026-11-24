"""Catálogo de pruebas, resultados Excel y evaluación psicológica de la persona."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.people import Person, default_psych_evaluation
from app.models.tests_module import ExcelTestResult, TestDefinition
from app.models.user import User
from app.services.candidate_rules import rescore_person
from app.services.excel_tests import evaluate_excel_test_rows
from app.services.scoring import evaluate_psychometric_battery


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_payload(t: TestDefinition) -> dict:
    out = {
        "id": t.id, "name": t.name, "category": t.category, "targetArea": t.target_area,
        "durationMinutes": t.duration_minutes, "questions": list(t.questions or []),
        "passingScore": t.passing_score, "createdBy": t.created_by_name, "createdAt": _iso(t.created_at),
    }
    if t.source_file_name:
        out["sourceFileName"] = t.source_file_name
    return out


def result_payload(r: ExcelTestResult, *, rows: bool = False) -> dict:
    return {
        "id": r.id, "testId": r.test_id, "testName": r.test_name, "fileName": r.file_name,
        "uploadedAt": _iso(r.uploaded_at), "uploadedBy": r.uploaded_by_name,
        "totalQuestions": r.total_questions, "answeredCount": r.answered_count,
        "autoComputedScore": r.auto_computed_score, "isConcreteResult": r.is_concrete_result,
        "concreteVerdict": r.concrete_verdict, "aiAnalysis": r.ai_analysis,
        "parsedRows": list(r.parsed_rows or []) if rows else [],
        "passingScore": r.passing_score, "passed": r.passed,
    }


def catalog_payload(db: Session) -> list[dict]:
    return [test_payload(t) for t in db.scalars(select(TestDefinition).order_by(TestDefinition.created_at, TestDefinition.id))]


def results_by_person(db: Session) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in db.scalars(select(ExcelTestResult).order_by(ExcelTestResult.uploaded_at, ExcelTestResult.id)):
        out.setdefault(r.person_id, []).append(result_payload(r))
    return out


def next_access_code(db: Session) -> str:
    top = 0
    for ev in db.scalars(select(Person.psych_evaluation)):
        code = (ev or {}).get("accessCode") or ""
        if code.startswith("PL-PS-") and code[6:].isdigit():
            top = max(top, int(code[6:]))
    return f"PL-PS-{top + 1:04d}"


def find_test_by_name(db: Session, name: str) -> TestDefinition | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    for t in db.scalars(select(TestDefinition).order_by(TestDefinition.created_at)):
        if t.name.strip().lower() == key:
            return t
    return None


def apply_psych_scores(db: Session, person: Person, scores: dict, battery_name: str, *, access_code: str | None = None,
                       duration_seconds: int | None = None) -> dict:
    """Deja la evaluación psicológica de la persona `Completada` con esos puntajes y recalcula sus reglas."""
    prev = dict(person.psych_evaluation or default_psych_evaluation())
    calc = evaluate_psychometric_battery(scores)
    ev = {
        **prev,
        "testBatteryName": battery_name,
        "accessCode": access_code if access_code is not None else prev.get("accessCode", ""),
        "status": "Completada",
        "completedAt": _iso(datetime.now(UTC)),
        "scores": {k: max(0, min(100, int(round(v)))) for k, v in scores.items()},
        "averageScore": calc["averageScore"],
        "aptitudeLevel": calc["aptitudeLevel"],
        "aiPsychObservation": calc["aiPsychObservation"],
    }
    if duration_seconds is not None:
        ev["durationSeconds"] = duration_seconds
    person.psych_evaluation = ev
    db.flush()
    rescore_person(db, person)
    return ev


def store_excel_result(
    db: Session, person: Person, test: TestDefinition | None, test_name: str, file_name: str, rows: list[dict],
    actor: User,
) -> tuple[ExcelTestResult | None, dict]:
    """Evalúa las filas. Sin ninguna respuesta válida no se guarda resultado (devuelve None)."""
    passing = test.passing_score if test is not None else None
    ev = evaluate_excel_test_rows(rows, passing)
    if ev["answeredCount"] == 0:
        return None, ev
    result = ExcelTestResult(
        person_id=person.id, test_id=test.id if test else None, test_name=test_name, file_name=file_name,
        uploaded_by_name=actor.full_name, total_questions=ev["totalQuestions"], answered_count=ev["answeredCount"],
        auto_computed_score=ev["autoComputedScore"], is_concrete_result=ev["isConcreteResult"],
        concrete_verdict=ev["concreteVerdict"], ai_analysis=ev["aiAnalysis"], parsed_rows=ev["parsedRows"],
        passing_score=passing, passed=ev["passed"],
    )
    db.add(result)
    db.flush()
    db.refresh(result)
    if test is not None and test.category == "Psicolaboral" and ev["concreteVerdict"] != "Inconsistencia Detectada":
        apply_psych_scores(db, person, ev["derivedScores"], test.name)
    return result, ev

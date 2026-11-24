"""Pruebas psicológicas de la persona, catálogo de pruebas y resultados Excel."""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import select

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.people import Candidate, Person, default_psych_evaluation
from app.models.tests_module import ExcelTestResult, TestDefinition
from app.routers._util import DbDep
from app.schemas.tests_module import PsychSendIn, PsychSubmitIn, TestCreateIn
from app.services import tests_module as svc
from app.services.excel_tests import (
    ExcelReadError,
    build_excel_template,
    extract_excel_test_metadata,
    read_excel_rows,
)
from app.services.scoring import score_psych_answers
from app.services.slugs import folder_name_for
from app.services.snapshot import pick, state_response

router = APIRouter(tags=["tests"])

MAX_EXCEL_BYTES = 10 * 1024 * 1024
MSG_NO_ANSWERS = (
    "El archivo no tiene respuestas válidas: la prueba quedó registrada, pero no se guardó ningún resultado. "
    "Completa la columna Respuesta y vuelve a subirlo."
)


def _candidate(db, candidate_id: str) -> tuple[Candidate, Person]:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")
    return candidate, db.get(Person, candidate.person_id)


async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    data = await file.read(MAX_EXCEL_BYTES + 1)
    if len(data) > MAX_EXCEL_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera 10 MB")
    return data, file.filename or "prueba.xlsx"


def _rows(data: bytes, filename: str):
    try:
        return read_excel_rows(data, filename)
    except ExcelReadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


# --- evaluación psicológica ---------------------------------------------------


@router.post("/recruitment/psych-tests/send")
def send_psych(body: PsychSendIn, request: Request, user: CurrentUser, db: DbDep):
    candidate, person = _candidate(db, body.candidate_id)
    code = svc.next_access_code(db)
    person.psych_evaluation = {
        **default_psych_evaluation(),
        "testBatteryName": body.test_battery_name, "accessCode": code, "status": "Enviada",
        "sentAt": datetime.now(UTC).isoformat(), "sentBy": user.full_name,
    }
    log_action(
        db, actor=user, action="psych.send", entity_type="person", entity_id=person.id,
        summary=f"Envió la batería psicológica «{body.test_battery_name}» a {person.full_name}",
        details={"accessCode": code, "candidateId": candidate.id}, ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)


@router.post("/recruitment/psych-tests/{candidate_id}/submit")
def submit_psych(candidate_id: str, body: PsychSubmitIn, request: Request, user: CurrentUser, db: DbDep):
    candidate, person = _candidate(db, candidate_id)
    scores = score_psych_answers(body.answers.model_dump())
    prev = person.psych_evaluation or default_psych_evaluation()
    ev = svc.apply_psych_scores(db, person, scores, prev.get("testBatteryName") or "Batería psicométrica")
    log_action(
        db, actor=user, action="psych.submit", entity_type="person", entity_id=person.id,
        summary=f"Registró la evaluación psicológica de {person.full_name} ({ev['averageScore']}/100)",
        details={"averageScore": ev["averageScore"], "aptitudeLevel": ev["aptitudeLevel"],
                 "candidateId": candidate.id},
        ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)


# --- catálogo ---------------------------------------------------------------


@router.post("/recruitment/tests", status_code=201)
def create_test(body: TestCreateIn, request: Request, user: CurrentUser, db: DbDep):
    test = TestDefinition(
        name=body.name, category=body.category, target_area=body.target_area, duration_minutes=body.duration_minutes,
        passing_score=body.passing_score, questions=body.questions, created_by_name=user.full_name,
    )
    db.add(test)
    db.flush()
    log_action(
        db, actor=user, action="test.create", entity_type="test", entity_id=test.id,
        summary=f"Creó la prueba «{test.name}» ({test.category})",
        details={"questions": len(test.questions)}, ip=client_ip(request),
    )
    db.commit()
    state = state_response(db, user)
    return {"test": pick(state["state"], "testCatalog", test.id), **state}


@router.delete("/recruitment/tests/{test_id}")
def delete_test(test_id: str, request: Request, user: CurrentUser, db: DbDep):
    test = db.get(TestDefinition, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Prueba no encontrada")
    name = test.name
    db.delete(test)
    log_action(
        db, actor=user, action="test.delete", entity_type="test", entity_id=test_id,
        summary=f"Eliminó la prueba «{name}»", ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)


@router.post("/recruitment/tests/import-excel")
async def import_excel(
    request: Request, user: CurrentUser, db: DbDep, file: Annotated[UploadFile, File()],
    custom_test_name: Annotated[str | None, Form(alias="customTestName")] = None,
    candidate_id: Annotated[str | None, Form(alias="candidateId")] = None,
):
    data, filename = await _read_upload(file)
    rows, sheet = _rows(data, filename)
    person = _candidate(db, candidate_id)[1] if candidate_id else None
    meta = extract_excel_test_metadata(rows, filename, sheet)
    name = (custom_test_name or "").strip() or meta["detectedTestName"]
    test = svc.find_test_by_name(db, name)
    is_new = test is None
    if is_new:
        test = TestDefinition(
            name=name, category=meta["detectedCategory"], target_area=meta["detectedTargetArea"],
            duration_minutes=max(10, len(meta["questions"]) * 2), passing_score=70,
            questions=meta["questions"], source_file_name=filename, created_by_name=user.full_name,
        )
        db.add(test)
        db.flush()
        log_action(
            db, actor=user, action="test.import", entity_type="test", entity_id=test.id,
            summary=f"Importó la prueba «{test.name}» desde {filename}",
            details={"category": test.category, "questions": len(test.questions)}, ip=client_ip(request),
        )
    result = None
    if person is not None:
        result, _ = svc.store_excel_result(db, person, test, test.name, filename, rows, user)
        if result is not None:
            log_action(
                db, actor=user, action="test.upload_result", entity_type="person", entity_id=person.id,
                summary=f"Cargó el resultado de «{test.name}» de {person.full_name}",
                details={"testId": test.id, "score": result.auto_computed_score, "verdict": result.concrete_verdict},
                ip=client_ip(request),
            )
    db.commit()
    state = state_response(db, user)
    out = {"test": pick(state["state"], "testCatalog", test.id), "isNewTest": is_new, **state}
    if result is not None:
        out["excelResult"] = svc.result_payload(result, rows=True)
    return out


@router.post("/recruitment/tests/upload-excel")
async def upload_excel(
    request: Request, user: CurrentUser, db: DbDep, file: Annotated[UploadFile, File()],
    candidate_id: Annotated[str, Form(alias="candidateId")],
    test_name: Annotated[str, Form(alias="testName")] = "",
    test_id: Annotated[str | None, Form(alias="testId")] = None,
):
    data, filename = await _read_upload(file)
    rows, sheet = _rows(data, filename)
    _, person = _candidate(db, candidate_id)
    test = db.get(TestDefinition, test_id) if test_id else None
    if test_id and test is None:
        raise HTTPException(status_code=404, detail="Prueba no encontrada")
    if test is None:
        test = svc.find_test_by_name(db, test_name)
    name = test.name if test else (test_name.strip() or extract_excel_test_metadata(rows, filename, sheet)["detectedTestName"])
    result, ev = svc.store_excel_result(db, person, test, name, filename, rows, user)
    if result is None:
        if test is None:  # se registra la prueba en el catálogo aunque no haya resultado
            meta = extract_excel_test_metadata(rows, filename, sheet)
            test = TestDefinition(
                name=name, category=meta["detectedCategory"], target_area=meta["detectedTargetArea"],
                duration_minutes=max(10, len(meta["questions"]) * 2), passing_score=70,
                questions=meta["questions"], source_file_name=filename, created_by_name=user.full_name,
            )
            db.add(test)
            db.flush()
            log_action(
                db, actor=user, action="test.import", entity_type="test", entity_id=test.id,
                summary=f"Registró la prueba «{test.name}» desde {filename} sin resultados",
                ip=client_ip(request),
            )
        db.commit()
        state = state_response(db, user)
        return {"registeredOnly": True, "test": pick(state["state"], "testCatalog", test.id),
                "message": MSG_NO_ANSWERS, **state}
    log_action(
        db, actor=user, action="test.upload_result", entity_type="person", entity_id=person.id,
        summary=f"Cargó el resultado de «{name}» de {person.full_name} ({result.auto_computed_score}/100)",
        details={"testId": test.id if test else None, "score": result.auto_computed_score,
                 "verdict": result.concrete_verdict, "passed": result.passed},
        ip=client_ip(request),
    )
    db.commit()
    state = state_response(db, user)
    out = {"excelResult": svc.result_payload(result, rows=True), **state}
    if test is not None:
        out["test"] = pick(state["state"], "testCatalog", test.id)
    return out


@router.get("/tests/excel-template")
def excel_template(
    user: CurrentUser, db: DbDep, test_id: Annotated[str | None, Query(alias="testId")] = None,
    candidate_id: Annotated[str | None, Query(alias="candidateId")] = None,
):
    test = db.get(TestDefinition, test_id) if test_id else None
    if test_id and test is None:
        raise HTTPException(status_code=404, detail="Prueba no encontrada")
    person = _candidate(db, candidate_id)[1] if candidate_id else None
    test_view = {"name": test.name, "questions": list(test.questions or [])} if test else None
    body = build_excel_template(test_view, person.full_name if person else None)
    name = folder_name_for(test.name) if test else "base"
    filename = f"Prueba_{name or 'base'}" + (f"_{folder_name_for(person.full_name)}" if person else "") + ".xlsx"
    return Response(
        content=body, headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

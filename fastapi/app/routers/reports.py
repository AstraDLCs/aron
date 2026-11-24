from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.routers._util import DbDep
from app.services import reports
from app.services.slugs import folder_name_for
from app.services.snapshot import build_state

router = APIRouter(prefix="/reports", tags=["reports"])


def download_response(body: str, media: str, filename: str) -> Response:
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return Response(content=body.encode("utf-8"), media_type=media, headers=headers)


def _download(db, user, request, *, report: str, summary: str, body: str, media: str, filename: str,
              entity_id: str | None = None) -> Response:
    log_action(
        db, actor=user, action="report.download", entity_type="report", entity_id=entity_id, summary=summary,
        details={"report": report}, ip=client_ip(request),
    )
    db.commit()
    return download_response(body, media, filename)


@router.get("/admin-doc")
def admin_doc(request: Request, user: CurrentUser, db: DbDep):
    state = build_state(db, user)
    return _download(
        db, user, request, report="admin-doc", summary="Descargó el informe ejecutivo",
        body=reports.build_admin_doc_html(state), media="application/msword",
        filename=f"Informe_Ejecutivo_{reports.today_str()}.doc",
    )


@router.get("/candidate/{candidate_id}/doc")
def candidate_doc(candidate_id: str, request: Request, user: CurrentUser, db: DbDep):
    state = build_state(db, user)
    candidate = next((c for c in state["candidates"] if c["id"] == candidate_id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada")
    return _download(
        db, user, request, report="candidate-doc", entity_id=candidate_id,
        summary=f"Descargó la ficha de {candidate['fullName']}",
        body=reports.build_candidate_doc_html(candidate, state["companyName"]), media="application/msword",
        filename=f"Ficha_{folder_name_for(candidate['fullName']) or 'candidato'}.doc",
    )


@router.get("/candidates-csv")
def candidates_csv(request: Request, user: CurrentUser, db: DbDep):
    state = build_state(db, user)
    return _download(
        db, user, request, report="candidates-csv", summary="Descargó el CSV de candidatos",
        body=reports.build_candidates_csv(state["candidates"]), media="text/csv; charset=utf-8",
        filename=f"Candidatos_{reports.today_str()}.csv",
    )


@router.get("/kpis-csv")
def kpis_csv(request: Request, user: CurrentUser, db: DbDep):
    state = build_state(db, user)
    return _download(
        db, user, request, report="kpis-csv", summary="Descargó el CSV de KPIs del proceso",
        body=reports.build_kpis_csv(state), media="text/csv; charset=utf-8",
        filename=f"KPIs_Procesos_{reports.today_str()}.csv",
    )

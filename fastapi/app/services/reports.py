"""Informes descargables: CSV de candidatos y KPIs, fichas Word (.doc en HTML) y CSV de la bitácora.

Port de recruitment.ts:573-924 sobre la foto (`build_state`), con la IA real (estado, veredicto, puntaje)
y la decisión humana (quién decidió).
"""
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

BOM = "﻿"
_TZ = ZoneInfo("America/Lima")


def today_str() -> str:
    return datetime.now(_TZ).strftime("%Y-%m-%d")


def _now_str() -> str:
    return datetime.now(_TZ).strftime("%Y-%m-%d %H:%M")


def _cell(value) -> str:
    text = "-" if value is None else str(value)
    return '"' + text.replace('"', '""') + '"'


def _row(values) -> str:
    return ",".join(_cell(v) for v in values)


def _h(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def _num(value, suffix: str = "") -> str:
    return "-" if value is None else f"{value}{suffix}"


# --- CSV -------------------------------------------------------------------

CANDIDATE_HEADERS = [
    "Candidato", "Edad", "Procedencia", "Universidad / Instituto", "Carrera", "Tiempo Trabajado (Años)",
    "Especificaciones Técnicas", "Bolsa de Trabajo Origen", "Vacante Postulada", "Estado Prueba Psicológica",
    "Estabilidad Emocional", "Tolerancia Faena/Altura", "Seguridad HSEC", "Trabajo en Equipo",
    "Razonamiento Operativo", "Promedio Psicológico", "Nivel Aptitud Psicológica", "Puntaje Técnico IA",
    "Puntaje Experiencia IA", "Puntaje Formación IA", "Índice Global Idoneidad IA", "Estado IA", "Veredicto IA",
    "Puntaje Aptitud IA", "Decisión", "Decidido por", "Días en Proceso",
]

_PSYCH_KEYS = (
    "estabilidadEmocional", "toleranciaFaenaAltura", "apegoSeguridadHSEC", "trabajoEquipo", "razonamientoOperativo",
)


def build_candidates_csv(candidates: list[dict]) -> str:
    rows = []
    for c in candidates:
        psych = c.get("psychEvaluation") or {}
        s = psych.get("scores")
        m = c.get("metricReport") or {}
        rows.append(_row([
            c.get("fullName"), c.get("age"), c.get("originLocation"), c.get("university"), c.get("career"),
            c.get("yearsWorked"), "; ".join(c.get("specifications") or []), c.get("sourceBoardName"),
            c.get("targetRoleTitle"), psych.get("status"),
            *([s.get(k) for k in _PSYCH_KEYS] if s else ["-"] * 5),
            psych.get("averageScore"), psych.get("aptitudeLevel"), m.get("technicalSpecsScore"),
            m.get("experienceScore"), m.get("educationCareerScore"), m.get("overallScore"), c.get("aiStatus"),
            c.get("aiVerdict"), c.get("aiAptitudeScore"), c.get("decision"), c.get("evaluatedBy"),
            c.get("processDaysElapsed"),
        ]))
    return BOM + "\r\n".join([_row(CANDIDATE_HEADERS), *rows])


def build_kpis_csv(state: dict) -> str:
    k = state["kpis"]
    lines = [
        _row(["RESUMEN KPI PROCESO RECLUTAMIENTO", state["companyName"]]),
        _row(["Cobertura Total de Vacantes", f"{k['filledVacancies']}/{k['totalVacancies']} ({k['coveragePercent']}%)"]),
        _row(["Total Candidatos en Proceso", k["totalCandidates"]]),
        _row(["Pruebas Psicológicas Completadas", k["psychCompletedCount"]]),
        _row(["Tiempo Promedio Proceso (Días)", k["avgProcessDays"]]),
        _row(["Bolsa con Mayor Aporte", f"{k['topBoardName']} ({k['topBoardCandidates']} candidatos)"]),
        "",
        _row(["VACANTE", "ÁREA", "URGENCIA", "REQUERIDAS", "CUBIERTAS", "PENDIENTES", "BOLSAS PUBLICADAS", "ESTADO"]),
    ]
    for n in state["jobNeeds"]:
        lines.append(_row([
            n["title"], n["department"], n["urgency"], n["vacancies"], n["filledCount"],
            max(0, n["vacancies"] - n["filledCount"]), "; ".join(n["publishedBoards"]), n["status"],
        ]))
    lines.append("")
    lines.append(_row([
        "BOLSA DE TRABAJO", "CATEGORÍA", "PROPUESTAS ENVIADAS", "CANDIDATOS ENVIADOS", "PRESELECCIONADOS IA",
        "CONTRATADOS", "RESPUESTA PROMEDIO (HRS)",
    ]))
    for b in state["jobBoards"]:
        lines.append(_row([
            b["name"], b["category"], b["proposalsSent"], b["candidatesReceived"], b["shortlistedCount"],
            b["hiredCount"], b["avgResponseHours"],
        ]))
    return BOM + "\r\n".join(lines)


AUDIT_HEADERS = ["Fecha", "Usuario", "Acción", "Entidad", "ID de entidad", "Resumen", "IP"]


def build_audit_csv(rows: list[dict]) -> str:
    lines = [_row(AUDIT_HEADERS)]
    for r in rows:
        lines.append(_row([
            r.get("at"), r.get("userName"), r.get("action"), r.get("entityType"), r.get("entityId"),
            r.get("summary"), r.get("ip"),
        ]))
    return BOM + "\r\n".join(lines)


# --- Word (HTML) -----------------------------------------------------------


def _bar(score, color: str = "#B26337") -> str:
    safe = max(0, min(100, round(score or 0)))
    return (
        '<div style="width:100%;background-color:#EFEFF1;height:8px;border-radius:4px;overflow:hidden;">'
        f'<div style="width:{safe}%;background-color:{color};height:8px;"></div></div>'
    )


_STYLE_COMMON = """
  body { font-family: Calibri, Arial, sans-serif; color: #23272E; margin: 28px; line-height: 1.45; }
  .banner { border-bottom: 3px solid #B26337; padding-bottom: 10px; margin-bottom: 14px; }
  .brand { color: #B26337; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.8px; }
  h1 { color: #23272E; font-size: 20px; margin: 3px 0 4px 0; }
  .sub { color: #5C626D; font-size: 11px; }
  h2 { color: #8C4722; font-size: 13px; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 18px; margin-bottom: 6px; border-bottom: 1px solid #E2E4E8; padding-bottom: 3px; }
  table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 11.5px; }
  th, td { border: 1px solid #D8DCE0; padding: 6px 8px; text-align: left; vertical-align: middle; }
  th { background-color: #F7F7F8; color: #23272E; font-weight: bold; }
  .kpi-grid { width: 100%; border-collapse: separate; border-spacing: 8px 0; margin: 10px -8px; }
  .kpi-box { border: 1px solid #E2E4E8; background-color: #F7F7F8; padding: 8px 10px; text-align: center; width: 25%; }
  .kpi-lbl { font-size: 10px; color: #5C626D; text-transform: uppercase; }
  .kpi-val { font-size: 18px; font-weight: bold; color: #23272E; margin-top: 2px; }
  .highlight { background-color: #FBF4EE; border: 1px solid #E6CDBE; padding: 10px 12px; margin-top: 12px; font-size: 12px; }
  .sign-table { margin-top: 24px; border: none; }
  .sign-table td { border: none; border-top: 1px solid #8F959E; width: 45%; padding-top: 6px; text-align: center; font-size: 11px; color: #5C626D; }
"""


def build_candidate_doc_html(candidate: dict, company_name: str) -> str:
    c = candidate
    m = c.get("metricReport") or {}
    psych = c.get("psychEvaluation") or {}
    s = psych.get("scores")
    years = c.get("yearsWorked")
    decider = c.get("evaluatedBy")
    decision_line = _h(c.get("decision"))
    if decider:
        decision_line += f" · decidido por {_h(decider)}"
    verdict = c.get("aiVerdict") or "Sin veredicto"
    if c.get("aiAptitudeScore") is not None:
        verdict += f" ({c['aiAptitudeScore']}/100)"
    if s:
        cells = "".join(
            f"<td>{s.get(k)}/100{_bar(s.get(k), '#B26337' if k == 'apegoSeguridadHSEC' else '#5C626D')}</td>"
            for k in _PSYCH_KEYS
        )
        psych_block = (
            "<table><tr><th>Estabilidad Emocional</th><th>Tolerancia Faena / Altura</th><th>Apego Seguridad HSEC</th>"
            "<th>Trabajo en Equipo</th><th>Razonamiento Operativo</th><th>Promedio</th></tr><tr>"
            f"{cells}<td><strong>{_h(psych.get('averageScore'))}/100</strong></td></tr></table>"
        )
    else:
        psych_block = (
            f'<p style="font-size:12px;">Prueba psicológica en estado: {_h(psych.get("status"))} '
            f'(Código: {_h(psych.get("accessCode"))}).</p>'
        )
    manager_note = (
        f"<br/><br/><strong>Nota Jefe de RR.HH.:</strong> {_h(c.get('managerNotes'))}" if c.get("managerNotes") else ""
    )
    decided_by = _h(decider) if decider else "Pendiente de decisión"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<title>Informe Candidato - {_h(c.get("fullName"))}</title>
<style>{_STYLE_COMMON}</style>
</head>
<body>
  <div class="banner">
    <div class="brand">{_h(company_name)} · Reporte Ejecutivo de Selección</div>
    <h1>Ficha Integral de Candidato: {_h(c.get("fullName"))}</h1>
    <div class="sub">Generado: {_h(_now_str())}</div>
  </div>

  <table class="kpi-grid">
    <tr>
      <td class="kpi-box"><div class="kpi-lbl">Índice Global IA</div><div class="kpi-val" style="color:#B26337;">{_h(m.get("overallScore"))}/100</div></td>
      <td class="kpi-box"><div class="kpi-lbl">Psicológico</div><div class="kpi-val">{_h(m.get("psychScore"))}/100</div></td>
      <td class="kpi-box"><div class="kpi-lbl">Experiencia</div><div class="kpi-val">{_num(years, " años")}</div></td>
      <td class="kpi-box"><div class="kpi-lbl">Decisión Actual</div><div class="kpi-val" style="font-size:13px;">{decision_line}</div></td>
    </tr>
  </table>

  <h2>1. Datos Generales y Perfil Profesional</h2>
  <table>
    <tr><th>Nombre Completo</th><td>{_h(c.get("fullName"))}</td><th>Edad</th><td>{_num(c.get("age"), " años")}</td></tr>
    <tr><th>Procedencia</th><td>{_h(c.get("originLocation"))}</td><th>Bolsa de Origen</th><td>{_h(c.get("sourceBoardName"))}</td></tr>
    <tr><th>Universidad / Instituto</th><td>{_h(c.get("university"))}</td><th>Carrera</th><td>{_h(c.get("career"))}</td></tr>
    <tr><th>Tiempo Trabajado</th><td>{_num(years, " años")}</td><th>Vacante Postulada</th><td>{_h(c.get("targetRoleTitle"))}</td></tr>
    <tr><th>Contacto</th><td>{_h(c.get("phoneOrEmail"))}</td><th>Veredicto IA</th><td>{_h(verdict)}</td></tr>
    <tr><th>Estado IA</th><td>{_h(c.get("aiStatus"))}</td><th>Decidido por</th><td>{decided_by}</td></tr>
  </table>

  <h2>2. Especificaciones Técnicas y Trayectoria</h2>
  <p style="font-size:12px;"><strong>Especificaciones acreditadas:</strong> {_h(" · ".join(c.get("specifications") or []))}</p>
  <p style="font-size:12px;"><strong>Resumen de experiencia:</strong> {_h(c.get("workHistorySummary"))}</p>

  <h2>3. Desempeño por Pilar del Puesto (Observación IA)</h2>
  <table>
    <tr><th style="width:32%;">Métrica Evaluada</th><th style="width:14%;">Puntaje</th><th style="width:24%;">Indicador Visual</th><th>Observación</th></tr>
    <tr><td>Especificaciones Técnicas y Faena</td><td><strong>{m.get("technicalSpecsScore")}/100</strong></td><td>{_bar(m.get("technicalSpecsScore"), "#23272E")}</td><td>Cruce con requisitos del cargo</td></tr>
    <tr><td>Experiencia y Tiempo Trabajado</td><td><strong>{m.get("experienceScore")}/100</strong></td><td>{_bar(m.get("experienceScore"), "#5C626D")}</td><td>{_num(years, " años")} acreditados</td></tr>
    <tr><td>Formación / Universidad / Carrera</td><td><strong>{m.get("educationCareerScore")}/100</strong></td><td>{_bar(m.get("educationCareerScore"), "#7A818D")}</td><td>{_h(c.get("career"))}</td></tr>
    <tr><td>Evaluación Psicológica</td><td><strong>{m.get("psychScore")}/100</strong></td><td>{_bar(m.get("psychScore"), "#B26337")}</td><td>{_h(psych.get("aptitudeLevel"))} ({_h(psych.get("status"))})</td></tr>
    <tr><th>Índice Global de Idoneidad</th><th>{m.get("overallScore")}/100</th><th>{_bar(m.get("overallScore"), "#B26337")}</th><th>{_h(m.get("fitVerdict"))}</th></tr>
  </table>

  <h2>4. Resultados de Prueba Psicológica</h2>
  {psych_block}
  <p style="font-size:12px; margin-top:6px;">{_h(psych.get("aiPsychObservation"))}</p>

  <div class="highlight">
    <strong>Dictamen Consolidado de la IA para Gerencia General:</strong><br/>
    {_h(m.get("aiDetailedReport"))}{manager_note}
  </div>

  <table class="sign-table">
    <tr>
      <td><strong>{decided_by}</strong><br/>Jefe de Recursos Humanos · {_h(company_name)}</td>
      <td style="border:none;width:10%;"></td>
      <td><strong>Visto Bueno Gerencia General</strong><br/>Administración Superior</td>
    </tr>
  </table>
</body>
</html>"""


def build_admin_doc_html(state: dict) -> str:
    k = state["kpis"]
    candidates = state["candidates"]
    ranked = sorted(state["jobBoards"], key=lambda b: -(b["candidatesReceived"]))
    max_board = max(1, ranked[0]["candidatesReceived"] if ranked else 1)
    top = sorted(candidates, key=lambda c: -c["metricReport"]["overallScore"])[:3]

    def psych(c):
        v = c["psychEvaluation"].get("averageScore")
        return "Pend." if v is None else v

    vacancy_rows = ""
    for n in state["jobNeeds"]:
        pct = round(n["filledCount"] / n["vacancies"] * 100) if n["vacancies"] > 0 else 0
        vacancy_rows += (
            f"<tr><td><strong>{_h(n['title'])}</strong></td><td>{_h(n['department'])}</td><td>{_h(n['urgency'])}</td>"
            f"<td>{n['filledCount']}/{n['vacancies']} ({pct}%)</td><td style=\"width:110px;\">{_bar(pct)}</td>"
            f"<td>{_h(', '.join(n['publishedBoards']))}</td><td>{_h(n['status'])}</td></tr>"
        )
    board_rows = ""
    for i, b in enumerate(ranked):
        pct = round(b["candidatesReceived"] / max_board * 100)
        board_rows += (
            f"<tr><td>{i + 1:02d}. <strong>{_h(b['name'])}</strong></td><td>{_h(b['category'])}</td>"
            f"<td>{b['proposalsSent']}</td><td><strong>{b['candidatesReceived']}</strong></td>"
            f"<td style=\"width:120px;\">{_bar(pct, '#B26337' if i == 0 else '#7A818D')}</td>"
            f"<td>{b['shortlistedCount']}</td><td>{b['hiredCount']}</td></tr>"
        )
    candidate_rows = "".join(
        f"<tr><td><strong>{_h(c['fullName'])}</strong></td><td>{_h(c['age'])}</td><td>{_h(c['originLocation'])}</td>"
        f"<td>{_h(c['university'])} / {_h(c['career'])}</td><td>{_num(c['yearsWorked'], ' años')}</td>"
        f"<td>{_h(c['sourceBoardName'])}</td><td>{psych(c)}</td>"
        f"<td><strong>{c['metricReport']['overallScore']}/100</strong>{_bar(c['metricReport']['overallScore'])}</td>"
        f"<td>{_h(c['decision'])}</td></tr>"
        for c in candidates
    )
    top_rows = "".join(
        f"<tr><td>#{i + 1}</td><td><strong>{_h(c['fullName'])}</strong></td><td>{_h(c['targetRoleTitle'])}</td>"
        f"<td>{_num(c['yearsWorked'], ' años')}</td><td>{psych(c)}/100</td>"
        f"<td><strong>{c['metricReport']['overallScore']}/100</strong></td><td>{_h(c['decision'])}</td></tr>"
        for i, c in enumerate(top)
    )
    company = state["companyName"]
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<title>Informe Ejecutivo Gerencia - {_h(company)}</title>
<style>{_STYLE_COMMON}</style>
</head>
<body>
  <div class="banner">
    <div class="brand">{_h(company)} · Dirección y Gerencia General</div>
    <h1>Informe Ejecutivo de Reclutamiento y Selección IA</h1>
    <div class="sub">Preparado para Gerencia General / Administración · Responsable: {_h(state["hrChiefName"])} ({_h(state["hrChiefTitle"])}) · Fecha: {today_str()}</div>
  </div>

  <table class="kpi-grid">
    <tr>
      <td class="kpi-box"><div class="kpi-lbl">Cobertura de Vacantes</div><div class="kpi-val" style="color:#B26337;">{k["coveragePercent"]}%</div><div class="sub">{k["filledVacancies"]}/{k["totalVacancies"]} plazas</div></td>
      <td class="kpi-box"><div class="kpi-lbl">Candidatos Evaluados</div><div class="kpi-val">{k["totalCandidates"]}</div><div class="sub">{k["psychCompletedCount"]} con prueba psico.</div></td>
      <td class="kpi-box"><div class="kpi-lbl">Bolsa Líder</div><div class="kpi-val" style="font-size:13px;">{_h(k["topBoardName"])}</div><div class="sub">{k["topBoardCandidates"]} postulantes</div></td>
      <td class="kpi-box"><div class="kpi-lbl">Tiempo y Calibración IA</div><div class="kpi-val">{k["avgProcessDays"]} días</div><div class="sub">Acuerdo IA/RR.HH.: {k["aiAgreementRate"]}%</div></td>
    </tr>
  </table>

  <h2>1. Terna Ejecutiva Prioritaria (Mejores Puntuaciones IA)</h2>
  <table>
    <tr><th>Orden</th><th>Candidato</th><th>Cargo Objetivo</th><th>Experiencia</th><th>Psicológico</th><th>Global IA</th><th>Estado</th></tr>
    {top_rows}
  </table>

  <h2>2. Vacantes por Cubrir y Avance Visual</h2>
  <table>
    <tr><th>Puesto / Cargo</th><th>Área</th><th>Urgencia</th><th>Cobertura</th><th>Avance</th><th>Bolsas Publicadas</th><th>Estado</th></tr>
    {vacancy_rows}
  </table>

  <h2>3. Ranking de Bolsas de Trabajo (Propuestas vs Candidatos Recibidos)</h2>
  <table>
    <tr><th>Bolsa / Canal</th><th>Categoría</th><th>Propuestas</th><th>Candidatos</th><th>Aporte Relativo</th><th>Preselección</th><th>Contratados</th></tr>
    {board_rows}
  </table>

  <h2>4. Base Maestra de Candidatos y Métricas Completas</h2>
  <table>
    <tr><th>Nombre</th><th>Edad</th><th>Procedencia</th><th>Universidad / Carrera</th><th>Experiencia</th><th>Bolsa</th><th>Psico.</th><th>Global IA</th><th>Decisión</th></tr>
    {candidate_rows}
  </table>

  <table class="sign-table">
    <tr>
      <td><strong>{_h(state["hrChiefName"])}</strong><br/>{_h(state["hrChiefTitle"])} · {_h(company)}</td>
      <td style="border:none;width:10%;"></td>
      <td><strong>Gerencia General / Administrador</strong><br/>Recepción de Informe Ejecutivo</td>
    </tr>
  </table>
</body>
</html>"""

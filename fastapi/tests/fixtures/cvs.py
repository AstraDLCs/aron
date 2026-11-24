"""CVs de prueba en PDF (fpdf2). Todos los datos personales son ficticios."""
from datetime import UTC, datetime

from fpdf import FPDF

_FIXED_DATE = datetime(2026, 1, 1, tzinfo=UTC)

DEFAULT_BODY = (
    "EXPERIENCIA LABORAL\n"
    "Operador de planta concentradora en Minera Ficticia S.A. 2015 - 2023\n"
    "Chancado, molienda SAG y flotación. Certificación HSEC vigente. IPERC continuo.\n"
    "FORMACIÓN ACADÉMICA\n"
    "TECSUP - Operación de plantas concentradoras\n"
)


def _pdf() -> FPDF:
    pdf = FPDF()
    pdf.set_creation_date(_FIXED_DATE)  # mismo contenido -> mismos bytes (mismo sha256)
    pdf.add_page()
    return pdf


def make_cv_pdf(full_name: str, dni: str, email: str, phone: str, body: str = DEFAULT_BODY) -> bytes:
    pdf = _pdf()
    pdf.set_font("Helvetica", size=11)
    lines = ["CURRICULUM VITAE", full_name]
    if dni:
        lines.append(f"DNI: {dni}")
    if email:
        lines.append(f"Email: {email}")
    if phone:
        lines.append(f"Celular: {phone}")
    lines.append("Ciudad: Arequipa")
    for line in [*lines, *body.split("\n")]:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def make_blank_pdf() -> bytes:
    """Una página sin texto: equivale a un PDF escaneado sin OCR."""
    return bytes(_pdf().output())


# --- ayudas para las pruebas de la API ---------------------------------------


def create_position(client, headers, name: str, area: str = "Planta", **kw) -> dict:
    r = client.post("/api/positions", json={"name": name, "area": area, **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["position"]


def create_source(client, headers, name: str, category: str = "Portal Minero") -> dict:
    r = client.post("/api/sources", json={"name": name, "category": category}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["source"]


def create_requirement(client, headers, position_id: str, quantity: int = 1, urgency: str = "Media") -> dict:
    r = client.post(
        "/api/requirements", json={"positionId": position_id, "quantity": quantity, "urgency": urgency},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["requirement"]


def upload_cv(client, headers, data: bytes, filename: str, position_id: str, source_id: str,
              requirement_id: str | None = None, origin: str = "app"):
    form = {"positionId": position_id, "sourceId": source_id, "origin": origin}
    if requirement_id is not None:
        form["requirementId"] = requirement_id
    return client.post(
        "/api/cv-files", files={"file": (filename, data, "application/octet-stream")}, data=form, headers=headers,
    )


def candidate_in(state: dict, candidate_id: str) -> dict:
    return next(c for c in state["candidates"] if c["id"] == candidate_id)

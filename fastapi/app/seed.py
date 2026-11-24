"""Datos de demostración: `python -m app.seed --demo` (solo si la base no tiene puestos)."""
import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.constants import SYSTEM_ACTOR
from app.db import SessionLocal
from app.models.criteria import RecruitmentCriterion
from app.models.org import Position, Requirement, Source
from app.seed_data import CRITERIA, VACANCIES
from app.services.app_settings import get_app_settings
from app.services.slugs import folder_name_for

COMPANY = "Compañía Minera Las Bravas"

# (nombre, área o None para heredar, hijos)
ORG = (
    "Gerencia General", "Gerencia", [
        ("Gerencia de Operaciones Mina", "Operaciones Mina", [
            ("Superintendencia de Mina", None, [
                ("Jefe de Guardia Mina (Subterránea / Tajo Abierto)", None, [
                    ("Operador de Maquinaria Pesada Mina (Scooptram / Volquete / Camión)", None, []),
                    ("Perforista y Cargador de Explosivos (Carnet SUCAMEC)", "Perforación y Voladura", []),
                    ("Técnico de Sostenimiento y Ventilación Mina", None, []),
                ]),
            ]),
            ("Superintendencia de Geología y Planeamiento", "Geología y Planeamiento", [
                ("Geólogo de Mina y Control de Leyes (Ore Control)", None, []),
                ("Ingeniero de Planeamiento Mina (Corto y Mediano Plazo)", None, []),
            ]),
        ]),
        ("Gerencia de Planta", "Control Metalúrgico", [
            ("Superintendencia de Planta Concentradora", None, [
                ("Operador de Planta Concentradora Senior", None, []),
            ]),
            ("Jefe de Laboratorio Metalúrgico", None, [
                ("Analista de Laboratorio Metalúrgico", None, []),
            ]),
        ]),
        ("Gerencia de Mantenimiento", "Mantenimiento Mina", [
            ("Mecánico de Mantenimiento Equipo Pesado (Trackless / Flota)", None, []),
            ("Electricista Industrial de Alta Tensión y Subestaciones Mina", None, []),
        ]),
        ("Gerencia de Seguridad HSEC", "Seguridad HSEC", [
            ("Ingeniero Supervisor de Seguridad HSEC", None, []),
            ("Paramédico / Médico Ocupacional de Tópico Minero", None, []),
        ]),
        ("Gerencia de Medio Ambiente y Relaciones Comunitarias", "Medio Ambiente y RR.CC.", [
            ("Supervisor de Medio Ambiente y Recursos Hídricos", None, []),
            ("Especialista de Relaciones Comunitarias y Gestión Social", None, []),
        ]),
        ("Gerencia de Logística", "Logística y Campamento", [
            ("Coordinador de Bodega, Explosivos y Campamento Minero", None, []),
        ]),
        ("Gerencia de Recursos Humanos", "Recursos Humanos", [
            ("Jefe de Recursos Humanos", None, []),
        ]),
    ],
)

# nombre, carpeta, categoría, propuestas, horas de respuesta
SOURCES = [
    ("Computrabajo Minería", "computrabajo", "Bolsa Nacional", 9, 6),
    ("LinkedIn Talento Minero", "linkedin", "Red Profesional", 7, 14),
    ("Bumeran Perú", "bumeran", "Bolsa Nacional", 6, 11),
    ("Referidos de Faena", "referidos-faena", "Referidos Faena", 4, 4),
    ("Portal Talento Las Bravas", "portal-las-bravas", "Portal Minero", 5, 9),
    ("Indeed Operaciones", "indeed", "Bolsa Nacional", 3, 18),
]


def _add_positions(db: Session, vacancies: dict[str, dict]) -> dict[str, Position]:
    by_name: dict[str, Position] = {}
    order = 0

    def walk(node, parent: Position | None, inherited: str):
        nonlocal order
        name, area, children = node
        area = area or inherited
        vac = vacancies.get(name)
        pos = Position(
            name=name, folder_name=folder_name_for(name), area=area, parent_id=parent.id if parent else None,
            required_skills=vac["required_skills"] if vac else "",
            technical_specifications=vac["technical_specifications"] if vac else "",
            sort_order=order,
        )
        order += 1
        db.add(pos)
        db.flush()
        by_name[name] = pos
        for child in children:
            walk(child, pos, area)

    walk(ORG, None, "Gerencia")
    return by_name


def load_demo(db: Session) -> dict:
    settings_row = get_app_settings(db)
    settings_row.company_name = COMPANY
    positions = _add_positions(db, {v["title"]: v for v in VACANCIES})
    sources = {}
    for name, folder, category, proposals, hours in SOURCES:
        src = Source(name=name, folder_name=folder, category=category, proposals_sent=proposals,
                     avg_response_hours=hours)
        db.add(src)
        sources[name] = src
    db.flush()
    for v in VACANCIES:
        db.add(Requirement(
            position_id=positions[v["title"]].id, quantity=v["vacancies"], urgency=v["urgency"],
            target_days_to_fill=v["target_days"], context=v["company_context"],
            published_source_ids=[sources[b].id for b in v["published_boards"] if b in sources],
            created_by_name=SYSTEM_ACTOR,
        ))
    for c in CRITERIA:
        db.add(RecruitmentCriterion(
            title=c["title"], applies_to_department=c["department"], weight_label=c["weight"],
            rule_text=c["rule_text"], is_correction=c["is_correction"],
            wrong_ai_assumption=c["wrong_ai_assumption"], learned_from_candidate=c["learned_from_candidate"],
            created_by_name=SYSTEM_ACTOR,
        ))
    db.flush()
    counts = {"positions": len(positions), "requirements": len(VACANCIES), "sources": len(SOURCES),
              "criteria": len(CRITERIA)}
    log_action(
        db, actor=SYSTEM_ACTOR, action="seed.demo", entity_type="seed",
        summary=f"Cargó los datos de demostración de {COMPANY}", details=counts,
    )
    return counts


def _run(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Position)):
        print("La base ya tiene datos; no se cargó la demo", file=sys.stderr)
        return 1
    counts = load_demo(db)
    db.commit()
    print(f"Demo cargada: {counts['positions']} puestos, {counts['requirements']} requerimientos, "
          f"{counts['sources']} fuentes, {counts['criteria']} criterios")
    return 0


def main(argv: list[str], db: Session | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    parser.add_argument("--demo", action="store_true", required=True, help="carga los datos de demostración")
    parser.parse_args(argv)
    if db is not None:  # sesión inyectada (pruebas): quien la pasa la cierra
        return _run(db)
    with SessionLocal() as session:
        return _run(session)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Personas: enlazar o crear, prioridad de los datos (user > ia > reglas), "posible misma persona" y unir.

Nada de este módulo hace commit: confirma quien llama.
"""
import re
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.models.people import Candidate, CvFile, Person, default_psych_evaluation
from app.models.user import User
from app.services.candidate_rules import rescore_person
from app.services.cv_parser import UNKNOWN_NAME, split_person_name
from app.services.slugs import normalize_key

FieldSource = Literal["user", "ia", "reglas"]
SOURCE_RANK = {"reglas": 1, "ia": 2, "user": 3}
PSYCH_STATUS_RANK = {"Sin enviar": 0, "Enviada": 1, "Completada": 2}

TEXT_FIELDS = (
    "first_names", "last_names", "full_name", "document_id", "email", "phone", "origin_location", "university",
    "career", "work_history_summary",
)
INT_FIELDS = ("age", "years_worked")
LIST_FIELDS = ("specifications", "languages", "licenses")
PERSON_FIELDS = TEXT_FIELDS + INT_FIELDS + LIST_FIELDS
NAME_FIELDS = ("full_name", "first_names", "last_names")
# Largo máximo de cada columna de texto: lo que lee el CV o la IA se recorta en vez de romper el INSERT.
MAX_LENGTH = {
    f: Person.__table__.c[f].type.length for f in TEXT_FIELDS if getattr(Person.__table__.c[f].type, "length", None)
}
LIST_ITEM_MAX = 200


def _clean(field: str, value):
    if field in TEXT_FIELDS:
        text = "" if value is None else str(value).strip()
        limit = MAX_LENGTH.get(field)
        return text[:limit].rstrip() if limit else text
    if field in INT_FIELDS:
        return None if value is None or value == "" else int(value)
    items = (str(v).strip()[:LIST_ITEM_MAX] for v in (value or []))
    return list(dict.fromkeys(v for v in items if v))  # sin vacíos ni repetidos, en orden


def _is_empty(value) -> bool:
    return value is None or value == "" or value == []


def _is_blank(field: str, value) -> bool:
    """Vacío, o el nombre provisorio que pone el lector cuando no encuentra el nombre."""
    return _is_empty(value) or (field == "full_name" and value == UNKNOWN_NAME)


def apply_person_fields(person: Person, values: dict, source: FieldSource) -> list[str]:
    """Aplica `values` (claves = campos del modelo) respetando la prioridad user > ia > reglas.

    - Una fuente pisa el valor de otra de igual o menor prioridad; nunca uno de mayor prioridad.
    - Un valor vacío no sobrescribe a uno lleno. Excepción deliberada: el usuario sí puede vaciar un campo
      (para corregir un dato mal leído); el campo queda como suyo y la IA o las reglas no lo vuelven a llenar.
    - El nombre completo nunca queda vacío, y el provisorio "Postulante (Verificar Nombre)" cuenta como vacío.

    Devuelve los campos cuyo valor cambió.
    """
    if source not in SOURCE_RANK:
        raise ValueError(f"Fuente de datos desconocida: {source}")
    rank = SOURCE_RANK[source]
    sources = dict(person.field_sources or {})
    changed: list[str] = []
    for field, raw in values.items():
        if field not in PERSON_FIELDS:
            raise ValueError(f"Campo de persona desconocido: {field}")
        value = _clean(field, raw)
        if _is_blank(field, value) and (source != "user" or field == "full_name"):
            continue
        if rank < SOURCE_RANK.get(sources.get(field), 0):
            continue
        sources[field] = source
        if getattr(person, field) != value:
            setattr(person, field, value)
            changed.append(field)
    if sources != (person.field_sources or {}):
        person.field_sources = sources  # se reasigna: JSONB no detecta cambios internos
    return changed


def with_name_parts(values: dict, person: Person | None = None) -> dict:
    """Mantiene juntos el nombre completo y sus partes cuando se da solo uno de los lados."""
    values = dict(values)
    has_parts = "first_names" in values or "last_names" in values
    if values.get("full_name") and not has_parts:
        values["first_names"], values["last_names"] = split_person_name(str(values["full_name"]).strip())
    elif has_parts and "full_name" not in values:
        first = values.get("first_names", person.first_names if person else "") or ""
        last = values.get("last_names", person.last_names if person else "") or ""
        if full := f"{first.strip()} {last.strip()}".strip():
            values["full_name"] = full
    return values


def _new_person() -> Person:
    return Person(
        full_name=UNKNOWN_NAME, first_names="", last_names="", document_id="", email="", phone="", age=None,
        origin_location="", university="", career="", years_worked=None, work_history_summary="",
        specifications=[], languages=[], licenses=[], field_sources={},
        psych_evaluation=default_psych_evaluation(), possible_same_person_ids=[],
    )


def find_same_person(db: Session, *, sha256: str, document_id: str, email: str) -> tuple[Person | None, str]:
    """La persona con este archivo (en otro puesto), este documento o este email: (persona, motivo)."""
    if sha256:
        person_id = db.scalar(
            select(Candidate.person_id)
            .join(CvFile, CvFile.id == Candidate.cv_file_id)
            .where(CvFile.sha256 == sha256)
            .order_by(CvFile.uploaded_at)
            .limit(1)
        )
        if person_id is not None:
            return db.get(Person, person_id), "mismo archivo"
    if document_id:
        person = db.scalar(
            select(Person).where(Person.document_id == document_id).order_by(Person.created_at).limit(1)
        )
        if person is not None:
            return person, "mismo documento"
    if email:
        person = db.scalar(
            select(Person).where(func.lower(Person.email) == email.lower()).order_by(Person.created_at).limit(1)
        )
        if person is not None:
            return person, "mismo email"
    return None, ""


def link_or_create_person(
    db: Session, *, sha256: str, values: dict, source: FieldSource, actor: User | str, ip: str | None = None
) -> Person:
    """Enlaza con la persona del mismo archivo, documento o email (en ese orden) o crea una nueva.

    Los datos de `values` se aplican con `apply_person_fields(…, source)`. El enlace queda en la bitácora
    (`person.link`). Al final se recalcula "posible misma persona".
    """
    document_id = _clean("document_id", values.get("document_id"))
    email = _clean("email", values.get("email"))
    person, reason = find_same_person(db, sha256=sha256, document_id=document_id, email=email)
    if person is None:
        person = _new_person()
        apply_person_fields(person, values, source)
        db.add(person)
        db.flush()
    else:
        apply_person_fields(person, values, source)
        db.flush()
        log_action(
            db, actor=actor, action="person.link", entity_type="person", entity_id=person.id,
            summary=f"Enlazó el CV a {person.full_name} ({reason})", details={"reason": reason}, ip=ip,
        )
    refresh_possible_same(db, person)
    return person


# --- posible misma persona -------------------------------------------------


def _phone_key(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 9:
        return digits[-9:]  # sin el prefijo de país (+51)
    return digits if len(digits) >= 6 else ""


def _name_key(name: str) -> str:
    return "" if not name or name == UNKNOWN_NAME else normalize_key(name)


def refresh_possible_same(db: Session, person: Person) -> None:
    """Marca, en ambos sentidos, a las otras personas con el mismo teléfono o el mismo nombre normalizado.

    También marca el mismo documento o email: en la ingesta esos casos se enlazan solos, pero pueden
    aparecer al editar a mano. Es solo un aviso para "Unir"; quita las marcas que ya no coinciden.
    """
    phone, name = _phone_key(person.phone), _name_key(person.full_name)
    doc, email = person.document_id, (person.email or "").lower()
    rows = db.execute(
        select(Person.id, Person.phone, Person.full_name, Person.document_id, Person.email).where(
            Person.id != person.id
        )
    ).all()
    matches = {
        r.id for r in rows
        if (phone and _phone_key(r.phone) == phone)
        or (name and _name_key(r.full_name) == name)
        or (doc and r.document_id == doc)
        or (email and (r.email or "").lower() == email)
    }
    for other_id in set(person.possible_same_person_ids or []) | matches:
        other = db.get(Person, other_id)
        if other is None:
            continue
        current = list(other.possible_same_person_ids or [])
        updated = [i for i in current if i != person.id] + ([person.id] if other_id in matches else [])
        if updated != current:
            other.possible_same_person_ids = updated
    person.possible_same_person_ids = sorted(matches)


def delete_person(db: Session, person: Person) -> None:
    """Borra a la persona (sin postulaciones) y la quita de las marcas de "posible misma persona"."""
    for other in db.scalars(select(Person).where(Person.possible_same_person_ids.contains([person.id]))):
        other.possible_same_person_ids = [i for i in other.possible_same_person_ids if i != person.id]
    db.delete(person)
    db.flush()


# --- unir ------------------------------------------------------------------


def _takes_drop_value(keep: Person, drop: Person, field: str) -> bool:
    drop_value = getattr(drop, field)
    if _is_blank(field, drop_value):
        return False
    keep_rank = SOURCE_RANK.get((keep.field_sources or {}).get(field), 0)
    drop_rank = SOURCE_RANK.get((drop.field_sources or {}).get(field), 0)
    return drop_rank > keep_rank or (_is_blank(field, getattr(keep, field)) and drop_rank >= keep_rank)


def merge_persons(db: Session, keep_id: str, drop_id: str, actor: User | str, ip: str | None = None) -> Person:
    """Une `drop` en `keep`: mueve las postulaciones y la evaluación psicológica, completa los datos y borra `drop`.

    Los datos de `drop` entran si `keep` no tiene ese dato o si vienen de una fuente de mayor prioridad. La
    evaluación psicológica que se conserva es la más avanzada (Completada > Enviada > Sin enviar).
    Lanza ValueError (misma persona) o LookupError (no existe). Bitácora `person.merge`.
    """
    if keep_id == drop_id:
        raise ValueError("No se puede unir una persona consigo misma")
    keep, drop = db.get(Person, keep_id), db.get(Person, drop_id)
    if keep is None or drop is None:
        raise LookupError("Persona no encontrada")
    drop_name = drop.full_name

    sources = dict(keep.field_sources or {})
    drop_sources = drop.field_sources or {}
    fields = [f for f in PERSON_FIELDS if f not in NAME_FIELDS]
    if _takes_drop_value(keep, drop, "full_name"):
        fields = [*NAME_FIELDS, *fields]  # el nombre se toma completo (nombres y apellidos juntos)
    for field in fields:
        if field in NAME_FIELDS or _takes_drop_value(keep, drop, field):
            setattr(keep, field, getattr(drop, field))
            if field in drop_sources:
                sources[field] = drop_sources[field]
    keep.field_sources = sources

    keep_psych, drop_psych = keep.psych_evaluation or {}, drop.psych_evaluation or {}
    if PSYCH_STATUS_RANK.get(drop_psych.get("status"), 0) > PSYCH_STATUS_RANK.get(keep_psych.get("status"), 0):
        keep.psych_evaluation = dict(drop_psych)

    for cand in db.scalars(select(Candidate).where(Candidate.person_id == drop.id)):
        cand.person_id = keep.id
    # Tarea 10: mover aquí también los resultados de pruebas Excel de `drop` (excel_test_results.person_id).
    db.flush()

    delete_person(db, drop)
    refresh_possible_same(db, keep)
    rescore_person(db, keep)
    log_action(
        db, actor=actor, action="person.merge", entity_type="person", entity_id=keep.id,
        summary=f"Unió a {drop_name} con {keep.full_name}", details={"keptId": keep.id, "droppedId": drop_id}, ip=ip,
    )
    return keep

"""Ingesta de CVs: la carpeta `rrhh/<puesto>/<fuente>/`, sin repetidos por puesto, enlazada a personas.

`ingest_cv` sirve tanto para la subida HTTP como para la revisión de la carpeta del servidor (Tarea 8, con
`existing_rel_path` y actor 'Sistema'). **No hace commit**: confirma quien llama, también en los rechazos
(`duplicate` / `deleted_before` dejan su fila de bitácora). Si el commit falla después de un `created` con
`file_written=True`, quien llama debe borrar el archivo con `discard_written_file`.

La fuente de verdad contra repetidos es la restricción UNIQUE(sha256, position_id): si dos subidas compiten,
la que pierde recibe `duplicate` y borra el archivo que escribió.
"""
import hashlib
import logging
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.config import get_settings
from app.constants import ALLOWED_CV_EXTENSIONS, CV_ORIGINS, MAX_CV_BYTES
from app.models.org import Position, Requirement, Source
from app.models.people import Candidate, CvFile, DeletedCvHash, Person
from app.models.user import User
from app.services.app_settings import get_app_settings
from app.services.candidate_rules import apply_rule_scores, position_view
from app.services.cv_parser import UNKNOWN_NAME, ParsedCv, parse_cv_text
from app.services.persons import link_or_create_person, with_name_parts
from app.services.storage import RrhhStorage
from app.services.text_extract import extract_text

logger = logging.getLogger(__name__)

IngestStatus = Literal["created", "duplicate", "deleted_before", "unsupported", "too_large", "invalid_target"]

MSG_UNSUPPORTED = "Formato no soportado: usa PDF, DOCX, TXT o RTF"
MSG_TOO_LARGE = "El archivo supera 15 MB"
MSG_BAD_REQUIREMENT = "El requerimiento no está abierto o no corresponde al puesto"
MSG_NO_POSITION = "El puesto no existe"
MSG_NO_SOURCE = "La fuente no existe"

MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
}


@dataclass
class IngestResult:
    status: IngestStatus
    message: str
    candidate_id: str | None = None
    cv_file_id: str | None = None
    person_id: str | None = None
    existing: dict | None = None
    stored_path: str | None = None  # ruta relativa registrada (solo en `created`)
    file_written: bool = False  # True si `ingest_cv` escribió el archivo (no si venía `existing_rel_path`)


# --- ayudas ----------------------------------------------------------------


def actor_name(actor: User | str | None) -> str:
    return actor.full_name if isinstance(actor, User) else (actor or "")


def actor_id(actor: User | str | None) -> str | None:
    return actor.id if isinstance(actor, User) else None


def extension_of(filename: str) -> str:
    return PurePosixPath((filename or "").replace("\\", "/")).suffix.lower()


def ai_available(db: Session) -> bool:
    return get_app_settings(db).ai_enabled and bool(get_settings().openrouter_api_key)


def initial_ai_status(db: Session, text_status: str) -> str:
    """'Sin texto' si no hay texto utilizable; si no, 'En cola' con IA disponible o 'Sin IA' sin ella."""
    if text_status != "ok":
        return "Sin texto"
    return "En cola" if ai_available(db) else "Sin IA"


def reset_ai_result(candidate: Candidate) -> None:
    """Borra el resultado de la IA (p. ej. al cambiar de puesto: el veredicto era para el puesto anterior)."""
    candidate.ai_verdict = None
    candidate.ai_aptitude_score = None
    candidate.ai_technical = candidate.ai_experience = candidate.ai_education = None
    candidate.ai_strengths = []
    candidate.ai_observations = []
    candidate.ai_reason = ""
    candidate.ai_applied_criteria = []
    candidate.ai_summary = ""
    candidate.ai_detailed_report = ""
    candidate.ai_model = None
    candidate.ai_classified_at = None
    candidate.ai_attempts = 0
    candidate.ai_next_attempt_at = None
    candidate.ai_error = None


def pick_requirement(db: Session, position_id: str, requirement_id: str | None) -> Requirement | None:
    """El requerimiento indicado (debe estar Abierto y ser del puesto) o, si no se indica, el Abierto más antiguo."""
    if requirement_id:
        req = db.get(Requirement, requirement_id)
        if req is None or req.position_id != position_id or req.status != "Abierto":
            raise ValueError(MSG_BAD_REQUIREMENT)
        return req
    return db.scalar(
        select(Requirement)
        .where(Requirement.position_id == position_id, Requirement.status == "Abierto")
        .order_by(Requirement.opened_at, Requirement.id)
        .limit(1)
    )


def find_blocked(db: Session, sha256: str, position_id: str) -> DeletedCvHash | None:
    return db.scalar(
        select(DeletedCvHash).where(DeletedCvHash.sha256 == sha256, DeletedCvHash.position_id == position_id)
    )


def find_duplicate(db: Session, sha256: str, position_id: str) -> CvFile | None:
    return db.scalar(select(CvFile).where(CvFile.sha256 == sha256, CvFile.position_id == position_id))


def duplicate_info(cv: CvFile) -> dict:
    return {"path": cv.stored_path, "uploadedBy": cv.uploaded_by_name, "uploadedAt": cv.uploaded_at.isoformat()}


def blocked_info(blocked: DeletedCvHash) -> dict:
    return {
        "blockedId": blocked.id, "originalName": blocked.original_name, "deletedBy": blocked.deleted_by_name,
        "deletedAt": blocked.deleted_at.isoformat(),
    }


def duplicate_message(position: Position) -> str:
    return f"Este CV ya está registrado en el puesto {position.name}"


def blocked_message(position: Position) -> str:
    return f"Este CV se eliminó antes del puesto {position.name}; permite reimportarlo para volver a subirlo"


def discard_written_file(storage: RrhhStorage, result: IngestResult) -> None:
    """Borra el archivo que escribió `ingest_cv` (para cuando el commit de quien llama falla)."""
    if result.file_written and result.stored_path:
        _safe_delete(storage, result.stored_path)


def _safe_delete(storage: RrhhStorage, rel: str) -> None:
    try:
        storage.delete(rel)
    except Exception:  # noqa: BLE001 - la limpieza no debe tapar el error original
        logger.exception("No se pudo borrar el archivo '%s'", rel)


def parsed_person_values(parsed: ParsedCv) -> dict:
    return {
        "full_name": "" if parsed.full_name == UNKNOWN_NAME else parsed.full_name,
        "first_names": parsed.first_names,
        "last_names": parsed.last_names,
        "document_id": parsed.document_id,
        "email": parsed.email,
        "phone": parsed.phone,
        "age": parsed.age,
        "origin_location": parsed.origin_location,
        "university": parsed.university,
        "career": parsed.career,
        "years_worked": parsed.years_worked,
        "work_history_summary": parsed.work_history_summary,
        "specifications": parsed.specifications,
    }


def manual_text(person: Person, interview_notes: str = "") -> str:
    """Texto armado con los datos de la persona, para clasificar una postulación sin CV legible."""
    rows = [
        ("Nombre", person.full_name if person.full_name != UNKNOWN_NAME else ""),
        ("Documento", person.document_id),
        ("Email", person.email),
        ("Teléfono", person.phone),
        ("Edad", "" if person.age is None else f"{person.age} años"),
        ("Procedencia", person.origin_location),
        ("Universidad / Instituto", person.university),
        ("Carrera", person.career),
        ("Años de experiencia", "" if person.years_worked is None else str(person.years_worked)),
        ("Trayectoria", person.work_history_summary),
        ("Certificaciones y especificaciones", ", ".join(person.specifications or [])),
        ("Licencias", ", ".join(person.licenses or [])),
        ("Idiomas", ", ".join(person.languages or [])),
        ("Notas de entrevista", interview_notes),
    ]
    return "\n".join(f"{label}: {value}" for label, value in rows if value)


def candidate_text(db: Session, candidate: Candidate) -> str:
    """Texto que se clasifica: el del CV si se pudo leer; si no (alta manual o PDF escaneado), el armado."""
    if candidate.cv_file_id:
        cv = db.get(CvFile, candidate.cv_file_id)
        if cv is not None and cv.text_status == "ok" and cv.text:
            return cv.text
    return manual_text(db.get(Person, candidate.person_id), candidate.interview_notes)


def _reject_duplicate(db, existing: CvFile, filename: str, position: Position, actor, ip) -> IngestResult:
    log_action(
        db, actor=actor, action="cv.duplicate_rejected", entity_type="cv_file", entity_id=existing.id,
        summary=f"Rechazó el CV {filename} para {position.name}: ya estaba registrado en ese puesto",
        details={"positionId": position.id, "sha256": existing.sha256, "existingPath": existing.stored_path}, ip=ip,
    )
    return IngestResult("duplicate", duplicate_message(position), existing=duplicate_info(existing))


# --- ingesta ---------------------------------------------------------------


def ingest_cv(
    db: Session,
    storage: RrhhStorage,
    *,
    data: bytes,
    filename: str,
    position_id: str,
    source_id: str,
    requirement_id: str | None,
    origin: str,
    actor: User | str,
    existing_rel_path: str | None = None,
    ip: str | None = None,
) -> IngestResult:
    """Registra un CV en un puesto y crea su postulación. No hace commit (ver el docstring del módulo)."""
    # 1. formato, tamaño y destino
    original_name = (PurePosixPath((filename or "").replace("\\", "/")).name or "archivo")[:500]
    extension = extension_of(original_name)
    if extension not in ALLOWED_CV_EXTENSIONS:
        return IngestResult("unsupported", MSG_UNSUPPORTED)
    if len(data) > MAX_CV_BYTES:
        return IngestResult("too_large", MSG_TOO_LARGE)
    position, source = db.get(Position, position_id), db.get(Source, source_id)
    if position is None:
        return IngestResult("invalid_target", MSG_NO_POSITION)
    if source is None:
        return IngestResult("invalid_target", MSG_NO_SOURCE)
    if origin not in CV_ORIGINS:
        return IngestResult("invalid_target", f"Origen de CV no válido: {origin}")
    try:
        requirement = pick_requirement(db, position.id, requirement_id)  # se valida antes de tocar el disco
    except ValueError as exc:
        return IngestResult("invalid_target", str(exc))

    # 2. hash
    sha256 = hashlib.sha256(data).hexdigest()

    # 3. bloqueado para este puesto
    blocked = find_blocked(db, sha256, position.id)
    if blocked is not None:
        log_action(
            db, actor=actor, action="cv.rejected_deleted", entity_type="cv_file", entity_id=blocked.id,
            summary=f"Rechazó el CV {original_name} para {position.name}: se había eliminado antes",
            details={"positionId": position.id, "sha256": sha256}, ip=ip,
        )
        return IngestResult("deleted_before", blocked_message(position), existing=blocked_info(blocked))

    # 4. repetido en este puesto
    existing = find_duplicate(db, sha256, position.id)
    if existing is not None:
        return _reject_duplicate(db, existing, original_name, position, actor, ip)

    # 5. guardar el archivo (o usar el que ya está en la carpeta del servidor)
    if existing_rel_path is None:
        rel = storage.save_bytes(position.folder_name, source.folder_name, original_name, data, sha256)
        written = True
    else:
        storage.abs_path(existing_rel_path)  # ValueError si sale de la raíz
        rel, written = existing_rel_path, False

    try:
        # 6. texto (sin caracteres que PostgreSQL no acepta, como surrogates sueltos)
        text, text_status = extract_text(data, original_name)
        text = text.encode("utf-8", "replace").decode("utf-8")
        cv = CvFile(
            sha256=sha256, position_id=position.id, source_id=source.id, original_name=original_name,
            stored_path=rel, mime=MIME_BY_EXTENSION[extension], size=len(data), origin=origin, text=text,
            text_status=text_status, missing=False, uploaded_by_id=actor_id(actor),
            uploaded_by_name=actor_name(actor),
        )
        try:
            with db.begin_nested():  # si pierde la carrera, solo se deshace este INSERT
                db.add(cv)
                db.flush()
        except IntegrityError:
            winner = find_duplicate(db, sha256, position.id)
            if winner is None:
                raise  # otra restricción: no es un repetido
            if written and winner.stored_path != rel:
                _safe_delete(storage, rel)
            written = False
            return _reject_duplicate(db, winner, original_name, position, actor, ip)

        # 7. lector de CV
        positions = [position_view(p) for p in db.scalars(select(Position))]
        parsed = parse_cv_text(text, positions)

        # 8. persona
        person = link_or_create_person(
            db, sha256=sha256, values=parsed_person_values(parsed), source="reglas", actor=actor, ip=ip,
        )

        # 9-11. requerimiento, puntaje por reglas y estado de la IA
        candidate = Candidate(
            person_id=person.id, cv_file_id=cv.id, position_id=position.id,
            requirement_id=requirement.id if requirement else None, source_id=source.id, interview_notes="",
            created_by_name=actor_name(actor), ai_status=initial_ai_status(db, text_status),
        )
        apply_rule_scores(candidate, person, position)
        db.add(candidate)
        db.flush()

        # 12. bitácora
        log_action(
            db, actor=actor, action="cv.upload", entity_type="cv_file", entity_id=cv.id,
            summary=f"Subió el CV de {person.full_name} a {position.folder_name}/{source.folder_name}",
            details={
                "candidateId": candidate.id, "personId": person.id, "positionId": position.id,
                "sourceId": source.id, "requirementId": candidate.requirement_id, "origin": origin,
                "sha256": sha256,
            },
            ip=ip,
        )
    except Exception:
        if written:
            _safe_delete(storage, rel)
        raise

    return IngestResult(
        "created", f"CV de {person.full_name} registrado en {position.name}", candidate_id=candidate.id,
        cv_file_id=cv.id, person_id=person.id, stored_path=rel, file_written=written,
    )


def create_manual_candidate(
    db: Session,
    *,
    values: dict,
    position_id: str,
    source_id: str,
    requirement_id: str | None,
    interview_notes: str,
    actor: User,
    ip: str | None = None,
) -> Candidate:
    """Alta manual sin CV: enlaza o crea la persona (datos de usuario) y crea la postulación. No hace commit.

    Lanza ValueError si el puesto, la fuente o el requerimiento no corresponden.
    """
    position, source = db.get(Position, position_id), db.get(Source, source_id)
    if position is None:
        raise ValueError(MSG_NO_POSITION)
    if source is None:
        raise ValueError(MSG_NO_SOURCE)
    requirement = pick_requirement(db, position.id, requirement_id)
    person = link_or_create_person(
        db, sha256="", values=with_name_parts(values), source="user", actor=actor, ip=ip,
    )
    candidate = Candidate(
        person_id=person.id, cv_file_id=None, position_id=position.id,
        requirement_id=requirement.id if requirement else None, source_id=source.id,
        interview_notes=interview_notes, created_by_name=actor_name(actor),
        # el texto armado con los datos siempre tiene al menos el nombre: se puede clasificar
        ai_status=initial_ai_status(db, "ok" if manual_text(person, interview_notes) else "empty"),
    )
    apply_rule_scores(candidate, person, position)
    db.add(candidate)
    db.flush()
    log_action(
        db, actor=actor, action="candidate.create_manual", entity_type="candidate", entity_id=candidate.id,
        summary=f"Registró manualmente a {person.full_name} para {position.name}",
        details={"personId": person.id, "positionId": position.id, "sourceId": source.id,
                 "requirementId": candidate.requirement_id},
        ip=ip,
    )
    return candidate

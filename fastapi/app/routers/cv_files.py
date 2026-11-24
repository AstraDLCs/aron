import logging
import uuid
from pathlib import PurePosixPath
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.audit import log_action
from app.constants import MAX_CV_BYTES
from app.deps import CurrentUser, client_ip
from app.models.org import Position, Source
from app.models.people import Candidate, CvFile, DeletedCvHash, Person
from app.routers._util import DbDep
from app.schemas.people import CvCheckIn, CvFileUpdate
from app.services import ingest
from app.services.candidate_rules import apply_rule_scores
from app.services.persons import delete_person
from app.services.snapshot import build_state, state_response
from app.services.storage import RrhhStorage, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv-files", tags=["cv-files"])

StorageDep = Annotated[RrhhStorage, Depends(get_storage)]
UploadOrigin = Literal["app", "importacion", "sync_local"]  # 'carpeta_servidor' solo lo usa el servidor

ERROR_STATUS = {"unsupported": 415, "too_large": 413, "invalid_target": 422}


def _get_cv(db, cv_id: str) -> CvFile:
    cv = db.get(CvFile, cv_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="CV no encontrado")
    return cv


def _candidate_of(db, cv: CvFile) -> Candidate | None:
    return db.scalar(select(Candidate).where(Candidate.cv_file_id == cv.id))


def _person_name(db, candidate: Candidate | None, fallback: str) -> str:
    person = db.get(Person, candidate.person_id) if candidate else None
    return person.full_name if person else fallback


def content_disposition(filename: str) -> str:
    """`attachment` con un nombre ASCII de respaldo y el original en `filename*` (RFC 5987, UTF-8)."""
    fallback = "".join(ch if 32 <= ord(ch) < 127 and ch not in '"\\' else "_" for ch in filename) or "archivo"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.post("/check")
def check_cv_files(body: CvCheckIn, user: CurrentUser, db: DbDep):
    """Estado de cada (sha256, puesto) antes de subir: 'new', 'duplicate' o 'deleted_before'. No modifica nada."""
    shas = {item.sha256 for item in body.items}
    blocked = {
        tuple(r) for r in db.execute(
            select(DeletedCvHash.sha256, DeletedCvHash.position_id).where(DeletedCvHash.sha256.in_(shas))
        )
    }
    present = {tuple(r) for r in db.execute(select(CvFile.sha256, CvFile.position_id).where(CvFile.sha256.in_(shas)))}
    results = []
    for item in body.items:
        key = (item.sha256, item.position_id)
        status = "deleted_before" if key in blocked else "duplicate" if key in present else "new"
        results.append({"sha256": item.sha256, "positionId": item.position_id, "status": status})
    return {"results": results}


@router.post("", status_code=201)
def upload_cv(
    request: Request,
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File()],
    position_id: Annotated[str, Form(alias="positionId")],
    source_id: Annotated[str, Form(alias="sourceId")],
    requirement_id: Annotated[str | None, Form(alias="requirementId")] = None,
    origin: Annotated[UploadOrigin, Form()] = "app",
):
    data = file.file.read(MAX_CV_BYTES + 1)  # con un byte de más ya se sabe que supera el límite
    result = ingest.ingest_cv(
        db, storage, data=data, filename=file.filename or "archivo", position_id=position_id,
        source_id=source_id, requirement_id=requirement_id or None, origin=origin, actor=user,
        ip=client_ip(request),
    )
    if result.status == "created":
        try:
            db.commit()
        except Exception:
            db.rollback()
            ingest.discard_written_file(storage, result)
            raise
        return {
            "result": {
                "status": result.status, "message": result.message, "candidateId": result.candidate_id,
                "cvFileId": result.cv_file_id, "personId": result.person_id,
            },
            "state": build_state(db, user),
        }
    if result.status in ("duplicate", "deleted_before"):
        db.commit()  # el rechazo queda en la bitácora
        raise HTTPException(
            status_code=409, detail={"code": result.status, "message": result.message, "existing": result.existing},
        )
    raise HTTPException(status_code=ERROR_STATUS[result.status], detail=result.message)


@router.get("/{cv_id}/download")
def download_cv(cv_id: str, request: Request, user: CurrentUser, db: DbDep, storage: StorageDep):
    cv = _get_cv(db, cv_id)
    path = storage.abs_path(cv.stored_path)
    if not path.is_file():
        if not cv.missing:
            cv.missing = True
            db.commit()
        raise HTTPException(status_code=404, detail="El archivo del CV no está en la carpeta del servidor")
    cv.missing = False
    position = db.get(Position, cv.position_id)
    name = _person_name(db, _candidate_of(db, cv), cv.original_name)
    log_action(
        db, actor=user, action="cv.download", entity_type="cv_file", entity_id=cv.id,
        summary=f"Descargó el CV de {name} ({position.name})", ip=client_ip(request),
    )
    db.commit()
    headers = {"Content-Disposition": content_disposition(cv.original_name)}
    return FileResponse(path, media_type=cv.mime, headers=headers)


def _conflict(code: str, message: str, existing: dict | None) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message, "existing": existing})


@router.patch("/{cv_id}")
def move_cv(cv_id: str, body: CvFileUpdate, request: Request, user: CurrentUser, db: DbDep, storage: StorageDep):
    """Reclasifica el CV a otro puesto o fuente: mueve el archivo y actualiza la postulación."""
    cv = _get_cv(db, cv_id)
    candidate = _candidate_of(db, cv)
    new_pos = db.get(Position, body.position_id or cv.position_id)
    if new_pos is None:
        raise HTTPException(status_code=422, detail=ingest.MSG_NO_POSITION)
    new_src = db.get(Source, body.source_id or cv.source_id)
    if new_src is None:
        raise HTTPException(status_code=422, detail=ingest.MSG_NO_SOURCE)
    pos_changed, src_changed = new_pos.id != cv.position_id, new_src.id != cv.source_id
    if not (pos_changed or src_changed):
        return state_response(db, user)
    if pos_changed:
        if candidate is not None and candidate.decision == "Contratado":
            raise HTTPException(status_code=409, detail="No se puede cambiar de puesto una postulación contratada")
        if (blocked := ingest.find_blocked(db, cv.sha256, new_pos.id)) is not None:
            raise _conflict("deleted_before", ingest.blocked_message(new_pos), ingest.blocked_info(blocked))
        if (dup := ingest.find_duplicate(db, cv.sha256, new_pos.id)) is not None:
            raise _conflict("duplicate", ingest.duplicate_message(new_pos), ingest.duplicate_info(dup))

    old_pos, old_src, old_rel = db.get(Position, cv.position_id), db.get(Source, cv.source_id), cv.stored_path
    moved = storage.abs_path(old_rel).is_file()
    if moved:
        new_rel = storage.move(old_rel, new_pos.folder_name, new_src.folder_name)
    else:  # el archivo ya no estaba: se actualiza la ruta y queda marcado como faltante
        new_rel = f"{new_pos.folder_name}/{new_src.folder_name}/{PurePosixPath(old_rel).name}"
        cv.missing = True

    def _move_back() -> None:
        if moved:
            try:
                storage.move(new_rel, old_pos.folder_name, old_src.folder_name)
            except Exception:  # noqa: BLE001
                logger.exception("No se pudo devolver el CV '%s' a su carpeta", new_rel)

    try:
        cv.position_id, cv.source_id, cv.stored_path = new_pos.id, new_src.id, new_rel
        name = cv.original_name
        if candidate is not None:
            person = db.get(Person, candidate.person_id)
            name = person.full_name
            candidate.position_id, candidate.source_id = new_pos.id, new_src.id
            if pos_changed:  # el requerimiento y el resultado de la IA eran del puesto anterior
                requirement = ingest.pick_requirement(db, new_pos.id, None)
                candidate.requirement_id = requirement.id if requirement else None
                ingest.reset_ai_result(candidate)
                candidate.ai_status = ingest.initial_ai_status(db, cv.text_status)
                apply_rule_scores(candidate, person, new_pos)
        db.flush()
        log_action(
            db, actor=user, action="cv.move", entity_type="cv_file", entity_id=cv.id,
            summary=(
                f"Movió el CV de {name} de {old_pos.folder_name}/{old_src.folder_name} "
                f"a {new_pos.folder_name}/{new_src.folder_name}"
            ),
            details={
                "before": {"positionId": old_pos.id, "sourceId": old_src.id, "path": old_rel},
                "after": {"positionId": new_pos.id, "sourceId": new_src.id, "path": new_rel},
            },
            ip=client_ip(request),
        )
        db.commit()
    except IntegrityError:  # carrera: otro CV igual llegó al puesto de destino
        db.rollback()
        _move_back()
        dup = ingest.find_duplicate(db, cv.sha256, new_pos.id)
        raise _conflict(
            "duplicate", ingest.duplicate_message(new_pos), ingest.duplicate_info(dup) if dup else None
        ) from None
    except Exception:
        db.rollback()
        _move_back()
        raise
    return state_response(db, user)


@router.delete("/blocked/{blocked_id}")
def unblock_cv(blocked_id: str, request: Request, user: CurrentUser, db: DbDep):
    """Permite volver a subir un CV eliminado a ese puesto."""
    blocked = db.get(DeletedCvHash, blocked_id)
    if blocked is None:
        raise HTTPException(status_code=404, detail="CV bloqueado no encontrado")
    position = db.get(Position, blocked.position_id)
    db.delete(blocked)
    log_action(
        db, actor=user, action="cv.unblock", entity_type="cv_file", entity_id=blocked_id,
        summary=f"Permitió volver a subir el CV {blocked.original_name} a {position.name}",
        details={"sha256": blocked.sha256, "positionId": blocked.position_id}, ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)


@router.delete("/{cv_id}")
def delete_cv(cv_id: str, request: Request, user: CurrentUser, db: DbDep, storage: StorageDep):
    """Borra el archivo y la postulación; si la persona queda sin postulaciones, también sus datos.

    El hash queda bloqueado para ese puesto. El archivo se borra del disco después del commit: si eso
    fallara, el archivo huérfano queda bloqueado y no se reimporta.
    """
    cv = _get_cv(db, cv_id)
    candidate = _candidate_of(db, cv)
    person = db.get(Person, candidate.person_id) if candidate else None
    position = db.get(Position, cv.position_id)
    name = person.full_name if person else cv.original_name
    rel = cv.stored_path

    db.execute(
        insert(DeletedCvHash)
        .values(
            id=str(uuid.uuid4()), sha256=cv.sha256, position_id=cv.position_id,
            original_name=cv.original_name, deleted_by_name=user.full_name,
        )
        .on_conflict_do_nothing(index_elements=["sha256", "position_id"])
    )
    if candidate is not None:
        db.delete(candidate)
        db.flush()
    db.delete(cv)
    db.flush()
    person_deleted = False
    if person is not None and db.scalar(select(Candidate.id).where(Candidate.person_id == person.id).limit(1)) is None:
        delete_person(db, person)
        person_deleted = True
    log_action(
        db, actor=user, action="cv.delete", entity_type="cv_file", entity_id=cv_id,
        summary=f"Eliminó el CV de {name} ({position.name})",
        details={"positionId": position.id, "sha256": cv.sha256, "personDeleted": person_deleted},
        ip=client_ip(request),
    )
    db.commit()
    try:
        storage.delete(rel)
    except Exception:  # noqa: BLE001 - la base ya quedó bien; el hash bloqueado evita reimportarlo
        logger.exception("No se pudo borrar del disco el CV '%s'", rel)
    return state_response(db, user)

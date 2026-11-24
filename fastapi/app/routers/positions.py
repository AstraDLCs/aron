import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.audit import log_action
from app.deps import CurrentUser, client_ip
from app.models.org import Position, Requirement
from app.models.people import Candidate, CvFile
from app.routers._util import DbDep, apply_changes
from app.schemas.org import PositionCreate, PositionUpdate
from app.services.slugs import folder_name_for
from app.services.snapshot import build_state, pick, state_response
from app.services.storage import RrhhStorage, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/positions", tags=["positions"])

StorageDep = Annotated[RrhhStorage, Depends(get_storage)]

DUP_NAME = "Ya existe un puesto con ese nombre"
DUP_FOLDER = "Ya existe un puesto con esa carpeta"
CYCLE = "No se puede mover un puesto debajo de sí mismo o de un subordinado"


def _get(db, position_id: str) -> Position:
    pos = db.get(Position, position_id)
    if pos is None:
        raise HTTPException(status_code=404, detail="Puesto no encontrado")
    return pos


def _folder(raw: str) -> str:
    folder = folder_name_for(raw)
    if not folder:
        raise HTTPException(status_code=422, detail="El nombre de carpeta no es válido")
    return folder


def _check_unique(db, *, name: str | None, folder: str | None, exclude_id: str | None = None) -> None:
    if name is not None:
        other = db.scalar(select(Position.id).where(Position.name == name))
        if other is not None and other != exclude_id:
            raise HTTPException(status_code=409, detail=DUP_NAME)
    if folder is not None:
        other = db.scalar(select(Position.id).where(Position.folder_name == folder))
        if other is not None and other != exclude_id:
            raise HTTPException(status_code=409, detail=DUP_FOLDER)


def _check_parent(db, position_id: str | None, parent_id: str) -> None:
    """El padre debe existir y no puede ser el propio puesto ni uno de sus subordinados."""
    if db.get(Position, parent_id) is None:
        raise HTTPException(status_code=422, detail="El puesto superior no existe")
    seen: set[str] = set()
    current: str | None = parent_id
    while current is not None and current not in seen:  # sube por los padres del nuevo superior
        if current == position_id:
            raise HTTPException(status_code=422, detail=CYCLE)
        seen.add(current)
        current = db.scalar(select(Position.parent_id).where(Position.id == current))


@router.post("", status_code=201)
def create_position(body: PositionCreate, request: Request, user: CurrentUser, db: DbDep):
    folder = _folder(body.folder_name or body.name)
    _check_unique(db, name=body.name, folder=folder)
    if body.parent_id is not None:
        _check_parent(db, None, body.parent_id)
    pos = Position(
        **body.model_dump(exclude={"folder_name"}), folder_name=folder, created_by_id=user.id,
    )
    db.add(pos)
    try:
        db.flush()
    except IntegrityError:  # carrera con otra creación del mismo nombre o carpeta
        db.rollback()
        raise HTTPException(status_code=409, detail=DUP_NAME) from None
    log_action(
        db, actor=user, action="position.create", entity_type="position", entity_id=pos.id,
        summary=f"Creó el puesto {pos.name}", ip=client_ip(request),
    )
    db.commit()
    state = build_state(db, user)
    return {"position": pick(state, "positions", pos.id), "state": state}


@router.patch("/{position_id}")
def update_position(
    position_id: str, body: PositionUpdate, request: Request, user: CurrentUser, db: DbDep, storage: StorageDep
):
    pos = _get(db, position_id)
    values = body.model_dump(exclude_unset=True)
    old_folder = pos.folder_name
    if "folder_name" in values:
        values["folder_name"] = _folder(values["folder_name"])
    _check_unique(db, name=values.get("name"), folder=values.get("folder_name"), exclude_id=pos.id)
    if values.get("parent_id") is not None:
        _check_parent(db, pos.id, values["parent_id"])
    before, after = apply_changes(pos, values)
    try:  # primero la base: una colisión de nombre o carpeta debe fallar antes de tocar el disco
        db.flush()
    except IntegrityError:
        db.rollback()
        _check_unique(db, name=values.get("name"), folder=values.get("folder_name"), exclude_id=position_id)
        raise HTTPException(status_code=409, detail=DUP_NAME) from None
    renamed = "folderName" in after
    if renamed:
        try:
            storage.rename_position_folder(old_folder, pos.folder_name)
        except FileExistsError:
            db.rollback()
            raise HTTPException(status_code=409, detail="La carpeta de destino ya existe en el servidor") from None
        except Exception:
            db.rollback()
            raise
    try:
        if renamed:
            _rewrite_cv_paths(db, pos.id, old_folder, pos.folder_name)
        if before:
            moved = "parentId" in after
            log_action(
                db, actor=user, action="position.move" if moved else "position.update", entity_type="position",
                entity_id=pos.id,
                summary=(
                    f"Movió el puesto {pos.name} en el organigrama" if moved else f"Actualizó el puesto {pos.name}"
                ),
                details={"before": before, "after": after}, ip=client_ip(request),
            )
        db.commit()
    except Exception:
        db.rollback()
        if renamed:  # la base no guardó el cambio: la carpeta vuelve a su sitio
            try:
                storage.rename_position_folder(after["folderName"], old_folder)
            except Exception:
                logger.exception(
                    "No se pudo devolver la carpeta '%s' a '%s' tras un error", after["folderName"], old_folder
                )
        raise
    state = build_state(db, user)
    return {"position": pick(state, "positions", pos.id), "state": state}


@router.delete("/{position_id}")
def delete_position(position_id: str, request: Request, user: CurrentUser, db: DbDep):
    pos = _get(db, position_id)
    in_use = (
        db.scalar(select(Position.id).where(Position.parent_id == pos.id).limit(1)) is not None
        or db.scalar(select(Requirement.id).where(Requirement.position_id == pos.id).limit(1)) is not None
        or _has_candidates(db, pos.id)
    )
    if in_use:
        raise HTTPException(status_code=409, detail="El puesto tiene subordinados, requerimientos o candidatos")
    name = pos.name
    db.delete(pos)
    log_action(
        db, actor=user, action="position.delete", entity_type="position", entity_id=position_id,
        summary=f"Eliminó el puesto {name}", ip=client_ip(request),
    )
    db.commit()
    return state_response(db, user)


def _has_candidates(db, position_id: str) -> bool:
    return db.scalar(select(Candidate.id).where(Candidate.position_id == position_id).limit(1)) is not None


def _rewrite_cv_paths(db, position_id: str, old_folder: str, new_folder: str) -> None:
    """Tras mover la carpeta del puesto en disco, actualiza las rutas guardadas de sus CVs (misma transacción)."""
    prefix = f"{old_folder}/"
    for cv in db.scalars(select(CvFile).where(CvFile.position_id == position_id)):
        if cv.stored_path.startswith(prefix):
            cv.stored_path = f"{new_folder}/{cv.stored_path[len(prefix):]}"
    db.flush()

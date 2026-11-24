"""Revisión de la carpeta de CVs del servidor: registra los archivos copiados a mano a `<puesto>/<fuente>/`.

Solo la ingesta de archivos NUEVOS deja filas de bitácora (las escribe `ingest_cv`). Los repetidos, bloqueados
y no soportados que encuentra la revisión solo se cuentan en el resumen: se comprueban antes de llamar a
`ingest_cv` para no volver a auditar el mismo archivo en cada pasada. Los archivos vacíos se omiten (puede que
alguien los esté copiando todavía). El archivo no se copia ni se mueve: se registra con su ruta actual.
"""
import hashlib
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ALLOWED_CV_EXTENSIONS, MAX_CV_BYTES, SYSTEM_ACTOR
from app.models.org import Position, Source
from app.models.people import CvFile
from app.services.ingest import extension_of, find_blocked, find_duplicate, ingest_cv
from app.services.slugs import normalize_key
from app.services.storage import RrhhStorage, get_storage

logger = logging.getLogger(__name__)


@dataclass
class ScanSummary:
    ingested: int = 0
    duplicates: int = 0
    blocked: int = 0
    unsupported: int = 0
    unmatched_folders: list[str] = field(default_factory=list)


def _lookup(items) -> tuple[dict, dict]:
    by_folder = {i.folder_name: i for i in items}
    by_key: dict = {}
    for i in items:
        by_key.setdefault(normalize_key(i.name), i)
    return by_folder, by_key


def _match(folder: str, by_folder: dict, by_key: dict):
    return by_folder.get(folder) or by_key.get(normalize_key(folder))


def scan_server_folder(db: Session, storage: RrhhStorage) -> ScanSummary:
    """Registra los archivos nuevos de la carpeta del servidor. Confirma (commit) cada ingreso."""
    summary = ScanSummary()
    positions = _lookup(list(db.scalars(select(Position))))
    sources = _lookup(list(db.scalars(select(Source))))
    known = set(db.scalars(select(CvFile.stored_path)))

    for pos_folder, src_folder, rel in storage.iter_files():
        if rel in known:
            continue
        position = _match(pos_folder, *positions)
        source = _match(src_folder, *sources)
        if position is None or source is None:
            label = f"{pos_folder}/{src_folder}"
            if label not in summary.unmatched_folders:
                summary.unmatched_folders.append(label)
            continue
        name = rel.rsplit("/", 1)[-1]
        if extension_of(name) not in ALLOWED_CV_EXTENSIONS:
            summary.unsupported += 1
            continue
        try:
            path = storage.abs_path(rel)
            size = path.stat().st_size
            if size == 0:  # puede estar copiándose todavía
                continue
            if size > MAX_CV_BYTES:
                summary.unsupported += 1
                continue
            data = path.read_bytes()
        except (OSError, ValueError):
            logger.warning("No se pudo leer '%s'; se omite", rel)
            continue
        if not data:
            continue
        sha256 = hashlib.sha256(data).hexdigest()
        if find_blocked(db, sha256, position.id) is not None:
            summary.blocked += 1
            continue
        if find_duplicate(db, sha256, position.id) is not None:
            summary.duplicates += 1
            continue
        try:
            result = ingest_cv(
                db, storage, data=data, filename=name, position_id=position.id, source_id=source.id,
                requirement_id=None, origin="carpeta_servidor", actor=SYSTEM_ACTOR, existing_rel_path=rel,
            )
            db.commit()
        except Exception:  # noqa: BLE001 - un archivo malo no debe frenar la revisión
            db.rollback()
            logger.exception("No se pudo registrar '%s'", rel)
            continue
        known.add(rel)
        if result.status == "created":
            summary.ingested += 1
        elif result.status == "duplicate":
            summary.duplicates += 1
        elif result.status == "deleted_before":
            summary.blocked += 1
        elif result.status in ("unsupported", "too_large"):
            summary.unsupported += 1
        else:
            logger.warning("'%s' no se registró: %s", rel, result.message)

    if summary.ingested:
        logger.info("Carpeta del servidor: %s CV(s) registrados", summary.ingested)
    return summary


def scan_once(db: Session) -> ScanSummary:
    """Gancho del worker (`app/worker.py`): revisa la carpeta configurada y confirma."""
    summary = scan_server_folder(db, get_storage())
    db.commit()
    return summary

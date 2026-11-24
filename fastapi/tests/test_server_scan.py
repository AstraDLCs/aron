import hashlib

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.org import Position, Source
from app.models.people import CvFile, DeletedCvHash
from app.services.server_scan import scan_server_folder
from app.services.storage import RrhhStorage
from tests.fixtures.cvs import make_cv_pdf

JUAN = dict(full_name="Juan Carlos Quispe Mamani", dni="45678912", email="juan.quispe@correo.pe", phone="987 654 321")


def _org(db):
    pos = Position(name="Operador de Planta", folder_name="operador-de-planta", area="Planta")
    src = Source(name="Portal Minero", folder_name="portal-minero", category="Portal Minero")
    db.add_all([pos, src])
    db.flush()
    return pos, src


def _put(root, pos_folder, src_folder, name, data):
    d = root / pos_folder / src_folder
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)


def _audits(db):
    return len(list(db.scalars(select(AuditLog))))


def test_scan_ingests_new_files_once(db, rrhh_root):
    _org(db)
    data = make_cv_pdf(**JUAN)
    _put(rrhh_root, "operador-de-planta", "portal-minero", "cv juan.pdf", data)
    storage = RrhhStorage(rrhh_root)
    first = scan_server_folder(db, storage)
    assert first.ingested == 1
    cv = db.scalar(select(CvFile))
    assert cv.origin == "carpeta_servidor" and cv.stored_path == "operador-de-planta/portal-minero/cv juan.pdf"
    assert [p.name for p in (rrhh_root / "operador-de-planta" / "portal-minero").iterdir()] == ["cv juan.pdf"]
    assert scan_server_folder(db, storage).ingested == 0


def test_scan_skips_blocked_and_reports_unmatched(db, rrhh_root):
    pos, _ = _org(db)
    data = make_cv_pdf(**JUAN)
    db.add(DeletedCvHash(sha256=hashlib.sha256(data).hexdigest(), position_id=pos.id, original_name="x.pdf"))
    db.flush()
    _put(rrhh_root, "operador-de-planta", "portal-minero", "bloqueado.pdf", data)
    _put(rrhh_root, "desconocido", "linkedin", "otro.pdf", b"%PDF-1.4 x")
    storage = RrhhStorage(rrhh_root)
    before = _audits(db)
    s = scan_server_folder(db, storage)
    assert s.blocked == 1 and s.ingested == 0
    assert s.unmatched_folders == ["desconocido/linkedin"]
    scan_server_folder(db, storage)
    assert _audits(db) == before  # los rechazos de la revisión no se auditan


def test_scan_counts_same_sha_other_name_as_duplicate(db, rrhh_root):
    _org(db)
    data = make_cv_pdf(**JUAN)
    _put(rrhh_root, "operador-de-planta", "portal-minero", "a.pdf", data)
    storage = RrhhStorage(rrhh_root)
    assert scan_server_folder(db, storage).ingested == 1
    _put(rrhh_root, "operador-de-planta", "portal-minero", "b.pdf", data)
    before = _audits(db)
    s = scan_server_folder(db, storage)
    assert s.duplicates == 1 and s.ingested == 0
    scan_server_folder(db, storage)
    assert _audits(db) == before


def test_scan_skips_empty_unsupported_and_matches_by_normalized_name(db, rrhh_root):
    _org(db)
    _put(rrhh_root, "operador-de-planta", "portal-minero", "vacio.pdf", b"")
    _put(rrhh_root, "operador-de-planta", "portal-minero", "foto.png", b"abc")
    _put(rrhh_root, "Operador de Planta", "Portal Minero", "cv.pdf", make_cv_pdf(**JUAN))
    s = scan_server_folder(db, RrhhStorage(rrhh_root))
    assert s.unsupported == 1 and s.ingested == 1 and s.unmatched_folders == []

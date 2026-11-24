import hashlib

import pytest

from app.services.storage import RrhhStorage


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_storage_safe_paths(tmp_path):
    st = RrhhStorage(tmp_path)
    data = b"%PDF-1.4 uno"
    rel = st.save_bytes("p", "s", "../../etc/x.pdf", data, _sha(data))
    path = st.abs_path(rel)
    assert path.is_file() and path.read_bytes() == data
    assert path.name == "x.pdf"
    assert path.resolve().is_relative_to(tmp_path.resolve())
    assert rel == "p/s/x.pdf"

    name = "CV José Ñuñez (1).pdf"
    assert st.safe_filename(name) == name
    rel2 = st.save_bytes("p", "s", name, b"abc", _sha(b"abc"))
    assert st.abs_path(rel2).name == name

    other = b"otro contenido"
    rel3 = st.save_bytes("p", "s", name, other, _sha(other))
    assert rel3 != rel2
    assert st.abs_path(rel3).name == f"CV José Ñuñez (1)-{_sha(other)[:8]}.pdf"
    assert st.abs_path(rel2).read_bytes() == b"abc"  # el original no se pisa

    with pytest.raises(ValueError):
        st.abs_path("../fuera")
    with pytest.raises(ValueError):
        st.abs_path("/etc/passwd")


def test_safe_filename_edge_cases(tmp_path):
    st = RrhhStorage(tmp_path)
    assert st.safe_filename("a\\b\\c.docx") == "c.docx"
    assert st.safe_filename("evil\x00\x1f.pdf") == "evil.pdf"
    assert ".." not in st.safe_filename("a..b.pdf")
    assert st.safe_filename("...") == "archivo"
    long = st.safe_filename("x" * 300 + ".pdf")
    assert len(long) <= 120 and long.endswith(".pdf")


def test_save_rejects_escaping_folders(tmp_path):
    st = RrhhStorage(tmp_path / "root")
    with pytest.raises(ValueError):
        st.save_bytes("../afuera", "s", "a.pdf", b"x", _sha(b"x"))


def test_rename_position_folder_moves_dir(tmp_path):
    st = RrhhStorage(tmp_path)
    st.save_bytes("viejo", "portal-minero", "a.pdf", b"x", _sha(b"x"))
    st.rename_position_folder("viejo", "nuevo")
    assert not (tmp_path / "viejo").exists()
    assert (tmp_path / "nuevo" / "portal-minero" / "a.pdf").read_bytes() == b"x"
    # carpeta inexistente: no hace nada
    st.rename_position_folder("no-existe", "otra")


def test_move_delete_and_iter_files(tmp_path):
    st = RrhhStorage(tmp_path)
    rel = st.save_bytes("p1", "s1", "a.pdf", b"x", _sha(b"x"))
    st.save_bytes("p1", "s2", "b.pdf", b"y", _sha(b"y"))
    (tmp_path / "suelto.txt").write_text("no cuenta")  # profundidad 1
    (tmp_path / "p1" / "s1" / "extra").mkdir()
    (tmp_path / "p1" / "s1" / "extra" / "hondo.pdf").write_bytes(b"z")  # profundidad 4
    assert sorted(st.iter_files()) == [("p1", "s1", "p1/s1/a.pdf"), ("p1", "s2", "p1/s2/b.pdf")]

    new = st.move(rel, "p2", "s9")
    assert new == "p2/s9/a.pdf"
    assert st.abs_path(new).read_bytes() == b"x" and not st.abs_path(rel).exists()

    st.delete(new)
    assert not st.abs_path(new).exists()
    st.delete(new)  # idempotente

import hashlib
import os

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


def _hidden(root):
    return [p for p in root.rglob(".*") if p.is_file()]


def test_save_bytes_never_overwrites_when_name_is_taken_mid_write(tmp_path, monkeypatch):
    """Otro proceso crea el mismo nombre justo antes de que lo tomemos: se usa un sufijo, nada se pisa."""
    st = RrhhStorage(tmp_path)
    real_link = os.link
    calls = {"n": 0}

    def racing_link(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            with open(dst, "wb") as f:  # la otra subida gana por un instante
                f.write(b"contenido ajeno")
        return real_link(src, dst)

    monkeypatch.setattr(os, "link", racing_link)
    data = b"mi contenido"
    rel = st.save_bytes("p", "s", "cv.pdf", data, _sha(data))
    assert rel == f"p/s/cv-{_sha(data)[:8]}.pdf"
    assert st.abs_path(rel).read_bytes() == data
    assert (tmp_path / "p" / "s" / "cv.pdf").read_bytes() == b"contenido ajeno"
    assert _hidden(tmp_path) == []  # el temporal no queda


def test_save_bytes_same_name_different_contents_keeps_both(tmp_path):
    st = RrhhStorage(tmp_path)
    contents = [b"uno", b"dos", b"tres"]
    rels = [st.save_bytes("p", "s", "cv.pdf", c, "a" * 64) for c in contents]  # mismo sha8 a propósito
    assert rels == ["p/s/cv.pdf", "p/s/cv-aaaaaaaa.pdf", "p/s/cv-aaaaaaaa-2.pdf"]
    assert [st.abs_path(r).read_bytes() for r in rels] == contents


def test_save_bytes_without_hard_links_is_still_exclusive(tmp_path, monkeypatch):
    def no_links(src, dst):
        raise PermissionError("el sistema de archivos no admite enlaces duros")

    monkeypatch.setattr(os, "link", no_links)
    st = RrhhStorage(tmp_path)
    a = st.save_bytes("p", "s", "cv.pdf", b"uno", _sha(b"uno"))
    b = st.save_bytes("p", "s", "cv.pdf", b"dos", _sha(b"dos"))
    assert a != b
    assert st.abs_path(a).read_bytes() == b"uno" and st.abs_path(b).read_bytes() == b"dos"
    assert _hidden(tmp_path) == []


def test_save_bytes_avoids_registered_paths(tmp_path):
    st = RrhhStorage(tmp_path)
    rel = st.save_bytes("p", "s", "cv.pdf", b"x", _sha(b"x"), avoid={"p/s/cv.pdf", "otra/s/cv-x.pdf"})
    assert rel == f"p/s/cv-{_sha(b'x')[:8]}.pdf"


def test_move_onto_occupied_name_is_suffixed(tmp_path, monkeypatch):
    st = RrhhStorage(tmp_path)
    x = st.save_bytes("p", "s1", "a.pdf", b"x", _sha(b"x"))
    st.save_bytes("p", "s2", "a.pdf", b"y", _sha(b"y"))
    moved = st.move(x, "p", "s2")
    assert moved == f"p/s2/a-{_sha(b'x')[:8]}.pdf"
    assert st.abs_path(moved).read_bytes() == b"x"
    assert st.abs_path("p/s2/a.pdf").read_bytes() == b"y"
    assert not st.abs_path(x).exists()

    # carrera: el destino aparece justo antes de tomarlo
    z = st.save_bytes("p", "s1", "b.pdf", b"z", _sha(b"z"))
    real_link = os.link
    calls = {"n": 0}

    def racing_link(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            with open(dst, "wb") as f:
                f.write(b"ajeno")
        return real_link(src, dst)

    monkeypatch.setattr(os, "link", racing_link)
    moved = st.move(z, "p", "s3")
    assert moved == f"p/s3/b-{_sha(b'z')[:8]}.pdf"
    assert st.abs_path(moved).read_bytes() == b"z"
    assert st.abs_path("p/s3/b.pdf").read_bytes() == b"ajeno"
    assert not st.abs_path(z).exists()

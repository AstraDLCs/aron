"""Carpeta de CVs del servidor: <puesto>/<fuente>/<archivo>. Todas las rutas son relativas a la raíz."""
import hashlib
import os
import re
import uuid
from collections.abc import Callable, Collection, Iterator
from pathlib import Path, PurePosixPath

from app.config import get_settings

FILENAME_MAX = 120
MAX_NAME_ATTEMPTS = 1000


def _candidate_names(name: str, digest: Callable[[], str]) -> Iterator[str]:
    """`name`, luego `name-<sha8>`, `name-<sha8>-2`, `-3`, … (el hash se calcula solo si hace falta)."""
    yield name
    stem, dot, ext = name.rpartition(".")
    if not (dot and stem):
        stem, ext = name, ""
    ext = f".{ext}" if ext else ""
    base = f"{stem}-{digest()[:8]}"
    yield f"{base}{ext}"
    for n in range(2, MAX_NAME_ATTEMPTS):
        yield f"{base}-{n}{ext}"


def _place_exclusive(src: Path, target: Path) -> None:
    """Lleva `src` a `target` sin pisar nada: FileExistsError si `target` ya existe.

    Con un enlace duro el nombre se toma de forma atómica. Si el sistema de archivos no admite enlaces
    duros, se reserva el nombre con O_CREAT|O_EXCL y luego se reemplaza esa reserva (que es nuestra).
    """
    try:
        os.link(src, target)
    except FileExistsError:
        raise
    except OSError:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # FileExistsError si ya está tomado
        os.close(fd)
        try:
            os.replace(src, target)
        except BaseException:
            target.unlink(missing_ok=True)  # la reserva vacía era nuestra
            raise
        return
    os.unlink(src)
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class RrhhStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    # --- nombres y rutas -------------------------------------------------

    def safe_filename(self, name: str) -> str:
        """Nombre sin directorios, caracteres de control ni `..`; conserva tildes y espacios (máx. 120)."""
        base = re.split(r"[/\\]", name or "")[-1]
        base = _CONTROL_CHARS.sub("", base)
        base = re.sub(r"\.{2,}", ".", base).strip(" .")
        if not base:
            return "archivo"
        if len(base) > FILENAME_MAX:
            stem, dot, ext = base.rpartition(".")
            if not dot or len(ext) > 10:
                stem, ext = base, ""
            else:
                ext = "." + ext
            base = stem[: FILENAME_MAX - len(ext)].rstrip(" .") + ext
        return base

    def abs_path(self, rel: str) -> Path:
        """Ruta absoluta de `rel`; falla si sale de la raíz."""
        root = self.root.resolve()
        path = (root / rel).resolve()
        if path == root or not path.is_relative_to(root):
            raise ValueError("La ruta sale de la carpeta de CVs")
        return path

    @staticmethod
    def _check_part(part: str) -> str:
        if not part or part in (".", "..") or re.search(r"[/\\\x00]", part):
            raise ValueError("Nombre de carpeta inválido")
        return part

    def _folder(self, position_folder: str, source_folder: str) -> tuple[Path, str]:
        rel_dir = f"{self._check_part(position_folder)}/{self._check_part(source_folder)}"
        return self.abs_path(rel_dir), rel_dir

    # --- operaciones -----------------------------------------------------

    def _claim(self, src: Path, folder: Path, name: str, digest: Callable[[], str], avoid: set[str]) -> Path:
        """Pone `src` en la carpeta con el primer nombre libre (en disco y fuera de `avoid`)."""
        for candidate in _candidate_names(name, digest):
            if candidate in avoid:
                continue
            target = folder / candidate
            try:
                _place_exclusive(src, target)
            except FileExistsError:
                continue
            return target
        raise FileExistsError(f"No hay un nombre libre para '{name}'")

    @staticmethod
    def _names_in(rel_dir: str, avoid: Collection[str]) -> set[str]:
        return {PurePosixPath(r).name for r in avoid if PurePosixPath(r).parent.as_posix() == rel_dir}

    def save_bytes(
        self, position_folder: str, source_folder: str, filename: str, data: bytes, sha256: str,
        *, avoid: Collection[str] = (),
    ) -> str:
        """Guarda `data` sin pisar ningún archivo y devuelve la ruta relativa que realmente quedó.

        Si el nombre está ocupado (o figura en `avoid`, rutas relativas ya registradas en la base), usa
        `-<sha8>`, `-<sha8>-2`, … El archivo temporal empieza con punto: la revisión de la carpeta lo ignora.
        """
        folder, rel_dir = self._folder(position_folder, source_folder)
        folder.mkdir(parents=True, exist_ok=True)
        name = self.safe_filename(filename)
        tmp = folder / f".{uuid.uuid4().hex}.part"  # propio de esta escritura: dos subidas no lo comparten
        tmp.write_bytes(data)
        try:
            target = self._claim(tmp, folder, name, lambda: sha256, self._names_in(rel_dir, avoid))
        finally:
            tmp.unlink(missing_ok=True)
        return f"{rel_dir}/{target.name}"

    def move(
        self, rel: str, position_folder: str, source_folder: str, *, avoid: Collection[str] = (),
        name: str | None = None,
    ) -> str:
        """Mueve el archivo a otra carpeta sin pisar ninguno; si el nombre está ocupado, usa un sufijo.

        `name` pide un nombre de destino distinto del actual (p. ej. el original, al deshacer un movimiento).
        """
        src = self.abs_path(rel)
        folder, rel_dir = self._folder(position_folder, source_folder)
        name = self.safe_filename(name) if name else src.name
        if src.parent == folder and src.name == name:
            return rel
        folder.mkdir(parents=True, exist_ok=True)

        def digest() -> str:
            return hashlib.sha256(src.read_bytes()).hexdigest()

        target = self._claim(src, folder, name, digest, self._names_in(rel_dir, avoid))
        return f"{rel_dir}/{target.name}"

    def delete(self, rel: str) -> None:
        self.abs_path(rel).unlink(missing_ok=True)

    def rename_position_folder(self, old: str, new: str) -> None:
        src = self.abs_path(self._check_part(old))
        dst = self.abs_path(self._check_part(new))
        if not src.exists():
            return
        if dst.exists():
            raise FileExistsError(f"La carpeta '{new}' ya existe en el servidor")
        src.rename(dst)

    def iter_files(self) -> Iterator[tuple[str, str, str]]:
        """(carpeta del puesto, carpeta de la fuente, ruta relativa) de los archivos a profundidad 3."""
        if not self.root.is_dir():
            return
        for pos_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for src_dir in sorted(p for p in pos_dir.iterdir() if p.is_dir()):
                for f in sorted(p for p in src_dir.iterdir() if p.is_file() and not p.name.startswith(".")):
                    yield pos_dir.name, src_dir.name, f"{pos_dir.name}/{src_dir.name}/{f.name}"


def get_storage() -> RrhhStorage:
    return RrhhStorage(get_settings().rrhh_root)

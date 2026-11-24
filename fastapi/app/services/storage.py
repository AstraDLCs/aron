"""Carpeta de CVs del servidor: <puesto>/<fuente>/<archivo>. Todas las rutas son relativas a la raíz."""
import hashlib
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

from app.config import get_settings

FILENAME_MAX = 120
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

    def save_bytes(self, position_folder: str, source_folder: str, filename: str, data: bytes, sha256: str) -> str:
        folder, rel_dir = self._folder(position_folder, source_folder)
        folder.mkdir(parents=True, exist_ok=True)
        name = self.safe_filename(filename)
        if (folder / name).exists():
            stem, dot, ext = name.rpartition(".")
            name = f"{stem}-{sha256[:8]}.{ext}" if dot and stem else f"{name}-{sha256[:8]}"
        target = folder / name
        tmp = folder / f".{name}.part"
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return f"{rel_dir}/{name}"

    def move(self, rel: str, position_folder: str, source_folder: str) -> str:
        src = self.abs_path(rel)
        folder, rel_dir = self._folder(position_folder, source_folder)
        if src.parent == folder:
            return rel
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / src.name
        if target.exists():
            digest = hashlib.sha256(src.read_bytes()).hexdigest()[:8]
            stem, dot, ext = src.name.rpartition(".")
            target = folder / (f"{stem}-{digest}.{ext}" if dot and stem else f"{src.name}-{digest}")
        shutil.move(str(src), str(target))
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

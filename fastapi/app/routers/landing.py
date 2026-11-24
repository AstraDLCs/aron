"""Página pública "/" para descargar la app de escritorio (instalador .msi). No requiere sesión."""

import hashlib
import html
import mimetypes
import re
from pathlib import Path
from string import Template

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.config import get_settings

router = APIRouter(include_in_schema=False)
mimetypes.add_type("font/woff2", ".woff2")  # la imagen slim no lo trae y /recursos sirve las tipografías

ASSETS = Path(__file__).resolve().parent.parent / "landing"
RESOURCES = ASSETS / "recursos"  # ícono y tipografías; main.py los monta en /recursos
_TEMPLATE = Template((ASSETS / "index.html").read_text(encoding="utf-8"))
_VERSION_RE = re.compile(r"_(\d+(?:\.\d+)+)_")
_NOT_PUBLISHED = "El instalador todavía no está publicado en este servidor."
_PAGE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; font-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
_sha_cache: dict[tuple[str, int, int], str] = {}


def _version(path: Path) -> tuple[int, ...]:
    m = _VERSION_RE.search(path.name)
    return tuple(int(p) for p in m.group(1).split(".")) if m else (0,)


def _installer() -> Path | None:
    folder = get_settings().downloads_dir
    files = [p for p in folder.glob("*.msi") if p.is_file()] if folder.is_dir() else []
    return max(files, key=lambda p: (_version(p), p.stat().st_mtime), default=None)


def _sha256(path: Path) -> str:
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _sha_cache:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _sha_cache[key] = h.hexdigest()
    return _sha_cache[key]


def _size_mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f}".replace(".", ",") + " MB"


def _download_block(path: Path | None) -> tuple[str, str]:
    if path is None:
        return (f'<p class="unavailable">{_NOT_PUBLISHED} Vuelve a intentarlo más tarde.</p>', "")
    version = ".".join(map(str, _version(path))) if _version(path) != (0,) else "—"
    size = _size_mb(path.stat().st_size)
    name = html.escape(path.name)
    block = (
        '<a class="download" href="/descargar/windows">Descargar Pulso Laboral para Windows</a>\n'
        f'<p class="meta">Versión {html.escape(version)}, instalador .msi de {size}. '
        "Para Windows 10 y 11 de 64 bits.</p>"
    )
    verify = (
        '<section class="verify" aria-labelledby="verificar">\n'
        '<h2 id="verificar">Comprobar el archivo</h2>\n'
        "<p>Para confirmar que la descarga llegó completa, abre PowerShell en la carpeta de descargas y "
        "compara el resultado con la huella de abajo.</p>\n"
        f"<pre><code>Get-FileHash .\\{name}</code></pre>\n"
        f'<p class="hash"><span>SHA-256</span><code>{_sha256(path)}</code></p>\n'
        "</section>"
    )
    return block, verify


def _account_note() -> str:
    if get_settings().registration_mode == "invite":
        return (
            "Para crear tu cuenta necesitas el código de invitación que entrega el administrador de "
            "Pulso Laboral."
        )
    return "Si todavía no tienes cuenta, puedes crear tu cuenta desde la aplicación."


@router.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    block, verify = _download_block(_installer())
    page = _TEMPLATE.substitute(download_block=block, verify_block=verify, account_note=_account_note())
    return HTMLResponse(page, headers=_PAGE_HEADERS)


@router.get("/descargar/windows")
def download_windows() -> FileResponse:
    path = _installer()
    if path is None:
        raise HTTPException(status_code=404, detail=_NOT_PUBLISHED)
    return FileResponse(path, media_type="application/x-msi", filename=path.name,
                        headers={"Cache-Control": "no-cache"})

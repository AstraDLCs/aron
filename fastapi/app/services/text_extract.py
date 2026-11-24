"""Extracción de texto de CVs (PDF, DOCX, TXT, RTF). Nunca lanza: devuelve (texto, estado)."""
import io
import re
from typing import Literal

from pypdf import PdfReader

MIN_TEXT_CHARS = 40

ExtractStatus = Literal['ok', 'empty', 'error']

_RTF_DESTINATIONS = re.compile(
    r'\{\\(?:fonttbl|colortbl|stylesheet|info|pict|object|header|footer|headerl|headerr|footerl|footerr'
    r'|footnote|listtable|listoverridetable|rsidtbl|generator|xmlnstbl)[\s\S]*?\}',
    re.IGNORECASE,
)


def strip_rtf_to_text(rtf: str) -> str:
    """Port de stripRtfToText (cvParser.ts:112-140)."""
    # Escapes hexadecimales \'xx (Windows-1252/Latin1), antes de quitar los grupos de control.
    decoded = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), rtf)
    decoded = _RTF_DESTINATIONS.sub(' ', decoded)
    decoded = re.sub(r'\\par\b|\\line\b', '\n', decoded, flags=re.IGNORECASE)
    decoded = re.sub(r'\\tab\b', ' ', decoded, flags=re.IGNORECASE)
    decoded = re.sub(r'\\u(-?\d+)\??', lambda m: chr(int(m.group(1))) if int(m.group(1)) > 0 else '', decoded)
    decoded = re.sub(r'\\[a-zA-Z]+-?\d* ?', '', decoded)
    decoded = re.sub(r'[{}]', '', decoded)
    decoded = decoded.replace('\r', '\n')
    decoded = re.sub(r'[ \t]+', ' ', decoded)
    decoded = re.sub(r'\n{3,}', '\n\n', decoded)
    return decoded.strip()


def strip_html_to_text(html: str) -> str:
    """Port de stripHtmlToText (cvParser.ts:142-156)."""
    text = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|li|tr|h[1-6]|br)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'&amp;', '&', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;', '<', text, flags=re.IGNORECASE)
    text = re.sub(r'&gt;', '>', text, flags=re.IGNORECASE)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('PDF cifrado')
    return '\n'.join((page.extract_text() or '') for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts: list[str] = []
    for block in doc.iter_inner_content():
        if hasattr(block, 'rows'):
            for row in block.rows:
                cells: list[str] = []
                seen = set()
                for cell in row.cells:
                    if cell._tc in seen:  # celdas combinadas se repiten
                        continue
                    seen.add(cell._tc)
                    if cell.text.strip():
                        cells.append(cell.text.strip())
                if cells:
                    parts.append(' | '.join(cells))
        elif block.text.strip():
            parts.append(block.text)
    return '\n'.join(parts)


def _decode_text(data: bytes) -> str:
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('latin-1')


def _clean(text: str) -> str:
    text = text.replace('\x00', ' ').replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t\f\v]+', ' ', text)
    text = re.sub(r' ?\n ?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_text(data: bytes, filename: str) -> tuple[str, ExtractStatus]:
    try:
        name = (filename or '').lower()
        if name.endswith('.pdf'):
            raw = _extract_pdf(data)
        elif name.endswith('.docx'):
            raw = _extract_docx(data)
        elif name.endswith('.txt'):
            raw = _decode_text(data)
        elif name.endswith('.rtf'):
            raw = strip_rtf_to_text(data.decode('latin-1'))
        else:
            return '', 'error'
        text = _clean(raw)
        if len(text) < MIN_TEXT_CHARS:
            return text, 'empty'
        return text, 'ok'
    except Exception:  # noqa: BLE001 - la extracción nunca debe romper la subida
        return '', 'error'

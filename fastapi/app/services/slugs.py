"""Claves normalizadas y nombres de carpeta (puestos y fuentes)."""
import re
import unicodedata

FOLDER_NAME_MAX = 80


def normalize_key(text: str) -> str:
    decomposed = unicodedata.normalize('NFD', text or '')
    no_marks = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '-', no_marks.lower()).strip('-')


def folder_name_for(text: str) -> str:
    return normalize_key(text)[:FOLDER_NAME_MAX].strip('-')

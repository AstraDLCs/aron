"""Lectura y puntuación de pruebas Excel (port de recruitment.ts:95-350).

Las filas llegan como dicts (encabezado -> valor) ya leídos de la hoja. Se imitan las reglas de coerción de
JavaScript (String(), Number(), valores 'falsos') para que el resultado sea idéntico al de la app original.
"""
import math
import re

from app.services.scoring import PSYCH_KEYS, js_round

_NUMBER = re.compile(r'^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$')
_SUMMARY_ROW = re.compile(r'^(promedio|total|resumen|nota|resultado global)', re.IGNORECASE)
_BLANK_ANSWER = re.compile(r'^(-|n/a|na|pendiente|vacio|vacío|\?)$', re.IGNORECASE)

TEST_NAME_PATTERNS = ['prueba', 'evaluac', 'examen', 'bateria', 'batería', 'test', 'titulo', 'título']
TEST_NAME_EXCLUDE = ['candidato', 'postulante', 'estado', 'fecha', 'puntaje']
META_ITEM_PATTERNS = ['pregunta', 'dimens', 'competencia', 'item', 'ítem', 'criterio', 'reactivo', 'indicador']
ITEM_PATTERNS = ['pregunta', 'dimens', 'competencia', 'item', 'criterio', 'reactivo', 'indicador']
ANSWER_PATTERNS = ['respuesta', 'marcada', 'valor', 'calif', 'opcion', 'opción']
SCORE_PATTERNS = ['puntaje', 'score', 'puntos', 'nota', 'resultado']
MAX_PATTERNS = ['max', 'escala']


def _js_str(v) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _js_number(v) -> float:
    """Number(v) de JavaScript: undefined/texto no numérico -> NaN, '' -> 0."""
    if v is None:
        return math.nan
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == '':
        return 0.0
    if _NUMBER.match(s):
        return float(s)
    return math.nan


def _truthy(v) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)):
        return not (v == 0 or (isinstance(v, float) and math.isnan(v)))
    return v != ''


def _entries(row: dict) -> list[tuple[str, object]]:
    return [(str(k).strip().lower(), v) for k, v in row.items()]


def _find_val(entries, patterns, exclude=()):
    for k, v in entries:
        if (
            any(p in k for p in patterns)
            and not any(ex in k for ex in exclude)
            and v is not None
            and _js_str(v).strip() != ''
        ):
            return v
    return None


def _first_long_string(entries, min_len):
    for _, v in entries:
        if isinstance(v, str) and len(v.strip()) > min_len:
            return v
    return None


def extract_excel_test_metadata(rows: list[dict], file_name: str, sheet_name: str | None = None) -> dict:
    """Port de extractExcelTestMetadata (recruitment.ts:95-194)."""
    name_from_cells = ''
    questions: list[str] = []

    for row in rows:
        entries = _entries(row)
        if not name_from_cells:
            candidate_name = _find_val(entries, TEST_NAME_PATTERNS, TEST_NAME_EXCLUDE)
            if candidate_name is not None:
                candidate_name = _js_str(candidate_name).strip()
                if len(candidate_name) >= 3:
                    name_from_cells = candidate_name

        item_raw = _find_val(entries, META_ITEM_PATTERNS)
        if item_raw is None:
            item_raw = _first_long_string(entries, 4)
        if _truthy(item_raw):
            q = _js_str(item_raw).strip()
            if not _SUMMARY_ROW.match(q):
                questions.append(q)

    cleaned_file = re.sub(r'\.(xlsx|xls|csv|ods)$', '', file_name or '', flags=re.IGNORECASE)
    cleaned_file = re.sub(
        r'^(?:Plantilla_Prueba_Automatica_|Prueba_Resuelta_Ejemplo_|Plantilla_Base_)', '', cleaned_file,
        flags=re.IGNORECASE,
    )
    cleaned_file = re.sub(r'[_-]+', ' ', cleaned_file)
    cleaned_file = re.sub(r'\s+', ' ', cleaned_file).strip()

    cleaned_sheet = ''
    if sheet_name and not re.match(r'^(sheet\d*|hoja\d*|prueba_automatica|resultados)$', sheet_name.strip(), re.IGNORECASE):
        cleaned_sheet = re.sub(r'[_-]+', ' ', sheet_name).strip()

    test_name = name_from_cells or cleaned_sheet or cleaned_file or 'Prueba Excel Importada'

    combined = f"{test_name} {' '.join(questions)}".lower()
    category = 'Técnica Minera'
    area = 'Operaciones Mina'
    if re.search(r'hsec|ssoma|iperc|petar|ds-024|seguridad', combined):
        category, area = 'Seguridad HSEC', 'Seguridad HSEC'
    elif re.search(r'scoop|jumbo|volquete|camion|maquinaria|sucamec|voladura', combined):
        category, area = 'Operación / Maquinaria', 'Operaciones Mina'
    elif re.search(r'psico|emocional|personalidad|liderazgo|clima|aptitud|conducta', combined):
        category, area = 'Psicolaboral', 'Operaciones Mina'
    elif re.search(r'planta|molienda|flotaci|metalurg|laboratorio|chancad', combined):
        category, area = 'Técnica Minera', 'Control Metalúrgico'

    return {
        'detectedTestName': test_name,
        'detectedCategory': category,
        'detectedTargetArea': area,
        'questions': questions,
    }


def _score_row(answer_raw, score_raw, max_raw, answer_str: str) -> tuple[int, bool]:
    numeric_score = _js_number(score_raw)
    numeric_ans = _js_number(answer_raw)
    max_scale = _js_number(max_raw)
    if math.isnan(max_scale) or max_scale == 0:
        max_scale = 5

    if math.isfinite(numeric_score) and numeric_score > 0:
        if numeric_score <= 5:
            return js_round(38 + max(1, min(5, numeric_score)) * 12), True
        return max(0, min(100, js_round(numeric_score))), True
    if math.isfinite(numeric_ans) and numeric_ans > 0:
        if numeric_ans <= max_scale and max_scale <= 10:
            ratio = max(0, min(1, numeric_ans / max_scale))
            return js_round(40 + ratio * 58), True
        return max(0, min(100, js_round(numeric_ans))), True
    if re.match(r'^(si|sí|aprobado|apto|cumple|siempre|correcto|alto|muy alto)$', answer_str, re.IGNORECASE):
        return 90, True
    if re.match(r'^(a veces|medio|regular|parcial)$', answer_str, re.IGNORECASE):
        return 68, True
    if re.match(r'^(no|no cumple|desaprobado|bajo|nunca)$', answer_str, re.IGNORECASE):
        return 42, True
    if len(answer_str) >= 4:  # respuesta cualitativa descriptiva
        return 76, True
    return 0, False


def _ai_analysis(verdict: str, answered: int, total: int, score: int, passing_score: int | None, passed) -> str:
    if verdict == 'Inconsistencia Detectada':
        return ('No se detectaron respuestas válidas en el archivo: revisa que tenga columnas de pregunta y '
                'respuesta y vuelve a cargarlo.')
    text = f'{verdict}: {answered} de {total} ítems respondidos con un puntaje automático de {score}/100.'
    if verdict == 'Resultados Parciales':
        text += ' Hay ítems sin responder o la prueba tiene menos de 3 ítems; el puntaje es referencial.'
    if passing_score is not None:
        text += (
            f' Supera el puntaje mínimo de {passing_score}.' if passed
            else f' No alcanza el puntaje mínimo de {passing_score}.'
        )
    return text


def evaluate_excel_test_rows(rows: list[dict], passing_score: int | None = None) -> dict:
    """Port de evaluateExcelTestRows (recruitment.ts:201-350).

    H-06: passed = autoComputedScore >= passing_score si se informa el mínimo; si no, None.
    """
    parsed_rows: list[dict] = []

    for row in rows:
        entries = _entries(row)
        item_raw = _find_val(entries, ITEM_PATTERNS)
        if item_raw is None:
            item_raw = _first_long_string(entries, 3)
        if not _truthy(item_raw):
            continue
        item = _js_str(item_raw).strip()
        if _SUMMARY_ROW.match(item):
            continue

        answer_raw = _find_val(entries, ANSWER_PATTERNS)
        score_raw = _find_val(entries, SCORE_PATTERNS)
        max_raw = _find_val(entries, MAX_PATTERNS)

        if answer_raw is not None:
            answer_str = _js_str(answer_raw).strip()
        elif score_raw is not None:
            answer_str = _js_str(score_raw).strip()
        else:
            answer_str = ''

        is_blank = not answer_str or bool(_BLANK_ANSWER.match(answer_str))
        score, concrete = (0, False) if is_blank else _score_row(answer_raw, score_raw, max_raw, answer_str)
        parsed_rows.append({
            'item': item,
            'answer': 'Sin responder' if is_blank else answer_str,
            'score': score,
            'concrete': concrete,
        })

    total = len(parsed_rows)
    answered_rows = [r for r in parsed_rows if r['concrete']]
    answered = len(answered_rows)
    auto_score = js_round(sum(r['score'] for r in answered_rows) / answered) if answered > 0 else 0

    if total == 0 or answered == 0:
        verdict, concrete_result = 'Inconsistencia Detectada', False
    elif answered < total or total < 3:
        verdict, concrete_result = 'Resultados Parciales', False
    else:
        verdict, concrete_result = 'Resultados Concretos', True

    def pick_axis(keywords: list[str], fallback: int) -> int:
        matched = [r for r in answered_rows if any(k in r['item'].lower() for k in keywords)]
        if not matched:
            return fallback
        return js_round(sum(r['score'] for r in matched) / len(matched))

    base = auto_score or 70
    derived = dict(zip(PSYCH_KEYS, (
        pick_axis(['estabil', 'emocion', 'presi'], base),
        pick_axis(['altura', 'faena', '14x7', 'campamento', 'remoto'], base),
        pick_axis(['hsec', 'seguridad', 'norma', 'ds-024', 'iperc'], base),
        pick_axis(['equipo', 'cuadrilla', 'comunic', 'lideraz'], base),
        pick_axis(['razonam', 'falla', 'planta', 'operativ', 'técnic', 'tecnic'], base),
    )))

    passed = (auto_score >= passing_score) if passing_score is not None else None

    return {
        'parsedRows': parsed_rows,
        'totalQuestions': total,
        'answeredCount': answered,
        'autoComputedScore': auto_score,
        'isConcreteResult': concrete_result,
        'concreteVerdict': verdict,
        'derivedScores': derived,
        'passed': passed,
        'aiAnalysis': _ai_analysis(verdict, answered, total, auto_score, passing_score, passed),
    }


# --- lectura y plantilla (Tarea 10) -------------------------------------------

TEMPLATE_COLUMNS = ['Prueba Evaluada', 'Candidato', 'Pregunta', 'Respuesta', 'Escala Máxima']
DEFAULT_TEMPLATE_QUESTIONS = [
    'Estabilidad operativa bajo presión en faena',
    'Cumplimiento estricto de normas HSEC y PETAR',
    'Dominio técnico del puesto minero',
    'Coordinación efectiva en guardia 14x7',
]
DEFAULT_TEMPLATE_NAME = 'Prueba Base'
MAX_EXCEL_ROWS = 2000


class ExcelReadError(ValueError):
    pass


def _clean_cell(v):
    return v.strip() if isinstance(v, str) else v


def read_excel_rows(data: bytes, filename: str) -> tuple[list[dict], str]:
    """Primera hoja de un .xlsx (o un CSV) como filas {encabezado: valor}; devuelve (filas, nombre de la hoja)."""
    import csv
    import io

    name = (filename or '').lower()
    try:
        if name.endswith('.csv'):
            text = data.decode('utf-8-sig', errors='replace')
            rows = [dict(r) for r in csv.DictReader(io.StringIO(text))]
            return [r for r in rows if any(v not in (None, '') for v in r.values())][:MAX_EXCEL_ROWS], ''
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        header = None
        rows: list[dict] = []
        for raw in ws.iter_rows(values_only=True):
            if all(c in (None, '') for c in raw):
                continue
            if header is None:
                header = [str(c).strip() if c is not None else '' for c in raw]
                continue
            rows.append({h: _clean_cell(c) for h, c in zip(header, raw) if h})
            if len(rows) >= MAX_EXCEL_ROWS:
                break
        title = ws.title
        wb.close()
        return rows, title
    except Exception:  # noqa: BLE001 - archivo dañado o de otro formato
        raise ExcelReadError('No se pudo leer el archivo: usa un .xlsx o .csv válido') from None


def _no_formula(v):
    """Texto que empieza como fórmula de Excel se escribe con un apóstrofo delante para que no se ejecute."""
    return "'" + v if isinstance(v, str) and v[:1] in ('=', '+', '-', '@', '\t', '\r') else v


def build_excel_template(test: dict | None, candidate_name: str | None) -> bytes:
    """Plantilla .xlsx con una hoja `Prueba`: una fila por pregunta, respuesta vacía y escala máxima 5."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = 'Prueba'
    ws.append(TEMPLATE_COLUMNS)
    name = (test or {}).get('name') or DEFAULT_TEMPLATE_NAME
    questions = list((test or {}).get('questions') or []) or DEFAULT_TEMPLATE_QUESTIONS
    for q in questions:
        ws.append([_no_formula(name), _no_formula(candidate_name or ''), _no_formula(q), None, 5])
    for col, width in zip('ABCDE', (32, 26, 56, 14, 16)):
        ws.column_dimensions[col].width = width
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

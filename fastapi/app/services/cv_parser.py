"""Lector de CVs peruano-minero: port de parseCvTextToCandidate (cvParser.ts:179-447).

Diferencias con el original: recibe puestos (no vacantes), email y teléfono van separados,
se extrae el documento de identidad y los apellidos se separan según el largo del nombre.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

_I = re.IGNORECASE

PERU_CITIES = [
    (re.compile(r'\bcerro\s+de\s+pasco\b', _I), 'Cerro de Pasco, Perú'),
    (re.compile(r'\barequipa\b', _I), 'Arequipa, Perú'),
    (re.compile(r'\bcajamarca\b', _I), 'Cajamarca, Perú'),
    (re.compile(r'\bcusco\b|\bcuzco\b', _I), 'Cusco, Perú'),
    (re.compile(r'\bmoquegua\b', _I), 'Moquegua, Perú'),
    (re.compile(r'\btacna\b', _I), 'Tacna, Perú'),
    (re.compile(r'\bhuancayo\b', _I), 'Huancayo, Junín, Perú'),
    (re.compile(r'\bjun[ií]n\b', _I), 'Junín, Perú'),
    (re.compile(r'\bpasco\b', _I), 'Pasco, Perú'),
    (re.compile(r'\bhuaraz\b', _I), 'Huaraz, Áncash, Perú'),
    (re.compile(r'\b[aá]ncash\b', _I), 'Áncash, Perú'),
    (re.compile(r'\bapur[ií]mac\b', _I), 'Apurímac, Perú'),
    (re.compile(r'\babancay\b', _I), 'Abancay, Apurímac, Perú'),
    (re.compile(r'\bayacucho\b', _I), 'Ayacucho, Perú'),
    (re.compile(r'\bpuno\b', _I), 'Puno, Perú'),
    (re.compile(r'\bjuliaca\b', _I), 'Juliaca, Puno, Perú'),
    (re.compile(r'\btrujillo\b', _I), 'Trujillo, La Libertad, Perú'),
    (re.compile(r'\bla\s+libertad\b', _I), 'La Libertad, Perú'),
    (re.compile(r'\bpiura\b', _I), 'Piura, Perú'),
    (re.compile(r'\bica\b', _I), 'Ica, Perú'),
    (re.compile(r'\bhuancavelica\b', _I), 'Huancavelica, Perú'),
    (re.compile(r'\bhu[aá]nuco\b', _I), 'Huánuco, Perú'),
    (re.compile(r'\blima\b', _I), 'Lima, Perú'),
]

KNOWN_INSTITUTIONS = [
    (re.compile(r'\b(?:UNI|Universidad\s+Nacional\s+de\s+Ingenier[ií]a)\b', _I), 'UNI - Universidad Nacional de Ingeniería'),
    (re.compile(r'\b(?:UNSA|Universidad\s+Nacional\s+de\s+San\s+Agust[ií]n)\b', _I), 'UNSA - Universidad Nacional de San Agustín'),
    (re.compile(r'\b(?:PUCP|Pontificia\s+Universidad\s+Cat[oó]lica(?:\s+del\s+Per[uú])?)\b', _I), 'PUCP - Pontificia Universidad Católica del Perú'),
    (re.compile(r'\b(?:UNMSM|San\s+Marcos|Universidad\s+Nacional\s+Mayor\s+de\s+San\s+Marcos)\b', _I), 'UNMSM - Universidad Nacional Mayor de San Marcos'),
    (re.compile(r'\b(?:UNCP|Universidad\s+Nacional\s+del\s+Centro(?:\s+del\s+Per[uú])?)\b', _I), 'UNCP - Universidad Nacional del Centro del Perú'),
    (re.compile(r'\b(?:UNSAAC|Universidad\s+Nacional\s+de\s+San\s+Antonio\s+Abad(?:\s+del\s+Cusco)?)\b', _I), 'UNSAAC - Universidad Nacional de San Antonio Abad del Cusco'),
    (re.compile(r'\b(?:TECSUP)\b', _I), 'TECSUP'),
    (re.compile(r'\b(?:CETEMIN)\b', _I), 'CETEMIN - Centro Tecnológico Minero'),
    (re.compile(r'\b(?:SENATI)\b', _I), 'SENATI'),
    (re.compile(r'\b(?:SENCICO)\b', _I), 'SENCICO'),
    (re.compile(r'\b(?:UNDAC|Daniel\s+Alcides\s+Carri[oó]n)\b', _I), 'UNDAC - Universidad Nacional Daniel Alcides Carrión'),
    (re.compile(r'\b(?:UNASAM|Santiago\s+Ant[uú]nez\s+de\s+Mayolo)\b', _I), 'UNASAM - Universidad Nacional Santiago Antúnez de Mayolo'),
    (re.compile(r'\b(?:UNJBG|Jorge\s+Basadre\s+Grohmann)\b', _I), 'UNJBG - Universidad Nacional Jorge Basadre Grohmann'),
    (re.compile(r'\b(?:UNAP|Universidad\s+Nacional\s+del\s+Altiplano)\b', _I), 'UNAP - Universidad Nacional del Altiplano'),
    (re.compile(r'\b(?:UNC|Universidad\s+Nacional\s+de\s+Cajamarca)\b', _I), 'Universidad Nacional de Cajamarca'),
    (re.compile(r'\b(?:UNT|Universidad\s+Nacional\s+de\s+Trujillo)\b', _I), 'Universidad Nacional de Trujillo'),
    (re.compile(r'\b(?:UTP|Universidad\s+Tecnol[oó]gica\s+del\s+Per[uú])\b', _I), 'UTP - Universidad Tecnológica del Perú'),
    (re.compile(r'\b(?:UPC|Universidad\s+Peruana\s+de\s+Ciencias\s+Aplicadas)\b', _I), 'UPC - Universidad Peruana de Ciencias Aplicadas'),
    (re.compile(r'\b(?:UPN|Universidad\s+Privada\s+del\s+Norte)\b', _I), 'UPN - Universidad Privada del Norte'),
    (re.compile(r'\bUniversidad\s+Continental\b', _I), 'Universidad Continental'),
    (re.compile(r'\b(?:UCSM|Cat[oó]lica\s+de\s+Santa\s+Mar[ií]a)\b', _I), 'UCSM - Universidad Católica de Santa María'),
]

KNOWN_CAREERS = [
    (re.compile(r'\bingenier[ií]a\s+de\s+minas\b|\bingenier[oa]\s+de\s+minas\b', _I), 'Ingeniería de Minas'),
    (re.compile(r'\bingenier[ií]a\s+metal[uú]rgica\b|\bingenier[oa]\s+metal[uú]rgic[oa]\b', _I), 'Ingeniería Metalúrgica'),
    (re.compile(r'\bingenier[ií]a\s+geol[oó]gica\b|\bge[oó]log[oa]\b', _I), 'Ingeniería Geológica / Geología'),
    (re.compile(r'\b(?:higiene\s+y\s+seguridad|seguridad\s+industrial|seguridad\s+minera|ingenier[ií]a\s+de\s+seguridad|HSEC|SSOMA)\b', _I), 'Seguridad Industrial y Minera (HSEC)'),
    (re.compile(r'\bingenier[ií]a\s+ambiental\b', _I), 'Ingeniería Ambiental'),
    (re.compile(r'\bingenier[ií]a\s+mec[aá]nica(?:\s+el[eé]ctrica)?\b', _I), 'Ingeniería Mecánica'),
    (re.compile(r'\bingenier[ií]a\s+el[eé]ctrica\b|\belectricista\s+industrial\b', _I), 'Ingeniería Eléctrica / Electricista Industrial'),
    (re.compile(r'\bingenier[ií]a\s+industrial\b', _I), 'Ingeniería Industrial'),
    (re.compile(r'\bingenier[ií]a\s+qu[ií]mica\b', _I), 'Ingeniería Química'),
    (re.compile(r'\bmantenimiento\s+de\s+maquinaria\s+pesada\b|\bmec[aá]nic[oa]\s+de\s+equipo\s+pesado\b', _I), 'Mantenimiento de Maquinaria Pesada'),
    (re.compile(r'\boperaci[oó]n\s+de\s+plantas(?:\s+concentradoras|\s+de\s+procesamiento)?\b|\boperador\s+de\s+planta\b', _I), 'Operación de Plantas Concentradoras'),
    (re.compile(r'\boperador\s+de\s+maquinaria\s+pesada\b|\boperador\s+(?:de\s+)?(?:scooptram|jumbo|volquete|camion|excavadora)\b', _I), 'Operación de Maquinaria Pesada Minera'),
    (re.compile(r'\bperforaci[oó]n\s+y\s+voladura\b|\bperforista\b', _I), 'Perforación y Voladura Minera'),
    (re.compile(r'\bmedicina\s+ocupacional\b|\benfermer[ií]a\b|\bparam[eé]dic[oa]\b', _I), 'Salud Ocupacional / Paramédico'),
    (re.compile(r'\brelaciones\s+comunitarias\b|\btrabajo\s+social\b|\bsociolog[ií]a\b|\bantropolog[ií]a\b', _I), 'Relaciones Comunitarias y Gestión Social'),
    (re.compile(r'\badministraci[oó]n(?:\s+de\s+empresas)?\b|\blog[ií]stica\b|\bcontabilidad\b', _I), 'Administración y Logística'),
]

SPEC_PATTERNS = [
    (re.compile(r'\bHSEC\b|\bSSOMA\b', _I), 'Certificación HSEC vigente'),
    (re.compile(r'\bDS[\s-]*024[\s-]*2016[\s-]*EM\b|\bDS[\s-]*024\b', _I), 'Normativa DS-024-2016-EM'),
    (re.compile(r'\bIPERC\b', _I), 'IPERC Continuo'),
    (re.compile(r'\bPETAR\b', _I), 'Gestión PETAR'),
    (re.compile(r'\bISO\s*45001\b', _I), 'Auditor / Norma ISO 45001'),
    (re.compile(r'\bISO\s*14001\b', _I), 'Norma ISO 14001'),
    (re.compile(r'\bSUCAMEC\b', _I), 'Carnet SUCAMEC vigente'),
    (re.compile(r'\b(?:licencia|brevete)\s*(?:de\s*conducir\s*)?(?:MTC\s*)?A[\s-]*(?:IIIc|IIIb|IIIa|IIb|IIa|I)\b', _I), ''),
    (re.compile(r'\b(?:altura|msnm|4[.,]?\d{3}\s*msnm|gran\s+altura)\b', _I), 'Trabajo en altura > 4,000 msnm'),
    (re.compile(r'\b14\s*[xX×]\s*7\b|\b20\s*[xX×]\s*10\b', _I), 'Disponibilidad régimen minero'),
    (re.compile(r'\bSAG\b|\bmolienda\b|\bchancado\b|\bflotaci[oó]n\b', _I), 'Planta Concentradora (Chancado/Molienda/Flotación)'),
    (re.compile(r'\bscooptram\b|\bjumbo\b|\bvolquete\b|\bcamion\s+minero\b|\bdumper\b', _I), 'Operación Trackless / Flota Mina'),
    (re.compile(r'\bdatamine\b|\bminesight\b|\bleapfrog\b|\bvulcan\b', _I), 'Software Geológico / Planeamiento Mina'),
    (re.compile(r'\bautocad\b', _I), 'AutoCAD'),
    (re.compile(r'\bsap\b', _I), 'SAP ERP / MM / PM'),
    (re.compile(r'\bpower\s*bi\b', _I), 'Power BI'),
    (re.compile(r'\bexcel\s+avanzado\b', _I), 'Excel Avanzado'),
    (re.compile(r'\bcolegiad[oa]\b|\bCIP\b', _I), 'Colegiado y Habilitado CIP'),
    (re.compile(r'\balta\s+tensi[oó]n\b|\bsubestaciones\b', _I), 'Alta Tensión y Subestaciones'),
    (re.compile(r'\bQA\s*/\s*QC\b|\bespectrometr[ií]a\b', _I), 'QA/QC y Espectrometría'),
    (re.compile(r'\bBLS\b|\bPHTLS\b|\bprimeros\s+auxilios\b', _I), 'Certificación BLS / Emergencias'),
]

HEADER_NOISE = re.compile(
    r'^(?:CURRICULUM\s+VITAE|CURR[IÍ]CULUM\s+VITAE|HOJA\s+DE\s+VIDA|RESUME|CV|DATOS\s+PERSONALES|PERFIL\s+PROFESIONAL'
    r'|RESUMEN\s+EJECUTIVO|EXPERIENCIA\s+LABORAL|FORMACI[OÓ]N\s+ACAD[EÉ]MICA|EDUCACI[OÓ]N|CONTACTO|OBJETIVO)$',
    _I,
)

DOCUMENT_ID = re.compile(
    r'\b(?:DNI|D\.N\.I\.|CE|Carn[eé] de extranjer[ií]a)\s*[:N°º#.\s]*([0-9]{8,12})', _I,
)
EMAIL = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE = re.compile(r'(?:\+?51[\s.-]*)?9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}|\+\d{1,3}[\s.-]?\d{6,12}')
PERSON_WORD = re.compile(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ.'-]+$")

DEFAULT_AGE = 32
DEFAULT_YEARS = 4
UNKNOWN_NAME = 'Postulante (Verificar Nombre)'


@dataclass
class ParsedCv:
    full_name: str
    first_names: str
    last_names: str
    age: int
    origin_location: str
    university: str
    career: str
    years_worked: int
    work_history_summary: str
    specifications: list[str] = field(default_factory=list)
    email: str = ''
    phone: str = ''
    document_id: str = ''
    suggested_position_id: str = ''


def _normalize_words(text: str) -> list[str]:
    decomposed = unicodedata.normalize('NFD', text.lower())
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return [w for w in re.split(r'[^a-z0-9]+', stripped) if len(w) >= 3]


def _labeled_field(lines: list[str], labels: list[re.Pattern]) -> str | None:
    for line in lines:
        for label in labels:
            m = label.search(line)
            if m and m.group(1).strip():
                return m.group(1).strip()
    return None


def split_person_name(full_name: str) -> tuple[str, str]:
    """Con 4 palabras o más, las 2 últimas son apellidos; con menos, solo la última."""
    words = full_name.split()
    if len(words) <= 1:
        return full_name, ''
    n_last = 2 if len(words) >= 4 else 1
    return ' '.join(words[:-n_last]), ' '.join(words[-n_last:])


def _title_case_if_upper(w: str) -> str:
    return w[0].upper() + w[1:].lower() if w == w.upper() else w


def parse_cv_text(text: str, positions: list[dict]) -> ParsedCv:
    clean = re.sub(r'\r\n?', '\n', text).replace('\x00', ' ').strip()
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in clean.split('\n')]
    lines = [ln for ln in lines if ln]
    current_year = datetime.now().year

    # 1. Nombre completo
    full_name = _labeled_field(lines, [re.compile(
        r'^(?:apellidos\s+y\s+nombres|nombres\s+y\s+apellidos|nombre\s+completo|postulante|candidato|nombre)\s*[:\-–]\s*(.+)$',
        _I,
    )]) or ''
    if not full_name:
        for line in lines[:12]:
            if (
                HEADER_NOISE.match(line) or '@' in line or re.search(r'https?://', line, _I)
                or re.search(r'\d{4,}', line) or len(line) > 58 or len(line) < 5
            ):
                continue
            words = line.split()
            if 2 <= len(words) <= 5 and all(PERSON_WORD.match(w) for w in words):
                full_name = ' '.join(_title_case_if_upper(w) for w in words)
                break

    # 2. Contacto: email y teléfono por separado
    email_m = EMAIL.search(clean)
    phone_m = PHONE.search(clean)
    email = email_m.group(0).strip() if email_m else ''
    phone = re.sub(r'\s+', ' ', phone_m.group(0)).strip() if phone_m else ''
    if not email and not phone:
        labeled = _labeled_field(lines, [re.compile(
            r'^(?:tel[eé]fono|celular|m[oó]vil|contacto|correo(?:\s+electr[oó]nico)?|email)\s*[:\-–]\s*(.+)$', _I,
        )])
        if labeled:
            if '@' in labeled:
                email = labeled
            else:
                phone = labeled

    # 3. Documento de identidad
    doc_m = DOCUMENT_ID.search(clean)
    document_id = doc_m.group(1) if doc_m else ''

    # 4. Edad
    age = DEFAULT_AGE
    age_m = (
        re.search(r'(?:edad)\s*[:\-–]?\s*(\d{2})\s*(?:a[nñ]os)?', clean, _I)
        or re.search(r'\b(\d{2})\s*a[nñ]os(?!\s*(?:de\s+)?experiencia|.*trabajad)', clean, _I)
    )
    if age_m:
        parsed_age = int(age_m.group(1))
        if 18 <= parsed_age <= 72:
            age = parsed_age
    else:
        birth_m = re.search(
            r'(?:nacimiento|nacido|f\.?\s*nac\.?)\s*[:\-–]?\s*(?:\d{1,2}[/-]\d{1,2}[/-])?(19[5-9]\d|200[0-7])',
            clean, _I,
        )
        if birth_m:
            computed = current_year - int(birth_m.group(1))
            if 18 <= computed <= 72:
                age = computed

    # 5. Procedencia
    origin = _labeled_field(lines, [re.compile(
        r'^(?:procedencia|ciudad|residencia|ubicaci[oó]n|lugar\s+de\s+residencia|direcci[oó]n)\s*[:\-–]\s*(.+)$', _I,
    )]) or ''
    for pattern, normalized in PERU_CITIES:
        if pattern.search(origin or clean):
            origin = normalized
            break
    if not origin:
        origin = 'Perú'

    # 6. Universidad / instituto
    university = _labeled_field(lines, [re.compile(
        r'^(?:universidad|instituto|centro\s+de\s+estudios|casa\s+de\s+estudios|instituci[oó]n)\s*[:\-–]\s*(.+)$', _I,
    )]) or ''
    if not university:
        for pattern, label in KNOWN_INSTITUTIONS:
            if pattern.search(clean):
                university = label
                break
    if not university:
        edu_line = next((ln for ln in lines if re.search(
            r'\b(?:Universidad|Instituto\s+Superior|Escuela\s+T[eé]cnica)\b', ln, _I)), None)
        if edu_line:
            university = edu_line[:90]
    if not university:
        university = 'Formación Técnica / Universitaria'

    # 7. Carrera
    career = _labeled_field(lines, [re.compile(
        r'^(?:carrera|profesi[oó]n|especialidad|t[ií]tulo(?:\s+profesional)?|puesto\s+actual|cargo\s+actual)\s*[:\-–]\s*(.+)$',
        _I,
    )]) or ''
    if not career:
        for pattern, label in KNOWN_CAREERS:
            if pattern.search(clean):
                career = label
                break
    if not career:
        career = 'Especialista Operaciones Mineras'

    # 8. Años trabajados
    years = DEFAULT_YEARS
    exp_m = (
        re.search(r'(\d{1,2})\s*\+?\s*a[nñ]os\s+(?:de\s+)?(?:experiencia|trayectoria|labor|trabajo)', clean, _I)
        or re.search(r'(?:experiencia|tiempo\s+trabajado)\s*[:\-–]?\s*(\d{1,2})\s*\+?\s*a[nñ]os', clean, _I)
    )
    if exp_m:
        years = max(0, min(45, int(exp_m.group(1))))
    else:
        ranges = list(re.finditer(
            r'\b(19[89]\d|20[0-2]\d)\s*[-–—a]\s*(19[89]\d|20[0-2]\d|actual(?:idad)?|presente)\b', clean, _I,
        ))
        if ranges:
            min_start, max_end = 9999, 0
            for m in ranges:
                start = int(m.group(1))
                end = current_year if re.search(r'actual|presente', m.group(2), _I) else int(m.group(2))
                min_start, max_end = min(min_start, start), max(max_end, end)
            if max_end >= min_start and min_start < 9999:
                years = max(1, min(40, max_end - min_start))

    # 9. Especificaciones
    specs: dict[str, None] = {}
    for pattern, label in SPEC_PATTERNS:
        m = pattern.search(clean)
        if not m:
            continue
        if label:
            specs[label] = None
        else:
            code = re.search(r'A[\s-]*(?:IIIc|IIIb|IIIa|IIb|IIa|I)', m.group(0), _I)
            if code:
                specs[f"Licencia {re.sub(r'\s+', '', code.group(0)).upper()}"] = None
    labeled_specs = _labeled_field(lines, [re.compile(
        r'^(?:certificaciones|habilidades|competencias|especificaciones|licencias)\s*[:\-–]\s*(.+)$', _I,
    )])
    if labeled_specs:
        parts = [p.strip() for p in re.split(r'[,;|•]', labeled_specs)]
        for p in [p for p in parts if 2 <= len(p) <= 55][:5]:
            specs[p] = None
    specifications = list(specs)[:8]
    if not specifications:
        specifications.append('Evaluación técnica de CV adjunto')

    # 10. Resumen de trayectoria
    summary = ''
    exp_idx = next((i for i, ln in enumerate(lines) if re.match(
        r'^(?:experiencia\s+laboral|trayectoria\s+laboral|experiencia\s+profesional|experiencia)\b', ln, _I)), -1)
    if exp_idx >= 0:
        chunk = [ln for ln in lines[exp_idx + 1:exp_idx + 6]
                 if not re.match(r'^(?:formaci[oó]n|educaci[oó]n|habilidades|referencias)\b', ln, _I)]
        summary = ' · '.join(chunk)[:320]
    if not summary:
        summary = ' · '.join([ln for ln in lines if not HEADER_NOISE.match(ln) and ln != full_name][:4])[:300]
    if not summary:
        summary = f'{years} años de experiencia en el rubro.'

    # 11. Puesto sugerido por coincidencia de palabras
    cv_tokens = set(_normalize_words(f"{career} {' '.join(specifications)} {clean[:3000]}"))
    best_id = positions[0]['id'] if positions else ''
    best_overlap = -1
    for pos in positions:
        words = _normalize_words(
            f"{pos.get('name') or ''} {pos.get('area') or ''} {pos.get('requiredSkills') or ''} "
            f"{pos.get('technicalSpecifications') or ''}"
        )
        overlap = sum(1 for w in words if w in cv_tokens)
        if overlap > best_overlap:
            best_overlap, best_id = overlap, pos['id']

    if full_name:
        first_names, last_names = split_person_name(full_name)
    else:
        full_name, first_names, last_names = UNKNOWN_NAME, UNKNOWN_NAME, ''

    return ParsedCv(
        full_name=full_name,
        first_names=first_names,
        last_names=last_names,
        age=age,
        origin_location=origin,
        university=university,
        career=career,
        years_worked=years,
        work_history_summary=summary,
        specifications=specifications,
        email=email,
        phone=phone,
        document_id=document_id,
        suggested_position_id=best_id,
    )

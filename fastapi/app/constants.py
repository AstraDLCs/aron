"""Constantes de dominio compartidas. Los textos son exactos: la app y la base los usan tal cual."""

AI_STATUSES = ('En cola', 'Procesando', 'Clasificado', 'Error IA', 'Sin texto', 'Sin IA')
AI_VERDICTS = ('Pre-aprobado', 'Pre-denegado')

DECISIONS = ('Pendiente de revisión', 'Aprobado', 'Rechazado', 'Contratado')
# Sin pasos obligatorios: desde cualquier estado se puede aprobar, rechazar o contratar (la bitácora deja el rastro).
_FINAL_DECISIONS = {'Aprobado', 'Rechazado', 'Contratado'}
DECISION_TRANSITIONS = {d: _FINAL_DECISIONS - {d} for d in DECISIONS}

REQUIREMENT_STATUSES = ('Abierto', 'Cubierto', 'Cancelado')
URGENCIES = ('Urgente', 'Media', 'Planificada')
SOURCE_CATEGORIES = ('Portal Minero', 'Red Profesional', 'Bolsa Nacional', 'Referidos Faena')
TEST_CATEGORIES = ('Psicolaboral', 'Técnica Minera', 'Seguridad HSEC', 'Operación / Maquinaria')
CV_ORIGINS = ('app', 'importacion', 'sync_local', 'carpeta_servidor')

ALL_AREAS = 'Todas las áreas'
SYSTEM_ACTOR = 'Sistema'
AI_ACTOR = 'Sistema (IA)'

ALLOWED_CV_EXTENSIONS = ('.pdf', '.docx', '.txt', '.rtf')
MAX_CV_BYTES = 15 * 1024 * 1024
CV_TEXT_LIMIT = 12000

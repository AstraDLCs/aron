"""Datos de la app original (src/data/seedData.ts) como fixtures de prueba.

Los puestos son los 15 de seedData.ts:13-286; los requerimientos replican vacantes y
cubiertos de cada uno (el estado 'Abierta' del original es 'Abierto' en el contrato nuevo).
"""

ELENA = 'Elena Vargas'


def _position(slug, name, area, required_skills, technical_specifications):
    return {
        'id': f'pos-{slug}',
        'name': name,
        'area': area,
        'requiredSkills': required_skills,
        'technicalSpecifications': technical_specifications,
    }


def _requirement(slug, position_name, area, urgency, vacancies, filled, days, boards):
    return {
        'id': f'need-{slug}',
        'positionId': f'pos-{slug}',
        'title': position_name,
        'department': area,
        'urgency': urgency,
        'vacancies': vacancies,
        'filledCount': filled,
        'status': 'Abierto',
        'targetDaysToFill': days,
        'createdBy': ELENA,
        'publishedBoards': boards,
    }


POSITIONS = [
    _position(
        'planta-1', 'Operador de Planta Concentradora Senior', 'Control Metalúrgico',
        'molienda, flotación, chancado SAG, seguridad HSEC, turno 14x7',
        'Experiencia >= 4 años en chancado y molienda SAG/bolas, Certificación HSEC vigente, aptitud médica altura > 4,200 msnm, Licencia A-IIb.',
    ),
    _position(
        'hsec-2', 'Ingeniero Supervisor de Seguridad HSEC', 'Seguridad HSEC',
        'DS-024-2016-EM, IPERC, auditoría mina, liderazgo de cuadrillas',
        'Titulado/Colegiado en Ing. de Minas o Seguridad Industrial, dominio de DS-024-2016-EM, 5+ años en tajo abierto o socavón.',
    ),
    _position(
        'mina-5', 'Jefe de Guardia Mina (Subterránea / Tajo Abierto)', 'Operaciones Mina',
        'ciclo de minado, sostenimiento, ventilación, voladura, DS-024-2016-EM',
        'Ingeniero de Minas colegiado y habilitado, >= 5 años dirigiendo guardias en socavón o tajo en sierra peruana (> 4,000 msnm).',
    ),
    _position(
        'mina-6', 'Operador de Maquinaria Pesada Mina (Scooptram / Volquete / Camión)', 'Operaciones Mina',
        'scooptram, camión minero, licencia A-IIIc, acarreo, altura',
        'Licencia MTC A-IIIc sin papeletas graves, certificación vigente en Scooptram / Volquete FMX / Dumper, 4+ años en mina.',
    ),
    _position(
        'vol-7', 'Perforista y Cargador de Explosivos (Carnet SUCAMEC)', 'Perforación y Voladura',
        'SUCAMEC, perforación jumbo, jackleg, voladura controlada, ANFO',
        'Carnet SUCAMEC vigente de manipulador de explosivos, experiencia en malla de perforación Jumbo/Jackleg y voladura en frente.',
    ),
    _position(
        'vent-8', 'Técnico de Sostenimiento y Ventilación Mina', 'Operaciones Mina',
        'shotcrete, pernos helicoidales, ventilación mina, monitoreo de gases',
        'Técnico minero con experiencia en lanzado de shotcrete, mallas electrosoldadas, medición de caudal y control de gases (CO, NO2).',
    ),
    _position(
        'geo-9', 'Geólogo de Mina y Control de Leyes (Ore Control)', 'Geología y Planeamiento',
        'ore control, mapeo geomecánico, logueo, muestreo, leyes Cu/Au',
        'Ingeniero Geólogo colegiado, dominio de mapeo de frentes, logueo geotécnico y modelamiento básico de leyes.',
    ),
    _position(
        'plan-10', 'Ingeniero de Planeamiento Mina (Corto y Mediano Plazo)', 'Geología y Planeamiento',
        'Datamine, MineSight, planeamiento corto plazo, KPIs producción',
        'Ingeniero de Minas titulado, manejo avanzado de Datamine / Vulcan / MineSight y control presupuestal de avances.',
    ),
    _position(
        'mant-11', 'Mecánico de Mantenimiento Equipo Pesado (Trackless / Flota)', 'Mantenimiento Mina',
        'hidráulica, motores diesel, Caterpillar, Sandvik, Epiroc, diagnóstico',
        'Técnico Mecánico SENATI / TECSUP, >= 4 años en mantenimiento preventivo y correctivo de Scooptram, Jumbo y volquetes.',
    ),
    _position(
        'elec-12', 'Electricista Industrial de Alta Tensión y Subestaciones Mina', 'Mantenimiento Mina',
        'media tensión, subestaciones, PLC, LOTO, tableros eléctricos',
        'Técnico Electricista Industrial certificado, experiencia en subestaciones mineras, variadores de frecuencia y bloqueo LOTO.',
    ),
    _position(
        'met-3', 'Analista de Laboratorio Metalúrgico', 'Control Metalúrgico',
        'absorción atómica, leyes de cobre/oro, QA/QC, control de reactivos',
        'Ingeniero Metalúrgico o Químico, manejo de espectrometría y balance metalúrgico, disponibilidad turno 14x7.',
    ),
    _position(
        'amb-13', 'Supervisor de Medio Ambiente y Recursos Hídricos', 'Medio Ambiente y RR.CC.',
        'ECA, LMP, monitoreo hídrico, relaves, OEFA, ISO 14001',
        'Ing. Ambiental / Químico colegiado, experiencia en monitoreo de agua, aire, relaveras y fiscalizaciones OEFA / ANA.',
    ),
    _position(
        'rrcc-14', 'Especialista de Relaciones Comunitarias y Gestión Social', 'Medio Ambiente y RR.CC.',
        'relaciones comunitarias, manejo de conflictos, convenios, quechua',
        'Sociólogo, Antropólogo o Comunicador, 4+ años en zonas altoandinas del Perú; dominio de quechua altamente valorado.',
    ),
    _position(
        'log-4', 'Coordinador de Bodega, Explosivos y Campamento Minero', 'Logística y Campamento',
        'SAP MM, inventario crítico, despacho mina, control EPP',
        'Carrera en Administración o Ing. Industrial, manejo de SAP MM / Excel avanzado, experiencia en almacenes remotos.',
    ),
    _position(
        'med-15', 'Paramédico / Médico Ocupacional de Tópico Minero', 'Seguridad HSEC',
        'emergencias altura, PHTLS, BLS, salud ocupacional, DS-024',
        'Profesional de salud habilitado, certificación PHTLS / ACLS vigente y experiencia en rescate minero sobre 4,000 msnm.',
    ),
]

_POSITION_BY_SLUG = {p['id']: p for p in POSITIONS}

# (slug, urgencia, vacantes, cubiertas, días objetivo, bolsas publicadas)
_REQUIREMENT_ROWS = [
    ('planta-1', 'Urgente', 3, 1, 20, ['Computrabajo Minería', 'Bumeran Perú', 'Portal Talento Las Bravas']),
    ('hsec-2', 'Urgente', 2, 1, 25, ['LinkedIn Talento Minero', 'Computrabajo Minería', 'Bumeran Perú']),
    ('mina-5', 'Urgente', 2, 0, 20, ['LinkedIn Talento Minero', 'Computrabajo Minería']),
    ('mina-6', 'Urgente', 4, 1, 18, ['Computrabajo Minería', 'Referidos de Faena', 'Portal Talento Las Bravas']),
    ('vol-7', 'Urgente', 3, 0, 20, ['Computrabajo Minería', 'Referidos de Faena']),
    ('vent-8', 'Media', 2, 0, 22, ['Computrabajo Minería', 'Bumeran Perú']),
    ('geo-9', 'Media', 2, 0, 25, ['LinkedIn Talento Minero', 'Portal Talento Las Bravas']),
    ('plan-10', 'Planificada', 1, 0, 30, ['LinkedIn Talento Minero']),
    ('mant-11', 'Urgente', 3, 0, 20, ['Computrabajo Minería', 'Bumeran Perú', 'Indeed Operaciones']),
    ('elec-12', 'Media', 2, 0, 24, ['Computrabajo Minería', 'LinkedIn Talento Minero']),
    ('met-3', 'Media', 2, 1, 22, ['LinkedIn Talento Minero', 'Indeed Operaciones', 'Referidos de Faena']),
    ('amb-13', 'Media', 1, 0, 28, ['LinkedIn Talento Minero', 'Bumeran Perú']),
    ('rrcc-14', 'Planificada', 1, 0, 30, ['LinkedIn Talento Minero', 'Portal Talento Las Bravas']),
    ('log-4', 'Planificada', 2, 1, 30, ['Computrabajo Minería', 'Portal Talento Las Bravas']),
    ('med-15', 'Urgente', 2, 0, 18, ['Computrabajo Minería', 'LinkedIn Talento Minero']),
]

REQUIREMENTS = [
    _requirement(
        slug, _POSITION_BY_SLUG[f'pos-{slug}']['name'], _POSITION_BY_SLUG[f'pos-{slug}']['area'],
        urgency, vacancies, filled, days, boards,
    )
    for slug, urgency, vacancies, filled, days, boards in _REQUIREMENT_ROWS
]

BOARDS = [
    {'id': 'board-computrabajo', 'name': 'Computrabajo Minería', 'category': 'Bolsa Nacional',
     'proposalsSent': 9, 'candidatesReceived': 42, 'shortlistedCount': 14, 'hiredCount': 3,
     'avgResponseHours': 6, 'active': True},
    {'id': 'board-linkedin', 'name': 'LinkedIn Talento Minero', 'category': 'Red Profesional',
     'proposalsSent': 7, 'candidatesReceived': 28, 'shortlistedCount': 11, 'hiredCount': 2,
     'avgResponseHours': 14, 'active': True},
    {'id': 'board-bumeran', 'name': 'Bumeran Perú', 'category': 'Bolsa Nacional',
     'proposalsSent': 6, 'candidatesReceived': 23, 'shortlistedCount': 7, 'hiredCount': 1,
     'avgResponseHours': 11, 'active': True},
    {'id': 'board-referidos', 'name': 'Referidos de Faena', 'category': 'Referidos Faena',
     'proposalsSent': 4, 'candidatesReceived': 16, 'shortlistedCount': 8, 'hiredCount': 2,
     'avgResponseHours': 4, 'active': True},
    {'id': 'board-portal', 'name': 'Portal Talento Las Bravas', 'category': 'Portal Minero',
     'proposalsSent': 5, 'candidatesReceived': 14, 'shortlistedCount': 6, 'hiredCount': 1,
     'avgResponseHours': 9, 'active': True},
    {'id': 'board-indeed', 'name': 'Indeed Operaciones', 'category': 'Bolsa Nacional',
     'proposalsSent': 3, 'candidatesReceived': 9, 'shortlistedCount': 2, 'hiredCount': 0,
     'avgResponseHours': 18, 'active': True},
]

ROBERTO = {
    'id': 'cand-roberto',
    'fullName': 'Roberto Silva Huamán',
    'firstNames': 'Roberto',
    'lastNames': 'Silva Huamán',
    'age': 44,
    'originLocation': 'Arequipa, Perú',
    'university': 'TECSUP Arequipa',
    'career': 'Operación de Plantas de Procesamiento de Minerales',
    'yearsWorked': 11,
    'workHistorySummary': '11 años como Operador Senior de molienda SAG y flotación en operaciones a 4,400 msnm.',
    'specifications': [
        'Certificación HSEC vigente',
        'Trabajo en altura > 4,200 msnm',
        'Licencia A-IIb',
        'Molienda SAG y Flotación',
    ],
    'email': 'rsilva.mineria@correo.pe',
    'phone': '+51 959 412 301',
    'sourceBoardId': 'board-computrabajo',
    'sourceBoardName': 'Computrabajo Minería',
    'positionId': 'pos-planta-1',
    'requirementId': 'need-planta-1',
    'targetRoleTitle': 'Operador de Planta Concentradora Senior',
    'interviewNotes': 'Destacó en control de emergencias de chancado y liderazgo en turno 14x7.',
    'psychEvaluation': {
        'testBatteryName': 'Pendiente de prueba Excel',
        'accessCode': 'BRV-PS-401',
        'status': 'Sin enviar',
        'scores': None,
        'averageScore': None,
        'aptitudeLevel': 'Pendiente',
        'aiPsychObservation': 'Sin prueba Excel cargada todavía. Sube el archivo Excel de la prueba para obtener resultados IA.',
    },
    'excelTestResults': [],
    'managerScore': None,
    'decision': 'Pendiente de revisión',
    'processDaysElapsed': 6,
}

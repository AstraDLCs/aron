"""Datos de la demo (copiados de src/data/seedData.ts)."""

VACANCIES = [{'title': 'Operador de Planta Concentradora Senior',
  'department': 'Control Metalúrgico',
  'urgency': 'Urgente',
  'vacancies': 3,
  'required_skills': 'molienda, flotación, chancado SAG, seguridad HSEC, turno 14x7',
  'technical_specifications': 'Experiencia >= 4 años en chancado y molienda SAG/bolas, Certificación HSEC '
                              'vigente, aptitud médica altura > 4,200 msnm, Licencia A-IIb.',
  'company_context': 'Ampliación de línea de molienda en Unidad Las Bravas; cobertura inmediata sin '
                     'incidentes.',
  'published_boards': ['Computrabajo Minería', 'Bumeran Perú', 'Portal Talento Las Bravas'],
  'target_days': 20},
 {'title': 'Ingeniero Supervisor de Seguridad HSEC',
  'department': 'Seguridad HSEC',
  'urgency': 'Urgente',
  'vacancies': 2,
  'required_skills': 'DS-024-2016-EM, IPERC, auditoría mina, liderazgo de cuadrillas',
  'technical_specifications': 'Titulado/Colegiado en Ing. de Minas o Seguridad Industrial, dominio de '
                              'DS-024-2016-EM, 5+ años en tajo abierto o socavón.',
  'company_context': 'Supervisión directa de contratistas y cumplimiento cero accidentes en frentes de '
                     'explotación.',
  'published_boards': ['LinkedIn Talento Minero', 'Computrabajo Minería', 'Bumeran Perú'],
  'target_days': 25},
 {'title': 'Jefe de Guardia Mina (Subterránea / Tajo Abierto)',
  'department': 'Operaciones Mina',
  'urgency': 'Urgente',
  'vacancies': 2,
  'required_skills': 'ciclo de minado, sostenimiento, ventilación, voladura, DS-024-2016-EM',
  'technical_specifications': 'Ingeniero de Minas colegiado y habilitado, >= 5 años dirigiendo guardias en '
                              'socavón o tajo en sierra peruana (> 4,000 msnm).',
  'company_context': 'Control operativo de frentes de avance, cumplimiento de programa diario de tonelaje y '
                     'seguridad en guardia.',
  'published_boards': ['LinkedIn Talento Minero', 'Computrabajo Minería'],
  'target_days': 20},
 {'title': 'Operador de Maquinaria Pesada Mina (Scooptram / Volquete / Camión)',
  'department': 'Operaciones Mina',
  'urgency': 'Urgente',
  'vacancies': 4,
  'required_skills': 'scooptram, camión minero, licencia A-IIIc, acarreo, altura',
  'technical_specifications': 'Licencia MTC A-IIIc sin papeletas graves, certificación vigente en Scooptram '
                              '/ Volquete FMX / Dumper, 4+ años en mina.',
  'company_context': 'Acarreo y limpieza continua de mineral en frentes de producción bajo régimen 14x7.',
  'published_boards': ['Computrabajo Minería', 'Referidos de Faena', 'Portal Talento Las Bravas'],
  'target_days': 18},
 {'title': 'Perforista y Cargador de Explosivos (Carnet SUCAMEC)',
  'department': 'Perforación y Voladura',
  'urgency': 'Urgente',
  'vacancies': 3,
  'required_skills': 'SUCAMEC, perforación jumbo, jackleg, voladura controlada, ANFO',
  'technical_specifications': 'Carnet SUCAMEC vigente de manipulador de explosivos, experiencia en malla de '
                              'perforación Jumbo/Jackleg y voladura en frente.',
  'company_context': 'Garantizar fragmentación óptima y control de vibraciones en labores subterráneas y '
                     'tajos.',
  'published_boards': ['Computrabajo Minería', 'Referidos de Faena'],
  'target_days': 20},
 {'title': 'Técnico de Sostenimiento y Ventilación Mina',
  'department': 'Operaciones Mina',
  'urgency': 'Media',
  'vacancies': 2,
  'required_skills': 'shotcrete, pernos helicoidales, ventilación mina, monitoreo de gases',
  'technical_specifications': 'Técnico minero con experiencia en lanzado de shotcrete, mallas '
                              'electrosoldadas, medición de caudal y control de gases (CO, NO2).',
  'company_context': 'Asegurar estabilidad geomecánica de labores subterráneas y calidad de aire según '
                     'DS-024.',
  'published_boards': ['Computrabajo Minería', 'Bumeran Perú'],
  'target_days': 22},
 {'title': 'Geólogo de Mina y Control de Leyes (Ore Control)',
  'department': 'Geología y Planeamiento',
  'urgency': 'Media',
  'vacancies': 2,
  'required_skills': 'ore control, mapeo geomecánico, logueo, muestreo, leyes Cu/Au',
  'technical_specifications': 'Ingeniero Geólogo colegiado, dominio de mapeo de frentes, logueo geotécnico y '
                              'modelamiento básico de leyes.',
  'company_context': 'Minimizar dilución de mineral y asegurar conciliación diaria entre mina y planta '
                     'concentradora.',
  'published_boards': ['LinkedIn Talento Minero', 'Portal Talento Las Bravas'],
  'target_days': 25},
 {'title': 'Ingeniero de Planeamiento Mina (Corto y Mediano Plazo)',
  'department': 'Geología y Planeamiento',
  'urgency': 'Planificada',
  'vacancies': 1,
  'required_skills': 'Datamine, MineSight, planeamiento corto plazo, KPIs producción',
  'technical_specifications': 'Ingeniero de Minas titulado, manejo avanzado de Datamine / Vulcan / MineSight '
                              'y control presupuestal de avances.',
  'company_context': 'Secuenciamiento semanal y mensual de explotación para sostener la ley de cabeza en Las '
                     'Bravas.',
  'published_boards': ['LinkedIn Talento Minero'],
  'target_days': 30},
 {'title': 'Mecánico de Mantenimiento Equipo Pesado (Trackless / Flota)',
  'department': 'Mantenimiento Mina',
  'urgency': 'Urgente',
  'vacancies': 3,
  'required_skills': 'hidráulica, motores diesel, Caterpillar, Sandvik, Epiroc, diagnóstico',
  'technical_specifications': 'Técnico Mecánico SENATI / TECSUP, >= 4 años en mantenimiento preventivo y '
                              'correctivo de Scooptram, Jumbo y volquetes.',
  'company_context': 'Maximizar disponibilidad mecánica de flota crítica (> 90%) en talleres de superficie e '
                     'interior mina.',
  'published_boards': ['Computrabajo Minería', 'Bumeran Perú', 'Indeed Operaciones'],
  'target_days': 20},
 {'title': 'Electricista Industrial de Alta Tensión y Subestaciones Mina',
  'department': 'Mantenimiento Mina',
  'urgency': 'Media',
  'vacancies': 2,
  'required_skills': 'media tensión, subestaciones, PLC, LOTO, tableros eléctricos',
  'technical_specifications': 'Técnico Electricista Industrial certificado, experiencia en subestaciones '
                              'mineras, variadores de frecuencia y bloqueo LOTO.',
  'company_context': 'Continuidad de suministro eléctrico en planta concentradora, bombas de drenaje y '
                     'ventiladores principales.',
  'published_boards': ['Computrabajo Minería', 'LinkedIn Talento Minero'],
  'target_days': 24},
 {'title': 'Analista de Laboratorio Metalúrgico',
  'department': 'Control Metalúrgico',
  'urgency': 'Media',
  'vacancies': 2,
  'required_skills': 'absorción atómica, leyes de cobre/oro, QA/QC, control de reactivos',
  'technical_specifications': 'Ingeniero Metalúrgico o Químico, manejo de espectrometría y balance '
                              'metalúrgico, disponibilidad turno 14x7.',
  'company_context': 'Asegurar trazabilidad horaria de recuperaciones metalúrgicas en laboratorio de unidad '
                     'minera.',
  'published_boards': ['LinkedIn Talento Minero', 'Indeed Operaciones', 'Referidos de Faena'],
  'target_days': 22},
 {'title': 'Supervisor de Medio Ambiente y Recursos Hídricos',
  'department': 'Medio Ambiente y RR.CC.',
  'urgency': 'Media',
  'vacancies': 1,
  'required_skills': 'ECA, LMP, monitoreo hídrico, relaves, OEFA, ISO 14001',
  'technical_specifications': 'Ing. Ambiental / Químico colegiado, experiencia en monitoreo de agua, aire, '
                              'relaveras y fiscalizaciones OEFA / ANA.',
  'company_context': 'Cumplimiento ambiental estricto de la Unidad Minera Las Bravas y manejo de efluentes.',
  'published_boards': ['LinkedIn Talento Minero', 'Bumeran Perú'],
  'target_days': 28},
 {'title': 'Especialista de Relaciones Comunitarias y Gestión Social',
  'department': 'Medio Ambiente y RR.CC.',
  'urgency': 'Planificada',
  'vacancies': 1,
  'required_skills': 'relaciones comunitarias, manejo de conflictos, convenios, quechua',
  'technical_specifications': 'Sociólogo, Antropólogo o Comunicador, 4+ años en zonas altoandinas del Perú; '
                              'dominio de quechua altamente valorado.',
  'company_context': 'Sostener la licencia social, mesas de diálogo y empleo local con las comunidades del '
                     'área de influencia.',
  'published_boards': ['LinkedIn Talento Minero', 'Portal Talento Las Bravas'],
  'target_days': 30},
 {'title': 'Coordinador de Bodega, Explosivos y Campamento Minero',
  'department': 'Logística y Campamento',
  'urgency': 'Planificada',
  'vacancies': 2,
  'required_skills': 'SAP MM, inventario crítico, despacho mina, control EPP',
  'technical_specifications': 'Carrera en Administración o Ing. Industrial, manejo de SAP MM / Excel '
                              'avanzado, experiencia en almacenes remotos.',
  'company_context': 'Renovación de stock estratégico de repuestos pesados y suministros para campamento Las '
                     'Bravas.',
  'published_boards': ['Computrabajo Minería', 'Portal Talento Las Bravas'],
  'target_days': 30},
 {'title': 'Paramédico / Médico Ocupacional de Tópico Minero',
  'department': 'Seguridad HSEC',
  'urgency': 'Urgente',
  'vacancies': 2,
  'required_skills': 'emergencias altura, PHTLS, BLS, salud ocupacional, DS-024',
  'technical_specifications': 'Profesional de salud habilitado, certificación PHTLS / ACLS vigente y '
                              'experiencia en rescate minero sobre 4,000 msnm.',
  'company_context': 'Cobertura médica 24/7 en tópico de unidad minera y brigada de respuesta ante '
                     'emergencias.',
  'published_boards': ['Computrabajo Minería', 'LinkedIn Talento Minero'],
  'target_days': 18}]

CRITERIA = [{'title': 'Priorizar experiencia comprobada en altura > 4,000 msnm y cultura HSEC',
  'department': 'Operaciones Mina',
  'weight': 'Prioritario',
  'rule_text': 'Valorar trayectoria real en faena minera sobre 4,000 msnm y cumplimiento HSEC por encima de '
               'postgrados teóricos.',
  'wrong_ai_assumption': 'Inicialmente la IA redujo el puntaje de operarios técnicos experimentados frente a '
                         'perfiles administrativos sin experiencia en altura.',
  'is_correction': True,
  'learned_from_candidate': 'Roberto Silva'},
 {'title': 'Exigir estabilidad emocional >= 75 para supervisión HSEC',
  'department': 'Seguridad HSEC',
  'weight': 'Prioritario',
  'rule_text': 'En puestos de supervisión de seguridad minera, la estabilidad emocional y apego a norma HSEC '
               'en la prueba psicológica son determinantes.',
  'wrong_ai_assumption': None,
  'is_correction': False,
  'learned_from_candidate': 'Lucía Fernández'}]

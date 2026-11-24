"""Reglas de puntuación portadas de src/utils/recruitment.ts (funciones puras, sin base de datos).

El redondeo replica Math.round de JavaScript (la mitad sube), no el redondeo bancario de Python.
"""
import math
import re

from app.constants import ALL_AREAS

PSYCH_BASELINE = 64
MAX_CRITERIA_BONUS = 10

PSYCH_KEYS = (
    'estabilidadEmocional',
    'toleranciaFaenaAltura',
    'apegoSeguridadHSEC',
    'trabajoEquipo',
    'razonamientoOperativo',
)


def js_round(x: float) -> int:
    return int(math.floor(x + 0.5))


def _num(x) -> str:
    """Formatea un número como lo haría una plantilla de JavaScript (64.0 -> '64')."""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def evaluate_psychometric_battery(scores: dict) -> dict:
    """Port de evaluatePsychometricBattery (recruitment.ts:31-70)."""

    def clamp(n):
        return max(0, min(100, js_round(n)))

    est = clamp(scores['estabilidadEmocional'])
    tol = clamp(scores['toleranciaFaenaAltura'])
    sec = clamp(scores['apegoSeguridadHSEC'])
    team = clamp(scores['trabajoEquipo'])
    raz = clamp(scores['razonamientoOperativo'])

    average = js_round(sec * 0.25 + est * 0.25 + tol * 0.2 + team * 0.15 + raz * 0.15)

    level = 'Requiere Entrevista'
    if average >= 78 and sec >= 75:
        level = 'Apto Recomendado'
    elif average >= 62:
        level = 'Apto con Observación'

    dims = [
        ('Seguridad HSEC', sec),
        ('Estabilidad Emocional', est),
        ('Tolerancia Faena/Altura', tol),
        ('Trabajo en Equipo', team),
        ('Razonamiento Operativo', raz),
    ]
    strongest = max(dims, key=lambda d: d[1])
    lowest = min(dims, key=lambda d: d[1])

    if lowest[1] < 70:
        observation = (
            f'IA observó tabla psicométrica ({average}/100 · {level}): destaca en {strongest[0]} '
            f'({strongest[1]}/100); reforzar seguimiento en {lowest[0]} ({lowest[1]}/100).'
        )
    else:
        observation = (
            f'IA observó tabla psicométrica ({average}/100 · {level}): perfil equilibrado para faena minera, '
            f'liderado por {strongest[0]} ({strongest[1]}/100).'
        )
    return {'averageScore': average, 'aptitudeLevel': level, 'aiPsychObservation': observation}


def score_psych_answers(answers: dict) -> dict:
    """Port de scorePsychAnswersToMetrics (recruitment.ts:76-93): respuestas 1-5 a puntajes 0-100."""

    def to_percent(rating):
        return max(40, min(98, js_round(38 + max(1, min(5, rating)) * 12)))

    return {
        'estabilidadEmocional': to_percent(answers['estabilidad']),
        'toleranciaFaenaAltura': to_percent(answers['tolerancia']),
        'apegoSeguridadHSEC': to_percent(answers['seguridad']),
        'trabajoEquipo': to_percent(answers['equipo']),
        'razonamientoOperativo': to_percent(answers['razonamiento']),
    }


# H-05: se quitó 'uni' (coincidía con "universidad" en cualquier universidad).
EDU_KEYWORDS = ('mina', 'metal', 'geolog', 'seguridad', 'indus', 'mecán', 'mecan', 'logíst', 'logist',
                'tecsup', 'unsa', 'operac', 'quím', 'quim')

_SPLIT = re.compile(r'[\s,.;:()/]+')


def _keywords(text: str) -> list[str]:
    return [w for w in _SPLIT.split(text.lower()) if len(w) >= 4]


def compute_rule_scores(candidate: dict, position: dict, criteria: list[dict]) -> dict:
    """Port de computeCandidateScoreReport (recruitment.ts:357-451): técnico, experiencia, formación y criterios.

    candidate: specifications, workHistorySummary, interviewNotes, yearsWorked, career, university, targetRoleTitle.
    position: name, area, requiredSkills, technicalSpecifications.
    """
    specs = candidate.get('specifications') or []
    specs_haystack = (
        f"{' '.join(specs)} {candidate.get('workHistorySummary') or ''} {candidate.get('interviewNotes') or ''}"
    ).lower()
    title = position.get('name') or candidate.get('targetRoleTitle') or ''
    need_text = (
        f"{position.get('technicalSpecifications') or ''} {position.get('requiredSkills') or ''} {title}"
    ).lower()
    need_keywords = list(dict.fromkeys(_keywords(need_text)))

    spec_matches = sum(1 for kw in need_keywords if kw in specs_haystack)
    spec_ratio = spec_matches / min(8, len(need_keywords)) if need_keywords else 0.6
    technical = max(48, min(98, js_round(54 + spec_ratio * 36 + min(8, len(specs) * 2))))

    years = candidate.get('yearsWorked') or 0
    if years >= 10:
        years_base = 95
    elif years >= 7:
        years_base = 89
    elif years >= 4:
        years_base = 80
    elif years >= 2:
        years_base = 70
    else:
        years_base = 56
    mining_bonus = 4 if any(k in specs_haystack for k in ('mina', 'planta', 'faena', 'hsec')) else 0
    experience = max(45, min(98, years_base + mining_bonus))

    edu_text = f"{candidate.get('career') or ''} {candidate.get('university') or ''}".lower()
    edu_hits = sum(1 for k in EDU_KEYWORDS if k in edu_text)
    education = max(58, min(96, 68 + edu_hits * 7))

    # H-02: solo aplican los criterios del área del puesto o de todas las áreas.
    area = position.get('area')
    applicable = [c for c in criteria if c.get('appliesToDepartment') in (area, ALL_AREAS)]
    ordered = [c for c in applicable if c.get('isCorrection')] + [c for c in applicable if not c.get('isCorrection')]

    role_title = (candidate.get('targetRoleTitle') or '').lower()
    matched = []
    for crit in ordered:
        crit_keywords = _keywords(f"{crit.get('ruleText') or ''} {crit.get('title') or ''}")
        if any(kw in specs_haystack or kw in edu_text or kw in role_title for kw in crit_keywords):
            matched.append(crit)

    correction = next((c for c in matched if c.get('isCorrection')), None)
    bonus = 0
    for c in matched:
        if c.get('isCorrection'):
            bonus += 5
        else:
            bonus += {'Prioritario': 4, 'Importante': 2}.get(c.get('weightLabel'), 1)

    return {
        'technical': technical,
        'experience': experience,
        'education': education,
        'appliedCriteria': [c.get('title') or '' for c in matched],
        'appliedCorrectionTitle': correction.get('title') if correction else None,
        'appliedCorrectionRule': correction.get('ruleText') if correction else None,
        'criteriaBonus': min(MAX_CRITERIA_BONUS, bonus),
    }


def global_index(technical: int, experience: int, education: int, psych: float | None, bonus: int = 0) -> int:
    """Índice Global: 0.30·técnico + 0.25·experiencia + 0.15·formación + 0.30·psicológico + bono, acotado a 30-98."""
    psych_value = PSYCH_BASELINE if psych is None else psych
    raw = (
        technical * 0.3
        + experience * 0.25
        + education * 0.15
        + psych_value * 0.3
        + max(0, min(MAX_CRITERIA_BONUS, bonus))
    )
    return max(30, min(98, js_round(raw)))


def fit_verdict(overall: int) -> str:
    if overall >= 85:
        return 'Idoneidad Alta para el Puesto'
    if overall >= 72:
        return 'Idoneidad Sólida (Apto)'
    return 'Requiere Validación Adicional'


def _psych_of(candidate: dict, scores: dict) -> tuple[bool, float, str]:
    ev = candidate.get('psychEvaluation') or {}
    level = ev.get('aptitudeLevel') or ''
    if 'psych' in scores:
        value = scores['psych']
    elif ev.get('status') == 'Completada':
        value = ev.get('averageScore')
    else:
        value = None
    if value is None:
        return False, PSYCH_BASELINE, level
    return True, value, level


def rule_report_text(candidate: dict, position: dict, scores: dict, overall: int) -> str:
    """Texto del dictamen de reglas (recruitment.ts:475-485), sin la 'propuesta' de decisión del original.

    scores es el resultado de compute_rule_scores; opcionalmente trae 'psych' (promedio o None).
    Si no, se toma de candidate['psychEvaluation'].
    """
    has_psych, psych, level = _psych_of(candidate, scores)
    title = position.get('name') or candidate.get('targetRoleTitle') or ''
    years = candidate.get('yearsWorked')
    technical, experience, education = scores['technical'], scores['experience'], scores['education']

    if has_psych:
        psych_clause = f'Prueba psicológica completada ({_num(psych)}/100 · {level}).'
    else:
        psych_clause = 'Prueba psicológica aún pendiente (puntaje base referencial hasta envío/respuesta).'

    correction_title = scores.get('appliedCorrectionTitle')
    if correction_title:
        return (
            f'Apliqué la corrección del Jefe de RR.HH. ("{correction_title}"): {scores.get("appliedCorrectionRule") or ""}. '
            f'Consolidado de métricas para {title}: Técnico {technical}/100, Experiencia {experience}/100 '
            f'({years} años), Formación {education}/100, Psicológico {_num(psych)}/100. {psych_clause}'
        )
    return (
        f'Evaluación integral IA ({overall}/100 · {fit_verdict(overall)}) para {title}: '
        f'Especificaciones técnicas {technical}/100, Trayectoria {experience}/100 ({years} años), '
        f'Formación ({candidate.get("career") or ""} - {candidate.get("university") or ""}) {education}/100. '
        f'{psych_clause}'
    )


def compute_kpis(requirements: list[dict], sources: list[dict], candidates: list[dict]) -> dict:
    """Port de computeRecruitmentKPIs (recruitment.ts:508-563) con la nueva definición de acuerdo IA/RR.HH."""
    total_vacancies = sum(r.get('vacancies') or 0 for r in requirements)
    filled = sum(min(r.get('vacancies') or 0, r.get('filledCount') or 0) for r in requirements)
    remaining = max(0, total_vacancies - filled)
    coverage = js_round(filled / total_vacancies * 100) if total_vacancies > 0 else 0

    total_candidates = len(candidates)
    preselected = sum(1 for c in candidates if c.get('decision') in ('Aprobado', 'Contratado'))
    psych_completed = sum(
        1 for c in candidates if (c.get('psychEvaluation') or {}).get('status') == 'Completada'
    )
    avg_days = (
        js_round(sum(c.get('processDaysElapsed') or 0 for c in candidates) / total_candidates)
        if total_candidates > 0 else 0
    )

    proposals = sum(s.get('proposalsSent') or 0 for s in sources)
    top = max(sources, key=lambda s: s.get('candidatesReceived') or 0) if sources else None

    reviewed = [
        c for c in candidates
        if c.get('aiVerdict') is not None and c.get('decision') != 'Pendiente de revisión'
    ]
    agreed = sum(
        1 for c in reviewed
        if (c['aiVerdict'] == 'Pre-aprobado' and c.get('decision') in ('Aprobado', 'Contratado'))
        or (c['aiVerdict'] == 'Pre-denegado' and c.get('decision') == 'Rechazado')
    )
    agreement = js_round(agreed / len(reviewed) * 100) if reviewed else 100

    return {
        'totalVacancies': total_vacancies,
        'filledVacancies': filled,
        'remainingVacancies': remaining,
        'coveragePercent': coverage,
        'totalCandidates': total_candidates,
        'preselectedOrHired': preselected,
        'psychCompletedCount': psych_completed,
        'psychPendingCount': total_candidates - psych_completed,
        'avgProcessDays': avg_days,
        'totalProposalsSent': proposals,
        'topBoardName': top.get('name') if top else 'Sin datos',
        'topBoardCandidates': (top.get('candidatesReceived') or 0) if top else 0,
        'aiAgreementRate': agreement,
    }

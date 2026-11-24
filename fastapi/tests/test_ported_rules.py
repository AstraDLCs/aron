"""Pruebas de las reglas portadas de src/utils/recruitment.ts y cvParser.ts (originales en recruitment.test.ts)."""
import copy

from fpdf import FPDF

from app.constants import ALL_AREAS
from app.services import cv_parser, excel_tests, scoring, slugs, text_extract
from tests.fixtures import legacy

CORRECTION_TITLE = 'Priorizar experiencia en altura y planta concentradora'


def _planta_position():
    return next(p for p in legacy.POSITIONS if p['name'] == 'Operador de Planta Concentradora Senior')


def _correction(area):
    return {
        'id': 'crit-corr-1',
        'title': CORRECTION_TITLE,
        'appliesToDepartment': area,
        'weightLabel': 'Prioritario',
        'ruleText': 'Valorar operarios con certificacion HSEC y experiencia real en altura sobre 4000 msnm.',
        'isCorrection': True,
        'wrongAiAssumption': 'La IA dio bajo puntaje por falta de maestria.',
        'createdBy': 'Elena Vargas',
        'createdAt': '2026-11-19',
    }


def test_psychometric_battery():
    res = scoring.evaluate_psychometric_battery({
        'estabilidadEmocional': 88,
        'toleranciaFaenaAltura': 84,
        'apegoSeguridadHSEC': 92,
        'trabajoEquipo': 85,
        'razonamientoOperativo': 80,
    })
    assert res['aptitudeLevel'] == 'Apto Recomendado'
    assert res['averageScore'] >= 85
    assert 'Seguridad HSEC' in res['aiPsychObservation']


def test_psych_answers():
    high = scoring.score_psych_answers({
        'estabilidad': 5, 'tolerancia': 5, 'seguridad': 5, 'equipo': 4, 'razonamiento': 4,
    })
    assert high['apegoSeguridadHSEC'] == 98
    assert high['trabajoEquipo'] == 86


def test_rule_scores_apply_correction_of_same_area():
    candidate = legacy.ROBERTO
    position = _planta_position()
    assert position['area'] == 'Control Metalúrgico'
    criteria = [_correction('Control Metalúrgico')]

    scores = scoring.compute_rule_scores(candidate, position, criteria)
    overall = scoring.global_index(
        scores['technical'], scores['experience'], scores['education'], None, scores['criteriaBonus'],
    )
    assert overall >= 75
    assert scores['appliedCorrectionTitle'] == CORRECTION_TITLE
    assert scores['appliedCriteria'] == [CORRECTION_TITLE]

    report = scoring.rule_report_text(candidate, position, scores, overall)
    assert 'Apliqué la corrección del Jefe de RR.HH.' in report


def test_rule_scores_ignore_other_area_criteria():
    candidate = legacy.ROBERTO
    position = _planta_position()

    other = scoring.compute_rule_scores(candidate, position, [_correction('Operaciones Mina')])
    assert other['appliedCriteria'] == []
    assert other['appliedCorrectionTitle'] is None
    assert other['criteriaBonus'] == 0

    everywhere = scoring.compute_rule_scores(candidate, position, [_correction(ALL_AREAS)])
    assert everywhere['appliedCriteria'] == [CORRECTION_TITLE]


def test_education_without_uni_keyword():
    candidate = copy.deepcopy(legacy.ROBERTO)
    candidate['career'] = 'Administración'
    candidate['university'] = 'Universidad Privada del Sur'
    scores = scoring.compute_rule_scores(candidate, _planta_position(), [])
    assert scores['education'] == 68


def test_global_index_and_verdict():
    assert scoring.global_index(90, 90, 90, 90) == 90
    assert scoring.global_index(10, 10, 10, 10) == 30
    assert scoring.global_index(100, 100, 100, 100, 50) == 98
    # sin evaluación psicológica se usa la base 64: 0.3*80 + 0.25*80 + 0.15*80 + 0.3*64
    assert scoring.global_index(80, 80, 80, None) == 75
    assert scoring.fit_verdict(85) == 'Idoneidad Alta para el Puesto'
    assert scoring.fit_verdict(72) == 'Idoneidad Sólida (Apto)'
    assert scoring.fit_verdict(71) == 'Requiere Validación Adicional'


def test_kpis_top_board_and_agreement():
    kpis = scoring.compute_kpis(legacy.REQUIREMENTS, legacy.BOARDS, [])
    assert kpis['totalVacancies'] >= 5
    assert 0 <= kpis['coveragePercent'] <= 100
    assert kpis['topBoardName'] == 'Computrabajo Minería'
    assert kpis['topBoardCandidates'] == 42
    assert kpis['totalProposalsSent'] == 34
    assert kpis['aiAgreementRate'] == 100  # sin casos revisados

    pairs = [
        ('Pre-aprobado', 'Aprobado'),
        ('Pre-aprobado', 'Rechazado'),
        (None, 'Rechazado'),
        ('Pre-denegado', 'Pendiente de revisión'),
    ]
    candidates = [{'aiVerdict': v, 'decision': d, 'psychEvaluation': {'status': 'Pendiente'}, 'processDaysElapsed': 2}
                  for v, d in pairs]
    kpis = scoring.compute_kpis(legacy.REQUIREMENTS, legacy.BOARDS, candidates)
    assert kpis['aiAgreementRate'] == 50
    assert kpis['totalCandidates'] == 4
    assert kpis['preselectedOrHired'] == 1


def test_kpis_agreement_pre_denegado_rechazado():
    candidates = [{'aiVerdict': 'Pre-denegado', 'decision': 'Rechazado'}]
    assert scoring.compute_kpis([], [], candidates)['aiAgreementRate'] == 100
    candidates = [{'aiVerdict': 'Pre-denegado', 'decision': 'Contratado'}]
    assert scoring.compute_kpis([], [], candidates)['aiAgreementRate'] == 0


def test_excel_rows_concrete_vs_partial():
    concrete = excel_tests.evaluate_excel_test_rows([
        {'Pregunta': 'Estabilidad emocional en turno 14x7', 'Respuesta': 5, 'Escala Máxima': 5},
        {'Pregunta': 'Tolerancia a altura > 4200 msnm', 'Respuesta': 4, 'Escala Máxima': 5},
        {'Pregunta': 'Cumplimiento normas seguridad HSEC', 'Respuesta': 5, 'Escala Máxima': 5},
        {'Pregunta': 'Trabajo en equipo en guardia', 'Respuesta': 4, 'Escala Máxima': 5},
    ])
    assert concrete['isConcreteResult'] is True
    assert concrete['concreteVerdict'] == 'Resultados Concretos'
    assert concrete['answeredCount'] == 4
    assert concrete['totalQuestions'] == 4
    assert concrete['autoComputedScore'] >= 85
    assert concrete['passed'] is None
    assert set(concrete['derivedScores']) == {
        'estabilidadEmocional', 'toleranciaFaenaAltura', 'apegoSeguridadHSEC',
        'trabajoEquipo', 'razonamientoOperativo',
    }
    assert isinstance(concrete['aiAnalysis'], str) and concrete['aiAnalysis']
    assert len(concrete['parsedRows']) == 4

    rows = [
        {'Pregunta': 'Estabilidad emocional en turno 14x7', 'Respuesta': 5, 'Escala Máxima': 5},
        {'Pregunta': 'Tolerancia a altura > 4200 msnm', 'Respuesta': 4, 'Escala Máxima': 5},
        {'Pregunta': 'Cumplimiento normas seguridad HSEC', 'Respuesta': 5, 'Escala Máxima': 5},
        {'Pregunta': 'Trabajo en equipo en guardia', 'Respuesta': 4, 'Escala Máxima': 5},
    ]
    assert excel_tests.evaluate_excel_test_rows(rows, passing_score=90)['passed'] is True
    assert excel_tests.evaluate_excel_test_rows(rows, passing_score=95)['passed'] is False

    partial = excel_tests.evaluate_excel_test_rows([
        {'Pregunta': 'Estabilidad emocional', 'Respuesta': 4},
        {'Pregunta': 'Seguridad HSEC', 'Respuesta': ''},
        {'Pregunta': 'Razonamiento operativo', 'Respuesta': '-'},
    ])
    assert partial['isConcreteResult'] is False
    assert partial['concreteVerdict'] == 'Resultados Parciales'
    assert partial['answeredCount'] == 1


def test_excel_rows_js_rounding_and_empty():
    # 0.5 sube (Math.round); round() de Python iría al par: 40 + 0.5 * 58 = 69
    res = excel_tests.evaluate_excel_test_rows([
        {'Pregunta': 'Item uno', 'Respuesta': 1, 'Escala Máxima': 2},
        {'Pregunta': 'Item dos', 'Respuesta': 1, 'Escala Máxima': 2},
        {'Pregunta': 'Item tres', 'Respuesta': 1, 'Escala Máxima': 2},
    ])
    assert [r['score'] for r in res['parsedRows']] == [69, 69, 69]

    empty = excel_tests.evaluate_excel_test_rows([])
    assert empty['concreteVerdict'] == 'Inconsistencia Detectada'
    assert empty['autoComputedScore'] == 0
    assert empty['passed'] is None
    assert excel_tests.evaluate_excel_test_rows([], passing_score=70)['passed'] is False


def test_excel_metadata_detection():
    meta = excel_tests.extract_excel_test_metadata(
        [
            {'Prueba Evaluada': 'Examen Seguridad HSEC Tajo', 'Pregunta': 'Norma DS-024-2016-EM', 'Respuesta': 5},
            {'Prueba Evaluada': 'Examen Seguridad HSEC Tajo', 'Pregunta': 'Uso de IPERC Continuo', 'Respuesta': 4},
        ],
        'examen_hsec.xlsx',
    )
    assert meta['detectedTestName'] == 'Examen Seguridad HSEC Tajo'
    assert meta['detectedCategory'] == 'Seguridad HSEC'
    assert meta['detectedTargetArea'] == 'Seguridad HSEC'
    assert len(meta['questions']) == 2


def test_excel_metadata_falls_back_to_file_name():
    meta = excel_tests.extract_excel_test_metadata(
        [{'Pregunta': 'Manejo de scooptram en rampa', 'Respuesta': 4}],
        'Plantilla_Prueba_Automatica_Operador_Scoop.xlsx',
        'Sheet1',
    )
    assert meta['detectedTestName'] == 'Operador Scoop'
    assert meta['detectedCategory'] == 'Operación / Maquinaria'


SAMPLE_CV = """CURRICULUM VITAE
Juan Carlos Mendoza Quispe
Edad: 34 años
Ciudad: Arequipa, Perú
Correo: jcmendoza@mineria.pe | Celular: +51 984 321 110
Formación: Ingeniero de Minas - Universidad Nacional de San Agustín (UNSA)
EXPERIENCIA LABORAL
8 años de experiencia en minería subterránea y tajo abierto como Jefe de Guardia Mina.
Certificaciones: DS-024-2016-EM, HSEC, IPERC Continuo, Licencia A-IIIc, trabajo en altura 4500 msnm, régimen 14x7."""


def test_parse_cv_peruvian_fields():
    parsed = cv_parser.parse_cv_text(SAMPLE_CV, legacy.POSITIONS)
    assert parsed.full_name == 'Juan Carlos Mendoza Quispe'
    assert parsed.first_names == 'Juan Carlos'
    assert parsed.last_names == 'Mendoza Quispe'
    assert parsed.age == 34
    assert parsed.origin_location == 'Arequipa, Perú'
    assert 'UNSA' in parsed.university
    assert 'Minas' in parsed.career
    assert parsed.years_worked == 8
    assert parsed.email == 'jcmendoza@mineria.pe'
    assert '984 321 110' in parsed.phone
    assert any('HSEC' in s for s in parsed.specifications)
    assert any('A-IIIC' in s for s in parsed.specifications)
    assert parsed.suggested_position_id in {p['id'] for p in legacy.POSITIONS}
    assert parsed.document_id == ''

    rtf = text_extract.strip_rtf_to_text(
        "{\\rtf1\\ansi{\\fonttbl{\\f0 Arial;}}Ingenier\\'eda de Minas\\par Arequipa, Per\\'fa}"
    )
    assert 'Ingeniería de Minas' in rtf
    assert 'Perú' in rtf

    html = text_extract.strip_html_to_text('<html><body><h1>Maria Torres</h1><p>HSEC &amp; IPERC</p></body></html>')
    assert 'Maria Torres' in html
    assert 'HSEC & IPERC' in html


def test_parse_cv_document_id_and_names():
    parsed = cv_parser.parse_cv_text(
        'Nombre completo: Ana María Torres\nDNI: 45678912\nTeléfono: 912 345 678\n', legacy.POSITIONS,
    )
    assert parsed.full_name == 'Ana María Torres'
    assert parsed.first_names == 'Ana María'
    assert parsed.last_names == 'Torres'
    assert parsed.document_id == '45678912'
    assert parsed.phone == '912 345 678'
    assert parsed.email == ''

    ce = cv_parser.parse_cv_text('Nombre: Pedro Pérez\nCarné de extranjería Nº 001234567\n', legacy.POSITIONS)
    assert ce.document_id == '001234567'


def test_normalize_key_vectors():
    assert slugs.normalize_key('Perforista y Cargador de Explosivos (Carnet SUCAMEC)') == (
        'perforista-y-cargador-de-explosivos-carnet-sucamec'
    )
    assert slugs.normalize_key('  Operación   Mina ') == 'operacion-mina'
    assert slugs.normalize_key('LinkedIn') == 'linkedin'
    assert slugs.normalize_key('Referidos de Faena') == 'referidos-de-faena'
    assert len(slugs.folder_name_for('a' * 200)) == 80
    assert not slugs.folder_name_for('Ñandú ' * 30).endswith('-')


def test_extract_text_bad_inputs():
    text, status = text_extract.extract_text(b'%PDF-1.4 basura', 'cv.pdf')
    assert status == 'error'

    pdf = FPDF()
    pdf.add_page()
    blank = bytes(pdf.output())
    text, status = text_extract.extract_text(blank, 'escaneado.pdf')
    assert status == 'empty'

    body = 'Currículum de José Ñuñez, ingeniero de minas con ocho años de experiencia en tajo abierto.'
    text, status = text_extract.extract_text(body.encode('latin-1'), 'cv.txt')
    assert status == 'ok'
    assert 'José Ñuñez' in text

    text, status = text_extract.extract_text(body.encode('utf-8'), 'cv.txt')
    assert status == 'ok' and 'José Ñuñez' in text

    assert text_extract.extract_text(b'corto', 'cv.txt')[1] == 'empty'
    assert text_extract.extract_text(b'PK\x03\x04 no es un docx', 'cv.docx')[1] == 'error'
    assert text_extract.extract_text(b'datos', 'cv.exe')[1] == 'error'


def test_extract_text_pdf_docx_rtf_ok():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', size=12)
    pdf.cell(text='Roberto Silva Huaman, operador de planta concentradora con once anos de experiencia.')
    text, status = text_extract.extract_text(bytes(pdf.output()), 'cv.pdf')
    assert status == 'ok' and 'Roberto Silva' in text

    import io

    from docx import Document

    doc = Document()
    doc.add_paragraph('Lucia Fernandez Quispe, ingeniera de seguridad industrial.')
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = 'Certificacion'
    table.rows[0].cells[1].text = 'HSEC vigente y DS-024-2016-EM'
    buf = io.BytesIO()
    doc.save(buf)
    text, status = text_extract.extract_text(buf.getvalue(), 'cv.docx')
    assert status == 'ok'
    assert 'Lucia Fernandez' in text and 'HSEC vigente' in text

    rtf = "{\\rtf1\\ansi{\\fonttbl{\\f0 Arial;}}Ingenier\\'eda de Minas, Arequipa, Per\\'fa, ocho a\\'f1os de experiencia\\par}"
    text, status = text_extract.extract_text(rtf.encode('ascii'), 'cv.rtf')
    assert status == 'ok' and 'Ingeniería de Minas' in text

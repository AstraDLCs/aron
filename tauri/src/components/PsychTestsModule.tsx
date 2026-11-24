import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ClipboardList,
  Database,
  FileDown,
  FileSpreadsheet,
  Loader2,
  Plus,
  Send,
  Trash2,
  Upload,
  UserPlus,
  X,
} from 'lucide-react';
import type { AppState, ExcelTestResult, ModuleProps, TestDefinition } from '../types';
import { PsychRadarChart } from './ExecutiveCharts';
import { apiFetch, errorMessage, fileFromPath, pickFiles } from '../api/client';
import { DownloadButton } from './common/DownloadButton';
import { toast } from './common/Toast';
import { UploadCvDialog } from './cv/UploadCvDialog';

const PERU_MINING_DEPARTMENTS = [
  'Operaciones Mina',
  'Perforación y Voladura',
  'Control Metalúrgico',
  'Seguridad HSEC',
  'Geología y Planeamiento',
  'Mantenimiento Mina',
  'Medio Ambiente y RR.CC.',
  'Logística y Campamento',
];

type StateRes = { state?: AppState };

export const PsychTestsModule: React.FC<ModuleProps & { initialCandidateId?: string | null }> = ({
  state,
  onState,
  refresh,
  initialCandidateId,
}) => {
  const hrChiefName = state.hrChiefName;
  const candidates = state.candidates;
  const testCatalog = state.testCatalog ?? [];

  const applyState = (r?: StateRes) => {
    if (r?.state) onState(r.state);
    else void refresh();
  };

  const onSendPsychTest = async (payload: { candidateId: string; testBatteryName: string }) => {
    applyState(await apiFetch<StateRes>('/api/recruitment/psych-tests/send', { method: 'POST', json: payload }));
  };
  const onSubmitPsychTest = async (
    candidateId: string,
    answers: { estabilidad: number; tolerancia: number; seguridad: number; equipo: number; razonamiento: number },
  ) => {
    applyState(
      await apiFetch<StateRes>(`/api/recruitment/psych-tests/${encodeURIComponent(candidateId)}/submit`, {
        method: 'POST',
        json: { answers },
      }),
    );
  };
  const onAddTest = async (payload: {
    name: string;
    category: TestDefinition['category'];
    targetArea: string;
    durationMinutes: number;
    passingScore: number;
    questions: string[];
  }): Promise<TestDefinition> => {
    const r = await apiFetch<StateRes & { test?: TestDefinition }>('/api/recruitment/tests', { method: 'POST', json: payload });
    applyState(r);
    const created =
      r?.test ?? r?.state?.testCatalog?.find((t) => t.name === payload.name) ?? ({ id: '', name: payload.name } as TestDefinition);
    return created;
  };
  const onDeleteTest = async (testId: string) => {
    const t = testCatalog.find((x) => x.id === testId);
    if (!window.confirm(`¿Eliminar la prueba "${t?.name ?? ''}"? Los resultados ya cargados se conservan.`)) return;
    try {
      applyState(await apiFetch<StateRes>(`/api/recruitment/tests/${encodeURIComponent(testId)}`, { method: 'DELETE' }));
      toast('Prueba eliminada.', 'ok');
    } catch (err) {
      toast(errorMessage(err), 'error');
    }
  };
  const [showUpload, setShowUpload] = useState(false);

  const [selectedCandId, setSelectedCandId] = useState<string>(
    initialCandidateId || candidates[0]?.id || ''
  );

  useEffect(() => {
    if (initialCandidateId) {
      setSelectedCandId(initialCandidateId);
    }
  }, [initialCandidateId]);

  const activeCand =
    candidates.find((c) => c.id === selectedCandId) ?? candidates[0] ?? null;

  const [selectedTestId, setSelectedTestId] = useState<string>(
    testCatalog[0]?.id || ''
  );

  useEffect(() => {
    if (testCatalog.length === 0) {
      setSelectedTestId('');
    } else if (!testCatalog.some((t) => t.id === selectedTestId)) {
      setSelectedTestId(testCatalog[0].id);
    }
  }, [testCatalog, selectedTestId]);

  const selectedTest =
    testCatalog.find((t) => t.id === selectedTestId) ?? null;

  const [sendFeedback, setSendFeedback] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  // Import Excel into Test Database state
  const [customExcelTestName, setCustomExcelTestName] = useState('');
  const [isImportingTest, setIsImportingTest] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importNotice, setImportNotice] = useState<string | null>(null);

  // Automated Test Runner (for applicant completion or HR simulation)
  const [showRunner, setShowRunner] = useState(false);
  const [ansEstabilidad, setAnsEstabilidad] = useState(5);
  const [ansTolerancia, setAnsTolerancia] = useState(4);
  const [ansSeguridad, setAnsSeguridad] = useState(5);
  const [ansEquipo, setAnsEquipo] = useState(4);
  const [ansRazonamiento, setAnsRazonamiento] = useState(4);
  const [isSubmittingTest, setIsSubmittingTest] = useState(false);
  const [testDoneNotice, setTestDoneNotice] = useState<string | null>(null);

  // Excel Auto-Test Solved Upload state
  const [isUploadingExcel, setIsUploadingExcel] = useState(false);
  const [excelError, setExcelError] = useState<string | null>(null);
  const [excelNotice, setExcelNotice] = useState<string | null>(null);
  const [excelWarning, setExcelWarning] = useState<string | null>(null);

  // Add New Test manual form state
  const [showAddTestForm, setShowAddTestForm] = useState(false);
  const [newTestName, setNewTestName] = useState('');
  const [newTestCategory, setNewTestCategory] =
    useState<TestDefinition['category']>('Técnica Minera');
  const [newTestArea, setNewTestArea] = useState(PERU_MINING_DEPARTMENTS[0]);
  const [newTestDuration, setNewTestDuration] = useState('25');
  const [newTestPassingScore, setNewTestPassingScore] = useState('78');
  const [newTestQuestionsText, setNewTestQuestionsText] = useState(
    'Estabilidad operativa bajo presión en faena\nCumplimiento estricto de normas HSEC y PETAR\nDominio técnico del puesto minero\nCoordinación efectiva en guardia 14x7'
  );
  const [isCreatingTest, setIsCreatingTest] = useState(false);
  const [testFormError, setTestFormError] = useState<string | null>(null);

  const handleImportExcelToDatabase = async () => {
    setImportError(null);
    setImportNotice(null);
    let paths: string[] = [];
    try {
      paths = await pickFiles({ name: 'Excel', extensions: ['xlsx', 'xls', 'csv', 'ods'] });
    } catch (err) {
      setImportError(errorMessage(err));
      return;
    }
    if (!paths.length) return;
    setIsImportingTest(true);
    try {
      const file = await fileFromPath(paths[0]);
      const form = new FormData();
      form.append('file', file, file.name);
      if (customExcelTestName.trim()) form.append('customTestName', customExcelTestName.trim());
      const res = await apiFetch<
        StateRes & { test: TestDefinition; isNewTest?: boolean; excelResult?: ExcelTestResult; aiWarning?: string }
      >('/api/recruitment/tests/import-excel', { method: 'POST', form });
      applyState(res);
      if (res.test?.id) setSelectedTestId(res.test.id);
      setCustomExcelTestName('');
      setImportNotice(
        `${res.isNewTest === false ? 'Prueba actualizada' : 'Prueba registrada en la base de pruebas'}: "${res.test?.name}" (${res.test?.questions?.length ?? 0} ítems desde ${file.name}). Ya puedes descargarla para entregarla a la persona evaluada.`
      );
      if (res.aiWarning) setImportError(res.aiWarning);
    } catch (err) {
      setImportError(errorMessage(err));
    } finally {
      setIsImportingTest(false);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCand || !selectedTest) return;
    setIsSending(true);
    setSendFeedback(null);
    try {
      await onSendPsychTest({
        candidateId: activeCand.id,
        testBatteryName: selectedTest.name,
      });
      setSendFeedback(
        `Prueba "${selectedTest.name}" marcada como enviada a ${activeCand.fullName} por ${hrChiefName}.`
      );
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setIsSending(false);
    }
  };

  const handleCompleteAutomatedTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCand) return;
    setIsSubmittingTest(true);
    setTestDoneNotice(null);
    try {
      await onSubmitPsychTest(activeCand.id, {
        estabilidad: ansEstabilidad,
        tolerancia: ansTolerancia,
        seguridad: ansSeguridad,
        equipo: ansEquipo,
        razonamiento: ansRazonamiento,
      });
      setShowRunner(false);
      setTestDoneNotice(
        `Resultados guardados para ${activeCand.fullName}. Valen para todas sus postulaciones.`
      );
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setIsSubmittingTest(false);
    }
  };

  const handleExcelFileUpload = async () => {
    if (!activeCand) return;
    setExcelError(null);
    setExcelNotice(null);
    setExcelWarning(null);
    let paths: string[] = [];
    try {
      paths = await pickFiles({ name: 'Excel', extensions: ['xlsx', 'xls', 'csv', 'ods'] });
    } catch (err) {
      setExcelError(errorMessage(err));
      return;
    }
    if (!paths.length) return;
    setIsUploadingExcel(true);
    try {
      const file = await fileFromPath(paths[0]);
      const form = new FormData();
      form.append('file', file, file.name);
      form.append('candidateId', activeCand.id);
      if (selectedTest?.id) form.append('testId', selectedTest.id);
      form.append('testName', selectedTest?.name || '');
      const res = await apiFetch<
        StateRes & {
          excelResult?: ExcelTestResult;
          registeredOnly?: boolean;
          test?: TestDefinition;
          message?: string;
          aiWarning?: string;
        }
      >('/api/recruitment/tests/upload-excel', { method: 'POST', form });
      applyState(res);
      if (res.test?.id) setSelectedTestId(res.test.id);
      if (res.registeredOnly) {
        setImportNotice(
          res.message ||
            `Prueba "${res.test?.name}" agregada a la base de pruebas. Súbela con respuestas resueltas para obtener el resultado.`
        );
      } else if (res.excelResult) {
        const r = res.excelResult;
        const pass =
          r.passed === true || r.passed === false
            ? ` · ${r.passed ? 'APROBADA' : 'NO APROBADA'} (mínimo ${r.passingScore ?? '—'})`
            : '';
        setExcelNotice(
          `Excel "${r.fileName}" (${r.testName}) resuelto para ${activeCand.fullName}: ${r.concreteVerdict} (${r.autoComputedScore}/100 · ${r.answeredCount}/${r.totalQuestions} ítems)${pass}.`
        );
      }
      if (res.aiWarning) setExcelWarning(res.aiWarning);
    } catch (err) {
      setExcelError(errorMessage(err));
    } finally {
      setIsUploadingExcel(false);
    }
  };

  const handleCreateTest = async (e: React.FormEvent) => {
    e.preventDefault();
    setTestFormError(null);
    setImportNotice(null);
    if (!newTestName.trim()) {
      setTestFormError('Ingresa el nombre de la nueva prueba.');
      return;
    }
    const questions = newTestQuestionsText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    setIsCreatingTest(true);
    try {
      const created = await onAddTest({
        name: newTestName.trim(),
        category: newTestCategory,
        targetArea: newTestArea,
        durationMinutes: Number(newTestDuration) || 25,
        passingScore: Number(newTestPassingScore) || 75,
        questions,
      });
      setSelectedTestId(created.id);
      setNewTestName('');
      setShowAddTestForm(false);
      setImportNotice(
        `Prueba "${created.name}" agregada a la base de datos. Ya puedes descargar su Excel para entregarlo.`
      );
    } catch (err) {
      setTestFormError(errorMessage(err));
    } finally {
      setIsCreatingTest(false);
    }
  };

  const excelHistory = activeCand?.excelTestResults ?? [];
  const latestExcel = excelHistory[0] ?? null;

  return (
    <div className="space-y-6">
      {/* Header Bar + Excel Test Database */}
      <section className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#23272E]">
              Pruebas y Resultados
            </h1>
            <p className="mt-0.5 text-sm text-[#5C626D]">
              La base de datos de pruebas inicia en blanco y se llena con los archivos Excel que subas para entregar y evaluar los resultados con IA.
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => {
                setShowAddTestForm((v) => !v);
                              }}
              className="inline-flex min-h-[42px] items-center gap-1.5 whitespace-nowrap shrink-0 rounded-lg border border-[#D8DCE0] bg-[#F7F7F8] px-3.5 py-2 text-xs sm:text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1] cursor-pointer"
            >
              <Plus className="h-4 w-4 text-[#B26337] shrink-0" />
              <span>{showAddTestForm ? 'Cerrar Manual' : 'Crear Prueba Manual'}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setShowUpload(true);
              }}
              className="inline-flex min-h-[42px] items-center gap-1.5 whitespace-nowrap shrink-0 rounded-lg bg-[#B26337] px-3.5 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#99522B] cursor-pointer"
            >
              <UserPlus className="h-4 w-4 shrink-0" />
              <span>
                Subir CV
              </span>
            </button>
          </div>
        </div>

        {/* Base de Datos de Pruebas (Starts Blank, Populated from Uploaded Excel Files) */}
        <div className="mt-5 rounded-xl border border-[#E2E4E8] bg-[#F7F7F8] p-4 sm:p-5">
          <div className="flex flex-col gap-3 border-b border-[#E2E4E8] pb-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-2.5">
              <Database className="mt-0.5 h-5 w-5 shrink-0 text-[#B26337]" />
              <div>
                <h2 className="text-sm font-bold text-[#23272E]">
                  Base de Datos de Pruebas ({testCatalog.length}{' '}
                  {testCatalog.length === 1 ? 'prueba registrada' : 'pruebas registradas'})
                </h2>
                <p className="mt-0.5 text-xs text-[#5C626D]">
                  Sube tu prueba en Excel (.xlsx, .xls o .csv) para registrarla por su nombre, descargarla lista para entregar o evaluarla cuando esté resuelta.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <DownloadButton path="/api/tests/excel-template" fileName="Formato_Prueba.xlsx" label="Formato Base Excel (.xlsx)" className="min-h-[38px] !px-3 !py-1.5 text-xs" icon={<FileDown className="h-3.5 w-3.5 text-[#5C626D]" />} />
            </div>
          </div>

          {/* Upload Excel Test to Database Bar */}
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label
                htmlFor="excel-custom-name"
                className="block text-xs font-semibold text-[#23272E]"
              >
                Nombre de la prueba (opcional — si lo dejas vacío se lee directo del Excel)
              </label>
              <input
                id="excel-custom-name"
                type="text"
                value={customExcelTestName}
                onChange={(e) => setCustomExcelTestName(e.target.value)}
                placeholder="Ej: Evaluación Técnica Perforación / Seguridad HSEC"
                className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm text-[#23272E]"
              />
            </div>

            <button
              type="button"
              onClick={() => void handleImportExcelToDatabase()}
              disabled={isImportingTest}
              className="inline-flex min-h-[42px] items-center justify-center gap-2 whitespace-nowrap shrink-0 rounded-lg bg-[#23272E] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#3A404B] transition-colors disabled:opacity-60"
            >
              {isImportingTest ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                  <span>Registrando Excel...</span>
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 shrink-0" />
                  <span>Subir Prueba en Excel (.xlsx / .xls / .csv)</span>
                </>
              )}
            </button>
          </div>

          {importError && (
            <p className="mt-3 rounded-lg border border-[#EACACA] bg-[#FDF2F2] px-3 py-2 text-xs font-semibold text-[#A84444]">
              {importError}
            </p>
          )}
          {importNotice && (
            <p
              role="status"
              className="mt-3 rounded-lg border border-[#D2E3D8] bg-[#F2F7F4] px-3.5 py-2 text-xs sm:text-sm font-medium text-[#3D7A5A]"
            >
              {importNotice}
            </p>
          )}

          {/* List of Excel Tests Currently in Database */}
          {testCatalog.length === 0 ? (
            <div className="mt-4 rounded-lg border border-dashed border-[#D4D7DD] bg-white px-4 py-5 text-center">
              <p className="text-sm font-semibold text-[#23272E]">
                Base de datos de pruebas en blanco
              </p>
              <p className="mt-1 text-xs text-[#5C626D]">
                Aún no hay pruebas cargadas. Sube un archivo Excel arriba (o un Excel resuelto abajo) y la base de datos se llenará automáticamente con el nombre de cada prueba.
              </p>
            </div>
          ) : (
            <div className="mt-4 divide-y divide-[#E2E4E8] rounded-lg border border-[#E2E4E8] bg-white">
              {testCatalog.map((t) => {
                const isActive = selectedTest?.id === t.id;
                return (
                  <div
                    key={t.id}
                    className={`flex flex-col gap-3 p-3.5 sm:flex-row sm:items-center sm:justify-between ${
                      isActive ? 'bg-[#FBF4EE]/60' : ''
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-[#5C626D]">
                        <span className="font-semibold text-[#8C4722]">
                          {t.category}
                        </span>
                        <span>·</span>
                        <span>{t.targetArea}</span>
                        <span>·</span>
                        <span className="font-mono-tabular">
                          {t.questions.length} ítems
                        </span>
                        {t.sourceFileName && (
                          <>
                            <span>·</span>
                            <span className="truncate">Archivo: {t.sourceFileName}</span>
                          </>
                        )}
                      </div>
                      <p className="mt-0.5 text-sm font-bold text-[#23272E]">
                        {t.name}
                      </p>
                    </div>

                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      <DownloadButton path={`/api/tests/excel-template?testId=${encodeURIComponent(t.id)}&candidateId=${encodeURIComponent(activeCand?.id || '')}`} fileName={`${t.name}.xlsx`} label="Entregar Excel (.xlsx)" className="min-h-[34px] !px-3 !py-1 text-xs !border-[#E6CDBE] !bg-[#FBF4EE] !text-[#8C4722]" icon={<FileDown className="h-3.5 w-3.5" />} />

                      <button
                        type="button"
                        onClick={() => setSelectedTestId(t.id)}
                        className={`min-h-[34px] rounded-lg border px-3 py-1 text-xs font-semibold cursor-pointer ${
                          isActive
                            ? 'border-[#B26337] bg-[#B26337] text-white'
                            : 'border-[#D8DCE0] bg-[#F7F7F8] text-[#23272E] hover:bg-[#EFEFF1]'
                        }`}
                      >
                        {isActive ? 'Seleccionada' : 'Seleccionar'}
                      </button>

                      <button
                        type="button"
                        onClick={() => void onDeleteTest(t.id)}
                        aria-label={`Eliminar prueba ${t.name}`}
                        className="inline-flex min-h-[34px] items-center justify-center rounded-lg border border-[#E2E4E8] bg-white px-2.5 text-[#5C626D] hover:text-[#A84444] cursor-pointer"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Inline Form: Crear Prueba Manual (opcional) */}
        {showAddTestForm && (
          <form
            onSubmit={handleCreateTest}
            className="mt-5 space-y-4 rounded-xl border border-[#E2E4E8] bg-[#F7F7F8] p-4 sm:p-5"
          >
            <div className="flex items-center justify-between border-b border-[#E2E4E8] pb-3">
              <h2 className="text-sm font-bold text-[#23272E]">
                Crear Prueba Manualmente
              </h2>
              <button
                type="button"
                onClick={() => setShowAddTestForm(false)}
                className="text-[#5C626D] hover:text-[#23272E] cursor-pointer"
                aria-label="Cerrar formulario de nueva prueba"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
              <div className="sm:col-span-2">
                <label htmlFor="new-test-name" className="block text-xs font-semibold text-[#23272E]">
                  Nombre de la prueba
                </label>
                <input
                  id="new-test-name"
                  type="text"
                  value={newTestName}
                  onChange={(e) => setNewTestName(e.target.value)}
                  placeholder="Ej. Evaluación Técnica Perforación Jumbo / HSEC"
                  className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm"
                />
              </div>

              <div>
                <label htmlFor="new-test-cat" className="block text-xs font-semibold text-[#23272E]">
                  Categoría
                </label>
                <select
                  id="new-test-cat"
                  value={newTestCategory}
                  onChange={(e) =>
                    setNewTestCategory(e.target.value as TestDefinition['category'])
                  }
                  className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm"
                >
                  <option value="Técnica Minera">Técnica Minera</option>
                  <option value="Psicolaboral">Psicolaboral</option>
                  <option value="Seguridad HSEC">Seguridad HSEC</option>
                  <option value="Operación / Maquinaria">Operación / Maquinaria</option>
                </select>
              </div>

              <div>
                <label htmlFor="new-test-area" className="block text-xs font-semibold text-[#23272E]">
                  Área objetivo
                </label>
                <select
                  id="new-test-area"
                  value={newTestArea}
                  onChange={(e) => setNewTestArea(e.target.value)}
                  className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm"
                >
                  {PERU_MINING_DEPARTMENTS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="new-test-dur" className="block text-xs font-semibold text-[#23272E]">
                  Duración (min)
                </label>
                <input
                  id="new-test-dur"
                  type="number"
                  min={5}
                  max={180}
                  value={newTestDuration}
                  onChange={(e) => setNewTestDuration(e.target.value)}
                  className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D8DCE0] bg-white px-3 font-mono-tabular text-sm"
                />
              </div>

              <div>
                <label htmlFor="new-test-pass" className="block text-xs font-semibold text-[#23272E]">
                  Nota mínima aprobatoria
                </label>
                <input
                  id="new-test-pass"
                  type="number"
                  min={40}
                  max={100}
                  value={newTestPassingScore}
                  onChange={(e) => setNewTestPassingScore(e.target.value)}
                  className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D8DCE0] bg-white px-3 font-mono-tabular text-sm"
                />
              </div>

              <div className="sm:col-span-2">
                <label htmlFor="new-test-questions" className="block text-xs font-semibold text-[#23272E]">
                  Ítems o preguntas (uno por línea)
                </label>
                <textarea
                  id="new-test-questions"
                  rows={3}
                  value={newTestQuestionsText}
                  onChange={(e) => setNewTestQuestionsText(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-[#D8DCE0] bg-white p-2.5 text-xs"
                />
              </div>
            </div>

            {testFormError && (
              <p className="text-xs font-semibold text-[#A84444]">{testFormError}</p>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isCreatingTest}
                className="inline-flex min-h-[42px] items-center gap-2 rounded-lg bg-[#23272E] px-5 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#3A404B] cursor-pointer"
              >
                <Plus className="h-4 w-4" />
                <span>{isCreatingTest ? 'Guardando Prueba...' : 'Guardar Nueva Prueba'}</span>
              </button>
            </div>
          </form>
        )}

      </section>

      {/* Top Split: Upload Solved Excel & Assign Test vs AI Candidate Result Report */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
        <div className="space-y-6 lg:col-span-5">
          {/* Card 1: Subir Excel Resuelto para Obtener Resultados IA */}
          <section
            aria-labelledby="excel-test-heading"
            className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-6"
          >
            <div className="flex items-start gap-2.5 border-b border-[#E2E4E8] pb-4">
              <FileSpreadsheet className="mt-0.5 h-5 w-5 shrink-0 text-[#B26337]" />
              <div>
                <h2 id="excel-test-heading" className="text-base font-bold text-[#23272E]">
                  Subir Excel Resuelto y Evaluar con IA
                </h2>
                <p className="mt-0.5 text-xs text-[#5C626D]">
                  Sube el Excel resuelto por el candidato. Si la prueba aún no está en tu base de datos, su nombre se registrará automáticamente y la IA entregará los resultados concretos.
                </p>
              </div>
            </div>

            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="psych-cand" className="block text-xs font-semibold text-[#23272E]">
                  Persona evaluada
                </label>
                <select
                  id="psych-cand"
                  value={selectedCandId}
                  onChange={(e) => {
                    setSelectedCandId(e.target.value);
                    setSendFeedback(null);
                    setTestDoneNotice(null);
                    setExcelNotice(null);
                    setExcelError(null);
                    setExcelWarning(null);
                  }}
                  className="mt-1 w-full min-h-[44px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm text-[#23272E]"
                >
                  {candidates.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.fullName} — {c.targetRoleTitle} · {c.psychEvaluation.status}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="psych-battery" className="block text-xs font-semibold text-[#23272E]">
                  Prueba de la base de datos ({testCatalog.length})
                </label>
                <select
                  id="psych-battery"
                  value={selectedTest?.id || ''}
                  onChange={(e) => setSelectedTestId(e.target.value)}
                  className="mt-1 w-full min-h-[44px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm text-[#23272E]"
                >
                  {testCatalog.length === 0 ? (
                    <option value="">
                      Detectar nombre automáticamente desde el Excel subido
                    </option>
                  ) : (
                    <>
                      <option value="">
                        Detectar automáticamente según el Excel subido
                      </option>
                      {testCatalog.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name} ({t.questions.length} ítems)
                        </option>
                      ))}
                    </>
                  )}
                </select>
              </div>

              <div className="flex flex-wrap gap-2">
                <DownloadButton path={`/api/tests/excel-template?testId=${encodeURIComponent(selectedTest?.id || '')}&candidateId=${encodeURIComponent(activeCand?.id || '')}`} fileName={`${selectedTest?.name || 'Prueba'}.xlsx`} label="Descargar Excel para Entregar (.xlsx)" className="min-h-[38px] !px-3 !py-1.5 text-xs" icon={<FileDown className="h-3.5 w-3.5 text-[#B26337]" />} />
              </div>

              <button type="button" onClick={() => void handleExcelFileUpload()} disabled={!activeCand || isUploadingExcel} className="flex min-h-[84px] w-full cursor-pointer disabled:opacity-60 flex-col items-center justify-center rounded-lg border border-dashed border-[#C99B7E] bg-[#FBF4EE]/40 px-4 py-3 text-center hover:border-[#B26337] hover:bg-[#FBF4EE] transition-colors">
                {isUploadingExcel ? (
                  <div className="flex items-center gap-2 text-xs font-semibold text-[#8C4722]">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Leyendo Excel resuelto y calculando resultados IA...</span>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-[#23272E]">
                      <Upload className="h-4 w-4 text-[#B26337]" />
                      <span>
                        Subir Excel resuelto de{' '}
                        <span className="text-[#8C4722]">
                          {activeCand?.fullName || 'candidato'}
                        </span>
                      </span>
                    </div>
                    <span className="mt-1 text-[11px] text-[#5C626D]">
                      Acepta .xlsx, .xls o .csv (autocalcula puntajes y verifica resultados)
                    </span>
                  </>
                )}
              </button>

              {excelError && (
                <p className="rounded-lg border border-[#EACACA] bg-[#FDF2F2] px-3 py-2 text-xs font-medium text-[#A84444]">
                  {excelError}
                </p>
              )}

              {excelNotice && (
                <p
                  role="status"
                  className="rounded-lg border border-[#D2E3D8] bg-[#F2F7F4] px-3 py-2 text-xs font-medium text-[#3D7A5A]"
                >
                  {excelNotice}
                </p>
              )}

              {excelWarning && (
                <p className="rounded-lg border border-[#E9D9B6] bg-[#FDF8EE] px-3 py-2 text-xs font-medium text-[#8C6118]">
                  {excelWarning}
                </p>
              )}
            </div>
          </section>

          {/* Card 2: Assign Registered Test or Complete Inline */}
          <section
            aria-labelledby="send-psych-heading"
            className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-6"
          >
            <div className="flex items-start gap-2.5 border-b border-[#E2E4E8] pb-3.5">
              <Send className="mt-0.5 h-5 w-5 shrink-0 text-[#5C626D]" />
              <div>
                <h2 id="send-psych-heading" className="text-sm font-bold text-[#23272E]">
                  Asignar Prueba o Responder en Plataforma
                </h2>
                <p className="mt-0.5 text-xs text-[#5C626D]">
                  Marca una prueba de tu base de datos como enviada al candidato o responde el cuestionario rápido aquí.
                </p>
              </div>
            </div>

            <form onSubmit={handleSend} className="mt-4 space-y-3">
              {sendFeedback && (
                <p
                  role="status"
                  className="rounded-lg border border-[#E6CDBE] bg-[#FBF4EE] px-3.5 py-2.5 text-xs font-medium text-[#8C4722]"
                >
                  {sendFeedback}
                </p>
              )}

              <div className="flex flex-col gap-2.5 sm:flex-row">
                <button
                  type="submit"
                  disabled={isSending || !activeCand || !selectedTest}
                  className="inline-flex min-h-[42px] flex-1 items-center justify-center gap-2 rounded-lg bg-[#B26337] px-4 py-2 text-xs font-semibold text-white hover:bg-[#99522B] transition-colors cursor-pointer disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5 shrink-0" />
                  <span>
                    {isSending
                      ? 'Enviando...'
                      : selectedTest
                      ? 'Marcar como Enviada'
                      : 'Sube primero un Excel'}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setShowRunner((v) => !v)}
                  className="inline-flex min-h-[42px] items-center justify-center gap-2 rounded-lg border border-[#D8DCE0] bg-[#F7F7F8] px-4 py-2 text-xs font-semibold text-[#23272E] hover:bg-[#EFEFF1] cursor-pointer"
                >
                  <ClipboardList className="h-3.5 w-3.5 text-[#B26337] shrink-0" />
                  <span>{showRunner ? 'Cerrar Test' : 'Responder Test'}</span>
                </button>
              </div>
            </form>

            {showRunner && activeCand && (
              <form
                onSubmit={handleCompleteAutomatedTest}
                className="mt-4 space-y-3 border-t border-[#E2E4E8] pt-4"
              >
                <p className="text-xs font-bold text-[#8C4722]">
                  Cuestionario Rápido ({activeCand.fullName} · Código {activeCand.psychEvaluation.accessCode})
                </p>

                {[
                  {
                    id: 'q-est',
                    label: '1. Control emocional bajo presión operativa (1-5)',
                    val: ansEstabilidad,
                    set: setAnsEstabilidad,
                  },
                  {
                    id: 'q-tol',
                    label: '2. Adaptación a campamento remoto / altura 14x7 (1-5)',
                    val: ansTolerancia,
                    set: setAnsTolerancia,
                  },
                  {
                    id: 'q-seg',
                    label: '3. Cumplimiento estricto de normas HSEC (1-5)',
                    val: ansSeguridad,
                    set: setAnsSeguridad,
                  },
                  {
                    id: 'q-eq',
                    label: '4. Cooperación en cuadrilla y comunicación (1-5)',
                    val: ansEquipo,
                    set: setAnsEquipo,
                  },
                  {
                    id: 'q-raz',
                    label: '5. Razonamiento ante fallas en planta / frente (1-5)',
                    val: ansRazonamiento,
                    set: setAnsRazonamiento,
                  },
                ].map((q) => (
                  <div key={q.id} className="flex items-center justify-between gap-3">
                    <label htmlFor={q.id} className="text-xs text-[#23272E]">
                      {q.label}
                    </label>
                    <select
                      id={q.id}
                      value={q.val}
                      onChange={(e) => q.set(Number(e.target.value))}
                      className="min-h-[36px] rounded-lg border border-[#D8DCE0] bg-white px-2.5 font-mono-tabular text-xs font-semibold"
                    >
                      <option value={5}>5 - Muy Alto</option>
                      <option value={4}>4 - Alto</option>
                      <option value={3}>3 - Medio</option>
                      <option value={2}>2 - Bajo</option>
                      <option value={1}>1 - Muy Bajo</option>
                    </select>
                  </div>
                ))}

                <button
                  type="submit"
                  disabled={isSubmittingTest}
                  className="flex w-full min-h-[42px] items-center justify-center gap-2 rounded-lg bg-[#23272E] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#3A404B] cursor-pointer"
                >
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>
                    {isSubmittingTest
                      ? 'Calculando puntuaciones IA...'
                      : 'Finalizar Prueba y Enviar Resultados a la IA'}
                  </span>
                </button>
              </form>
            )}
          </section>
        </div>

        {/* Right: AI Full Candidate Score Report + Excel Concrete Verification Result */}
        <section
          aria-labelledby="ai-psych-report-heading"
          className="space-y-6 rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7 lg:col-span-7"
        >
          {!activeCand ? (
            <p className="py-10 text-center text-sm text-[#5C626D]">
              Selecciona un candidato de la tabla o registra uno nuevo.
            </p>
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#E2E4E8] pb-4">
                <div className="flex items-start gap-2.5">
                  <BrainCircuit className="mt-0.5 h-5 w-5 shrink-0 text-[#B26337]" />
                  <div>
                    <h2 id="ai-psych-report-heading" className="text-lg font-bold text-[#23272E]">
                      Reporte de Puntuaciones y Resultados — {activeCand.fullName}
                    </h2>
                    <p className="mt-0.5 text-[11px] font-semibold text-[#8C4722]">
                      Evaluación de la persona (vale para todas sus postulaciones)
                    </p>
                    <p className="mt-0.5 text-xs text-[#5C626D]">
                      {activeCand.targetRoleTitle} · Código:{' '}
                      <span className="font-mono-tabular">
                        {activeCand.psychEvaluation.accessCode}
                      </span>
                    </p>
                  </div>
                </div>
                <DownloadButton variant="primary" path={`/api/reports/candidate/${encodeURIComponent(activeCand.id)}/doc`} fileName={`Ficha_${activeCand.fullName.replace(/\s+/g, '_')}.doc`} label="Descargar Reporte (.doc)" className="min-h-[38px] !px-3.5 !py-1.5 text-xs" icon={<FileDown className="h-3.5 w-3.5 shrink-0" />} />
              </div>

              {testDoneNotice && (
                <p
                  role="status"
                  className="rounded-lg border border-[#D2E3D8] bg-[#F2F7F4] px-4 py-2.5 text-sm font-medium text-[#3D7A5A]"
                >
                  {testDoneNotice}
                </p>
              )}

              {/* Latest Excel Concrete-Results Verdict Panel */}
              {latestExcel ? (
                <div
                  className={`rounded-xl border p-4 ${
                    latestExcel.concreteVerdict === 'Resultados Concretos'
                      ? 'border-[#D2E3D8] bg-[#F2F7F4]'
                      : latestExcel.concreteVerdict === 'Resultados Parciales'
                      ? 'border-[#E9D9B6] bg-[#FDF8EE]'
                      : 'border-[#EACACA] bg-[#FDF2F2]'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {latestExcel.concreteVerdict === 'Resultados Concretos' ? (
                        <CheckCircle2 className="h-4 w-4 text-[#3D7A5A]" />
                      ) : (
                        <AlertTriangle
                          className={`h-4 w-4 ${
                            latestExcel.concreteVerdict === 'Resultados Parciales'
                              ? 'text-[#A6752B]'
                              : 'text-[#A84444]'
                          }`}
                        />
                      )}
                      <span
                        className={`text-sm font-bold ${
                          latestExcel.concreteVerdict === 'Resultados Concretos'
                            ? 'text-[#3D7A5A]'
                            : latestExcel.concreteVerdict === 'Resultados Parciales'
                            ? 'text-[#8C6118]'
                            : 'text-[#A84444]'
                        }`}
                      >
                        Resultados IA según Excel ({latestExcel.testName}):{' '}
                        {latestExcel.concreteVerdict}
                      </span>
                    </div>
                    <span className="font-mono-tabular text-sm font-bold text-[#23272E]">
                      {latestExcel.autoComputedScore}/100 ({latestExcel.answeredCount}/
                      {latestExcel.totalQuestions} ítems)
                    </span>
                  </div>
                  {(latestExcel.passed === true || latestExcel.passed === false) && (
                    <p
                      className={`mt-2 inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold ${
                        latestExcel.passed ? 'bg-[#E3F1E8] text-[#2F6B4D]' : 'bg-[#FBE4E4] text-[#A84444]'
                      }`}
                    >
                      {latestExcel.passed ? 'Aprobada' : 'No aprobada'} · puntaje mínimo exigido:{' '}
                      {latestExcel.passingScore ?? '—'}
                    </p>
                  )}

                  <p className="mt-1.5 text-xs text-[#5C626D]">
                    Archivo: <strong className="text-[#23272E]">{latestExcel.fileName}</strong> ·{' '}
                    {latestExcel.uploadedAt}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-[#23272E]">
                    {latestExcel.aiAnalysis}
                  </p>

                  {latestExcel.parsedRows.length > 0 && (
                    <div className="mt-3 overflow-x-auto rounded-lg border border-[#E2E4E8] bg-white">
                      <table className="w-full border-collapse text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#E2E4E8] bg-[#F7F7F8] text-[#5C626D]">
                            <th className="px-3 py-2">Ítem / Pregunta</th>
                            <th className="px-3 py-2">Respuesta</th>
                            <th className="px-3 py-2 text-right">Puntaje</th>
                            <th className="px-3 py-2 text-right">Concreto</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#EFEFF1]">
                          {latestExcel.parsedRows.map((row, idx) => (
                            <tr key={`${row.item}-${idx}`}>
                              <td className="px-3 py-2 text-[#23272E]">{row.item}</td>
                              <td className="px-3 py-2 font-mono-tabular text-[#5C626D]">
                                {row.answer}
                              </td>
                              <td className="px-3 py-2 text-right font-mono-tabular font-semibold text-[#23272E]">
                                {row.score}/100
                              </td>
                              <td
                                className={`px-3 py-2 text-right font-semibold ${
                                  row.concrete ? 'text-[#3D7A5A]' : 'text-[#A84444]'
                                }`}
                              >
                                {row.concrete ? 'Sí' : 'Incompleto'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-[#D8DCE0] bg-[#F7F7F8] p-4 text-xs text-[#5C626D]">
                  Este candidato aún no tiene un archivo Excel resuelto cargado. Sube el Excel resuelto en el panel izquierdo para que la IA analice sus respuestas y entregue los resultados concretos.
                </div>
              )}

              {/* 5-Metric Consolidated Score Strip for the Position */}
              <div className="grid grid-cols-2 gap-4 border-b border-[#E2E4E8] pb-4 sm:grid-cols-5">
                {[
                  {
                    label: 'Técnico / Specs',
                    val: activeCand.metricReport.technicalSpecsScore,
                    accent: false,
                  },
                  {
                    label: 'Experiencia',
                    val: activeCand.metricReport.experienceScore,
                    accent: false,
                  },
                  {
                    label: 'Formación',
                    val: activeCand.metricReport.educationCareerScore,
                    accent: false,
                  },
                  {
                    label: 'Pruebas / Eval.',
                    val: activeCand.metricReport.psychScore,
                    accent: true,
                  },
                ].map((m) => (
                  <div key={m.label}>
                    <p className="text-xs text-[#5C626D]">{m.label}</p>
                    <p
                      className={`mt-0.5 font-mono-tabular text-xl font-bold ${
                        m.accent ? 'text-[#B26337]' : 'text-[#23272E]'
                      }`}
                    >
                      {m.val}
                    </p>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[#EFEFF1]">
                      <div
                        className={`h-full rounded-full ${
                          m.accent ? 'bg-[#B26337]' : 'bg-[#5C626D]'
                        }`}
                        style={{ width: `${m.val}%` }}
                      />
                    </div>
                  </div>
                ))}
                <div>
                  <p className="text-xs font-semibold text-[#8C4722]">Global Puesto</p>
                  <p className="mt-0.5 font-mono-tabular text-2xl font-bold text-[#B26337]">
                    {activeCand.metricReport.overallScore}/100
                  </p>
                </div>
              </div>

              {/* Psychometric 5-Axis Radar + AI Observation */}
              <div className="grid grid-cols-1 gap-5 rounded-lg border border-[#EFEFF1] bg-[#F7F7F8] p-4 sm:grid-cols-12 sm:items-start">
                {activeCand.psychEvaluation.scores ? (
                  <div className="sm:col-span-5">
                    <PsychRadarChart
                      axes={[
                        {
                          label: 'Estabilidad',
                          value: activeCand.psychEvaluation.scores.estabilidadEmocional,
                        },
                        {
                          label: 'Altura 14x7',
                          value: activeCand.psychEvaluation.scores.toleranciaFaenaAltura,
                        },
                        {
                          label: 'HSEC',
                          value: activeCand.psychEvaluation.scores.apegoSeguridadHSEC,
                        },
                        {
                          label: 'Equipo',
                          value: activeCand.psychEvaluation.scores.trabajoEquipo,
                        },
                        {
                          label: 'Razonam.',
                          value: activeCand.psychEvaluation.scores.razonamientoOperativo,
                        },
                      ]}
                    />
                  </div>
                ) : (
                  <div className="sm:col-span-5 rounded-lg border border-dashed border-[#D8DCE0] bg-white p-5 text-center text-xs text-[#5C626D]">
                    Gráfico disponible en cuanto subas el Excel resuelto de la prueba.
                  </div>
                )}

                <div className="space-y-3 text-sm text-[#23272E] sm:col-span-7">
                  <div>
                    <p className="text-xs font-bold text-[#8C4722]">
                      Observación IA sobre Resultados ({activeCand.psychEvaluation.aptitudeLevel})
                    </p>
                    <p className="mt-1 leading-relaxed">
                      {activeCand.psychEvaluation.aiPsychObservation}
                    </p>
                  </div>
                  <div className="border-t border-[#E2E4E8] pt-3">
                    <p className="text-xs font-bold text-[#5C626D]">
                      Dictamen Completo del Puesto (listo para Gerencia)
                    </p>
                    <p className="mt-1 leading-relaxed">
                      {activeCand.metricReport.aiDetailedReport}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Bottom: Full Results Table Observed by AI */}
      <section
        aria-labelledby="psych-table-heading"
        className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7"
      >
        <div className="flex flex-col gap-2 border-b border-[#E2E4E8] pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 id="psych-table-heading" className="text-lg font-bold text-[#23272E]">
              Tabla de Pruebas y Resultados Automáticos (Observada por la IA)
            </h2>
            <p className="mt-0.5 text-sm text-[#5C626D]">
              Cada Excel resuelto cargado registra la prueba y recalcula las puntuaciones del candidato para Gerencia.
            </p>
          </div>
          <DownloadButton path="/api/reports/candidates-csv" fileName="Candidatos.csv" label="Exportar Tabla (.csv)" className="min-h-[38px] !px-3 !py-1.5 text-xs" icon={<FileDown className="h-3.5 w-3.5" />} />
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[980px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-[#E2E4E8] text-xs font-semibold text-[#5C626D]">
                <th className="py-3 pr-4">Candidato</th>
                <th className="py-3 pr-4">Prueba Excel / Estado</th>
                <th className="py-3 pr-4">Resultado Excel IA</th>
                <th className="py-3 pr-4 text-right">Estabilidad</th>
                <th className="py-3 pr-4 text-right">Tolerancia 14x7</th>
                <th className="py-3 pr-4 text-right">Seguridad HSEC</th>
                <th className="py-3 pr-4 text-right">Equipo</th>
                <th className="py-3 pr-4 text-right">Razonamiento</th>
                <th className="py-3 pr-4 text-right">Promedio</th>
                <th className="py-3 text-right">Aptitud IA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EFEFF1]">
              {candidates.map((c) => {
                const s = c.psychEvaluation.scores;
                const isSelected = activeCand?.id === c.id;
                const candLatestExcel = c.excelTestResults?.[0];
                return (
                  <tr
                    key={c.id}
                    onClick={() => setSelectedCandId(c.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-[#FBF4EE]' : 'hover:bg-[#F7F7F8]'
                    }`}
                  >
                    <td className="py-3 pr-4">
                      <p className="font-bold text-[#23272E]">{c.fullName}</p>
                      <p className="text-xs text-[#5C626D]">{c.targetRoleTitle}</p>
                    </td>
                    <td className="py-3 pr-4 text-xs">
                      <p className="font-semibold text-[#23272E]">
                        {candLatestExcel?.testName || c.psychEvaluation.testBatteryName}
                      </p>
                      <span
                        className={
                          c.psychEvaluation.status === 'Completada'
                            ? 'font-semibold text-[#3D7A5A]'
                            : c.psychEvaluation.status === 'Enviada'
                            ? 'font-semibold text-[#8C4722]'
                            : 'text-[#5C626D]'
                        }
                      >
                        {c.psychEvaluation.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs">
                      {candLatestExcel ? (
                        <span
                          className={`font-semibold ${
                            candLatestExcel.concreteVerdict === 'Resultados Concretos'
                              ? 'text-[#3D7A5A]'
                              : candLatestExcel.concreteVerdict === 'Resultados Parciales'
                              ? 'text-[#8C6118]'
                              : 'text-[#A84444]'
                          }`}
                        >
                          {candLatestExcel.concreteVerdict} ({candLatestExcel.autoComputedScore}/100)
                        </span>
                      ) : (
                        <span className="text-[#5C626D]">Sin Excel cargado</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono-tabular">
                      {s ? s.estabilidadEmocional : '-'}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono-tabular">
                      {s ? s.toleranciaFaenaAltura : '-'}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono-tabular font-semibold">
                      {s ? s.apegoSeguridadHSEC : '-'}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono-tabular">
                      {s ? s.trabajoEquipo : '-'}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono-tabular">
                      {s ? s.razonamientoOperativo : '-'}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono-tabular font-bold text-[#B26337]">
                      {c.psychEvaluation.averageScore !== null
                        ? `${c.psychEvaluation.averageScore}/100`
                        : '-'}
                    </td>
                    <td className="py-3 text-right text-xs font-semibold text-[#23272E]">
                      {c.psychEvaluation.aptitudeLevel}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <UploadCvDialog
        open={showUpload}
        state={state}
        onDone={(st) => {
          onState(st);
          setShowUpload(false);
        }}
        onClose={() => setShowUpload(false)}
      />
    </div>
  );
};

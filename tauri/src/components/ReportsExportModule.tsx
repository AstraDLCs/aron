import React, { useEffect, useState } from 'react';
import { Database, Download, FileSpreadsheet, FileText, HardDrive, Printer, Upload, X } from 'lucide-react';
import type { DataCenterStatus, ModuleProps } from '../types';
import { DonutGaugeChart, HorizontalDistributionBars } from './ExecutiveCharts';
import { apiFetch, errorMessage, fileFromPath, pickFiles } from '../api/client';
import { DownloadButton } from './common/DownloadButton';
import { toast } from './common/Toast';
import { parseBackupFile } from '../utils/backup';

function fmtDate(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString('es-CL');
}

export const ReportsExportModule: React.FC<ModuleProps & { initialCandidateId?: string | null }> = ({
  state,
  onState,
  refresh,
}) => {
  const companyName = state.companyName;
  const hrChiefName = state.hrChiefName;
  const candidates = state.candidates;
  const jobNeeds = state.jobNeeds;
  const jobBoards = state.jobBoards;
  const kpis = state.kpis;
  const [dcStatus, setDcStatus] = useState<DataCenterStatus | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>(candidates[0]?.id ?? '');
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);
  const [pendingBackup, setPendingBackup] = useState<{ backup: unknown; fileName: string } | null>(null);
  const [confirmText, setConfirmText] = useState('');

  const loadDataCenterStatus = async () => {
    try {
      setDcStatus(await apiFetch<DataCenterStatus>('/api/datacenter/status'));
    } catch {
      // se ignora: el estado es informativo
    }
  };

  useEffect(() => {
    void loadDataCenterStatus();
  }, [candidates.length, jobNeeds.length, kpis.psychCompletedCount]);

  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId) ?? candidates[0] ?? null;

  const handlePickRestoreFile = async () => {
    setRestoreMessage(null);
    setRestoreError(null);
    try {
      const paths = await pickFiles({ name: 'Respaldo JSON', extensions: ['json'] });
      if (!paths.length) return;
      const file = await fileFromPath(paths[0]);
      const parsed = parseBackupFile(await file.text());
      if (!parsed.ok) {
        setRestoreError(parsed.error);
        return;
      }
      setConfirmText('');
      setPendingBackup({ backup: parsed.backup, fileName: file.name });
    } catch (err) {
      setRestoreError(errorMessage(err));
    }
  };

  const confirmRestore = async () => {
    if (!pendingBackup || confirmText !== 'RESTAURAR') return;
    setIsRestoring(true);
    try {
      const res = await apiFetch<{ state: typeof state }>('/api/datacenter/restore', {
        method: 'POST',
        json: { confirm: 'RESTAURAR', backup: pendingBackup.backup },
      });
      if (res?.state) onState(res.state);
      else await refresh();
      setRestoreMessage('Respaldo restaurado correctamente. Los datos fueron reemplazados por los del archivo.');
      toast('Respaldo restaurado correctamente.', 'ok');
      setPendingBackup(null);
      await loadDataCenterStatus();
    } catch (err) {
      setRestoreError(errorMessage(err));
      setPendingBackup(null);
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <div className="min-w-0 space-y-6">
      {/* Executive Deliverables Section */}
      <section className="min-w-0 rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7">
        <div className="flex flex-col gap-4 border-b border-[#E2E4E8] pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#23272E] sm:text-2xl">
              Centro de Documentos y Telemetría para el Administrador
            </h1>
            <p className="mt-1 text-sm text-[#5C626D]">
              Descarga informes ejecutivos listos para entregar en Word, tablas Excel con telemetría completa de candidatos, resultados psicológicos IA y KPIs de fuentes.
            </p>
          </div>
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex min-h-[42px] items-center justify-center gap-2 rounded-lg border border-[#D4D7DD] bg-white px-4 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1] transition-colors whitespace-nowrap shrink-0 cursor-pointer"
          >
            <Printer className="h-4 w-4 text-[#5C626D]" />
            <span>Imprimir / Guardar PDF</span>
          </button>
        </div>

        {/* Snapshot KPIs before download */}
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-[#5C626D]">
              Candidatos en Base
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-[#23272E]">
              {kpis.totalCandidates}
            </p>
          </div>
          <div className="rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-[#5C626D]">
              Cobertura Vacantes
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-[#B26337]">
              {kpis.coveragePercent}%
            </p>
          </div>
          <div className="rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-[#5C626D]">
              Psicológicas Completas
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-[#23272E]">
              {kpis.psychCompletedCount} / {kpis.totalCandidates}
            </p>
          </div>
          <div className="rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-[#5C626D]">
              Fuente Líder
            </p>
            <p className="mt-1 truncate text-base font-bold text-[#23272E]" title={kpis.topBoardName}>
              {kpis.topBoardName}
            </p>
            <p className="text-xs tabular-nums text-[#5C626D]">
              {kpis.topBoardCandidates} postulantes
            </p>
          </div>
        </div>

        {/* Executive Visual Snapshot for General Manager */}
        <div className="mt-6 grid min-w-0 gap-5 rounded-xl border border-[#EFEFF1] bg-[#F7F7F8]/70 p-5 md:grid-cols-12">
          <div className="min-w-0 md:col-span-5">
            <p className="mb-3 text-xs font-bold uppercase tracking-wide text-[#23272E]">
              Cobertura de Vacantes (Resumen Gerencial)
            </p>
            <DonutGaugeChart
              percent={kpis.coveragePercent}
              title="Cobertura de Vacantes"
              centerLabel={`${kpis.coveragePercent}%`}
              centerSublabel={`${kpis.filledVacancies}/${kpis.totalVacancies} plazas`}
              filledLabel={`${kpis.filledVacancies} cubiertas`}
              remainingLabel={`${kpis.remainingVacancies} pendientes`}
            />
          </div>
          <div className="min-w-0 border-t border-[#E2E4E8] pt-4 md:col-span-7 md:border-t-0 md:border-l md:pt-0 md:pl-6">
            <p className="mb-3 text-xs font-bold uppercase tracking-wide text-[#23272E]">
              Top Candidatos por Índice Global IA (Listos para Gerencia)
            </p>
            <HorizontalDistributionBars
              items={[...candidates]
                .sort((a, b) => b.metricReport.overallScore - a.metricReport.overallScore)
                .slice(0, 4)
                .map((c, idx) => ({
                  label: `${c.fullName} — ${c.targetRoleTitle}`,
                  value: c.metricReport.overallScore,
                  sublabel: c.decision,
                  accent: idx < 2 ? 'orange' : 'plomo',
                }))}
              maxOverride={100}
              unitLabel="/100"
            />
          </div>
        </div>

        {/* Primary Download Cards */}
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <article className="flex flex-col justify-between rounded-xl border border-[#E6CDBE] bg-[#FBF4EE] p-5">
            <div>
              <div className="flex items-center gap-2.5 text-[#8C4722]">
                <FileText className="h-5 w-5 shrink-0" />
                <h2 className="text-base font-bold text-[#23272E]">
                  Informe Ejecutivo Administrador
                </h2>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-[#5C626D]">
                Documento Word (.doc) estructurado con resumen gerencial de {companyName}, cobertura de vacantes, ranking de fuentes, cuadro de puntuaciones IA y estado psicológico de cada candidato.
              </p>
            </div>
            <DownloadButton variant="primary" path={"/api/reports/admin-doc"} fileName="Informe_Ejecutivo.doc" label="Descargar Informe (.doc)" className="mt-5 min-h-[44px] w-full" />
          </article>

          <article className="flex flex-col justify-between rounded-xl border border-[#E2E4E8] bg-white p-5">
            <div>
              <div className="flex items-center gap-2.5 text-[#23272E]">
                <FileSpreadsheet className="h-5 w-5 shrink-0 text-[#B26337]" />
                <h2 className="text-base font-bold text-[#23272E]">
                  Telemetría de Candidatos (.csv)
                </h2>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-[#5C626D]">
                Archivo compatible con Excel (UTF-8) con edad, procedencia, universidad, carrera, años trabajados, especificaciones, puntajes técnicos, 5 dimensiones psicológicas y decisión Jefe de RR.HH.
              </p>
            </div>
            <DownloadButton variant="ghost" path={"/api/reports/candidates-csv"} fileName="Candidatos.csv" label="Descargar Base Excel (.csv)" className="mt-5 min-h-[44px] w-full bg-white" />
          </article>

          <article className="flex flex-col justify-between rounded-xl border border-[#E2E4E8] bg-white p-5">
            <div>
              <div className="flex items-center gap-2.5 text-[#23272E]">
                <FileSpreadsheet className="h-5 w-5 shrink-0 text-[#5C626D]" />
                <h2 className="text-base font-bold text-[#23272E]">
                  KPIs de Procesos y Fuentes (.csv)
                </h2>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-[#5C626D]">
                Reporte tabular descargable con cobertura por vacante minera, propuestas enviadas a cada fuente, candidatos aportados, preseleccionados, contratados y tiempos de respuesta.
              </p>
            </div>
            <DownloadButton variant="ghost" path={"/api/reports/kpis-csv"} fileName="KPIs_Fuentes.csv" label="Descargar KPIs Excel (.csv)" className="mt-5 min-h-[44px] w-full" />
          </article>
        </div>
      </section>

      {/* Individual Candidate Scorecard Download */}
      <section className="min-w-0 rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-[#23272E]">
              Ficha Individual Descargable por Candidato (.doc)
            </h2>
            <p className="mt-1 text-sm text-[#5C626D]">
              Selecciona cualquier postulante para generar su documento individual con métricas completas, observaciones de la prueba psicológica automática y veredicto de {hrChiefName}.
            </p>
          </div>
          {selectedCandidate && (
            <div className="flex w-full min-w-0 flex-wrap items-center gap-3 sm:w-auto">
              <select
                aria-label="Seleccionar candidato para descargar ficha"
                value={selectedCandidate.id}
                onChange={(e) => setSelectedCandidateId(e.target.value)}
                className="min-h-[42px] w-full max-w-full sm:w-auto rounded-lg border border-[#D4D7DD] bg-white px-3.5 py-2 text-sm text-[#23272E] focus:border-[#B26337] focus:outline-none"
              >
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.fullName} — {c.targetRoleTitle} ({c.metricReport.overallScore} pts)
                  </option>
                ))}
              </select>
              <DownloadButton variant="primary" path={`/api/reports/candidate/${encodeURIComponent(selectedCandidate.id)}/doc`} fileName={`Ficha_${selectedCandidate.fullName.replace(/\s+/g, "_")}.doc`} label="Descargar Ficha (.doc)" className="min-h-[42px] whitespace-nowrap shrink-0" />
            </div>
          )}
        </div>

        {/* Compact Telemetry Preview Table */}
        <div className="mt-5 w-full overflow-x-auto rounded-lg border border-[#E2E4E8]">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[#E2E4E8] bg-[#F7F7F8] text-xs uppercase tracking-wide text-[#5C626D]">
              <tr>
                <th className="px-4 py-3 font-semibold">Candidato</th>
                <th className="px-4 py-3 font-semibold">Puesto Objetivo</th>
                <th className="px-4 py-3 font-semibold text-right">Técnico</th>
                <th className="px-4 py-3 font-semibold text-right">Psicológico</th>
                <th className="px-4 py-3 font-semibold text-right">Global IA</th>
                <th className="px-4 py-3 font-semibold">Estado</th>
                <th className="px-4 py-3 font-semibold text-right">Archivo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EFEFF1]">
              {candidates.map((cand) => (
                <tr key={cand.id} className="hover:bg-[#F7F7F8]/80">
                  <td className="px-4 py-3 font-semibold text-[#23272E]">
                    {cand.fullName}
                  </td>
                  <td className="px-4 py-3 text-[#5C626D]">{cand.targetRoleTitle}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#23272E]">
                    {cand.metricReport.technicalSpecsScore}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#23272E]">
                    {cand.psychEvaluation.averageScore ?? 'Pend.'}
                  </td>
                  <td className="px-4 py-3 text-right font-bold tabular-nums text-[#B26337]">
                    {cand.metricReport.overallScore}/100
                  </td>
                  <td className="px-4 py-3 text-[#5C626D]">{cand.decision}</td>
                  <td className="px-4 py-3 text-right">
                    <DownloadButton variant="ghost" path={`/api/reports/candidate/${encodeURIComponent(cand.id)}/doc`} fileName={`Ficha_${cand.fullName.replace(/\s+/g, "_")}.doc`} label=".doc" className="!px-2 !py-1 text-xs" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Respaldo y restauración */}
      <section className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7">
        <div className="flex flex-col gap-3 border-b border-[#E2E4E8] pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5">
            <HardDrive className="h-5 w-5 text-[#B26337]" />
            <div>
              <h2 className="text-lg font-bold text-[#23272E]">Respaldo y restauración de datos</h2>
              <p className="text-sm text-[#5C626D]">
                Descarga una copia de los datos del sistema o restaura una copia anterior.
              </p>
            </div>
          </div>
          {dcStatus && (
            <span className="text-xs font-medium tabular-nums text-[#5C626D]">
              Último movimiento: {fmtDate(dcStatus.lastSavedAt)}
            </span>
          )}
        </div>

        <div className="mt-5 rounded-lg border border-[#E2E4E8] bg-[#F7F7F8] p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-[#23272E]">
            <Database className="h-4 w-4 text-[#B26337]" />
            <span>Estado de los datos ({dcStatus?.mode ?? 'servidor'})</span>
          </div>
          <p className="mt-2 text-sm text-[#5C626D]">
            Registros activos:{' '}
            <strong className="tabular-nums text-[#23272E]">
              {dcStatus?.totalRecords ?? candidates.length + jobNeeds.length + jobBoards.length}
            </strong>{' '}
            ({dcStatus?.candidatesCount ?? candidates.length} postulaciones, {dcStatus?.vacanciesCount ?? jobNeeds.length}{' '}
            requerimientos, {dcStatus?.boardsCount ?? jobBoards.length} fuentes
            {dcStatus ? `, ${dcStatus.criteriaCount} criterios` : ''}).
          </p>
          {dcStatus?.storagePath && (
            <p className="mt-1 text-xs text-[#5C626D]">Carpeta de CVs en el servidor: {dcStatus.storagePath}</p>
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <DownloadButton
              path="/api/datacenter/backup"
              fileName="Respaldo_Pulso_Laboral.json"
              label="Descargar respaldo (.json)"
              className="min-h-[42px] bg-white"
            />
            <button
              type="button"
              onClick={() => void handlePickRestoreFile()}
              disabled={isRestoring}
              className="inline-flex min-h-[42px] items-center gap-2 rounded-lg border border-[#D4D7DD] bg-white px-4 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1] transition-colors disabled:opacity-60"
            >
              <Upload className="h-4 w-4 text-[#5C626D]" />
              <span>{isRestoring ? 'Restaurando...' : 'Restaurar respaldo (.json)'}</span>
            </button>
          </div>

          {restoreMessage && <p className="mt-3 text-xs font-semibold text-[#3D7A5A]">{restoreMessage}</p>}
          {restoreError && <p className="mt-3 text-xs font-semibold text-red-700">{restoreError}</p>}
        </div>
      </section>

      {pendingBackup && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-lg font-bold text-[#23272E]">Restaurar respaldo</h3>
              <button type="button" onClick={() => setPendingBackup(null)} aria-label="Cerrar" className="text-[#5C626D] hover:text-[#23272E]">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-3 text-sm text-[#5C626D]">
              Archivo: <strong className="text-[#23272E]">{pendingBackup.fileName}</strong>
            </p>
            <p className="mt-2 rounded-lg border border-[#E6CDBE] bg-[#FBF4EE] px-3 py-2 text-sm text-[#8C4722]">
              Esto reemplazará TODOS los datos actuales (candidatos, requerimientos, fuentes, criterios) por los del archivo. Esta acción no se puede deshacer.
            </p>
            <label htmlFor="restore-confirm" className="mt-4 block text-xs font-semibold text-[#23272E]">
              Escribe RESTAURAR para confirmar
            </label>
            <input
              id="restore-confirm"
              autoFocus
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="mt-1 w-full min-h-[42px] rounded-lg border border-[#D4D7DD] px-3 text-sm focus:border-[#B26337] focus:outline-none"
              placeholder="RESTAURAR"
            />
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setPendingBackup(null)}
                className="rounded-lg border border-[#D4D7DD] bg-white px-4 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1]"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={confirmText !== 'RESTAURAR' || isRestoring}
                onClick={() => void confirmRestore()}
                className="rounded-lg bg-[#B26337] px-4 py-2 text-sm font-semibold text-white hover:bg-[#99522B] disabled:opacity-50"
              >
                {isRestoring ? 'Restaurando...' : 'Restaurar datos'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

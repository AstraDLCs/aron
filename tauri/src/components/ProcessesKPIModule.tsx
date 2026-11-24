import React, { useMemo, useState } from 'react';
import { FileDown, Send, TrendingUp } from 'lucide-react';
import type { ModuleProps } from '../types';
import { DonutGaugeChart, GroupedBoardsChart } from './ExecutiveCharts';
import { apiFetch, errorMessage } from '../api/client';
import { DownloadButton } from './common/DownloadButton';
import { toast } from './common/Toast';
import { useCreatable } from './common/creatable';

export const ProcessesKPIModule: React.FC<ModuleProps & { initialCandidateId?: string | null }> = ({ state, onState }) => {
  const jobNeeds = state.jobNeeds;
  const jobBoards = state.jobBoards;
  const kpis = state.kpis;
  const [selectedNeedId, setSelectedNeedId] = useState(jobNeeds.find((n) => n.status === 'Abierto')?.id ?? jobNeeds[0]?.id ?? '');
  const [selectedBoardId, setSelectedBoardId] = useState(jobBoards.find((b) => b.active)?.id ?? jobBoards[0]?.id ?? '');
  const [dispatchNotice, setDispatchNotice] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const boardSel = useCreatable({
    kind: 'fuente', state, value: selectedBoardId, onSelect: setSelectedBoardId,
    onCreated: (id, s) => {
      if (s) onState(s);
      setSelectedBoardId(id);
    },
  });

  const rankedBoards = useMemo(
    () => [...jobBoards].sort((a, b) => b.candidatesReceived - a.candidatesReceived),
    [jobBoards]
  );

  const maxCandidatesFromBoard = Math.max(
    1,
    rankedBoards[0]?.candidatesReceived ?? 1
  );

  const handleDispatchProposal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedNeedId || !selectedBoardId || boardSel.pending) return;
    setIsSending(true);
    setDispatchNotice(null);
    try {
      const res = await apiFetch<{ state: typeof state }>(`/api/sources/${selectedBoardId}/proposals`, {
        method: 'POST',
        json: { requirementId: selectedNeedId },
      });
      if (res?.state) onState(res.state);
      const boardName = jobBoards.find((b) => b.id === selectedBoardId)?.name;
      const needTitle = jobNeeds.find((n) => n.id === selectedNeedId)?.title;
      setDispatchNotice(
        `Propuesta de "${needTitle}" registrada en ${boardName}. Conteo de propuestas actualizado.`
      );
    } catch (err) {
      toast(errorMessage(err), 'error');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top KPI Summary Strip */}
      <section className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7">
        <div className="flex flex-col gap-4 border-b border-[#E2E4E8] pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#23272E] sm:text-2xl">
              KPIs de Procesos, Cobertura de Vacantes y Fuentes de Reclutamiento
            </h1>
            <p className="mt-1 text-sm text-[#5C626D]">
              Control de avance de vacantes, canales donde se envían propuestas y ranking de fuentes que más candidatos aportan.
            </p>
          </div>
          <DownloadButton
            path="/api/reports/kpis-csv"
            fileName="KPIs_Fuentes.csv"
            icon={<FileDown className="h-4 w-4 text-[#5C626D] shrink-0" />}
            label="Descargar KPIs y Fuentes (.csv)"
            className="min-h-[42px] whitespace-nowrap shrink-0"
          />
        </div>

        <div className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-4">
          <div>
            <p className="text-xs font-medium text-[#5C626D]">Cobertura de Vacantes</p>
            <p className="mt-1 font-mono-tabular text-2xl font-bold text-[#B26337]">
              {kpis.coveragePercent}%
            </p>
            <p className="text-xs text-[#5C626D] font-mono-tabular">
              {kpis.filledVacancies} de {kpis.totalVacancies} plazas
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-[#5C626D]">Propuestas Enviadas</p>
            <p className="mt-1 font-mono-tabular text-2xl font-bold text-[#23272E]">
              {kpis.totalProposalsSent}
            </p>
            <p className="text-xs text-[#5C626D]">En {jobBoards.filter((b) => b.active).length} fuentes activas</p>
          </div>
          <div>
            <p className="text-xs font-medium text-[#5C626D]">Tiempo Promedio Proceso</p>
            <p className="mt-1 font-mono-tabular text-2xl font-bold text-[#23272E]">
              {kpis.avgProcessDays} días
            </p>
            <p className="text-xs text-[#5C626D]" title="Porcentaje de postulaciones ya revisadas por RR.HH. cuya decisión coincide con el veredicto de la IA (Pre-aprobado = Aprobado o Contratado; Pre-denegado = Rechazado). Las pendientes de revisión no cuentan.">
              Acuerdo IA/RR.HH.: {kpis.aiAgreementRate}%
            </p>
            <p className="text-[11px] leading-snug text-[#8A8F99]">
              Acuerdo = decisiones de RR.HH. ya tomadas que coinciden con el veredicto de la IA.
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-[#5C626D]">Fuente Líder en Postulantes</p>
            <p className="mt-1 text-lg font-bold text-[#23272E] truncate">
              {kpis.topBoardName}
            </p>
            <p className="text-xs font-mono-tabular font-semibold text-[#B26337]">
              {kpis.topBoardCandidates} candidatos enviados
            </p>
          </div>
        </div>
      </section>

      {/* Executive Visual Analytics Row: Coverage Gauge + Job Board Comparison Chart */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="min-w-0 rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-6 lg:col-span-4">
          <div className="border-b border-[#E2E4E8] pb-3">
            <h2 className="text-sm font-bold uppercase tracking-wide text-[#23272E]">
              Cobertura Global de Plazas
            </h2>
            <p className="mt-0.5 text-xs text-[#5C626D]">
              Avance consolidado frente a vacantes abiertas.
            </p>
          </div>
          <div className="mt-5">
            <DonutGaugeChart
              percent={kpis.coveragePercent}
              title="Cobertura Global de Vacantes"
              centerLabel={`${kpis.coveragePercent}%`}
              centerSublabel={`${kpis.filledVacancies}/${kpis.totalVacancies} plazas`}
              filledLabel={`${kpis.filledVacancies} cubiertas`}
              remainingLabel={`${kpis.remainingVacancies} pendientes`}
            />
          </div>
        </section>

        <section className="min-w-0 rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-6 lg:col-span-8">
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[#E2E4E8] pb-3">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wide text-[#23272E]">
                Rendimiento Comparativo por Fuente
              </h2>
              <p className="mt-0.5 text-xs text-[#5C626D]">
                Propuestas enviadas frente a candidatos recibidos y preseleccionados por la IA.
              </p>
            </div>
          </div>
          <div className="mt-4">
            <GroupedBoardsChart
              data={rankedBoards.map((b) => ({
                name: b.name,
                proposals: b.proposalsSent,
                candidates: b.candidatesReceived,
                shortlisted: b.shortlistedCount,
              }))}
            />
          </div>
        </section>
      </div>

      {/* Split: Job Boards Ranking + Send Proposal Dispatch */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
        <section
          aria-labelledby="boards-ranking-heading"
          className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7 lg:col-span-8"
        >
          <div className="flex items-center gap-2 border-b border-[#E2E4E8] pb-4">
            <TrendingUp className="h-5 w-5 text-[#B26337]" />
            <div>
              <h2 id="boards-ranking-heading" className="text-lg font-bold text-[#23272E]">
                Fuentes: Propuestas Enviadas vs Candidatos Recibidos
              </h2>
              <p className="mt-0.5 text-sm text-[#5C626D]">
                Ordenadas de mayor a menor según cuántos candidatos ha aportado cada fuente.
              </p>
            </div>
          </div>

          <div className="mt-4 divide-y divide-[#EFEFF1]">
            {rankedBoards.map((board, idx) => {
              const barPct = Math.round(
                (board.candidatesReceived / maxCandidatesFromBoard) * 100
              );
              const conversion =
                board.candidatesReceived > 0
                  ? Math.round((board.shortlistedCount / board.candidatesReceived) * 100)
                  : 0;

              return (
                <div key={board.id} className="py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono-tabular text-xs font-bold text-[#5C626D]">
                        0{idx + 1}.
                      </span>
                      <h3 className="text-base font-bold text-[#23272E]">{board.name}</h3>
                      <span className="text-xs text-[#5C626D]">· {board.category}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 font-mono-tabular text-xs">
                      <span className="text-[#5C626D]">
                        Propuestas: <strong className="text-[#23272E]">{board.proposalsSent}</strong>
                      </span>
                      <span className="text-[#5C626D]">
                        Candidatos: <strong className="text-[#B26337]">{board.candidatesReceived}</strong>
                      </span>
                      <span className="text-[#5C626D]">
                        Preselección: <strong className="text-[#23272E]">{conversion}%</strong>
                      </span>
                      <span className="text-[#5C626D]">
                        Contratados: <strong className="text-[#3D7A5A]">{board.hiredCount}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Muted opaque orange & plomo proportional bar */}
                  <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-[#EFEFF1]">
                    <div
                      className="h-full rounded-full bg-[#C97A4B] transition-all duration-300"
                      style={{ width: `${barPct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Dispatch New Recruitment Proposal to Job Board */}
        <section
          aria-labelledby="dispatch-board-heading"
          className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7 lg:col-span-4"
        >
          <h2 id="dispatch-board-heading" className="border-b border-[#E2E4E8] pb-4 text-lg font-bold text-[#23272E]">
            Registrar Propuesta en una Fuente
          </h2>
          <p className="mt-2 text-sm text-[#5C626D]">
            Registra que una vacante fue enviada a una fuente (portal, red profesional, referidos) para llevar el conteo de propuestas.
          </p>

          <form onSubmit={handleDispatchProposal} className="mt-4 space-y-4">
            <div>
              <label htmlFor="dispatch-need" className="block text-xs font-semibold text-[#23272E]">
                Vacante a publicar
              </label>
              <select
                id="dispatch-need"
                value={selectedNeedId}
                onChange={(e) => setSelectedNeedId(e.target.value)}
                className="mt-1 w-full min-h-[44px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm text-[#23272E]"
              >
                {jobNeeds.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="dispatch-board" className="block text-xs font-semibold text-[#23272E]">
                Fuente destino
              </label>
              <select
                id="dispatch-board"
                value={boardSel.value}
                onChange={boardSel.onChange}
                disabled={boardSel.disabled}
                className="mt-1 w-full min-h-[44px] rounded-lg border border-[#D8DCE0] bg-white px-3 text-sm text-[#23272E]"
              >
                {!selectedBoardId && <option value="">Elige una fuente…</option>}
                {jobBoards.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.candidatesReceived} candidatos)
                  </option>
                ))}
                {boardSel.newOption}
              </select>
              {boardSel.panel && <div className="mt-2">{boardSel.panel}</div>}
            </div>

            {dispatchNotice && (
              <p role="status" className="rounded-lg border border-[#E6CDBE] bg-[#FBF4EE] px-3.5 py-2.5 text-xs font-medium text-[#8C4722]">
                {dispatchNotice}
              </p>
            )}

            <button
              type="submit"
              disabled={isSending}
              className="flex w-full min-h-[46px] items-center justify-center gap-2 rounded-lg bg-[#B26337] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#99522B] transition-colors cursor-pointer"
            >
              <Send className="h-4 w-4 shrink-0" />
              <span>{isSending ? 'Registrando...' : 'Registrar Propuesta'}</span>
            </button>
          </form>
        </section>
      </div>

      {/* Vacancy Coverage Breakdown */}
      <section
        aria-labelledby="coverage-table-heading"
        className="rounded-xl border border-[#E2E4E8] bg-white p-5 sm:p-7"
      >
        <h2 id="coverage-table-heading" className="border-b border-[#E2E4E8] pb-4 text-lg font-bold text-[#23272E]">
          Cobertura por Requerimiento
        </h2>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[780px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-[#E2E4E8] text-xs font-semibold text-[#5C626D]">
                <th className="py-3 pr-4">Puesto / Vacante</th>
                <th className="py-3 pr-4">Área Minera</th>
                <th className="py-3 pr-4">Urgencia</th>
                <th className="py-3 pr-4">Fuentes Publicadas</th>
                <th className="py-3 pr-4 text-right">Cubiertas / Req.</th>
                <th className="py-3 text-right">Avance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EFEFF1]">
              {jobNeeds.map((need) => {
                const pct =
                  need.vacancies > 0
                    ? Math.round((need.filledCount / need.vacancies) * 100)
                    : 0;
                return (
                  <tr key={need.id} className="hover:bg-[#F7F7F8]">
                    <td className="py-3.5 pr-4 font-semibold text-[#23272E]">
                      {need.title}
                    </td>
                    <td className="py-3.5 pr-4 text-[#5C626D]">{need.department}</td>
                    <td className="py-3.5 pr-4">
                      <span
                        className={`text-xs font-semibold ${
                          need.urgency === 'Urgente'
                            ? 'text-[#A84444]'
                            : need.urgency === 'Media'
                            ? 'text-[#8C4722]'
                            : 'text-[#5C626D]'
                        }`}
                      >
                        {need.urgency}
                      </span>
                    </td>
                    <td className="py-3.5 pr-4 text-xs text-[#5C626D]">
                      {(need.publishedSourceIds ?? []).map((id) => jobBoards.find((b) => b.id === id)?.name).filter(Boolean).join(' · ') || (need.publishedBoards ?? []).join(' · ') || '—'}
                    </td>
                    <td className="py-3.5 pr-4 text-right font-mono-tabular font-semibold text-[#23272E]">
                      {need.filledCount}/{need.vacancies}
                    </td>
                    <td className="py-3.5 text-right font-mono-tabular font-bold text-[#B26337]">
                      {pct}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

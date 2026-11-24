import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  Check,
  ClipboardList,
  GraduationCap,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import type { AppState, Candidate, CandidateDecision, JobUrgency, ModuleProps, RecruitmentCriterion } from '../types';
import { apiFetch, errorMessage } from '../api/client';
import { toast } from './common/Toast';
import { AiBlock, Badge, btnGhost, btnPrimary, card, CvActions, inputCls, labelCls } from './CandidatesDashboard';
import { agreeWithAi, allowedNextDecisions, DECISION_ACTION_LABEL, sortSelectionQueue } from '../utils/decisions';
import { decisionBadgeClass, formatDate, formatDateTime, TONE_CLASSES, verdictBadgeClass } from '../utils/labels';

type Props = ModuleProps & { initialCandidateId?: string | null; initialPositionId?: string | null };

const URGENCIES: JobUrgency[] = ['Urgente', 'Media', 'Planificada'];

function NewRequirementForm({ state, onState, onClose, initialPositionId }: { state: AppState; onState: (s: AppState) => void; onClose: () => void; initialPositionId?: string | null }) {
  const [positionId, setPositionId] = useState(initialPositionId || state.positions[0]?.id || '');
  const [quantity, setQuantity] = useState('1');
  const [urgency, setUrgency] = useState<JobUrgency>('Media');
  const [days, setDays] = useState('30');
  const [context, setContext] = useState('');
  const [extraSkills, setExtraSkills] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pos = state.positions.find((p) => p.id === positionId);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const q = Number(quantity);
    if (!positionId) return setError('Elige un puesto del organigrama.');
    if (!Number.isInteger(q) || q < 1 || q > 500) return setError('Las plazas deben estar entre 1 y 500.');
    setBusy(true);
    try {
      const r = await apiFetch<{ state: AppState }>('/api/requirements', {
        method: 'POST',
        json: {
          positionId,
          quantity: q,
          urgency,
          targetDaysToFill: Number(days) || 30,
          context: context.trim(),
          extraSkills: extraSkills.trim(),
          publishedSourceIds: sources,
        },
      });
      onState(r.state);
      toast('Requerimiento creado.');
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-[#E6CDBE] bg-[#FBF4EE]/50 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-[#23272E]">Nuevo requerimiento</h3>
        <button type="button" onClick={onClose} className="text-[#5C626D]" aria-label="Cerrar">
          <X className="h-4 w-4" />
        </button>
      </div>
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {state.positions.length === 0 ? (
        <p className="text-sm text-[#5C626D]">Primero crea puestos en el Organigrama.</p>
      ) : (
        <>
          <div>
            <label className={labelCls}>Puesto del organigrama</label>
            <select className={inputCls} value={positionId} onChange={(e) => setPositionId(e.target.value)}>
              {state.positions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.area}
                </option>
              ))}
            </select>
            {pos?.requiredSkills && <p className="mt-1 text-xs text-[#5C626D]">Competencias del puesto: {pos.requiredSkills}</p>}
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className={labelCls}>Plazas</label>
              <input type="number" min={1} max={500} className={inputCls} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>Urgencia</label>
              <select className={inputCls} value={urgency} onChange={(e) => setUrgency(e.target.value as JobUrgency)}>
                {URGENCIES.map((u) => (
                  <option key={u}>{u}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls}>Plazo (días)</label>
              <input type="number" min={1} className={inputCls} value={days} onChange={(e) => setDays(e.target.value)} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Contexto</label>
            <textarea rows={2} className={inputCls} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Motivo, proyecto, turno…" />
          </div>
          <div>
            <label className={labelCls}>Competencias extra</label>
            <input className={inputCls} value={extraSkills} onChange={(e) => setExtraSkills(e.target.value)} />
          </div>
          <div>
            <label className={labelCls}>Fuentes donde se publica</label>
            <div className="flex flex-wrap gap-1.5">
              {state.jobBoards.map((b) => {
                const on = sources.includes(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => setSources(on ? sources.filter((x) => x !== b.id) : [...sources, b.id])}
                    className={`rounded-md border px-2 py-1 text-xs font-semibold ${on ? 'border-[#B26337] bg-[#B26337] text-white' : 'border-[#D4D7DD] bg-white text-[#5C626D]'}`}
                  >
                    {b.name}
                  </button>
                );
              })}
            </div>
          </div>
          <button type="submit" className={`${btnPrimary} w-full`} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}Crear requerimiento
          </button>
        </>
      )}
    </form>
  );
}

function AiReportPanel({ c, state, onState }: { c: Candidate; state: AppState; onState: (s: AppState) => void }) {
  const convs = state.aiConversations.filter((x) => x.candidateId === c.id);
  const conv = convs[convs.length - 1] ?? null;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<{ state: AppState }>) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (r?.state) onState(r.state);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const evaluate = () => run(() => apiFetch('/api/ai/evaluate-candidate', { method: 'POST', json: { candidateId: c.id } }));
  const send = () => {
    const text = msg.trim();
    if (!text) return;
    setMsg('');
    return run(() =>
      apiFetch('/api/ai/assistant-chat', { method: 'POST', json: { conversationId: conv?.id, candidateId: c.id, message: text } }),
    );
  };
  const vote = (messageId: string, v: 'up' | 'down') => {
    if (!conv) return;
    const feedbackNote = v === 'down' ? window.prompt('¿Qué estuvo mal en esta respuesta? (opcional)') ?? '' : '';
    return run(() =>
      apiFetch('/api/ai/vote-response', { method: 'POST', json: { conversationId: conv.id, messageId, vote: v, feedbackNote } }),
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wide text-[#5C626D]">
          <Sparkles className="h-4 w-4 text-[#B26337]" /> Informe y chat IA
        </h3>
        <button type="button" className={btnGhost} onClick={evaluate} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
          {conv ? 'Nuevo informe IA' : 'Generar informe IA'}
        </button>
      </div>
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {conv?.structuredReport && (
        <div className="rounded-lg bg-[#F7F7F8] p-3 text-sm">
          <p className="font-semibold text-[#23272E]">{conv.structuredReport.recommendation}</p>
          {conv.structuredReport.concreteSummary && <p className="mt-1 text-[#5C626D]">{conv.structuredReport.concreteSummary}</p>}
          <div className="mt-2 grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs font-semibold text-emerald-700">Fortalezas</p>
              <ul className="ml-4 list-disc">
                {conv.structuredReport.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-amber-700">Alertas</p>
              <ul className="ml-4 list-disc">
                {conv.structuredReport.watchouts.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
      {conv && (
        <div className="max-h-72 space-y-2 overflow-auto rounded-lg border border-[#E2E4E8] p-3">
          {conv.messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${m.role === 'user' ? 'bg-[#B26337] text-white' : 'bg-[#F7F7F8] text-[#23272E]'}`}>
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.role === 'assistant' && (
                  <div className="mt-1 flex items-center gap-2 text-[#5C626D]">
                    <button type="button" title="Útil" onClick={() => vote(m.id, 'up')} className={m.vote === 'up' ? 'text-emerald-600' : 'hover:text-emerald-600'}>
                      <ThumbsUp className="h-3.5 w-3.5" />
                    </button>
                    <button type="button" title="No útil" onClick={() => vote(m.id, 'down')} className={m.vote === 'down' ? 'text-red-600' : 'hover:text-red-600'}>
                      <ThumbsDown className="h-3.5 w-3.5" />
                    </button>
                    <span className="text-[10px]">{formatDateTime(m.createdAt)}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <input
          className={inputCls}
          placeholder="Pregunta a la IA sobre este candidato…"
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void send();
          }}
        />
        <button type="button" className={btnPrimary} onClick={() => void send()} disabled={busy || !msg.trim()}>
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function DecisionPanel({ c, state, onState }: { c: Candidate; state: AppState; onState: (s: AppState) => void }) {
  const [score, setScore] = useState<string>(c.managerScore != null ? String(c.managerScore) : '');
  const [notes, setNotes] = useState(c.managerNotes ?? '');
  const [requirementId, setRequirementId] = useState(c.requirementId ?? '');
  const [teachAi, setTeachAi] = useState(false);
  const [critTitle, setCritTitle] = useState('');
  const [critRule, setCritRule] = useState('');
  const [critWeight, setCritWeight] = useState<RecruitmentCriterion['weightLabel']>('Importante');
  const [isCorrection, setIsCorrection] = useState(false);
  const [wrongAssumption, setWrongAssumption] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setScore(c.managerScore != null ? String(c.managerScore) : '');
    setNotes(c.managerNotes ?? '');
    setRequirementId(c.requirementId ?? '');
    setTeachAi(false);
    setCritTitle('');
    setCritRule('');
    setIsCorrection(false);
    setWrongAssumption('');
    setError(null);
  }, [c.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const openReqs = state.jobNeeds.filter((r) => r.positionId === c.positionId && r.status === 'Abierto');
  const next = allowedNextDecisions(c.decision);
  const agree = agreeWithAi(c.aiVerdict);
  const agreeAllowed = agree != null && next.includes(agree);

  const decide = async (decision: CandidateDecision) => {
    setError(null);
    if (decision === 'Contratado' && !c.requirementId && !requirementId) {
      setError('Para contratar, elige el requerimiento cuya plaza se cubre.');
      return;
    }
    if (teachAi && (!critTitle.trim() || !critRule.trim())) {
      setError('Para enseñar a la IA indica el título y la regla del criterio.');
      return;
    }
    setBusy(decision);
    try {
      const r = await apiFetch<{ state: AppState }>(`/api/candidates/${c.id}/decision`, {
        method: 'POST',
        json: {
          decision,
          managerScore: score === '' ? null : Math.max(0, Math.min(100, Number(score))),
          managerNotes: notes,
          requirementId: c.requirementId || requirementId || null,
          teachAi,
          criterionTitle: teachAi ? critTitle.trim() : null,
          criterionRule: teachAi ? critRule.trim() : null,
          criterionWeight: critWeight,
          isCorrection: teachAi && isCorrection,
          wrongAiAssumption: teachAi && isCorrection ? wrongAssumption.trim() : null,
        },
      });
      onState(r.state);
      toast(`Decisión registrada: ${decision}.`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const reclassify = async () => {
    setBusy('reclass');
    try {
      const r = await apiFetch<{ state: AppState }>(`/api/candidates/${c.id}/reclassify`, { method: 'POST' });
      if (r?.state) onState(r.state);
      toast('Postulación enviada a la cola de la IA.');
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const decisionBtnCls = (d: CandidateDecision) =>
    d === 'Rechazado'
      ? 'inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-white px-3.5 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-60'
      : d === 'Contratado'
        ? 'inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-60'
        : btnPrimary;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-bold text-[#23272E]">{c.fullName}</h2>
          <p className="text-sm text-[#5C626D]">
            {c.targetRoleTitle} · {c.sourceBoardName} · {c.career}
            {c.yearsWorked != null && ` · ${c.yearsWorked} años`}
          </p>
        </div>
        <Badge className={decisionBadgeClass(c.decision)}>{c.decision}</Badge>
      </div>

      <div className="rounded-lg border border-[#E2E4E8] p-4">
        <AiBlock c={c} />
        <div className="mt-3 flex flex-wrap gap-2">
          <CvActions c={c} />
          <button type="button" className={btnGhost} onClick={reclassify} disabled={busy != null}>
            {busy === 'reclass' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Reclasificar con IA
          </button>
        </div>
      </div>

      <div className="space-y-3 rounded-lg border border-[#E6CDBE] bg-[#FBF4EE]/40 p-4">
        <h3 className="text-sm font-bold uppercase tracking-wide text-[#5C626D]">Decisión humana</h3>
        {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <div>
            <label className={labelCls}>Puntaje (0-100)</label>
            <input type="number" min={0} max={100} className={inputCls} value={score} onChange={(e) => setScore(e.target.value)} />
          </div>
          <div>
            <label className={labelCls}>Notas del evaluador</label>
            <input className={inputCls} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        {!c.requirementId && next.includes('Contratado') && (
          <div>
            <label className={labelCls}>Requerimiento que se cubre al contratar</label>
            <select className={inputCls} value={requirementId} onChange={(e) => setRequirementId(e.target.value)}>
              <option value="">Elegir requerimiento…</option>
              {openReqs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} · {r.filledCount}/{r.vacancies} plazas · {formatDate(r.openedAt)}
                </option>
              ))}
            </select>
            {openReqs.length === 0 && <p className="mt-1 text-xs text-amber-700">No hay requerimientos abiertos para este puesto.</p>}
          </div>
        )}

        <label className="flex items-center gap-2 text-sm font-semibold text-[#23272E]">
          <input type="checkbox" checked={teachAi} onChange={(e) => setTeachAi(e.target.checked)} className="h-4 w-4 accent-[#B26337]" />
          <GraduationCap className="h-4 w-4 text-[#B26337]" /> Retroalimentar criterio a la IA
        </label>
        {teachAi && (
          <div className="space-y-2 rounded-lg border border-[#E2E4E8] bg-white p-3">
            <div className="grid grid-cols-[1fr_150px] gap-2">
              <div>
                <label className={labelCls}>Título del criterio</label>
                <input className={inputCls} value={critTitle} onChange={(e) => setCritTitle(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Peso</label>
                <select className={inputCls} value={critWeight} onChange={(e) => setCritWeight(e.target.value as RecruitmentCriterion['weightLabel'])}>
                  <option>Prioritario</option>
                  <option>Importante</option>
                  <option>Deseable</option>
                </select>
              </div>
            </div>
            <div>
              <label className={labelCls}>Regla (cómo debe evaluar la IA)</label>
              <textarea rows={2} className={inputCls} value={critRule} onChange={(e) => setCritRule(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm text-[#23272E]">
              <input type="checkbox" checked={isCorrection} onChange={(e) => setIsCorrection(e.target.checked)} className="h-4 w-4 accent-[#B26337]" />
              Es una corrección a un supuesto equivocado de la IA
            </label>
            {isCorrection && (
              <div>
                <label className={labelCls}>¿Qué supuso mal la IA?</label>
                <input className={inputCls} value={wrongAssumption} onChange={(e) => setWrongAssumption(e.target.value)} />
              </div>
            )}
            <p className="text-xs text-[#5C626D]">El criterio se aplicará a las próximas clasificaciones del área del puesto.</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t border-[#E6CDBE] pt-3">
          <button
            type="button"
            disabled={!agreeAllowed || busy != null}
            title={agree ? '' : 'La IA aún no emitió veredicto'}
            onClick={() => agree && decide(agree)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#B26337] bg-white px-3.5 py-2 text-sm font-semibold text-[#B26337] hover:bg-[#FBF4EE] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check className="h-4 w-4" />
            De acuerdo con la IA{agree ? ` (${agree === 'Aprobado' ? 'Aprobar' : 'Rechazar'})` : ''}
          </button>
          {next.map((d) => (
            <button key={d} type="button" className={decisionBtnCls(d)} disabled={busy != null} onClick={() => decide(d)}>
              {busy === d && <Loader2 className="h-4 w-4 animate-spin" />}
              {DECISION_ACTION_LABEL[d]}
            </button>
          ))}
        </div>
        {c.evaluatedBy && (
          <p className="text-xs text-[#5C626D]">
            Última decisión: {c.evaluatedBy} · {formatDateTime(c.evaluatedAt)}
          </p>
        )}
      </div>

      <div className="rounded-lg border border-[#E2E4E8] p-4">
        <AiReportPanel c={c} state={state} onState={onState} />
      </div>
    </div>
  );
}

export const RequirementsSelectionModule: React.FC<Props> = ({ state, onState, initialCandidateId, initialPositionId }) => {
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'Abierto' | 'Cubierto' | 'Cancelado' | 'all'>('Abierto');
  const initialCand = initialCandidateId ? state.candidates.find((c) => c.id === initialCandidateId) : null;
  const [reqFilter, setReqFilter] = useState<string>(initialCand?.requirementId ?? 'all');
  const [posFilter, setPosFilter] = useState<string>(initialCand ? initialCand.positionId : initialPositionId ?? 'all');
  const [decisionFilter, setDecisionFilter] = useState<string>(initialCand ? 'all' : 'Pendiente de revisión');
  const [selectedId, setSelectedId] = useState<string>(initialCandidateId ?? '');

  useEffect(() => {
    if (initialCandidateId) setSelectedId(initialCandidateId);
  }, [initialCandidateId]);

  const reqs = useMemo(
    () => state.jobNeeds.filter((r) => statusFilter === 'all' || r.status === statusFilter),
    [state.jobNeeds, statusFilter],
  );

  const queue = useMemo(() => {
    const list = state.candidates.filter((c) => {
      if (reqFilter !== 'all' && c.requirementId !== reqFilter) return false;
      if (posFilter !== 'all' && c.positionId !== posFilter) return false;
      if (decisionFilter !== 'all' && c.decision !== decisionFilter) return false;
      return true;
    });
    return sortSelectionQueue(list);
  }, [state.candidates, reqFilter, posFilter, decisionFilter]);

  const selected = state.candidates.find((c) => c.id === selectedId) ?? queue[0] ?? null;

  const setReqStatus = async (id: string, status: 'Abierto' | 'Cancelado') => {
    try {
      const r = await apiFetch<{ state: AppState }>(`/api/requirements/${id}`, { method: 'PATCH', json: { status } });
      onState(r.state);
      toast(status === 'Cancelado' ? 'Requerimiento cancelado.' : 'Requerimiento reabierto.');
    } catch (e) {
      toast(errorMessage(e), 'error');
    }
  };

  const urgencyCls = (u: string) =>
    u === 'Urgente' ? TONE_CLASSES.danger : u === 'Media' ? TONE_CLASSES.warning : TONE_CLASSES.neutral;

  return (
    <div className="space-y-5">
      <section className={`${card} flex flex-wrap items-end justify-between gap-4 p-6`}>
        <div>
          <h1 className="font-display text-2xl font-bold text-[#23272E]">Requerimientos y Selección</h1>
          <p className="mt-1 text-sm text-[#5C626D]">
            Abre requerimientos desde el organigrama, revisa la bandeja ordenada por aptitud de la IA y registra la decisión humana.
          </p>
        </div>
        <button type="button" className={btnPrimary} onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" /> Nuevo requerimiento
        </button>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[320px_340px_minmax(0,1fr)]">
        {/* Requerimientos */}
        <section className={`${card} flex max-h-[760px] flex-col`}>
          <div className="space-y-3 border-b border-[#E2E4E8] p-4">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-1.5 text-sm font-bold text-[#23272E]">
                <ClipboardList className="h-4 w-4 text-[#B26337]" /> Requerimientos
              </h2>
              <select className="rounded-md border border-[#D4D7DD] px-2 py-1 text-xs" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)}>
                <option value="Abierto">Abiertos</option>
                <option value="Cubierto">Cubiertos</option>
                <option value="Cancelado">Cancelados</option>
                <option value="all">Todos</option>
              </select>
            </div>
            {showForm && <NewRequirementForm state={state} onState={onState} onClose={() => setShowForm(false)} initialPositionId={initialPositionId} />}
          </div>
          <div className="flex-1 overflow-auto">
            <button
              type="button"
              onClick={() => {
                setReqFilter('all');
                setPosFilter('all');
              }}
              className={`block w-full border-b border-[#F0F1F3] px-4 py-2.5 text-left text-sm ${reqFilter === 'all' && posFilter === 'all' ? 'bg-[#FBF4EE] font-semibold text-[#B26337]' : 'text-[#5C626D] hover:bg-[#F7F7F8]'}`}
            >
              Todas las postulaciones
            </button>
            {reqs.length === 0 && <p className="p-4 text-sm text-[#5C626D]">No hay requerimientos en esta vista.</p>}
            {reqs.map((r) => {
              const sel = reqFilter === r.id;
              const pct = r.vacancies ? Math.min(100, Math.round((r.filledCount / r.vacancies) * 100)) : 0;
              return (
                <div
                  key={r.id}
                  onClick={() => {
                    setReqFilter(r.id);
                    setPosFilter('all');
                  }}
                  className={`cursor-pointer border-b border-[#F0F1F3] px-4 py-3 ${sel ? 'bg-[#FBF4EE]' : 'hover:bg-[#F7F7F8]'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[#23272E]">{r.title}</p>
                      <p className="text-xs text-[#5C626D]">
                        {r.department} · desde {formatDate(r.openedAt)}
                      </p>
                    </div>
                    <Badge className={urgencyCls(r.urgency)}>{r.urgency}</Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#EFEFF1]">
                      <div className="h-full bg-[#B26337]" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="font-mono-tabular text-xs font-semibold text-[#23272E]">
                      Plazas: {r.filledCount}/{r.vacancies}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center justify-between">
                    <Badge
                      className={
                        r.status === 'Abierto' ? TONE_CLASSES.warning : r.status === 'Cubierto' ? TONE_CLASSES.success : TONE_CLASSES.neutral
                      }
                    >
                      {r.status}
                    </Badge>
                    {r.status === 'Abierto' ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(`¿Cancelar el requerimiento de ${r.title}?`)) void setReqStatus(r.id, 'Cancelado');
                        }}
                        className="text-xs font-semibold text-red-700 hover:underline"
                      >
                        Cancelar
                      </button>
                    ) : r.status === 'Cancelado' ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          void setReqStatus(r.id, 'Abierto');
                        }}
                        className="text-xs font-semibold text-[#B26337] hover:underline"
                      >
                        Reabrir
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Bandeja */}
        <section className={`${card} flex max-h-[760px] flex-col`}>
          <div className="space-y-2 border-b border-[#E2E4E8] p-4">
            <h2 className="flex items-center gap-1.5 text-sm font-bold text-[#23272E]">
              <MessageSquare className="h-4 w-4 text-[#B26337]" /> Bandeja de selección ({queue.length})
            </h2>
            <div className="grid grid-cols-2 gap-2">
              <select className="rounded-md border border-[#D4D7DD] px-2 py-1.5 text-xs" value={posFilter} onChange={(e) => { setPosFilter(e.target.value); setReqFilter('all'); }}>
                <option value="all">Todos los puestos</option>
                {state.positions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select className="rounded-md border border-[#D4D7DD] px-2 py-1.5 text-xs" value={decisionFilter} onChange={(e) => setDecisionFilter(e.target.value)}>
                <option value="all">Toda decisión</option>
                {['Pendiente de revisión', 'Aprobado', 'Rechazado', 'Contratado'].map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </div>
            <p className="text-[11px] text-[#9AA0A8]">Ordenada por aptitud IA y luego por índice global.</p>
          </div>
          <div className="flex-1 overflow-auto">
            {queue.length === 0 && <p className="p-4 text-sm text-[#5C626D]">No hay postulaciones en esta bandeja.</p>}
            {queue.map((c, i) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedId(c.id)}
                className={`block w-full border-b border-[#F0F1F3] px-4 py-3 text-left ${selected?.id === c.id ? 'bg-[#FBF4EE]' : 'hover:bg-[#F7F7F8]'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#23272E]">
                      <span className="mr-1 text-[#9AA0A8]">{i + 1}.</span>
                      {c.fullName}
                    </p>
                    <p className="truncate text-xs text-[#5C626D]">{c.targetRoleTitle}</p>
                  </div>
                  <span className="font-mono-tabular text-sm font-bold text-[#23272E]">{c.aiAptitudeScore ?? '—'}</span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {c.aiVerdict ? <Badge className={verdictBadgeClass(c.aiVerdict)}>{c.aiVerdict}</Badge> : <Badge className={TONE_CLASSES.neutral}>{c.aiStatus}</Badge>}
                  <Badge className={decisionBadgeClass(c.decision)}>{c.decision}</Badge>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Panel de decisión */}
        <section className={`${card} max-h-[760px] overflow-auto p-5`}>
          {selected ? (
            <DecisionPanel c={selected} state={state} onState={onState} />
          ) : (
            <p className="text-sm text-[#5C626D]">Selecciona una postulación de la bandeja.</p>
          )}
        </section>
      </div>
    </div>
  );
};

export default RequirementsSelectionModule;

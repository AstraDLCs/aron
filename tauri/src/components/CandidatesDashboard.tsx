import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  Eye,
  FileDown,
  FileText,
  Loader2,
  Pencil,
  RefreshCw,
  Search,
  Upload,
  UserPlus,
  Users,
  X,
  ArrowRight,
  Merge,
} from 'lucide-react';
import type { AppState, Candidate, ModuleProps } from '../types';
import { apiFetch, errorMessage, openRemoteFile } from '../api/client';
import { DownloadButton } from './common/DownloadButton';
import { toast } from './common/Toast';
import { UploadCvDialog } from './cv/UploadCvDialog';
import { HorizontalDistributionBars } from './ExecutiveCharts';
import {
  aiStatusTone,
  decisionBadgeClass,
  formatDate,
  formatDateTime,
  TONE_CLASSES,
  verdictBadgeClass,
  verdictLabel,
} from '../utils/labels';

export const card = 'rounded-xl border border-[#E2E4E8] bg-white';
export const inputCls =
  'w-full rounded-lg border border-[#D4D7DD] bg-white px-3 py-2 text-sm outline-none focus:border-[#B26337] focus:ring-2 focus:ring-[#B26337]/20';
export const labelCls = 'mb-1 block text-[11px] font-semibold uppercase tracking-wide text-[#5C626D]';
export const btnPrimary =
  'inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#B26337] px-3.5 py-2 text-sm font-semibold text-white hover:bg-[#99522B] disabled:opacity-60 transition-colors';
export const btnGhost =
  'inline-flex items-center justify-center gap-1.5 rounded-lg border border-[#D4D7DD] bg-white px-3.5 py-2 text-sm font-semibold text-[#23272E] hover:bg-[#EFEFF1] disabled:opacity-60 transition-colors';

export function Badge({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-semibold ${className}`}>
      {children}
    </span>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#23272E]/40 p-6">
      <div className={`my-6 w-full ${wide ? 'max-w-3xl' : 'max-w-xl'} rounded-2xl border border-[#E2E4E8] bg-white shadow-xl`}>
        <div className="flex items-center justify-between border-b border-[#E2E4E8] px-6 py-4">
          <h2 className="font-display text-lg font-bold text-[#23272E]">{title}</h2>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-[#5C626D] hover:bg-[#EFEFF1]" aria-label="Cerrar">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

const splitList = (s: string) =>
  s
    .split(/[,;\n]/)
    .map((x) => x.trim())
    .filter(Boolean);

function ManualCandidateForm({ state, onState, onClose }: { state: AppState; onState: (s: AppState) => void; onClose: () => void }) {
  const [positionId, setPositionId] = useState(state.positions[0]?.id ?? '');
  const reqs = state.jobNeeds.filter((r) => r.positionId === positionId && r.status === 'Abierto');
  const [requirementId, setRequirementId] = useState('');
  const [sourceId, setSourceId] = useState(state.jobBoards.find((b) => b.active)?.id ?? state.jobBoards[0]?.id ?? '');
  const [f, setF] = useState({
    fullName: '',
    career: '',
    documentId: '',
    email: '',
    phone: '',
    age: '',
    originLocation: '',
    university: '',
    yearsWorked: '',
    specifications: '',
    workHistorySummary: '',
    interviewNotes: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    setRequirementId(reqs.length === 1 ? reqs[0].id : '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!f.fullName.trim() || !f.career.trim()) return setError('Ingresa al menos el nombre completo y la carrera.');
    if (!positionId || !sourceId) return setError('Elige el puesto y la fuente.');
    setBusy(true);
    try {
      const r = await apiFetch<{ state: AppState }>('/api/candidates', {
        method: 'POST',
        json: {
          fullName: f.fullName.trim(),
          career: f.career.trim(),
          positionId,
          sourceId,
          requirementId: requirementId || null,
          age: f.age ? Number(f.age) : null,
          yearsWorked: f.yearsWorked ? Number(f.yearsWorked) : null,
          originLocation: f.originLocation.trim(),
          university: f.university.trim(),
          workHistorySummary: f.workHistorySummary.trim(),
          specifications: splitList(f.specifications),
          email: f.email.trim(),
          phone: f.phone.trim(),
          documentId: f.documentId.trim(),
          interviewNotes: f.interviewNotes.trim(),
        },
      });
      onState(r.state);
      toast('Candidato registrado.');
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Nuevo candidato (alta manual, sin CV)" onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={labelCls}>Puesto *</label>
            <select className={inputCls} value={positionId} onChange={(e) => setPositionId(e.target.value)}>
              {state.positions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.area}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Requerimiento</label>
            <select className={inputCls} value={requirementId} onChange={(e) => setRequirementId(e.target.value)}>
              <option value="">Sin requerimiento</option>
              {reqs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} · {r.filledCount}/{r.vacancies} plazas
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Fuente *</label>
            <select className={inputCls} value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
              {state.jobBoards.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Nombre completo *</label>
            <input className={inputCls} value={f.fullName} onChange={set('fullName')} />
          </div>
          <div>
            <label className={labelCls}>Carrera *</label>
            <input className={inputCls} value={f.career} onChange={set('career')} />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <div>
            <label className={labelCls}>DNI</label>
            <input className={inputCls} value={f.documentId} onChange={set('documentId')} />
          </div>
          <div>
            <label className={labelCls}>Edad</label>
            <input type="number" min={14} max={100} className={inputCls} value={f.age} onChange={set('age')} />
          </div>
          <div>
            <label className={labelCls}>Años de experiencia</label>
            <input type="number" min={0} max={60} className={inputCls} value={f.yearsWorked} onChange={set('yearsWorked')} />
          </div>
          <div>
            <label className={labelCls}>Procedencia</label>
            <input className={inputCls} value={f.originLocation} onChange={set('originLocation')} />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={labelCls}>Email</label>
            <input type="email" className={inputCls} value={f.email} onChange={set('email')} />
          </div>
          <div>
            <label className={labelCls}>Teléfono</label>
            <input className={inputCls} value={f.phone} onChange={set('phone')} />
          </div>
          <div>
            <label className={labelCls}>Universidad / Instituto</label>
            <input className={inputCls} value={f.university} onChange={set('university')} />
          </div>
        </div>
        <div>
          <label className={labelCls}>Especificaciones técnicas (separadas por coma)</label>
          <input className={inputCls} value={f.specifications} onChange={set('specifications')} placeholder="Licencia A-IIb, Trabajo en altura, …" />
        </div>
        <div>
          <label className={labelCls}>Experiencia previa</label>
          <textarea rows={3} className={inputCls} value={f.workHistorySummary} onChange={set('workHistorySummary')} />
        </div>
        <div>
          <label className={labelCls}>Notas de entrevista</label>
          <textarea rows={2} className={inputCls} value={f.interviewNotes} onChange={set('interviewNotes')} />
        </div>
        <div className="flex justify-end gap-2 border-t border-[#E2E4E8] pt-4">
          <button type="button" className={btnGhost} onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className={btnPrimary} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}Registrar candidato
          </button>
        </div>
      </form>
    </Modal>
  );
}

function PersonPanel({ c, state, onState }: { c: Candidate; state: AppState; onState: (s: AppState) => void }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const blank = () => ({
    firstNames: c.firstNames ?? '',
    lastNames: c.lastNames ?? '',
    documentId: c.documentId ?? '',
    email: c.email ?? '',
    phone: c.phone ?? '',
    age: c.age == null ? '' : String(c.age),
    originLocation: c.originLocation ?? '',
    university: c.university ?? '',
    career: c.career ?? '',
    yearsWorked: c.yearsWorked == null ? '' : String(c.yearsWorked),
    specifications: (c.specifications ?? []).join(', '),
    languages: (c.languages ?? []).join(', '),
    licenses: (c.licenses ?? []).join(', '),
    workHistorySummary: c.workHistorySummary ?? '',
  });
  const [f, setF] = useState(blank);
  useEffect(() => {
    setF(blank());
    setEditing(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c.id]);
  const set = (k: keyof ReturnType<typeof blank>) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setF({ ...f, [k]: e.target.value });

  const save = async () => {
    setBusy(true);
    try {
      const fullName = `${f.firstNames.trim()} ${f.lastNames.trim()}`.trim();
      const r = await apiFetch<{ state: AppState }>(`/api/persons/${c.personId}`, {
        method: 'PATCH',
        json: {
          firstNames: f.firstNames.trim(),
          lastNames: f.lastNames.trim(),
          ...(fullName ? { fullName } : {}),
          documentId: f.documentId.trim(),
          email: f.email.trim(),
          phone: f.phone.trim(),
          age: f.age ? Number(f.age) : null,
          originLocation: f.originLocation.trim(),
          university: f.university.trim(),
          career: f.career.trim(),
          yearsWorked: f.yearsWorked ? Number(f.yearsWorked) : null,
          specifications: splitList(f.specifications),
          languages: splitList(f.languages),
          licenses: splitList(f.licenses),
          workHistorySummary: f.workHistorySummary,
        },
      });
      onState(r.state);
      setEditing(false);
      toast('Datos de la persona actualizados.');
    } catch (e) {
      toast(errorMessage(e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const merge = async (otherCandidateId: string) => {
    const other = state.candidates.find((x) => x.id === otherCandidateId);
    if (!other) return;
    if (!window.confirm(`¿Unir a ${c.fullName} con ${other.fullName}? Las postulaciones quedarán en una sola persona.`)) return;
    try {
      const r = await apiFetch<{ state: AppState }>(`/api/persons/${c.personId}/merge`, {
        method: 'POST',
        json: { otherPersonId: other.personId },
      });
      onState(r.state);
      toast('Personas unidas.');
    } catch (e) {
      toast(errorMessage(e), 'error');
    }
  };

  const row = (label: string, value: React.ReactNode) => (
    <div className="flex justify-between gap-3 border-b border-[#F0F1F3] py-1.5 text-sm last:border-0">
      <span className="text-[#5C626D]">{label}</span>
      <span className="text-right font-medium text-[#23272E]">{value || '—'}</span>
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold uppercase tracking-wide text-[#5C626D]">Datos de la persona</h3>
        {!editing ? (
          <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-[#B26337] hover:underline" onClick={() => setEditing(true)}>
            <Pencil className="h-3.5 w-3.5" /> Editar
          </button>
        ) : (
          <div className="flex gap-2">
            <button type="button" className="text-xs font-semibold text-[#5C626D] hover:underline" onClick={() => setEditing(false)}>
              Cancelar
            </button>
            <button type="button" className="text-xs font-semibold text-[#B26337] hover:underline" onClick={save} disabled={busy}>
              {busy ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        )}
      </div>
      {!editing ? (
        <div>
          {row('DNI', c.documentId)}
          {row('Email', c.email)}
          {row('Teléfono', c.phone)}
          {row('Edad', c.age != null ? `${c.age} años` : '')}
          {row('Procedencia', c.originLocation)}
          {row('Formación', [c.career, c.university].filter(Boolean).join(' · '))}
          {row('Experiencia', c.yearsWorked != null ? `${c.yearsWorked} años` : '')}
          {row('Idiomas', (c.languages ?? []).join(', '))}
          {row('Licencias', (c.licenses ?? []).join(', '))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2.5">
          {(
            [
              ['firstNames', 'Nombres'],
              ['lastNames', 'Apellidos'],
              ['documentId', 'DNI'],
              ['email', 'Email'],
              ['phone', 'Teléfono'],
              ['age', 'Edad'],
              ['originLocation', 'Procedencia'],
              ['yearsWorked', 'Años de experiencia'],
              ['career', 'Carrera'],
              ['university', 'Universidad'],
              ['languages', 'Idiomas (coma)'],
              ['licenses', 'Licencias (coma)'],
            ] as const
          ).map(([k, l]) => (
            <div key={k}>
              <label className={labelCls}>{l}</label>
              <input className={inputCls} value={f[k]} onChange={set(k)} />
            </div>
          ))}
          <div className="col-span-2">
            <label className={labelCls}>Especificaciones (coma)</label>
            <input className={inputCls} value={f.specifications} onChange={set('specifications')} />
          </div>
          <div className="col-span-2">
            <label className={labelCls}>Experiencia previa</label>
            <textarea rows={3} className={inputCls} value={f.workHistorySummary} onChange={set('workHistorySummary')} />
          </div>
        </div>
      )}
      {(c.possibleSamePersonIds ?? []).length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="mb-2 font-semibold">Posible misma persona:</p>
          {c.possibleSamePersonIds.map((id) => {
            const o = state.candidates.find((x) => x.id === id || x.personId === id);
            if (!o) return null;
            return (
              <div key={id} className="flex items-center justify-between gap-2 py-1">
                <span>
                  {o.fullName} · {o.targetRoleTitle}
                </span>
                <button type="button" onClick={() => merge(o.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-[#B26337] hover:underline">
                  <Merge className="h-3.5 w-3.5" /> Unir
                </button>
              </div>
            );
          })}
        </div>
      )}
      {(c.otherApplications ?? []).length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[#5C626D]">Otras postulaciones</p>
          {c.otherApplications.map((o) => (
            <div key={o.candidateId} className="flex items-center justify-between py-1 text-sm">
              <span>{o.positionName}</span>
              <Badge className={decisionBadgeClass(o.decision)}>{o.decision}</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function AiBlock({ c }: { c: Candidate }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={TONE_CLASSES[aiStatusTone(c.aiStatus)]}>
          <Bot className="mr-1 h-3 w-3" />
          {c.aiStatus}
        </Badge>
        <Badge className={verdictBadgeClass(c.aiVerdict)}>{verdictLabel(c.aiVerdict)}</Badge>
        {c.aiAptitudeScore != null && <Badge className={TONE_CLASSES.neutral}>Aptitud IA: {c.aiAptitudeScore}/100</Badge>}
      </div>
      {c.aiError && <p className="text-sm text-red-700">Error IA: {c.aiError}</p>}
      {c.aiReason && <p className="text-sm text-[#23272E]">{c.aiReason}</p>}
      {(c.aiStrengths ?? []).length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Fortalezas</p>
          <ul className="ml-4 list-disc text-sm text-[#23272E]">
            {c.aiStrengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {(c.aiObservations ?? []).length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Observaciones</p>
          <ul className="ml-4 list-disc text-sm text-[#23272E]">
            {c.aiObservations.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {(c.aiAppliedCriteria ?? []).length > 0 && (
        <p className="text-xs text-[#5C626D]">Criterios aplicados: {c.aiAppliedCriteria.join(' · ')}</p>
      )}
      {c.aiModel && (
        <p className="text-[11px] text-[#9AA0A8]">
          {c.aiModel} · {formatDateTime(c.aiClassifiedAt)}
        </p>
      )}
    </div>
  );
}

export function CvActions({ c }: { c: Candidate }) {
  if (!c.cvFileId) return <p className="text-sm text-[#5C626D]">Sin CV adjunto (alta manual).</p>;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        className={btnGhost}
        onClick={() => openRemoteFile(`/api/cv-files/${c.cvFileId}/download`, c.cvFileName || 'CV.pdf').catch((e) => toast(errorMessage(e), 'error'))}
      >
        <Eye className="h-4 w-4" /> Ver CV
      </button>
      <DownloadButton path={`/api/cv-files/${c.cvFileId}/download`} fileName={c.cvFileName || 'CV.pdf'} label="Descargar CV" />
      {c.cvMissing && <Badge className={TONE_CLASSES.danger}>Archivo no encontrado en el servidor</Badge>}
    </div>
  );
}

export const CandidatesDashboard: React.FC<ModuleProps> = ({ state, onState, navigate }) => {
  const { candidates, jobBoards, positions, kpis } = state;
  const [searchTerm, setSearchTerm] = useState('');
  const [filterPosition, setFilterPosition] = useState('all');
  const [filterBoardId, setFilterBoardId] = useState('all');
  const [filterDecision, setFilterDecision] = useState('all');
  const [filterAiStatus, setFilterAiStatus] = useState('all');
  const [filterVerdict, setFilterVerdict] = useState('all');
  const [selectedId, setSelectedId] = useState<string>('');
  const [showUpload, setShowUpload] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [reclassifying, setReclassifying] = useState(false);

  const filtered = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return candidates.filter((c) => {
      if (filterPosition !== 'all' && c.positionId !== filterPosition) return false;
      if (filterBoardId !== 'all' && c.sourceBoardId !== filterBoardId) return false;
      if (filterDecision !== 'all' && c.decision !== filterDecision) return false;
      if (filterAiStatus !== 'all' && c.aiStatus !== filterAiStatus) return false;
      if (filterVerdict !== 'all' && (c.aiVerdict ?? 'none') !== filterVerdict) return false;
      if (!q) return true;
      const blob = `${c.fullName} ${c.documentId} ${c.email} ${c.originLocation} ${c.university} ${c.career} ${(c.specifications ?? []).join(' ')} ${c.targetRoleTitle}`.toLowerCase();
      return blob.includes(q);
    });
  }, [candidates, searchTerm, filterPosition, filterBoardId, filterDecision, filterAiStatus, filterVerdict]);

  const active = filtered.find((c) => c.id === selectedId) ?? filtered[0] ?? null;

  const funnel = useMemo(
    () => [
      { label: 'Contratado', value: candidates.filter((c) => c.decision === 'Contratado').length, accent: 'sage' as const },
      { label: 'Aprobado', value: candidates.filter((c) => c.decision === 'Aprobado').length, accent: 'orange' as const },
      { label: 'Pendiente de revisión', value: candidates.filter((c) => c.decision === 'Pendiente de revisión').length, accent: 'plomo' as const },
      { label: 'Rechazado', value: candidates.filter((c) => c.decision === 'Rechazado').length, accent: 'plomo' as const },
    ],
    [candidates],
  );
  const aiFunnel = useMemo(
    () => [
      { label: 'Pre-aprobado por IA', value: candidates.filter((c) => c.aiVerdict === 'Pre-aprobado').length, accent: 'sage' as const },
      { label: 'Pre-denegado por IA', value: candidates.filter((c) => c.aiVerdict === 'Pre-denegado').length, accent: 'plomo' as const },
      { label: 'En cola / procesando', value: candidates.filter((c) => c.aiStatus === 'En cola' || c.aiStatus === 'Procesando').length, accent: 'orange' as const },
      { label: 'Sin IA / sin texto / error', value: candidates.filter((c) => ['Sin IA', 'Sin texto', 'Error IA'].includes(c.aiStatus)).length, accent: 'plomo' as const },
    ],
    [candidates],
  );

  const reclassify = async (c: Candidate) => {
    setReclassifying(true);
    try {
      const r = await apiFetch<{ state: AppState }>(`/api/candidates/${c.id}/reclassify`, { method: 'POST' });
      if (r?.state) onState(r.state);
      toast('Postulación enviada a la cola de la IA.');
    } catch (e) {
      toast(errorMessage(e), 'error');
    } finally {
      setReclassifying(false);
    }
  };

  const kpiCell = (label: string, value: React.ReactNode, sub?: string) => (
    <div className="px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[#5C626D]">{label}</p>
      <p className="font-mono-tabular text-2xl font-bold text-[#23272E]">{value}</p>
      {sub && <p className="text-xs text-[#5C626D]">{sub}</p>}
    </div>
  );

  return (
    <div className="space-y-5">
      <section className={`${card} p-6`}>
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#E2E4E8] pb-5">
          <div>
            <h1 className="font-display text-2xl font-bold text-[#23272E]">Candidatos</h1>
            <p className="mt-1 text-sm text-[#5C626D]">Una fila por postulación: datos de la persona, clasificación de la IA y decisión humana.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <DownloadButton path="/api/reports/candidates-csv" fileName="Candidatos.csv" label="Exportar CSV" icon={<FileDown className="h-4 w-4" />} />
            <button type="button" className={btnGhost} onClick={() => setShowManual(true)}>
              <UserPlus className="h-4 w-4" /> Nuevo candidato
            </button>
            <button type="button" className={btnPrimary} onClick={() => setShowUpload(true)}>
              <Upload className="h-4 w-4" /> Subir CV
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 divide-x divide-[#E2E4E8] pt-3 md:grid-cols-5">
          {kpiCell('Postulaciones', candidates.length)}
          {kpiCell('Plazas cubiertas', `${kpis.filledVacancies}/${kpis.totalVacancies}`, `${kpis.coveragePercent}% de cobertura`)}
          {kpiCell('Aprobados + contratados', kpis.preselectedOrHired)}
          {kpiCell('Acuerdo con la IA', `${kpis.aiAgreementRate}%`)}
          {kpiCell('Días promedio de proceso', kpis.avgProcessDays)}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className={`${card} p-5`}>
          <h2 className="mb-3 text-sm font-bold text-[#23272E]">Decisión humana</h2>
          <HorizontalDistributionBars items={funnel} unitLabel="postulaciones" />
        </section>
        <section className={`${card} p-5`}>
          <h2 className="mb-3 text-sm font-bold text-[#23272E]">Clasificación de la IA</h2>
          <HorizontalDistributionBars items={aiFunnel} unitLabel="postulaciones" />
        </section>
      </div>

      <section className={`${card}`}>
        <div className="flex flex-wrap items-center gap-2 border-b border-[#E2E4E8] p-4">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[#9AA0A8]" />
            <input className={`${inputCls} pl-9`} placeholder="Buscar por nombre, DNI, carrera, especificación…" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
          </div>
          <select className={`${inputCls} w-auto`} value={filterPosition} onChange={(e) => setFilterPosition(e.target.value)}>
            <option value="all">Todos los puestos</option>
            {positions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select className={`${inputCls} w-auto`} value={filterBoardId} onChange={(e) => setFilterBoardId(e.target.value)}>
            <option value="all">Todas las fuentes</option>
            {jobBoards.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <select className={`${inputCls} w-auto`} value={filterDecision} onChange={(e) => setFilterDecision(e.target.value)}>
            <option value="all">Toda decisión</option>
            {['Pendiente de revisión', 'Aprobado', 'Rechazado', 'Contratado'].map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
          <select className={`${inputCls} w-auto`} value={filterAiStatus} onChange={(e) => setFilterAiStatus(e.target.value)}>
            <option value="all">Todo estado IA</option>
            {['En cola', 'Procesando', 'Clasificado', 'Error IA', 'Sin texto', 'Sin IA'].map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
          <select className={`${inputCls} w-auto`} value={filterVerdict} onChange={(e) => setFilterVerdict(e.target.value)}>
            <option value="all">Todo veredicto</option>
            <option value="Pre-aprobado">Pre-aprobado</option>
            <option value="Pre-denegado">Pre-denegado</option>
            <option value="none">Sin veredicto</option>
          </select>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
          <div className="max-h-[640px] overflow-auto border-r border-[#E2E4E8]">
            {filtered.length === 0 ? (
              <div className="p-10 text-center text-sm text-[#5C626D]">
                <Users className="mx-auto mb-2 h-8 w-8 text-[#C9CDD3]" />
                No hay postulaciones con estos filtros. Usa “Subir CV” para registrar candidatos.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-[#F7F7F8] text-left text-[11px] uppercase tracking-wide text-[#5C626D]">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Candidato</th>
                    <th className="px-3 py-2.5 font-semibold">Puesto / fuente</th>
                    <th className="px-3 py-2.5 font-semibold">IA</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Índice</th>
                    <th className="px-3 py-2.5 font-semibold">Decisión</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => {
                    const sel = active?.id === c.id;
                    return (
                      <tr
                        key={c.id}
                        onClick={() => setSelectedId(c.id)}
                        className={`cursor-pointer border-t border-[#F0F1F3] ${sel ? 'bg-[#FBF4EE]' : 'hover:bg-[#F7F7F8]'}`}
                      >
                        <td className="px-4 py-2.5">
                          <p className="font-semibold text-[#23272E]">{c.fullName || 'Sin nombre'}</p>
                          <p className="text-xs text-[#5C626D]">
                            {c.career || '—'}
                            {c.yearsWorked != null && ` · ${c.yearsWorked} años`}
                          </p>
                        </td>
                        <td className="px-3 py-2.5">
                          <p className="text-[#23272E]">{c.targetRoleTitle}</p>
                          <p className="text-xs text-[#5C626D]">{c.sourceBoardName}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-col items-start gap-1">
                            <Badge className={TONE_CLASSES[aiStatusTone(c.aiStatus)]}>{c.aiStatus}</Badge>
                            {c.aiVerdict && (
                              <Badge className={verdictBadgeClass(c.aiVerdict)}>
                                {c.aiVerdict}
                                {c.aiAptitudeScore != null && ` · ${c.aiAptitudeScore}`}
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono-tabular font-semibold">{c.metricReport?.overallScore ?? '—'}</td>
                        <td className="px-3 py-2.5">
                          <Badge className={decisionBadgeClass(c.decision)}>{c.decision}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          <div className="max-h-[640px] overflow-auto p-5">
            {!active ? (
              <p className="text-sm text-[#5C626D]">Selecciona una postulación para ver su ficha.</p>
            ) : (
              <div className="space-y-5">
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="font-display text-xl font-bold text-[#23272E]">{active.fullName}</h2>
                      <p className="text-sm text-[#5C626D]">
                        {active.targetRoleTitle} · {active.sourceBoardName} · ingresó el {formatDate(active.createdAt)}
                      </p>
                    </div>
                    <Badge className={decisionBadgeClass(active.decision)}>{active.decision}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" className={btnPrimary} onClick={() => navigate('requerimientos', { candidateId: active.id })}>
                      Decidir en Selección <ArrowRight className="h-4 w-4" />
                    </button>
                    <DownloadButton
                      path={`/api/reports/candidate/${active.id}/doc`}
                      fileName={`Ficha_${active.fullName.replace(/\s+/g, '_')}.doc`}
                      label="Ficha Word"
                      icon={<FileText className="h-4 w-4" />}
                    />
                    <button type="button" className={btnGhost} disabled={reclassifying} onClick={() => reclassify(active)}>
                      {reclassifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Reclasificar con IA
                    </button>
                  </div>
                </div>

                <div className="rounded-lg border border-[#E2E4E8] p-4">
                  <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-[#5C626D]">CV</h3>
                  {active.cvFileName && <p className="mb-2 text-sm text-[#23272E]">{active.cvFileName}</p>}
                  <CvActions c={active} />
                </div>

                <div className="rounded-lg border border-[#E2E4E8] p-4">
                  <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-[#5C626D]">Clasificación de la IA</h3>
                  <AiBlock c={active} />
                </div>

                <div className="rounded-lg border border-[#E2E4E8] p-4">
                  <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-[#5C626D]">Índice global</h3>
                  <div className="grid grid-cols-5 gap-2 text-center">
                    {(
                      [
                        ['Técnico', active.metricReport?.technicalSpecsScore],
                        ['Experiencia', active.metricReport?.experienceScore],
                        ['Formación', active.metricReport?.educationCareerScore],
                        ['Psicológico', active.metricReport?.psychScore],
                        ['Global', active.metricReport?.overallScore],
                      ] as const
                    ).map(([l, v]) => (
                      <div key={l} className="rounded-lg bg-[#F7F7F8] p-2">
                        <p className="text-[10px] uppercase text-[#5C626D]">{l}</p>
                        <p className="font-mono-tabular text-lg font-bold">{v ?? '—'}</p>
                      </div>
                    ))}
                  </div>
                  {active.metricReport?.fitVerdict && <p className="mt-2 text-sm font-semibold text-[#B26337]">{active.metricReport.fitVerdict}</p>}
                </div>

                <div className="rounded-lg border border-[#E2E4E8] p-4">
                  <PersonPanel c={active} state={state} onState={onState} />
                </div>

                {(active.specifications ?? []).length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[#5C626D]">Especificaciones</p>
                    <div className="flex flex-wrap gap-1.5">
                      {active.specifications.map((s) => (
                        <Badge key={s} className={TONE_CLASSES.neutral}>
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {active.workHistorySummary && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[#5C626D]">Experiencia previa</p>
                    <p className="whitespace-pre-wrap text-sm text-[#23272E]">{active.workHistorySummary}</p>
                  </div>
                )}
                {active.managerNotes && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[#5C626D]">Notas del evaluador</p>
                    <p className="text-sm text-[#23272E]">
                      {active.managerNotes} {active.evaluatedBy && <span className="text-[#5C626D]">— {active.evaluatedBy}, {formatDateTime(active.evaluatedAt)}</span>}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {showUpload && <UploadCvDialog open={showUpload} state={state} onDone={onState} onClose={() => setShowUpload(false)} />}
      {showManual && <ManualCandidateForm state={state} onState={onState} onClose={() => setShowManual(false)} />}
    </div>
  );
};

export default CandidatesDashboard;

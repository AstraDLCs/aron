import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Copy, FilePlus2, FileText, Loader2, Ban, Trash2, Upload, XCircle } from 'lucide-react';
import type { AppState } from '../../types';
import { apiFetch, errorMessage, fileNameFromPath, pickFiles, readLocalFile, mimeFromName } from '../../api/client';
import { positionPath } from '../../utils/orgTree';
import { apiErrorCode, MAX_CV_BYTES } from '../../sync/runSync';
import { Button, Field, Modal, Notice, formatDateTime, inputClass } from './ui';

export interface UploadCvDialogProps {
  open: boolean;
  state: AppState;
  initialPositionId?: string;
  initialSourceId?: string;
  onDone: (s: AppState) => void;
  onClose: () => void;
}

type FileStatus = 'pendiente' | 'subiendo' | 'creado' | 'repetido' | 'eliminado' | 'error';

interface FileRow {
  path: string;
  name: string;
  status: FileStatus;
  message?: string;
}

const ALLOWED = ['pdf', 'docx', 'txt', 'rtf'];

function describeExisting(detail: unknown): string {
  const d = detail as { message?: string; existing?: Record<string, string> | null } | undefined;
  const ex = d?.existing;
  if (!ex) return d?.message ?? '';
  if (ex.uploadedBy || ex.uploadedAt) {
    return `${d?.message ?? 'Ya existe'} — subido por ${ex.uploadedBy ?? '—'} el ${formatDateTime(ex.uploadedAt)}${
      ex.path ? ` (${ex.path})` : ''
    }`;
  }
  if (ex.deletedBy || ex.deletedAt) {
    return `${d?.message ?? 'Eliminado antes'} — eliminado por ${ex.deletedBy ?? '—'} el ${formatDateTime(ex.deletedAt)}`;
  }
  return d?.message ?? '';
}

export function UploadCvDialog({ open, state, initialPositionId, initialSourceId, onDone, onClose }: UploadCvDialogProps) {
  const positions = state.positions;
  const sources = useMemo(() => state.jobBoards.filter((s) => s.active || s.id === initialSourceId), [state.jobBoards, initialSourceId]);
  const [positionId, setPositionId] = useState(initialPositionId ?? '');
  const [sourceId, setSourceId] = useState(initialSourceId ?? '');
  const [requirementId, setRequirementId] = useState('');
  const [files, setFiles] = useState<FileRow[]>([]);
  const [running, setRunning] = useState(false);
  const [latest, setLatest] = useState<AppState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPositionId(initialPositionId ?? '');
      setSourceId(initialSourceId ?? '');
      setRequirementId('');
      setFiles([]);
      setLatest(null);
      setError(null);
    }
  }, [open, initialPositionId, initialSourceId]);

  const positionOptions = useMemo(
    () =>
      positions
        .map((p) => ({ id: p.id, label: positionPath(p.id, positions), open: p.openRequirementsCount }))
        .sort((a, b) => a.label.localeCompare(b.label, 'es')),
    [positions],
  );
  const openReqs = useMemo(
    () => state.jobNeeds.filter((r) => r.positionId === positionId && r.status === 'Abierto'),
    [state.jobNeeds, positionId],
  );

  useEffect(() => {
    setRequirementId(openReqs.length === 1 ? openReqs[0].id : '');
  }, [positionId, openReqs]);

  if (!open) return null;

  const done = files.filter((f) => f.status !== 'pendiente' && f.status !== 'subiendo').length;
  const pending = files.filter((f) => f.status === 'pendiente');
  const finished = files.length > 0 && pending.length === 0 && !running;

  async function choose() {
    setError(null);
    try {
      const paths = await pickFiles({ multiple: true, name: 'CV', extensions: ALLOWED });
      if (!paths.length) return;
      setFiles((prev) => {
        const known = new Set(prev.map((f) => f.path));
        const added = paths
          .filter((p) => !known.has(p))
          .map((p) => {
            const name = fileNameFromPath(p);
            const ext = name.split('.').pop()?.toLowerCase() ?? '';
            return ALLOWED.includes(ext)
              ? { path: p, name, status: 'pendiente' as FileStatus }
              : { path: p, name, status: 'error' as FileStatus, message: 'Formato no admitido (solo PDF, DOCX, TXT o RTF)' };
          });
        return [...prev, ...added];
      });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  function update(path: string, patch: Partial<FileRow>) {
    setFiles((prev) => prev.map((f) => (f.path === path ? { ...f, ...patch } : f)));
  }

  async function upload() {
    setError(null);
    if (!positionId) return setError('Elige el puesto al que postulan estos CV.');
    if (!sourceId) return setError('Elige la fuente de donde vienen los CV.');
    if (openReqs.length > 1 && !requirementId) return setError('Este puesto tiene varios requerimientos abiertos: elige uno.');
    setRunning(true);
    let last: AppState | null = latest;
    for (const f of files.filter((x) => x.status === 'pendiente')) {
      update(f.path, { status: 'subiendo' });
      try {
        const bytes = await readLocalFile(f.path);
        if (bytes.byteLength > MAX_CV_BYTES) throw new Error('El archivo supera el máximo de 15 MB');
        const form = new FormData();
        form.append('file', new File([bytes as BlobPart], f.name, { type: mimeFromName(f.name) }));
        form.append('positionId', positionId);
        form.append('sourceId', sourceId);
        if (requirementId) form.append('requirementId', requirementId);
        form.append('origin', 'app');
        const res = await apiFetch<{ result: { message?: string }; state: AppState }>('/api/cv-files', {
          method: 'POST',
          form,
        });
        last = res.state;
        setLatest(res.state);
        update(f.path, { status: 'creado', message: res.result?.message || 'CV registrado' });
      } catch (e) {
        const status = (e as { status?: number })?.status;
        const code = apiErrorCode(e);
        const detail = (e as { detail?: unknown })?.detail;
        if (status === 409 && code === 'deleted_before') {
          update(f.path, { status: 'eliminado', message: describeExisting(detail) || errorMessage(e) });
        } else if (status === 409) {
          update(f.path, { status: 'repetido', message: describeExisting(detail) || errorMessage(e) });
        } else {
          update(f.path, { status: 'error', message: typeof e === 'string' ? e : errorMessage(e) });
        }
      }
    }
    setRunning(false);
    if (last) setLatest(last);
  }

  function close() {
    if (running) return;
    if (latest) onDone(latest);
    else onClose();
  }

  const counts = {
    creado: files.filter((f) => f.status === 'creado').length,
    repetido: files.filter((f) => f.status === 'repetido').length,
    eliminado: files.filter((f) => f.status === 'eliminado').length,
    error: files.filter((f) => f.status === 'error').length,
  };

  return (
    <Modal
      title="Subir CVs"
      subtitle="Clasifica los archivos por puesto y fuente. Se guardan en rrhh/<puesto>/<fuente>/ del servidor."
      onClose={close}
      width="max-w-2xl"
      footer={
        <>
          <span className="mr-auto text-xs text-[#5C626D]">
            {files.length > 0 && `${done} de ${files.length} procesados`}
          </span>
          <Button onClick={close} disabled={running}>
            {finished ? 'Listo' : 'Cancelar'}
          </Button>
          <Button
            variant="primary"
            icon={<Upload className="h-4 w-4" />}
            onClick={upload}
            loading={running}
            disabled={pending.length === 0}
          >
            {pending.length > 0 ? `Subir ${pending.length} archivo${pending.length === 1 ? '' : 's'}` : 'Subir'}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Puesto *">
          <select className={inputClass} value={positionId} onChange={(e) => setPositionId(e.target.value)} disabled={running}>
            <option value="">Elige un puesto…</option>
            {positionOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
                {p.open > 0 ? ` (${p.open} req. abierto${p.open === 1 ? '' : 's'})` : ''}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Fuente *">
          <select className={inputClass} value={sourceId} onChange={(e) => setSourceId(e.target.value)} disabled={running}>
            <option value="">Elige una fuente…</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        {positionId && openReqs.length > 1 && (
          <Field label="Requerimiento *" className="sm:col-span-2" hint="El puesto tiene varios requerimientos abiertos.">
            <select
              className={inputClass}
              value={requirementId}
              onChange={(e) => setRequirementId(e.target.value)}
              disabled={running}
            >
              <option value="">Elige un requerimiento…</option>
              {openReqs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} · {r.filledCount}/{r.vacancies} plazas · {r.urgency} · abierto el {formatDateTime(r.openedAt)}
                </option>
              ))}
            </select>
          </Field>
        )}
        {positionId && openReqs.length === 0 && (
          <div className="sm:col-span-2">
            <Notice kind="info">Este puesto no tiene requerimientos abiertos: el CV quedará registrado sin requerimiento.</Notice>
          </div>
        )}
      </div>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold text-[#23272E]">Archivos (PDF, DOCX, TXT o RTF; máx. 15 MB)</span>
          <Button size="sm" icon={<FilePlus2 className="h-3.5 w-3.5" />} onClick={choose} disabled={running}>
            Elegir archivos…
          </Button>
        </div>
        {files.length === 0 ? (
          <button
            onClick={choose}
            className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-[#D8DCE0] bg-[#F7F7F8] px-4 py-8 text-center hover:border-[#E6CDBE] hover:bg-[#FBF4EE]"
          >
            <Upload className="h-6 w-6 text-[#B26337]" />
            <span className="mt-2 text-sm font-semibold text-[#23272E]">Haz clic para elegir uno o varios CV</span>
            <span className="text-xs text-[#5C626D]">Se detectan automáticamente los repetidos</span>
          </button>
        ) : (
          <ul className="divide-y divide-[#EFEFF1] rounded-lg border border-[#E2E4E8]">
            {files.map((f) => (
              <li key={f.path} className="flex items-start gap-3 px-3 py-2.5">
                <span className="mt-0.5">
                  {f.status === 'pendiente' && <FileText className="h-4 w-4 text-[#9AA0A8]" />}
                  {f.status === 'subiendo' && <Loader2 className="h-4 w-4 animate-spin text-[#B26337]" />}
                  {f.status === 'creado' && <CheckCircle2 className="h-4 w-4 text-[#2E6B4B]" />}
                  {f.status === 'repetido' && <Copy className="h-4 w-4 text-[#8A6100]" />}
                  {f.status === 'eliminado' && <Ban className="h-4 w-4 text-[#8C4722]" />}
                  {f.status === 'error' && <XCircle className="h-4 w-4 text-[#B42318]" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-[#23272E]" title={f.path}>
                    {f.name}
                  </div>
                  <div
                    className={`text-xs ${
                      f.status === 'error'
                        ? 'text-[#B42318]'
                        : f.status === 'creado'
                          ? 'text-[#2E6B4B]'
                          : f.status === 'repetido' || f.status === 'eliminado'
                            ? 'text-[#8C4722]'
                            : 'text-[#5C626D]'
                    }`}
                  >
                    {f.status === 'pendiente' && 'Listo para subir'}
                    {f.status === 'subiendo' && 'Subiendo…'}
                    {f.status === 'creado' && `Creado. ${f.message ?? ''}`}
                    {f.status === 'repetido' && `Repetido: ${f.message ?? 'ya existe en este puesto'}`}
                    {f.status === 'eliminado' && `Eliminado antes: ${f.message ?? 'no se vuelve a importar'}`}
                    {f.status === 'error' && `Error: ${f.message ?? ''}`}
                  </div>
                </div>
                {f.status === 'pendiente' && !running && (
                  <button
                    onClick={() => setFiles((prev) => prev.filter((x) => x.path !== f.path))}
                    className="rounded p-1 text-[#9AA0A8] hover:bg-[#EFEFF1] hover:text-[#B42318]"
                    title="Quitar de la lista"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {finished && (
        <div className="mt-4">
          <Notice kind={counts.error ? 'warning' : 'success'}>
            {counts.creado} creados · {counts.repetido} repetidos · {counts.eliminado} eliminados antes · {counts.error} con
            error. Los CV nuevos entran a la cola de la IA.
          </Notice>
        </div>
      )}
      {error && (
        <div className="mt-4">
          <Notice kind="error">{error}</Notice>
        </div>
      )}
    </Modal>
  );
}

export default UploadCvDialog;

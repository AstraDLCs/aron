import { useEffect, useMemo, useState } from 'react';
import {
  Ban,
  ChevronDown,
  ChevronRight,
  Eye,
  Folder,
  FolderInput,
  FolderOpen,
  FolderPlus,
  FolderSync,
  HardDrive,
  MoveRight,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  FileText,
  PauseCircle,
} from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import type { AppState, AppSection, Candidate } from '../../types';
import { apiFetch, errorMessage, openRemoteFile } from '../../api/client';
import { loadConfig, type AppConfig } from '../../api/config';
import { runSync, summaryLine, anyErrorMessage, type SyncOrigin, type SyncSummary } from '../../sync/runSync';
import { loadLastSummary, saveLastSummary, SYNC_EVENT } from '../../sync/autoSync';
import { positionPath } from '../../utils/orgTree';
import { Badge, Button, Card, ConfirmDialog, EmptyState, Field, Modal, Notice, SectionHeader, formatDateTime, inputClass } from './ui';
import { UploadCvDialog } from './UploadCvDialog';
import { SyncSummaryDialog } from './SyncSummaryDialog';

export interface CvFolderModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

type Selection = { positionId: string | null; sourceId: string | null };

const ORIGIN_LABEL: Record<string, string> = {
  app: 'App',
  importacion: 'Importación',
  sync_local: 'Carpeta local',
  carpeta_servidor: 'Carpeta del servidor',
};

export function aiTone(status: string): 'green' | 'blue' | 'amber' | 'red' | 'neutral' {
  if (status === 'Clasificado') return 'green';
  if (status === 'En cola') return 'blue';
  if (status === 'Procesando') return 'amber';
  if (status === 'Error IA') return 'red';
  return 'neutral';
}

export function decisionTone(d: string): 'green' | 'red' | 'accent' | 'neutral' {
  if (d === 'Aprobado') return 'green';
  if (d === 'Rechazado') return 'red';
  if (d === 'Contratado') return 'accent';
  return 'neutral';
}

export function CvFolderModule({ state, onState, refresh, navigate }: CvFolderModuleProps) {
  const [tab, setTab] = useState<'archivos' | 'eliminados'>('archivos');
  const [sel, setSel] = useState<Selection>({ positionId: null, sourceId: null });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [onlyWithCv, setOnlyWithCv] = useState(true);
  const [query, setQuery] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [moving, setMoving] = useState<Candidate | null>(null);
  const [deleting, setDeleting] = useState<Candidate | null>(null);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [syncing, setSyncing] = useState<{ label: string; done: number; total: number } | null>(null);
  const [summary, setSummary] = useState<SyncSummary | null>(null);
  const [lastSummary, setLastSummary] = useState<SyncSummary | null>(() => loadLastSummary());
  const [notice, setNotice] = useState<{ kind: 'success' | 'error' | 'info' | 'warning'; text: string } | null>(null);
  const [unblocking, setUnblocking] = useState<string | null>(null);

  useEffect(() => {
    loadConfig()
      .then(setConfig)
      .catch(() => setConfig(null));
    const onSync = (e: Event) => setLastSummary((e as CustomEvent<SyncSummary>).detail);
    window.addEventListener(SYNC_EVENT, onSync);
    return () => window.removeEventListener(SYNC_EVENT, onSync);
  }, []);

  const files = useMemo(() => state.candidates.filter((c) => !!c.cvFileId), [state.candidates]);
  const positionsById = useMemo(() => new Map(state.positions.map((p) => [p.id, p])), [state.positions]);
  const sourcesById = useMemo(() => new Map(state.jobBoards.map((s) => [s.id, s])), [state.jobBoards]);

  const counts = useMemo(() => {
    const byPos = new Map<string, number>();
    const byPosSrc = new Map<string, number>();
    for (const c of files) {
      byPos.set(c.positionId, (byPos.get(c.positionId) ?? 0) + 1);
      const k = `${c.positionId}|${c.sourceBoardId}`;
      byPosSrc.set(k, (byPosSrc.get(k) ?? 0) + 1);
    }
    return { byPos, byPosSrc };
  }, [files]);

  const treePositions = useMemo(
    () =>
      state.positions
        .filter((p) => !onlyWithCv || (counts.byPos.get(p.id) ?? 0) > 0 || p.openRequirementsCount > 0)
        .sort((a, b) => a.name.localeCompare(b.name, 'es')),
    [state.positions, counts, onlyWithCv],
  );

  const visibleFiles = useMemo(() => {
    const q = query.trim().toLowerCase();
    return files
      .filter((c) => !sel.positionId || c.positionId === sel.positionId)
      .filter((c) => !sel.sourceId || c.sourceBoardId === sel.sourceId)
      .filter(
        (c) =>
          !q ||
          `${c.cvFileName ?? ''} ${c.fullName} ${c.targetRoleTitle} ${c.sourceBoardName} ${c.cvUploadedBy ?? ''}`
            .toLowerCase()
            .includes(q),
      )
      .sort((a, b) => (b.cvUploadedAt ?? b.createdAt ?? '').localeCompare(a.cvUploadedAt ?? a.createdAt ?? ''));
  }, [files, sel, query]);

  const selectedLabel = sel.positionId
    ? `rrhh/${positionsById.get(sel.positionId)?.folderName ?? '?'}/${sel.sourceId ? `${sourcesById.get(sel.sourceId)?.folderName ?? '?'}/` : ''}`
    : 'rrhh/';

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function doSync(root: string, origin: SyncOrigin) {
    setSyncing({ label: origin === 'importacion' ? 'Importando carpeta' : 'Sincronizando carpeta local', done: 0, total: 0 });
    setNotice(null);
    try {
      const s = await runSync({
        root,
        origin,
        positions: state.positions,
        sources: state.jobBoards,
        onProgress: (done, total) => setSyncing((prev) => (prev ? { ...prev, done, total } : prev)),
      });
      saveLastSummary(s);
      setLastSummary(s);
      setSummary(s);
      try {
        await refresh();
      } catch {
        /* la foto se refresca sola */
      }
    } catch (e) {
      setNotice({ kind: 'error', text: anyErrorMessage(e) });
    } finally {
      setSyncing(null);
    }
  }

  async function importFolder() {
    try {
      const dir = await openDialog({ directory: true, multiple: false, title: 'Elige la carpeta a importar (rrhh/puesto/fuente)' });
      if (!dir || Array.isArray(dir)) return;
      await doSync(dir, 'importacion');
    } catch (e) {
      setNotice({ kind: 'error', text: anyErrorMessage(e) });
    }
  }

  async function syncNow() {
    const cfg = await loadConfig().catch(() => null);
    setConfig(cfg);
    if (!cfg?.cvFolder) {
      setNotice({ kind: 'info', text: 'Primero elige la carpeta local de CVs en Configuración.' });
      navigate('configuracion');
      return;
    }
    await doSync(cfg.cvFolder, 'sync_local');
  }

  async function createStructure() {
    setNotice(null);
    try {
      let root = (await loadConfig().catch(() => null))?.cvFolder ?? null;
      if (!root) {
        const dir = await openDialog({ directory: true, multiple: false, title: 'Elige dónde crear la estructura de carpetas' });
        if (!dir || Array.isArray(dir)) return;
        root = dir;
      }
      const activeSources = state.jobBoards.filter((s) => s.active);
      const targets = state.positions.filter((p) => p.openRequirementsCount > 0);
      if (!targets.length || !activeSources.length) {
        setNotice({
          kind: 'warning',
          text: 'No hay puestos con requerimientos abiertos o no hay fuentes activas: no hay carpetas que crear.',
        });
        return;
      }
      const folders: [string, string][] = [];
      for (const p of targets) for (const s of activeSources) folders.push([p.folderName, s.folderName]);
      // Si la carpeta ya tiene una subcarpeta "rrhh", la sincronización lee desde ahí: se crea dentro de ella.
      try {
        const scan = await invoke<{ rootUsed: string }>('scan_cv_folder', { root });
        if (scan?.rootUsed) root = scan.rootUsed;
      } catch {
        /* la carpeta aún no existe: se crea */
      }
      const created = await invoke<number>('create_folder_structure', { root, folders });
      setNotice({
        kind: 'success',
        text: `Estructura lista en ${root}: ${created} carpeta${created === 1 ? '' : 's'} nueva${created === 1 ? '' : 's'} (${targets.length} puestos × ${activeSources.length} fuentes).`,
      });
    } catch (e) {
      setNotice({ kind: 'error', text: `No se pudo crear la estructura: ${anyErrorMessage(e)}` });
    }
  }

  async function doDelete() {
    if (!deleting?.cvFileId) return;
    setBusy(true);
    setDialogError(null);
    try {
      const res = await apiFetch<{ state: AppState }>(`/api/cv-files/${deleting.cvFileId}`, { method: 'DELETE' });
      onState(res.state);
      setNotice({ kind: 'success', text: `Se eliminó el CV de ${deleting.fullName}.` });
      setDeleting(null);
    } catch (e) {
      setDialogError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function unblock(id: string) {
    setUnblocking(id);
    try {
      const res = await apiFetch<{ state: AppState }>(`/api/cv-files/blocked/${id}`, { method: 'DELETE' });
      onState(res.state);
      setNotice({ kind: 'success', text: 'Listo: ese CV se podrá volver a importar en ese puesto.' });
    } catch (e) {
      setNotice({ kind: 'error', text: errorMessage(e) });
    } finally {
      setUnblocking(null);
    }
  }

  async function viewCv(c: Candidate) {
    try {
      await openRemoteFile(`/api/cv-files/${c.cvFileId}/download`, c.cvFileName || `CV_${c.fullName}.pdf`);
    } catch (e) {
      setNotice({ kind: 'error', text: errorMessage(e) });
    }
  }

  const blocked = state.blockedCvFiles ?? [];
  const paused = state.aiQueue?.pausedUntil;

  return (
    <div className="space-y-5">
      <SectionHeader
        icon={<FolderOpen className="h-5 w-5" />}
        title="Carpeta de CVs"
        subtitle="Todos los CV del servidor ordenados en rrhh/puesto/fuente. Sube, importa o sincroniza tu carpeta local."
        actions={
          <>
            <Button variant="primary" icon={<Upload className="h-4 w-4" />} onClick={() => setUploadOpen(true)} disabled={!!syncing}>
              Subir CVs
            </Button>
            <Button icon={<FolderInput className="h-4 w-4" />} onClick={importFolder} disabled={!!syncing}>
              Importar carpeta
            </Button>
            <Button icon={<FolderSync className="h-4 w-4" />} onClick={syncNow} disabled={!!syncing}>
              Sincronizar ahora
            </Button>
            <Button icon={<FolderPlus className="h-4 w-4" />} onClick={createStructure} disabled={!!syncing}>
              Crear estructura local
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[#E2E4E8] bg-white px-3.5 py-2.5 text-sm">
        <HardDrive className="h-4 w-4 text-[#5C626D]" />
        <span className="text-[#5C626D]">Carpeta local:</span>
        {config?.cvFolder ? (
          <>
            <code className="font-mono-tabular text-xs text-[#23272E]">{config.cvFolder}</code>
            <Badge tone={config.syncOnOpen ? 'green' : 'neutral'}>
              {config.syncOnOpen ? 'Se sincroniza al abrir' : 'Sincronización manual'}
            </Badge>
          </>
        ) : (
          <span className="text-[#9AA0A8]">no configurada</span>
        )}
        <button onClick={() => navigate('configuracion')} className="ml-auto text-xs font-semibold text-[#B26337] hover:underline">
          Cambiar en Configuración
        </button>
      </div>

      {syncing && (
        <Card className="px-4 py-3">
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-[#23272E]">{syncing.label}…</span>
            <span className="font-mono-tabular text-xs text-[#5C626D]">
              {syncing.total ? `${syncing.done} / ${syncing.total} archivos` : 'Revisando archivos…'}
            </span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[#EFEFF1]">
            <div
              className="h-full rounded-full bg-[#B26337] transition-all"
              style={{ width: syncing.total ? `${Math.round((syncing.done / syncing.total) * 100)}%` : '15%' }}
            />
          </div>
        </Card>
      )}

      {notice && (
        <Notice kind={notice.kind} onDismiss={() => setNotice(null)}>
          {notice.text}
        </Notice>
      )}

      {paused && (
        <Notice kind="warning">
          <span className="inline-flex items-center gap-1.5">
            <PauseCircle className="h-4 w-4" /> La cola de la IA está en pausa hasta {formatDateTime(paused)} (límite de
            consultas de OpenRouter). Los CV quedan en cola y se clasificarán después.
          </span>
        </Notice>
      )}

      {lastSummary && !syncing && (
        <Notice
          kind={lastSummary.errors.length ? 'warning' : 'info'}
          action={
            <button onClick={() => setSummary(lastSummary)} className="text-xs font-semibold text-[#B26337] hover:underline">
              Ver detalle
            </button>
          }
          onDismiss={() => setLastSummary(null)}
        >
          Última {lastSummary.origin === 'importacion' ? 'importación' : 'sincronización'} ({formatDateTime(lastSummary.finishedAt)}):{' '}
          {summaryLine(lastSummary)}.
        </Notice>
      )}

      <div className="flex gap-1 border-b border-[#E2E4E8]">
        {[
          { id: 'archivos' as const, label: 'Archivos', count: files.length },
          { id: 'eliminados' as const, label: 'Eliminados', count: blocked.length },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-semibold ${
              tab === t.id ? 'border-[#B26337] text-[#23272E]' : 'border-transparent text-[#5C626D] hover:text-[#23272E]'
            }`}
          >
            {t.label}
            <span className="rounded-full bg-[#EFEFF1] px-1.5 py-0.5 font-mono-tabular text-[11px] text-[#5C626D]">{t.count}</span>
          </button>
        ))}
      </div>

      {tab === 'archivos' ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <Card className="h-fit p-3">
            <button
              onClick={() => setSel({ positionId: null, sourceId: null })}
              className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm font-semibold ${
                !sel.positionId ? 'bg-[#FBF4EE] text-[#23272E]' : 'text-[#23272E] hover:bg-[#F7F7F8]'
              }`}
            >
              <FolderOpen className="h-4 w-4 text-[#B26337]" />
              <span className="flex-1 font-mono-tabular">rrhh/</span>
              <span className="font-mono-tabular text-xs text-[#5C626D]">{files.length}</span>
            </button>
            <div className="mt-1 space-y-0.5">
              {treePositions.map((p) => {
                const isOpen = expanded.has(p.id);
                const posCount = counts.byPos.get(p.id) ?? 0;
                const srcs = state.jobBoards
                  .filter((s) => s.active || (counts.byPosSrc.get(`${p.id}|${s.id}`) ?? 0) > 0)
                  .sort((a, b) => a.name.localeCompare(b.name, 'es'));
                return (
                  <div key={p.id}>
                    <div
                      className={`flex items-center gap-1 rounded-lg pr-2 text-sm ${
                        sel.positionId === p.id && !sel.sourceId ? 'bg-[#FBF4EE]' : 'hover:bg-[#F7F7F8]'
                      }`}
                    >
                      <button onClick={() => toggle(p.id)} className="ml-2 rounded p-0.5 text-[#5C626D] hover:bg-[#EFEFF1]">
                        {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                      </button>
                      <button
                        onClick={() => {
                          setSel({ positionId: p.id, sourceId: null });
                          if (!isOpen) toggle(p.id);
                        }}
                        className="flex min-w-0 flex-1 items-center gap-1.5 py-1.5 text-left"
                        title={positionPath(p.id, state.positions)}
                      >
                        <Folder className="h-4 w-4 shrink-0 text-[#B26337]" />
                        <span className="truncate text-[#23272E]">{p.name}</span>
                      </button>
                      <span className={`font-mono-tabular text-xs ${posCount ? 'text-[#23272E]' : 'text-[#9AA0A8]'}`}>{posCount}</span>
                    </div>
                    {isOpen &&
                      srcs.map((s) => {
                        const n = counts.byPosSrc.get(`${p.id}|${s.id}`) ?? 0;
                        return (
                          <button
                            key={s.id}
                            onClick={() => setSel({ positionId: p.id, sourceId: s.id })}
                            className={`flex w-full items-center gap-1.5 rounded-lg py-1.5 pl-10 pr-2 text-left text-xs ${
                              sel.positionId === p.id && sel.sourceId === s.id ? 'bg-[#FBF4EE]' : 'hover:bg-[#F7F7F8]'
                            }`}
                          >
                            <Folder className="h-3.5 w-3.5 shrink-0 text-[#9AA0A8]" />
                            <span className="flex-1 truncate text-[#23272E]">{s.name}</span>
                            <span className={`font-mono-tabular ${n ? 'text-[#23272E]' : 'text-[#9AA0A8]'}`}>{n}</span>
                          </button>
                        );
                      })}
                  </div>
                );
              })}
            </div>
            <label className="mt-3 flex items-center gap-2 border-t border-[#EFEFF1] px-2 pt-3 text-xs text-[#5C626D]">
              <input type="checkbox" checked={onlyWithCv} onChange={(e) => setOnlyWithCv(e.target.checked)} className="accent-[#B26337]" />
              Solo puestos con CV o requerimientos abiertos
            </label>
          </Card>

          <Card className="min-w-0">
            <div className="flex flex-wrap items-center gap-3 border-b border-[#E2E4E8] px-4 py-3">
              <code className="font-mono-tabular text-sm font-semibold text-[#23272E]">{selectedLabel}</code>
              <span className="text-xs text-[#5C626D]">
                {visibleFiles.length} archivo{visibleFiles.length === 1 ? '' : 's'}
              </span>
              <div className="relative ml-auto w-full max-w-xs">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9AA0A8]" />
                <input
                  className={`${inputClass} pl-9`}
                  placeholder="Buscar archivo o candidato…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            </div>
            {visibleFiles.length === 0 ? (
              <EmptyState
                icon={<FileText className="h-5 w-5" />}
                title={files.length === 0 ? 'Todavía no hay CV en el servidor' : 'No hay archivos en esta carpeta'}
                description={
                  files.length === 0
                    ? 'Sube CV desde tu computadora, importa una carpeta organizada por puesto y fuente o configura la sincronización con tu carpeta local.'
                    : 'Elige otra carpeta a la izquierda o cambia la búsqueda.'
                }
                action={
                  <Button variant="primary" icon={<Upload className="h-4 w-4" />} onClick={() => setUploadOpen(true)}>
                    Subir CVs
                  </Button>
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-[#E2E4E8] bg-[#F7F7F8] text-xs font-semibold text-[#5C626D]">
                      <th className="px-4 py-2.5">Archivo</th>
                      <th className="px-3 py-2.5">Candidato</th>
                      <th className="px-3 py-2.5">IA</th>
                      <th className="px-3 py-2.5">Decisión</th>
                      <th className="px-3 py-2.5">Subido por</th>
                      <th className="px-3 py-2.5 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#EFEFF1]">
                    {visibleFiles.map((c) => (
                      <tr key={c.id} className="hover:bg-[#FAFAFB]">
                        <td className="max-w-[240px] px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <FileText className={`h-4 w-4 shrink-0 ${c.cvMissing ? 'text-[#B42318]' : 'text-[#B26337]'}`} />
                            <span className="truncate font-medium text-[#23272E]" title={c.cvPath || c.cvFileName}>
                              {c.cvFileName || 'CV'}
                            </span>
                          </div>
                          <div className="mt-0.5 truncate pl-6 text-xs text-[#5C626D]">
                            {c.targetRoleTitle} · {c.sourceBoardName}
                            {c.cvMissing && <span className="ml-1 font-semibold text-[#B42318]">· falta en el servidor</span>}
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <button
                            onClick={() => navigate('candidatos', { candidateId: c.id })}
                            className="text-left font-medium text-[#23272E] hover:text-[#B26337] hover:underline"
                          >
                            {c.fullName || 'Sin nombre'}
                          </button>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-wrap items-center gap-1">
                            <Badge tone={aiTone(c.aiStatus)} title={c.aiError ?? undefined}>
                              {c.aiStatus}
                            </Badge>
                            {c.aiVerdict && (
                              <Badge tone={c.aiVerdict === 'Pre-aprobado' ? 'green' : 'red'}>
                                {c.aiVerdict}
                                {c.aiAptitudeScore != null && ` · ${c.aiAptitudeScore}`}
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <Badge tone={decisionTone(c.decision)}>{c.decision}</Badge>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-[#5C626D]">
                          <div className="text-[#23272E]">{c.cvUploadedBy || '—'}</div>
                          <div>
                            {formatDateTime(c.cvUploadedAt || c.createdAt)}
                            {c.cvOrigin && ` · ${ORIGIN_LABEL[c.cvOrigin] ?? c.cvOrigin}`}
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex justify-end gap-1">
                            <Button size="sm" variant="ghost" icon={<Eye className="h-3.5 w-3.5" />} onClick={() => viewCv(c)} title="Ver CV">
                              Ver
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              icon={<MoveRight className="h-3.5 w-3.5" />}
                              onClick={() => setMoving(c)}
                              title="Mover a otro puesto o fuente"
                            >
                              Mover
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              icon={<Trash2 className="h-3.5 w-3.5 text-[#B42318]" />}
                              onClick={() => {
                                setDialogError(null);
                                setDeleting(c);
                              }}
                              title="Eliminar CV"
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      ) : (
        <Card>
          <div className="border-b border-[#E2E4E8] px-4 py-3 text-sm text-[#5C626D]">
            CV eliminados: no se vuelven a importar en ese puesto (ni al subir, ni al importar, ni al sincronizar) salvo que
            lo permitas.
          </div>
          {blocked.length === 0 ? (
            <EmptyState icon={<Ban className="h-5 w-5" />} title="No hay CV eliminados" description="Cuando elimines un CV aparecerá aquí." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-[#E2E4E8] bg-[#F7F7F8] text-xs font-semibold text-[#5C626D]">
                    <th className="px-4 py-2.5">Archivo</th>
                    <th className="px-3 py-2.5">Puesto</th>
                    <th className="px-3 py-2.5">Eliminado por</th>
                    <th className="px-3 py-2.5">Fecha</th>
                    <th className="px-3 py-2.5 text-right">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EFEFF1]">
                  {blocked
                    .slice()
                    .sort((a, b) => (b.deletedAt ?? '').localeCompare(a.deletedAt ?? ''))
                    .map((b) => (
                      <tr key={b.id}>
                        <td className="px-4 py-2.5 font-medium text-[#23272E]">{b.originalName}</td>
                        <td className="px-3 py-2.5 text-[#5C626D]">{positionsById.get(b.positionId)?.name ?? '—'}</td>
                        <td className="px-3 py-2.5 text-[#5C626D]">{b.deletedBy}</td>
                        <td className="px-3 py-2.5 text-xs text-[#5C626D]">{formatDateTime(b.deletedAt)}</td>
                        <td className="px-3 py-2.5 text-right">
                          <Button
                            size="sm"
                            icon={<RotateCcw className="h-3.5 w-3.5" />}
                            loading={unblocking === b.id}
                            onClick={() => unblock(b.id)}
                          >
                            Permitir reimportar
                          </Button>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <UploadCvDialog
        open={uploadOpen}
        state={state}
        initialPositionId={sel.positionId ?? undefined}
        initialSourceId={sel.sourceId ?? undefined}
        onClose={() => setUploadOpen(false)}
        onDone={(s) => {
          onState(s);
          setUploadOpen(false);
        }}
      />

      {moving && (
        <MoveCvDialog
          candidate={moving}
          state={state}
          onClose={() => setMoving(null)}
          onDone={(s) => {
            onState(s);
            setNotice({ kind: 'success', text: `Se movió el CV de ${moving.fullName}.` });
            setMoving(null);
          }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Eliminar CV"
          danger
          confirmLabel="Eliminar"
          busy={busy}
          error={dialogError}
          message={
            <>
              Se borrará el archivo y los datos de <strong>{deleting.fullName || deleting.cvFileName}</strong> de este puesto. No se
              volverá a importar salvo que lo permitas.
            </>
          }
          onConfirm={doDelete}
          onCancel={() => setDeleting(null)}
        />
      )}

      {summary && <SyncSummaryDialog summary={summary} onClose={() => setSummary(null)} />}
    </div>
  );
}

function MoveCvDialog({
  candidate,
  state,
  onClose,
  onDone,
}: {
  candidate: Candidate;
  state: AppState;
  onClose: () => void;
  onDone: (s: AppState) => void;
}) {
  const [positionId, setPositionId] = useState(candidate.positionId);
  const [sourceId, setSourceId] = useState(candidate.sourceBoardId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const positionOptions = useMemo(
    () =>
      state.positions
        .map((p) => ({ id: p.id, label: p.area ? `${p.name} — ${p.area}` : p.name }))
        .sort((a, b) => a.label.localeCompare(b.label, 'es')),
    [state.positions],
  );
  const pos = state.positions.find((p) => p.id === positionId);
  const src = state.jobBoards.find((s) => s.id === sourceId);
  const unchanged = positionId === candidate.positionId && sourceId === candidate.sourceBoardId;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ state: AppState }>(`/api/cv-files/${candidate.cvFileId}`, {
        method: 'PATCH',
        json: { positionId, sourceId },
      });
      onDone(res.state);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Mover CV de ${candidate.fullName || candidate.cvFileName}`}
      subtitle="Cambia el puesto o la fuente; el archivo se mueve también en el servidor."
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={save} loading={busy} disabled={unchanged}>
            Mover
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Puesto">
          <select className={inputClass} value={positionId} onChange={(e) => setPositionId(e.target.value)}>
            {positionOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Fuente">
          <select className={inputClass} value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            {state.jobBoards
              .filter((s) => s.active || s.id === candidate.sourceBoardId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </Field>
        <div className="rounded-lg bg-[#F7F7F8] px-3 py-2 text-xs text-[#5C626D]">
          Destino:{' '}
          <code className="font-mono-tabular text-[#23272E]">
            rrhh/{pos?.folderName ?? '?'}/{src?.folderName ?? '?'}/
          </code>
        </div>
        {positionId !== candidate.positionId && (
          <Notice kind="info">Al cambiar de puesto, la IA vuelve a evaluar la postulación con el perfil del nuevo puesto.</Notice>
        )}
        {error && <Notice kind="error">{error}</Notice>}
      </div>
    </Modal>
  );
}

export default CvFolderModule;

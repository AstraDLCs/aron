import { invoke } from '@tauri-apps/api/core';
import { apiFetch, errorMessage } from '../api/client';
import { finalizePlan, planMatches, type CheckStatus, type ScanResult, type UnmatchedFolder } from './syncPlan';

export const MAX_CV_BYTES = 15 * 1024 * 1024;
export const UPLOAD_CONCURRENCY = 3;

export type SyncOrigin = 'importacion' | 'sync_local';

export interface SyncFileRef {
  path: string;
  fileName: string;
  positionFolder: string;
  sourceFolder: string;
}

export interface SyncSummary {
  root: string;
  origin: SyncOrigin;
  scanned: number;
  uploaded: number;
  duplicates: number;
  deletedBefore: number;
  unmatchedFolders: UnmatchedFolder[];
  skipped: { path: string; reason: string }[];
  errors: { path: string; message: string }[];
  uploadedFiles: SyncFileRef[];
  duplicateFiles: SyncFileRef[];
  deletedBeforeFiles: SyncFileRef[];
  finishedAt: string;
}

type Named = { id: string; name: string; folderName: string };

const MIME: Record<string, string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  txt: 'text/plain',
  rtf: 'application/rtf',
};

export function mimeFor(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? '';
  return MIME[ext] ?? 'application/octet-stream';
}

/** Mensaje legible de cualquier error (incluye los `string` que devuelven los comandos de Rust). */
export function anyErrorMessage(e: unknown): string {
  if (typeof e === 'string') return e;
  try {
    return errorMessage(e);
  } catch {
    return String(e);
  }
}

/** Código de un 409 de la API (`detail.code`: 'duplicate' o 'deleted_before'). */
export function apiErrorCode(e: unknown): string | undefined {
  const err = e as { code?: string; detail?: unknown } | null;
  if (err?.code) return err.code;
  const d = err?.detail as { code?: string } | undefined;
  return d && typeof d === 'object' ? d.code : undefined;
}

function ref(e: SyncFileRef): SyncFileRef {
  return { path: e.path, fileName: e.fileName, positionFolder: e.positionFolder, sourceFolder: e.sourceFolder };
}

/** Ejecuta tareas con un máximo de `limit` a la vez. */
export async function runLimited<T>(items: T[], limit: number, worker: (item: T) => Promise<void>): Promise<void> {
  let next = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const item = items[next++];
      await worker(item);
    }
  });
  await Promise.all(runners);
}

export async function runSync(opts: {
  root: string;
  origin: SyncOrigin;
  positions: Named[];
  sources: Named[];
  onProgress?: (done: number, total: number) => void;
}): Promise<SyncSummary> {
  const summary: SyncSummary = {
    root: opts.root,
    origin: opts.origin,
    scanned: 0,
    uploaded: 0,
    duplicates: 0,
    deletedBefore: 0,
    unmatchedFolders: [],
    skipped: [],
    errors: [],
    uploadedFiles: [],
    duplicateFiles: [],
    deletedBeforeFiles: [],
    finishedAt: new Date().toISOString(),
  };

  let scan: ScanResult;
  try {
    scan = await invoke<ScanResult>('scan_cv_folder', { root: opts.root });
  } catch (e) {
    const msg = anyErrorMessage(e);
    summary.errors.push({ path: opts.root, message: msg || `La carpeta ${opts.root} no existe o no se puede leer` });
    summary.finishedAt = new Date().toISOString();
    return summary;
  }
  summary.root = scan.rootUsed || opts.root;
  summary.scanned = scan.entries?.length ?? 0;
  summary.skipped = scan.skipped ?? [];

  const plan = planMatches({ ...scan, entries: scan.entries ?? [] }, opts.positions, opts.sources);
  summary.unmatchedFolders = plan.unmatchedFolders;
  summary.duplicates += plan.inScanDuplicates.length;
  summary.duplicateFiles.push(...plan.inScanDuplicates.map(ref));

  let results: { sha256: string; positionId: string; status: CheckStatus }[] = [];
  if (plan.matched.length > 0) {
    try {
      // La API admite hasta 2000 elementos por consulta.
      for (let i = 0; i < plan.matched.length; i += 2000) {
        const chunk = plan.matched.slice(i, i + 2000);
        const r = await apiFetch<{ results: { sha256: string; positionId: string; status: CheckStatus }[] }>(
          '/api/cv-files/check',
          { method: 'POST', json: { items: chunk.map((m) => ({ sha256: m.sha256, positionId: m.positionId })) } },
        );
        results = results.concat(r.results);
      }
    } catch (e) {
      summary.errors.push({ path: summary.root, message: `No se pudo consultar el servidor: ${anyErrorMessage(e)}` });
      summary.finishedAt = new Date().toISOString();
      return summary;
    }
  }

  const final = finalizePlan(plan.matched, results);
  summary.duplicates += final.duplicates.length;
  summary.duplicateFiles.push(...final.duplicates.map(ref));
  summary.deletedBefore += final.deletedBefore.length;
  summary.deletedBeforeFiles.push(...final.deletedBefore.map(ref));

  const total = final.toUpload.length;
  let done = 0;
  opts.onProgress?.(0, total);
  await runLimited(final.toUpload, UPLOAD_CONCURRENCY, async (m) => {
    try {
      if (m.size > MAX_CV_BYTES) throw new Error('El archivo supera el máximo de 15 MB');
      const bytes = await invoke<ArrayBuffer>('read_file_bytes', { path: m.path });
      const form = new FormData();
      form.append('file', new File([bytes], m.fileName, { type: mimeFor(m.fileName) }));
      form.append('positionId', m.positionId);
      form.append('sourceId', m.sourceId);
      form.append('origin', opts.origin);
      await apiFetch('/api/cv-files', { method: 'POST', form });
      summary.uploaded += 1;
      summary.uploadedFiles.push(ref(m));
    } catch (e) {
      const status = (e as { status?: number } | null)?.status;
      const code = apiErrorCode(e);
      if (status === 409 && code === 'deleted_before') {
        summary.deletedBefore += 1;
        summary.deletedBeforeFiles.push(ref(m));
      } else if (status === 409) {
        summary.duplicates += 1;
        summary.duplicateFiles.push(ref(m));
      } else {
        summary.errors.push({ path: m.path, message: anyErrorMessage(e) });
      }
    } finally {
      done += 1;
      opts.onProgress?.(done, total);
    }
  });

  summary.finishedAt = new Date().toISOString();
  return summary;
}

export function summaryLine(s: SyncSummary): string {
  const parts = [`${s.uploaded} nuevos`, `${s.duplicates} repetidos`];
  if (s.deletedBefore) parts.push(`${s.deletedBefore} eliminados antes`);
  if (s.unmatchedFolders.length) parts.push(`${s.unmatchedFolders.length} carpetas sin coincidencia`);
  if (s.errors.length) parts.push(`${s.errors.length} con error`);
  return parts.join(', ');
}

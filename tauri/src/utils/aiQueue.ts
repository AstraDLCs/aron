import type { AiQueueStatus } from '../types';
import { formatTime } from './labels';

/** El worker escribe su estado cada pocos segundos; si pasa más de esto sin señal, probablemente está detenido. */
export const WORKER_STALE_MS = 90_000;

export type QueueTone = 'neutral' | 'green' | 'orange' | 'amber' | 'red';

export function workerSilentFor(q: AiQueueStatus, now = Date.now()): number | null {
  if (!q.workerSeenAt) return null;
  return Math.max(0, now - Date.parse(q.workerSeenAt));
}

export function workerStale(q: AiQueueStatus, now = Date.now()): boolean {
  const silent = workerSilentFor(q, now);
  return silent == null || silent > WORKER_STALE_MS;
}

/** «hace 12 s», «hace 3 min». */
export function agoText(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `hace ${s} s`;
  const m = Math.round(s / 60);
  return m < 60 ? `hace ${m} min` : `hace ${Math.round(m / 60)} h`;
}

/** Resumen de una línea para la barra superior. */
export function aiQueueHeadline(q: AiQueueStatus, now = Date.now()): { text: string; tone: QueueTone } {
  if (!q.aiEnabled) return { text: 'IA desactivada', tone: 'neutral' };
  if (q.pausedUntil) return { text: `IA en pausa hasta ${formatTime(q.pausedUntil)}`, tone: 'amber' };
  if (q.processing > 0)
    return { text: `IA: clasificando${q.queued ? ` · ${q.queued} en cola` : ''}`, tone: 'orange' };
  if (q.queued > 0 && workerStale(q, now)) return { text: `IA: ${q.queued} en cola · worker sin señal`, tone: 'red' };
  if (q.queued > 0 && q.nextAttemptAt)
    return { text: `IA: ${q.queued} en cola · reintento ${formatTime(q.nextAttemptAt)}`, tone: 'amber' };
  if (q.queued > 0) return { text: `IA: ${q.queued} en cola`, tone: 'orange' };
  return { text: q.errors ? `IA: al día · ${q.errors} con error` : 'IA: al día', tone: q.errors ? 'amber' : 'green' };
}

/** Texto para el tooltip: qué hace el worker, cuándo dio señales y el último motivo. */
export function aiQueueDetail(q: AiQueueStatus, now = Date.now()): string {
  const silent = workerSilentFor(q, now);
  const parts = [
    `Worker: ${q.workerStatus || 'sin datos'}`,
    silent == null ? 'Sin señales del worker todavía' : `Última señal ${agoText(silent)}`,
  ];
  if (q.nextAttemptAt) parts.push(`Próximo intento: ${formatTime(q.nextAttemptAt)}`);
  if (q.lastError) parts.push(`Último motivo: ${q.lastError}`);
  parts.push(`Modelo: ${q.model || '—'}`);
  return parts.join('\n');
}

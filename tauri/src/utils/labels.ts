import type { AiStatus, AiVerdict, CandidateDecision } from '../types';

export type Tone = 'success' | 'danger' | 'neutral' | 'warning';

export function decisionTone(d: CandidateDecision): Tone {
  if (d === 'Contratado') return 'success';
  if (d === 'Aprobado') return 'success';
  if (d === 'Rechazado') return 'danger';
  return 'warning';
}

export function verdictLabel(v: AiVerdict | null | undefined): string {
  if (v === 'Pre-aprobado') return 'Pre-aprobado por IA';
  if (v === 'Pre-denegado') return 'Pre-denegado por IA';
  return 'Sin veredicto IA';
}

export function aiStatusTone(s: AiStatus): Tone {
  if (s === 'Clasificado') return 'success';
  if (s === 'Error IA') return 'danger';
  if (s === 'En cola' || s === 'Procesando') return 'warning';
  return 'neutral';
}

export const TONE_CLASSES: Record<Tone, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  danger: 'border-red-200 bg-red-50 text-red-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  neutral: 'border-[#E2E4E8] bg-[#F7F7F8] text-[#5C626D]',
};

export function decisionBadgeClass(d: CandidateDecision): string {
  if (d === 'Contratado') return 'border-emerald-300 bg-emerald-100 text-emerald-900';
  return TONE_CLASSES[decisionTone(d)];
}

export function verdictBadgeClass(v: AiVerdict | null | undefined): string {
  if (v === 'Pre-aprobado') return TONE_CLASSES.success;
  if (v === 'Pre-denegado') return TONE_CLASSES.danger;
  return TONE_CLASSES.neutral;
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
}

export function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('es-PE');
}

export function formatTime(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
}

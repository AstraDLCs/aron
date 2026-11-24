import type { AiVerdict, Candidate, CandidateDecision } from '../types';

// Igual que la API: sin pasos obligatorios, desde cualquier estado se puede aprobar, rechazar o contratar.
export const DECISION_TRANSITIONS: Record<CandidateDecision, CandidateDecision[]> = {
  'Pendiente de revisión': ['Aprobado', 'Rechazado', 'Contratado'],
  Aprobado: ['Contratado', 'Rechazado'],
  Rechazado: ['Aprobado', 'Contratado'],
  Contratado: ['Aprobado', 'Rechazado'],
};

export function allowedNextDecisions(d: CandidateDecision): CandidateDecision[] {
  return DECISION_TRANSITIONS[d] ?? [];
}

export function agreeWithAi(v: AiVerdict | null | undefined): CandidateDecision | null {
  if (v === 'Pre-aprobado') return 'Aprobado';
  if (v === 'Pre-denegado') return 'Rechazado';
  return null;
}

export function sortSelectionQueue(c: Candidate[]): Candidate[] {
  return [...c].sort((a, b) => {
    const aa = a.aiAptitudeScore;
    const bb = b.aiAptitudeScore;
    if (aa == null && bb != null) return 1;
    if (bb == null && aa != null) return -1;
    if (aa != null && bb != null && aa !== bb) return bb - aa;
    return (b.metricReport?.overallScore ?? 0) - (a.metricReport?.overallScore ?? 0);
  });
}

export const DECISION_ACTION_LABEL: Record<CandidateDecision, string> = {
  'Pendiente de revisión': 'Volver a pendiente',
  Aprobado: 'Aprobar',
  Rechazado: 'Rechazar',
  Contratado: 'Contratar',
};

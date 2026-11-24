import type { AppState, AppSection } from '../types';

export interface AuditLogModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

export function AuditLogModule(_props: AuditLogModuleProps) {
  return <div className="p-6 text-sm text-slate-500">Bitácora (en construcción)</div>;
}

export default AuditLogModule;

import type { AppState, AppSection } from '../types';

export interface SettingsModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

export function SettingsModule(_props: SettingsModuleProps) {
  return <div className="p-6 text-sm text-slate-500">Configuración (en construcción)</div>;
}

export default SettingsModule;

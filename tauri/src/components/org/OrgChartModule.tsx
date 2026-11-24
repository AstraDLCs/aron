import type { AppState, AppSection } from '../../types';

export interface OrgChartModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

export function OrgChartModule(_props: OrgChartModuleProps) {
  return <div className="p-6 text-sm text-slate-500">Organigrama (en construcción)</div>;
}

export default OrgChartModule;

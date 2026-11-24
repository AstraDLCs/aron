import type { AppState, AppSection } from '../../types';

export interface CvFolderModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

export function CvFolderModule(_props: CvFolderModuleProps) {
  return <div className="p-6 text-sm text-slate-500">Carpeta de CVs (en construcción)</div>;
}

export default CvFolderModule;

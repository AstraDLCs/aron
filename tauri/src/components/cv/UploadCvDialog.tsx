import type { AppState } from '../../types';

export interface UploadCvDialogProps {
  open: boolean;
  state: AppState;
  initialPositionId?: string;
  initialSourceId?: string;
  onDone: (s: AppState) => void;
  onClose: () => void;
}

export function UploadCvDialog({ open, onClose }: UploadCvDialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="rounded-lg bg-white p-6">
        Subir CVs (en construcción) <button onClick={onClose}>Cerrar</button>
      </div>
    </div>
  );
}

export default UploadCvDialog;

import { useState, type ReactNode } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { downloadFile, errorMessage, openLocalPath } from '../../api/client';
import { toast } from './Toast';

export async function runDownload(path: string, fileName: string) {
  try {
    const saved = await downloadFile(path, fileName);
    if (!saved) return;
    toast(`Guardado en ${saved}`, 'ok', {
      label: 'Abrir',
      run: () => void openLocalPath(saved).catch((e) => toast(errorMessage(e), 'error')),
    });
  } catch (e) {
    toast(errorMessage(e), 'error');
  }
}

export function DownloadButton({
  path,
  fileName,
  label,
  variant = 'ghost',
  className = '',
  icon,
}: {
  path: string;
  fileName: string;
  label: ReactNode;
  variant?: 'primary' | 'ghost';
  className?: string;
  icon?: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const base =
    variant === 'primary'
      ? 'bg-[#B26337] text-white hover:bg-[#99522B] border border-[#B26337]'
      : 'border border-[#D4D7DD] bg-white text-[#23272E] hover:bg-[#EFEFF1]';
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await runDownload(path, fileName);
        setBusy(false);
      }}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition-colors disabled:opacity-60 ${base} ${className}`}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : icon ?? <Download className="h-4 w-4" />}
      {label}
    </button>
  );
}
